import json
import asyncio
import websockets
import time
import datetime
import hmac
import hashlib
import aioredis  # Redis client for async operations

class OrderExecutor:
    def __init__(self, redis_url="redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client = None
        self.order_list = []
        self.ask_limit_order = []
        self.bid_limit_order = []

    async def connect_redis(self):
        """Connect to Redis."""
        self.redis_client = await aioredis.from_url(self.redis_url)
        print(f"Connected to Redis at {self.redis_url}")

    async def subscribe_to_signals(self, signal_channel):
        """Subscribe to the signal channel."""
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(signal_channel)
        print(f"Subscribed to signal channel: {signal_channel}")
        return pubsub
    async def subscribe_to_private_data(self, private_data_channel):
        """Subscribe to the private data."""
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(private_data_channel)
        print(f"Subscribed to private data channel: {private_data_channel}")
        return pubsub
    
    async def listen_for_signals(self, pubsub):
        """Listen for incoming signals."""
        print("Listening for signals...")
        async for message in pubsub.listen():
            if message["type"] == "message":
                signal = json.loads(message["data"])
                self.order_list.append(signal)

    async def listen_for_execution_report(self, pubsub):
        """Listen for incoming execution reports."""
        print("Listening for execution reports...")
        async for message in pubsub.listen():
            if message["type"] == "message":
                execution_report = json.loads(message["data"])
                await self.process_execution_report(execution_report)

    async def listen_for_position_data(self, pubsub):
        """Listen for incoming position data."""
        print("Listening for private data...")
        async for message in pubsub.listen():
            if message["type"] == "message":
                position = json.loads(message["data"])
                await self.process_position_data(position)

    async def listen_to_balance(self, pubsub):
        """Listen for incoming balance data."""
        print("Listening for balance data...")
        async for message in pubsub.listen():
            if message["type"] == "message":
                balance = json.loads(message["data"])
                await self.process_balance_data(balance)

    async def execute_order(self, signal):
        """Process the signal and execute an order."""
        print(f"Executing order for signal: {signal}")
        if ['order_type'] == 'send_order':
            print(f"Sending order to exchange: {signal}")
            params = {
                "symbol": signal["symbol"],
                "quantity": signal["quantity"],
                "price": signal["price"],
                "side": signal["side"],
                "type": signal["type"],
            }

        await asyncio.sleep(0.1)  # Simulate order execution delay

    async def process_balance_data(self, balance_data):
        """Process the private data."""
        print(f"Processing balance data: {balance_data}")
        await asyncio.sleep(0.1)
    
    async def process_execution_report(self, execution_report):
        """Process the execution report."""
        print(f"Processing execution report: {execution_report}")
        if execution_report['magType'] == 0:
            if execution_report['status'] == 'FILLED':
                client_order_id = execution_report['client_order_id']
                if execution_report['side'] == 'SELL':
                    self.ask_limit_order[client_order_id] -= execution_report['executedQuantity']
                    if self.ask_limit_order[client_order_id] == 0:
                        self.ask_limit_order.remove(execution_report)
                    if self.ask_limit_order[client_order_id] < 0:
                        raise Exception("Error: Negative order quantity")
                elif execution_report['side'] == 'BUY':
                    self.bid_limit_order[client_order_id] -= execution_report['executedQuantity']
                    if self.bid_limit_order[client_order_id] == 0:
                        self.bid_limit_order.remove(execution_report)
                    if self.bid_limit_order[client_order_id] < 0:
                        raise Exception("Error: Negative order quantity")
                    
        if execution_report['magType'] == 1:
            pass
        await asyncio.sleep(0.1)
    
    async def process_position_data(self, position_data):
        """Process the position data."""
        print(f"Processing position data: {position_data}")
        await asyncio.sleep(0.1)

