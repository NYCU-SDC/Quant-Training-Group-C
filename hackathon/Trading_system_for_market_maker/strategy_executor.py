import json
import logging
import asyncio
from typing import Dict, List, Optional
from redis import asyncio as aioredis
from manager.config_manager import ConfigManager
from manager.risk_manager import RiskManager
from strategy_logics.maker_strategy_2 import MakerStrategy2 
import os
class StrategyExecutor:
    """Strategy execution manager that handles multiple trading strategies"""
    
    def __init__(self, redis_url: str, config: Optional[Dict] = None):
        self.redis_url = redis_url
        self.redis_client = None
        self.strategies = {}
        self.config = config or {}
        
        # Initialize managers
        self.config_manager = ConfigManager()
        self.risk_manager = RiskManager(self.config.get('risk_management', {}))
        
        # Setup logging
        self.logger = self.setup_logger(name='StrategyExecutor', log_file='strategy_executor.log')

        # Track connection status
        self.is_running = False

    def setup_logger(self, name: str, log_file: Optional[str] = 'strategy_executor.log', level: int = logging.INFO) -> logging.Logger:
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

    async def add_strategy(self, strategy_class: type, config: Dict = None) -> None:
        """
        Add a new strategy to the executor
        Args:
            strategy_class: Strategy class to instantiate
            config: Strategy configuration
        """
        try:
            strategy_name = strategy_class.__name__
            if strategy_name not in self.strategies:
                strategy_config = config or self.config_manager.get_strategy_config(strategy_name)
                
                # 使用正確的參數創建策略實例
                strategy_instance = strategy_class(
                    signal_channel=self.config.get('signal_channel', 'trading_signals'),
                    config=strategy_config
                )
                self.strategies[strategy_name] = strategy_instance
                self.logger.info(f"Added strategy: {strategy_name}")
                # 這裡順便寫到策略自己的 log檔案
                strategy_instance.logger.info(f"StrategyExecutor - INFO - Added strategy: {strategy_name}")
                self.logger.info(f"Added strategy: {strategy_name}")
            else:
                self.logger.warning(f"Strategy {strategy_name} already exists")
        except Exception as e:
            self.logger.error(f"Error adding strategy: {e}")
            raise

    def remove_strategy(self, strategy_name: str) -> None:
        """Remove a strategy from the executor"""
        if strategy_name in self.strategies:
            strategy = self.strategies.pop(strategy_name)
            strategy.stop()
            self.logger.info(f"Removed strategy: {strategy_name}")

    async def subscribe_to_channels(self, market_channels: List[str],
                                  private_channels: List[str]) -> tuple:
        """Subscribe to market and private data channels"""
        try:
            market_pubsub = self.redis_client.pubsub()
            private_pubsub = self.redis_client.pubsub()
            
            # Add channel prefixes
            prefixed_market = [f"[MD]{ch}" for ch in market_channels]
            prefixed_private = [f"[PD]{ch}" for ch in private_channels]
            
            # Subscribe to channels
            if prefixed_market:
                await market_pubsub.subscribe(*prefixed_market)
                self.logger.info(f"Subscribed to market channels: {prefixed_market}")
                
            if prefixed_private:
                await private_pubsub.subscribe(*prefixed_private)
                self.logger.info(f"Subscribed to private channels: {prefixed_private}")
                
            return market_pubsub, private_pubsub
            
        except Exception as e:
            self.logger.error(f"Error subscribing to channels: {e}")
            raise

    async def dispatch_to_strategies(self, channel: str, data: dict) -> None:
        """Dispatch data to all registered strategies"""
        try:
            if not self.is_running:
                return

            tasks = []
            for strategy in self.strategies.values():
                # 直接分派給策略，不檢查 can_trade
                task = asyncio.create_task(
                    strategy.execute(channel, data, self.redis_client)
                )
                tasks.append(task)
            
            if tasks:
                await asyncio.gather(*tasks)
                    
        except Exception as e:
            self.logger.error(f"Error dispatching to strategies: {e}")

    async def process_market_data(self, pubsub: aioredis.client.PubSub) -> None:
        """Process market data stream"""
        try:
            async for message in pubsub.listen():
                if not self.is_running:
                    break
                    
                if message["type"] == "message":
                    channel = message["channel"].decode("utf-8")
                    data = json.loads(message["data"])
                    await self.dispatch_to_strategies(channel, data)
                    
        except asyncio.CancelledError:
            self.logger.info("Market data processing cancelled")
        except Exception as e:
            self.logger.error(f"Error processing market data: {e}")

    async def process_private_data(self, pubsub: aioredis.client.PubSub) -> None:
        """Process private data stream"""
        try:
            async for message in pubsub.listen():
                if not self.is_running:
                    break
                    
                if message["type"] == "message":
                    channel = message["channel"].decode("utf-8")
                    data = json.loads(message["data"])
                    await self.dispatch_to_strategies(channel, data)
                    
        except asyncio.CancelledError:
            self.logger.info("Private data processing cancelled")
        except Exception as e:
            self.logger.error(f"Error processing private data: {e}")

    async def start(self, market_channels: List[str],
                   private_channels: List[str]) -> None:
        """Start the strategy executor"""
        try:
            if not self.redis_client:
                await self.connect_redis()
            
            self.is_running = True
            
            # Subscribe to channels
            market_pubsub, private_pubsub = await self.subscribe_to_channels(
                market_channels, private_channels
            )
            
            # Start all strategies
            for strategy in self.strategies.values():
                strategy.start()
            
            # Create processing tasks
            tasks = []
            if market_channels:
                tasks.append(self.process_market_data(market_pubsub))
            if private_channels:
                tasks.append(self.process_private_data(private_pubsub))
            
            # Run all tasks
            await asyncio.gather(*tasks)
            
        except Exception as e:
            self.logger.error(f"Error starting strategy executor: {e}")
            raise
        finally:
            await self.cleanup()

    async def cleanup(self) -> None:
        """Cleanup resources"""
        self.is_running = False
        
        # Stop all strategies
        for strategy in self.strategies.values():
            strategy.stop()
        
        # Close Redis connection
        if self.redis_client:
            await self.redis_client.close()
            
        self.logger.info("Strategy executor cleaned up")

async def main():
    """Main function for testing"""
    try:
        config = {
            'redis': {'url': 'redis://localhost:6379'},
            'signal_channel': 'trading_signals'
        }
        
        executor = StrategyExecutor(redis_url=config['redis']['url'], config=config)
        
        symbol = 'PERP_BTC_USDT'
        symbol_2 = 'PERP_ETH_USDT'
        
        # 修改訂閱的頻道，使用完整的頻道名稱
        market_channels = [
            f'{symbol}-kline_1m',
            f'{symbol}-processed-kline_1m'  # 添加處理過的K線頻道
        ]
        private_channels = ['executionreport', 'position']
        
        await executor.start(market_channels, private_channels)
        
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    except Exception as e:
        logging.error(f"Error in main: {e}")

# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO)
#     asyncio.run(main())