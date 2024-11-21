import json
import asyncio
import websockets
import time
import datetime
import hmac
import hashlib
import aioredis  # Redis client for async operations
from strategy_logics.strategy_init import Strategy

class ExampleStrategy(Strategy):
    """Example: send order each 1 sec."""
    async def execute(self, channel, data, redis_client):
        # Simulate signal generation
        await asyncio.sleep(0.1)
        print(f"[MovingAverageStrategy] Processing data from {channel}: {data}")

        # Example signal generation
        signal = {
            "target": "send_order",
            "order_price": 90000,
            "order_quantity": 0.0001,
            "order_type": "LIMIT",
            "side": "BUY",
            "symbol": "SPOT_BTC_USDT"
        }

        # Publish the signal to the order executor
        await self.publish_signal(signal, redis_client)