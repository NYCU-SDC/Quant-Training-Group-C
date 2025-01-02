import json
import asyncio
import logging
import time
import aiohttp
from typing import Dict, Optional
from redis import asyncio as aioredis
from datetime import datetime
import os
from manager.order_manager import OrderManager, OrderInfo, OrderStatus
from manager.risk_manager import RiskManager
from WooX_REST_API_Client import WooX_REST_API_Client

class OrderExecutor:
    """Order execution manager that handles trading signals and executes orders"""
    
    def __init__(self, api_key: str, api_secret: str, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client = None
        
        # Initialize API client
        self.api = WooX_REST_API_Client(api_key, api_secret)
        self.last_request_time = 0
        self.request_interval = 0.1
        self.semaphore = asyncio.Semaphore(1)
        
        # Initialize managers
        self.order_manager = OrderManager()
        self.risk_manager = RiskManager({})  # Add risk params as needed
        
        # Setup logging
        self.logger = self.setup_logger(name='OrderExecutor', log_file='order_executor.log')
        
        # Track active orders and tasks
        self.active_orders: Dict[str, Dict] = {}
        self.order_tasks = []
        
        # Status flags
        self.is_running = False

    def setup_logger(self, name: str, log_file: Optional[str] = 'order_executor.log', level: int = logging.INFO) -> logging.Logger:
        """
        Sets up a logger that logs both to the console and a log file.

        Args:
            name: Name of the logger.
            log_file: Path to the log file where logs should be stored (default is 'order_executor.log').
            level: Logging level (default is logging.INFO).

        Returns:
            Logger instance.
        """
        logger = logging.getLogger(name)
        logger.setLevel(level)

        # Avoid adding duplicate handlers
        if not logger.handlers:
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            
            # Console handler for logging to console
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

            # File handler for logging to a file
            if log_file:
                print("!!!!!!!!!!!!!!!!!!!!!!!!!!")
                # If log_file is just a filename, join it with 'logs/'
                if not os.path.dirname(log_file):  # If no directory specified
                    log_file = os.path.join('logs', log_file)  # Join with 'logs/' folder

                print("Log file path:", log_file)

                # Ensure the directory exists before creating the log file
                log_dir = os.path.dirname(log_file)
                if not os.path.exists(log_dir):
                    print("Creating directory:", log_dir)
                    os.makedirs(log_dir)  # Create the directory if it doesn't exist


                # Create or append the log file
                file_handler = logging.FileHandler(log_file)
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)

        return logger
    
    async def connect_redis(self) -> None:
        """Connect to Redis server"""
        try:
            self.redis_client = await aioredis.from_url(self.redis_url)
            self.logger.info(f"Connected to Redis at {self.redis_url}")
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def subscribe_to_channels(self, signal_channel: str,
                                  execution_channel: str) -> tuple:
        """Subscribe to signal and execution channels"""
        try:
            signal_pubsub = self.redis_client.pubsub()
            execution_pubsub = self.redis_client.pubsub()
            
            await signal_pubsub.subscribe(signal_channel)
            await execution_pubsub.subscribe(execution_channel)
            
            self.logger.info(f"Subscribed to channels: {signal_channel}, {execution_channel}")
            return signal_pubsub, execution_pubsub
            
        except Exception as e:
            self.logger.error(f"Error subscribing to channels: {e}")
            raise

    async def execute_order(self, signal: dict, session: aiohttp.ClientSession) -> dict:
        """Execute order based on signal with rate limiting."""
        try:
            # Acquire the semaphore to ensure that only one request is processed at a time
            async with self.semaphore:
                # Rate limiting: wait if the last request was too recent
                current_time = time.time()
                time_since_last_request = current_time - self.last_request_time
                
                # If the time since the last request is less than the required interval, sleep
                if time_since_last_request < self.request_interval:
                    sleep_time = self.request_interval - time_since_last_request
                    print(f"Sleeping for {sleep_time} seconds")
                    await asyncio.sleep(sleep_time)
                
                # Update last request time
                self.last_request_time = time.time()

                if signal['target'] == 'send_order':
                    # Prepare order parameters
                    if signal['position_side'] == 'LONG':
                        side = 'BUY'
                    elif signal['position_side'] == 'SHORT':
                        side = 'SELL'
                    else:
                        return {'success': False, 'error': f"Unknown position_side: {signal['position_side']}"}
                    
                    order_params = {
                        'client_order_id': signal['order_id'],
                        'symbol': signal['symbol'],
                        'side': side, 
                        'order_type': signal['order_type'],
                        'order_quantity': signal['quantity'],
                        'reduce_only': signal.get('reduce_only', False)
                    }
                    if 'margin_mode' in signal:
                        order_params['margin_mode'] = signal['margin_mode']

                    if signal['order_type'] == 'LIMIT' or signal['order_type'] == 'POST_ONLY':
                        order_params['order_price'] = signal['price']
                    
                    # Create order tracking
                    order_info = OrderInfo(
                        order_id=str(order_params['client_order_id']),
                        client_order_id=signal['order_id'],
                        symbol=signal['symbol'],
                        side=side,
                        order_type=signal['order_type'],
                        price=signal.get('price', 0),
                        quantity=signal['quantity'],
                        status=OrderStatus.PENDING,
                        create_time=datetime.now()
                    )
                    self.order_manager.add_order(order_info)

                    # Send order to exchange
                    self.logger.info(f"Sending order: {order_params}")
                    result = await self.api.send_order(session, order_params)
                    
                    if result.get('success'):
                        self.logger.info(f"Order successfully placed: {result}")
                    else:
                        self.logger.error(f"Order placement failed: {result}")
                    
                    return result
                elif signal['target'] == 'cancel_order':
                    # Cancel order
                    order_id = signal['order_id']
                    self.logger.info(f"Cancelling order: {order_id}")
                    result = await self.api.cancel_order(session, order_id)

                    if result.get('success'):
                        self.logger.info(f"Order successfully cancelled: {result}")
                    else:
                        self.logger.error(f"Order cancellation failed: {result}")
                    
                    return result
                elif signal['target'] == 'cancel_all_orders':
                    # Cancel all orders
                    self.logger.info("Cancelling all orders")
                    result = await self.api.cancel_all_pending_orders(session)

                    if result.get('success'):
                        self.logger.info(f"All orders successfully cancelled: {result}")
                    else:
                        self.logger.error(f"Order cancellation failed: {result}")
                    
                    return result

        except Exception as e:
            self.logger.error(f"Error executing order: {e}")
            return {'success': False, 'error': str(e)}

    async def process_execution_report(self, report: dict) -> None:
        """Process execution report updates"""
        try:
            client_order_id = report.get('clientOrderId')
            if not client_order_id:
                return
                
            self.order_manager.update_order(client_order_id, {
                'status': report.get('status'),
                'executed_quantity': report.get('executedQuantity'),
                'fill_info': {
                    'price': report.get('price'),
                    'quantity': report.get('executedQuantity'),
                    'time': datetime.now().isoformat()
                }
            })
            
            # Update risk tracking if order is filled
            if report.get('status') == 'FILLED':
                await self.risk_manager.update_position(report)
                
        except Exception as e:
            self.logger.error(f"Error processing execution report: {e}")

    async def listen_for_signals(self, pubsub: aioredis.client.PubSub) -> None:
        """Listen for trading signals"""
        try:
            self.logger.info("Started listening for trading signals")
            async with aiohttp.ClientSession() as session:
                async for message in pubsub.listen():
                    if not self.is_running:
                        break
                        
                    if message["type"] == "message":
                        signal = json.loads(message["data"])
                        self.logger.info(f"Received signal: {signal}")
                        
                        result = await self.execute_order(signal, session)
                        # self.logger.info(f"Order execution result: {result}")
                        
        except asyncio.CancelledError:
            self.logger.info("Signal listener cancelled")
        except Exception as e:
            self.logger.error(f"Error in signal listener: {e}")

    async def listen_for_execution_reports(self, pubsub: aioredis.client.PubSub) -> None:
        """Listen for execution reports"""
        try:
            self.logger.info("Started listening for execution reports")
            async for message in pubsub.listen():
                if not self.is_running:
                    break
                    
                if message["type"] == "message":
                    report = json.loads(message["data"])
                    await self.process_execution_report(report)
                    
        except asyncio.CancelledError:
            self.logger.info("Execution report listener cancelled")
        except Exception as e:
            self.logger.error(f"Error in execution report listener: {e}")

    async def start(self, signal_channel: str, execution_channel: str) -> None:
        """Start the order executor"""
        try:
            if not self.redis_client:
                await self.connect_redis()
            
            self.is_running = True
            
            # Subscribe to channels
            signal_pubsub, execution_pubsub = await self.subscribe_to_channels(
                signal_channel, execution_channel
            )
            
            # Create listener tasks
            tasks = [
                asyncio.create_task(self.listen_for_signals(signal_pubsub)),
                asyncio.create_task(self.listen_for_execution_reports(execution_pubsub))
            ]
            
            # Run all tasks
            await asyncio.gather(*tasks)
            
        except Exception as e:
            self.logger.error(f"Error starting order executor: {e}")
            raise
        finally:
            await self.cleanup()

    async def cleanup(self) -> None:
        """Cleanup resources"""
        self.is_running = False
        
        # Close Redis connection
        if self.redis_client:
            await self.redis_client.aclose()
            
        # Clean up old orders
        self.order_manager.cleanup_old_orders()
        
        self.logger.info("Order executor cleaned up")

    async def stop(self) -> None:
        """Stop the order executor"""
        self.is_running = False
        await self.cleanup()
        self.logger.info("Order executor stopped")

async def main():
    """Main function for testing"""
    try:
        # Initialize with your API credentials
        app_id = "460c97db-f51d-451c-a23e-3cce56d4c932"
        api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
        api_secret = 'FWQGXZCW4P3V4D4EN4EIBL6KLTDA'
        redis_url = "redis://localhost:6379"
        
        # Create order executor instance
        executor = OrderExecutor(
            api_key=api_key,
            api_secret=api_secret,
            redis_url=redis_url
        )
        
        # Connect to Redis
        await executor.connect_redis()
        
        # Start the executor
        await executor.start(
            signal_channel="trading_signals",
            execution_channel="execution_reports"
        )
        
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    except Exception as e:
        logging.error(f"Error in main: {e}")
    finally:
        if 'executor' in locals():
            await executor.stop()

# if __name__ == "__main__":
#     # Setup logging
#     logging.basicConfig(
#         level=logging.INFO,
#         format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
#     )
    
#     # Run the main function
#     asyncio.run(main())