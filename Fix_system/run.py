import asyncio
import logging
from typing import List, Dict, Any
from redis import asyncio as aioredis
from strategy_logics.cta_strategy import ExampleStrategy
from data_publisher import WooXStagingAPI
from strategy_executor import StrategyExecutor
from test_order_executor import OrderExecutor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('TradingSystem')

class TradingSystem:
    def __init__(self, app_id: str, api_key, api_secret, redis_host: str, redis_port: int = 6379):
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_url = f"redis://{self.redis_host}:{self.redis_port}"
        self.redis_client = None
        self.data_publisher = None
        self.strategy_executor = None
        self.order_executor = None

    async def initialize(self):
        try:
            # Initialize All
            self.redis_client = await aioredis.from_url(self.redis_url)
            logger.info("Redis client initialized")

            self.data_publisher = WooXStagingAPI(self.app_id, self.api_key, self.api_secret, self.redis_host, self.redis_port)
            self.strategy_executor = StrategyExecutor(self.redis_url)
            self.order_executor = OrderExecutor(self.api_key, self.api_secret, redis_url=self.redis_url)

            logger.info("All components initialized successfully")

        except Exception as e:
            logger.error(f"Initialization error: {e}")
            raise

    async def start_data_publisher(self, symbol: str, market_config: Dict[str, Any], private_config: Dict[str, Any], interval: str = '1m') -> asyncio.Task:
        try:
            await self.data_publisher.connect_to_redis()
            logger.info("Starting data publisher...")
            return asyncio.create_task(self.data_publisher.start(symbol, market_config, private_config, interval))
        
        except Exception as e:
            logger.error(f"Error starting data publisher: {e}")
            raise
    
    async def start_strategy_executor(self, symbol: str) -> asyncio.Task:
        try:
            await self.strategy_executor.connect_to_redis()
            logger.info("Starting strategy executor...")

            # Add strategy 
            self.strategy_executor.add_strategy(ExampleStrategy(signal_channel="strategy_signals"))

            # sub data channels
            pubsub = await self.strategy_executor.subscribe_to_channels(
                symbol,
                {"orderbook": True, "kline": True},  # market data setting
                {"executionreport": True}            # private data setting
            )
            return asyncio.create_task(
                self.strategy_executor.listen_to_market_data(pubsub)
            )
        except Exception as e:
            logger.error(f"Error starting strategy executor: {e}")
            raise
    
    async def start_order_executor(self) -> List[asyncio.Task]:
        try:
            await self.order_executor.connect_to_redis()
            logger.info("Starting order executor...")

            # sub signals and execution reports channel
            strategy_pubsub, execution_pubsub = await self.order_executor.subscribe_to_channels(
                "strategy_signals",
                "execution-reports"
            )
            # create listen tasks 
            tasks = [
                asyncio.create_task(self.order_executor.listen_for_signals(strategy_pubsub)),
                asyncio.create_task(self.order_executor.listen_for_execution_reports(execution_pubsub))
            ]
            return tasks
        except Exception as e:
            logger.error(f"Error starting order executor: {e}")
            raise
    
    async def cleanup(self) -> None:
        """clean redis"""
        try:
            if self.redis_client:
                await self.redis_client.aclose()
            logger.info("System cleanup completed")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    async def run(self, symbol: str, market_config: Dict[str, Any], private_config: Dict[str, Any]) -> None:
        """run all trading system"""
        try:
            # Initialze
            await self.initialize()
            logger.info("Starting trading system...")

            # start all config(s)
            data_publisher_task = await self.start_data_publisher(symbol, market_config, private_config)
            strategy_task = await self.start_strategy_executor(symbol)
            order_executor_tasks = await self.start_order_executor()

            # run all tasks
            all_tasks = [data_publisher_task, strategy_task] + order_executor_tasks
            await asyncio.gather(*all_tasks)
        
        except asyncio.CancelledError:
            logger.info("Trading system shutdown initiated")
        except Exception as e:
            logger.error(f"Trading system error: {e}")
        finally:
            # clean redis
            await self.cleanup()
    
async def main():
    app_id = "460c97db-f51d-451c-a23e-3cce56d4c932"
    api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
    api_secret = 'FWQGXZCW4P3V4D4EN4EIBL6KLTDA'
    
    # Trading Settings
    symbol = "PERP_BTC_USDT"
    market_config = {
        "orderbook": False,
        "bbo": False,
        "trade": False,
        "kline": True
    }
    private_config = {
        "executionreport": True,
        "position": True,
        "balance": True
    }

    # create and run Trading System
    try:
        trading_system = TradingSystem(app_id=app_id, api_key=api_key, api_secret=api_secret, redis_host="localhost")
        await trading_system.run(symbol, market_config, private_config)
        
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