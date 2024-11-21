import json
import asyncio
import websockets
import time
import datetime
import hmac
import hashlib
import aioredis  # Redis client for async operations
import aiohttp
from WooX_REST_API_Client import WooX_REST_API_Client

class OrderExecutor:
    def __init__(self, api_key, api_secret, redis_url="redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client = None
        self.api = WooX_REST_API_Client(api_key, api_secret)
        self.order_tasks = []
        self.ask_limit_order = dict()
        self.bid_limit_order = dict()
        self.condition = asyncio.Condition()

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
        count = 1
        async with aiohttp.ClientSession() as session:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    signal = json.loads(message["data"])
                    await self.execute_order(signal, client_order_id=count, session=session)
                    count += 1

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

    async def add_order_task(self, task):
        """Add an order task and notify the order loop."""
        async with self.condition:
            self.order_tasks.append(task)
            self.condition.notify_all()  # Notify the order loop about the update

    async def order_loop(self):
        """Process order tasks."""
        while True:
            async with self.condition:
                await self.condition.wait_for(lambda: any(task.done() for task in self.order_tasks))

                for order_task in list(self.order_tasks):  # Iterate over a copy
                    if order_task.done():
                        try:
                            # set now to flaot timestamp 
                            now = time.time()
                            result = await order_task
                            print("[Order Task Completed] Result:", result)
                            if result['success'] == True:
                                if result['order_type'] == 'LIMIT':
                                    if result['side'] == 'SELL':
                                        self.ask_limit_order[result['client_order_id']]['status'] = 'FILLED'
                                    elif result['side'] == 'BUY':
                                        self.bid_limit_order[result['client_order_id']]['status'] = 'FILLED'
                            elif result['success'] == False:
                                if result['order_type'] == 'LIMIT':
                                    if result['side'] == 'SELL':
                                        self.ask_limit_order[result['client_order_id']]['status'] = 'CANCELLED'
                                    elif result['side'] == 'BUY':
                                        self.bid_limit_order[result['client_order_id']]['status'] = 'CANCELLED'
                            RTT = float(now) - float(result['timestamp'])
                            print(f"Round Trip Time: {RTT}")   
                        except Exception as e:
                            print("[Order Task Error]:", e)
                        finally:
                            self.order_tasks.remove(order_task)
                        await asyncio.sleep(0.1)

    async def execute_order(self, signal, client_order_id, session):
        """Process the signal and execute an order."""
        if signal['target'] == 'send_order':
            print(f"Sending order to exchange: {signal}")
            params = {
                'client_order_id': client_order_id,
                'order_price': signal['order_price'],
                'order_quantity': signal['order_quantity'],
                'order_type': signal['order_type'],
                'side': signal['side'],
                'symbol': signal['symbol']
            }
            if signal['side'] == 'SELL':
                self.ask_limit_order[client_order_id] = {'price': signal['order_price'], 'quantity': signal['order_quantity'], 'status': 'PENDING'}
            elif signal['side'] == 'BUY':
                self.bid_limit_order[client_order_id] = {'price': signal['order_price'], 'quantity': signal['order_quantity'], 'status': 'PENDING'}

            new_task = asyncio.create_task(self.api.send_order(session, params))
            await self.add_order_task(new_task)  # Add the task dynamically
        elif signal['target'] == 'cancel_order':
            print(f"Cancelling order on exchange: {signal}")
            params = {
                'client_order_id': client_order_id,
                'symbol': signal['symbol']
            }
            new_task = asyncio.create_task(self.api.cancel_order_by_client_order_id(session, params))
            await self.add_order_task(new_task)
        elif signal['target'] == 'edit_order_by_client_order_id':
            print(f"Editing order on exchange: {signal}")
            params = {
                'client_order_id': client_order_id,
                'order_price': signal['order_price'],
                'order_quantity': signal['order_quantity'],
            }
            new_task = asyncio.create_task(self.api.edit_order_by_client_order_id(session, params))
            await self.add_order_task(new_task)

async def main():
    api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
    api_secret = 'FWQGXZCW4P3V4D4EN4EIBL6KLTDA'
    redis_client = await aioredis.from_url("redis://localhost:6379")
    executor = OrderExecutor(api_key=api_key, api_secret=api_secret)
    await executor.connect_redis()

    # Start the order loop and listen for signals
    signal_pubsub = await executor.subscribe_to_signals("order-executor")
    execution_report = await executor.subscribe_to_private_data("execution-reports")

    # Start listening tasks
    listen_tasks = asyncio.gather(
        executor.listen_for_signals(signal_pubsub),
        executor.listen_for_execution_report(execution_report),
        executor.order_loop()
    )

    # Wait a moment to ensure subscriber is ready
    await asyncio.sleep(1)

    # Simulate order execution signals
    for i in range(5):
        signal = {
            "target": "send_order",
            "order_price": 90000,
            "order_quantity": 0.0001,
            "order_type": "LIMIT",
            "side": "BUY",
            "symbol": "SPOT_BTC_USDT"
        }
        await redis_client.publish("order-executor", json.dumps(signal))
        await asyncio.sleep(0.8)  # Simulate delay between signals

    # Wait for listeners to finish
    await listen_tasks


if __name__ == "__main__":
    asyncio.run(main())
