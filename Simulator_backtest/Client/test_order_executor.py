import json
import asyncio
import time
import aiohttp
import logging

from typing import Optional, Dict, Any
from redis import asyncio as aioredis
from datetime import datetime
from WooX_REST_API_Client import WooX_REST_API_Client
from strategy_logics.strategy_init import OrderType, PositionType, OrderAction

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('OrderExecutor')

class OrderExecutor:
    def __init__(self, api_key, api_secret, redis_url="redis://localhost:6379"):
        """Initialize order executor, getting the trading signals and send the order"""
        self.redis_url = redis_url
        self.redis_client = None
        self.api = WooX_REST_API_Client(api_key, api_secret, server_port=10001)
        self.positions: Dict[str, Dict[str, Any]] = {}  # track all positions
        # self.order_tasks = []
        # self.ask_market_order = dict()
        # self.bid_market_order = dict()
        # self.condition = asyncio.Condition()
        # self.current_position = None
        # self.position_size = 0.0
        # self.entry_price = None
        # self.current_atr = None
        logger.info("OrderExecutor initialized")

    async def connect_to_redis(self):
        """Establish Redis connection"""
        self.redis_client = await aioredis.from_url(self.redis_url)
        logger.info(f"Connected to Redis at {self.redis_url}")
    
    async def subscribe_to_channels(self, strategy_channel: str, execution_channel: str) -> tuple:
        """Subscribe strategy channel and pub to execution channel"""
        """Return: tuple: two pubsub 對象"""
        try:
            strategy_pubsub = self.redis_client.pubsub()
            execution_pubsub = self.redis_client.pubsub()

            await strategy_pubsub.subscribe(strategy_channel)
            await execution_pubsub.subscribe(execution_channel)

            logger.info(f"Subscribed to channels: {strategy_channel}, {execution_channel}")
            return strategy_pubsub, execution_pubsub
        
        except Exception as e:
            logger.error(f"Failed to subscribe to channels: {e}")
            raise
    
    async def execute_order(self, signal_data: dict, session: aiohttp.ClientSession) -> dict:
        """execute the order"""
        """Return: the result of the executed order"""
        # Construct order parameters
        try:
            params = {
                'client_order_id': int(time.time() * 1000),
                'order_quantity': signal_data['quantity'],
                'order_type': signal_data['order_type'],
                'symbol': signal_data['symbol'],
                'margin_mode': 'CROSS',
                'position_side': signal_data['position_type'],
                'reduce_only': signal_data['reduce_only']
            }
            # According to the operation type and position type to determine the direction of order.
            if signal_data['action'] == OrderAction.CLOSE.value:
                params['side'] = "SELL" if signal_data['position_type'] == PositionType.LONG.value else "BUY"
            else:  # OPEN
                params['side'] = "BUY" if signal_data['position_type'] == PositionType.LONG.value else "SELL"
            
            # Add the order price if it's limit order
            if signal_data['order_type'] == OrderType.LIMIT.value:
                if not signal_data.get('price'):
                    raise ValueError("Limit order requires price")
                params['order_price'] = signal_data['price']

            logger.info(f"Sending order with parameters: {params}")
            result = await self.api.send_order(session, params)
            
            if not result.get('error'):
                await self.update_position_tracking(signal_data, result)
            
            return result
        
        except Exception as e:
            logger.error(f"Error executing order: {e}")
            return {'error': str(e)}
    
    async def process_execution_report(self, report_data: dict) -> None:
        """Args: process execution_report """
        try:
            logger.info(f"Processing execution report: {report_data}")
            if report_data.get('status') == 'FILLED':
                symbol = report_data.get('symbol')
                if symbol in self.positions:
                    position = self.positions[symbol]
                    position['filled_price'] = report_data.get('price')
                    position['filled_time'] = datetime.now().isoformat()
                    
                    # Sub filled order message to Redis 
                    await self.redis_client.set(f"position_{symbol}",json.dumps(position))
                    logger.info(f"Updated position for {symbol}: {position}")
        except Exception as e:
            logger.error(f"Error processing execution report: {e}")

    async def update_position_tracking(self, signal_data: dict, order_result: dict) -> None:
        """update the position tracking message"""
        """Args: signal_data, the result of executed order"""
        symbol = signal_data['symbol']
        if signal_data['action'] == OrderAction.CLOSE.value:
            self.positions.pop(symbol, None)
        else:  # OPEN
            self.positions[symbol] = {
                'position_type': signal_data['position_type'],
                'quantity': signal_data['quantity'],
                'entry_time': datetime.now().isoformat(),
                'order_id': order_result.get('order_id')
            }

    async def listen_for_signals(self, pubsub) -> None:
        """listen Strategy Signals """""
        """Args: pubsub: Redis pubsub 對象"""
            
        logger.info("Started listening for strategy signals")
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    signal_data = json.loads(message["data"])
                    logger.info(f"Received strategy signal: {signal_data}")
                    
                    async with aiohttp.ClientSession() as session:
                        result = await self.execute_order(signal_data, session)
                        logger.info(f"Order execution result: {result}")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode strategy signal: {e}")
                except Exception as e:
                    logger.error(f"Error processing strategy signal: {e}")
    
    async def listen_for_execution_reports(self, pubsub) -> None:
        """listen for execution reports"""
        logger.info(f"Started listening for execution reports")
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    report_data = json.loads(message["data"])
                    await self.process_execution_report(report_data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode execution report: {e}")
                except Exception as e:
                    logger.error(f"Error processing execution report: {e}")

    async def cleanup(self) -> None:
        """clean redis"""
        try:
            if self.redis_client:
                await self.redis_client.aclose()
            logger.info("Cleaned up resources")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


    async def run(self) -> None:
        try:
            # sub channels 
            strategy_pubsub, execution_pubsub = await self.subscribe_to_channels(
                "strategy_signals",
                "execution-reports"
            )
            # create listen tasks
            tasks = [
                asyncio.create_task(self.listen_for_signals(strategy_pubsub)),
                asyncio.create_task(self.listen_for_execution_reports(execution_pubsub))
            ]
            # wait for all tasks
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Order executor shutdown initiated")
        except Exception as e:
            logger.error(f"Error in order executor main loop: {e}")
        finally:
            # cleanup
            await self.cleanup()

async def main():
    try:
        api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
        api_secret = 'FWQGXZCW4P3V4D4EN4EIBL6KLTDA'
        
        redis_client = await aioredis.from_url("redis://localhost:6379")
        logger.info("Connected to Redis")

        executor = OrderExecutor(api_key=api_key, api_secret=api_secret)
        await executor.connect_to_redis()
        logger.info("Order executor initialized")
        await executor.run()
    
    except KeyboardInterrupt:
        logger.info("Program terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")