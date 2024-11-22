import json
import asyncio
import websockets
import time
import datetime
import hmac
import hashlib
import aioredis  # Redis client for async operations
from strategy_logics.example_strategy import ExampleStrategy

class StrategyExecutor:
    def __init__(self, redis_url="redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client = None
        self.strategies = []

    def add_strategy(self, strategy):
        """Add a strategy to the executor."""
        self.strategies.append(strategy)
        print("[Strategy Executor] Added strategy:", self.strategies)

    async def connect_redis(self):
        """Connect to Redis."""
        self.redis_client = await aioredis.from_url(self.redis_url)
        print(f"[Strategy Executor] Connected to Redis at {self.redis_url}")

    async def subscribe_to_channels(self, channels):
        """Subscribe to market data channels."""
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(*channels)
        print(f"[Strategy Executor] Subscribed to channels: {channels}")
        return pubsub

    async def listen_to_market_data(self, pubsub):
        """Listen for market data and dispatch it to strategies."""
        print("[Strategy Executor] Listening for market data...")
        async for message in pubsub.listen():
            if message["type"] == "message":
                channel = message["channel"].decode("utf-8")
                data = json.loads(message["data"])
                print(f"[Strategy Executor] Received data from channel {channel}: {data}")
                await self.dispatch_to_strategies(channel, data)

    async def dispatch_to_strategies(self, channel, data):
        """Dispatch market data to all registered strategies."""
        print(f"[Strategy Executor] Dispatching data to strategies for channel {channel}.")
        tasks = [
            asyncio.create_task(strategy.execute(channel, data, self.redis_client))
            for strategy in self.strategies
        ]
        await asyncio.gather(*tasks)

async def main():
    redis_url = "redis://localhost:6379"

    # Strategy Executor
    strategy_executor = StrategyExecutor(redis_url)
    print("[Strategy Executor] Connecting to Redis...")
    await strategy_executor.connect_redis()
    strategy_executor.add_strategy(MovingAverageStrategy(signal_channel="order-executor"))
    pubsub = await strategy_executor.subscribe_to_channels(["SPOT_ETH_USDT-orderbook", "SPOT_ETH_USDT-bbo"])

    # # Order Executor
    # order_executor = OrderExecutor(redis_url)
    # await order_executor.connect_redis()
    # signal_pubsub = await order_executor.subscribe_to_signals("order-executor")

    # Run both concurrently
    await asyncio.gather(
        strategy_executor.listen_to_market_data(pubsub),
        # order_executor.listen_for_signals(signal_pubsub),
    )

if __name__ == "__main__":
    asyncio.run(main())
