import json
import asyncio
import websockets
import time
import datetime
import hmac
import hashlib
import aioredis  # Redis client for async operations
from strategy_logics.example_strategy import ExampleStrategy
from market_data_publisher import MarketWooXStagingAPI
from private_data_publisher import PrivateWooXStagingAPI
from strategy_executor import StrategyExecutor
from order_executor import OrderExecutor

class TradingSystem:
    def __init__(self, app_id: str, api_key, api_secret, redis_host: str, redis_port: int = 6379):
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_url = f"redis://{self.redis_host}:{self.redis_port}"
        self.redis_client = None
        self.market_publisher = None
        self.private_publisher = None
        self.strategy_executor = None
        self.order_executor = None

    async def initialize(self):
        self.redis_client = await aioredis.from_url(self.redis_url)
        self.market_publisher = MarketWooXStagingAPI(self.app_id, self.api_key, self.api_secret, self.redis_host, self.redis_port)
        self.private_publisher = PrivateWooXStagingAPI(self.app_id, self.api_key, self.api_secret, self.redis_host, self.redis_port)
        self.strategy_executor = StrategyExecutor(self.redis_url)
        self.order_executor = OrderExecutor(self.api_key, self.api_secret, redis_url="redis://localhost:6379")

    async def start_market_publisher(self, symbol, config):
        await self.market_publisher.connect_redis()
        market_websocket = await self.market_publisher.market_connect()
        await self.market_publisher.subscribe(market_websocket, symbol, config)
        return asyncio.create_task(self.market_publisher.listen_for_data(market_websocket, symbol, config))
        
    async def start_private_publisher(self, config):
        print("Starting private publisher")
        await self.private_publisher.connect_redis()
        await self.private_publisher.authenticate()
        private_websocket = await self.private_publisher.connect_private()
        await self.private_publisher.subscribe(private_websocket, config)
        return asyncio.create_task(self.private_publisher.listen_for_data(private_websocket, config))

    async def start_strategy_executor(self, symbols, config):
        await self.strategy_executor.connect_redis()
        self.strategy_executor.add_strategy(ExampleStrategy(signal_channel="order-executor"))
        channels = []
        # Iterate over symbols and all keys in market and private configs
        for symbol in symbols:
            for market_channel, is_enabled in config["market"].items():
                if is_enabled:
                    channels.append(f"[MD]{symbol}-{market_channel}")
            for private_channel, is_enabled in config["private"].items():
                if is_enabled:
                    channels.append(f"[PD]{symbol}-{private_channel}")
        
        market_data_pubsub = await self.strategy_executor.subscribe_to_channels(channels)
        private_data_pubsub = await self.strategy_executor.subscribe_to_channels(["[PD]executionreport", "[PD]position", "[PD]balance"])
        market_data_task = asyncio.create_task(self.strategy_executor.listen_to_market_data(market_data_pubsub))
        private_data_task = asyncio.create_task(self.strategy_executor.listen_to_private_data(private_data_pubsub))
        return market_data_task, private_data_task

    async def start_order_executor(self, config):
        await self.order_executor.connect_redis()
        signal_pubsub = await self.order_executor.subscribe_to_signals("order-executor")
        execution_report_pubsub = await self.order_executor.subscribe_to_private_data("[PD]executionreport")
        
        signal_task = asyncio.create_task(self.order_executor.listen_for_signals(signal_pubsub))
        report_task = asyncio.create_task(self.order_executor.listen_for_execution_report(execution_report_pubsub))
        return signal_task, report_task

    async def run(self, symbols, config):
        """Run the trading system by gathering all components."""
        # Connect Redis for all components
        await asyncio.gather(
            self.market_publisher.connect_redis(),
            self.private_publisher.connect_redis(),
            self.strategy_executor.connect_redis(),
            self.order_executor.connect_redis()
        )

        # Start market and private publishers
        market_task = await self.start_market_publisher(symbols[0], config["market"])  # Assuming first symbol for market
        private_task = await self.start_private_publisher(config["private"])

        # Start strategy executor
        strategy_task1, strategy_task2 = await self.start_strategy_executor(symbols, config)

        # Start order executor
        order_signals_task, execution_report_task= await self.start_order_executor(config)

        # Run everything concurrently
        await asyncio.gather(
            market_task,
            private_task,
            strategy_task1,
            strategy_task2,
            order_signals_task,
            execution_report_task,
        )

if __name__ == "__main__":
    # Define the configuration for the trading system
    app_id = "460c97db-f51d-451c-a23e-3cce56d4c932"
    api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
    api_secret = 'FWQGXZCW4P3V4D4EN4EIBL6KLTDA'
    config = {
        "market": {
            "orderbook": False,
            "bbo": False,
            "trade": False,
            "kline": "1m"
        },
        "private": {
            "executionreport": True,
            "position": False,
            "balance": False
        }
    }

    # Define the symbols to trade
    symbols = ["SPOT_BTC_USDT"]

    # Initialize the trading system
    trading_system = TradingSystem(app_id, api_key, api_secret, "localhost")

    asyncio.run(trading_system.initialize())
    # Run the trading system
    asyncio.run(trading_system.run(symbols, config))

