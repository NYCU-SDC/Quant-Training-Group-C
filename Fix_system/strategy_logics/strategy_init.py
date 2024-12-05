import json
import asyncio
from redis import asyncio as aioredis  # Redis client for async operations

class Strategy:
    """Base class for strategies."""
    def __init__(self, signal_channel):
        self.signal_channel = signal_channel

    async def execute(self, channel, data, redis_client):
        """Override this method in derived classes to implement specific strategy logic."""
        raise NotImplementedError("Strategy must implement the execute method")

    async def publish_signal(self, signal, redis_client):
        """Publish the generated signal to the Redis signal channel."""
        await redis_client.publish(self.signal_channel, json.dumps(signal))
        print(f"Published signal to channel {self.signal_channel}: {signal}")

