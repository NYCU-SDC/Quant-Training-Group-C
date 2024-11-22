import json
import asyncio
import websockets
import time
import datetime
import hmac
import hashlib
import aioredis  # Redis client for async operations

# Import your existing classes
from data_processing.Orderbook import OrderBook
from data_processing.BBO import BBO

class PrivateWooXStagingAPI:
    def __init__(self, app_id: str, api_key, api_secret, redis_host: str, redis_port: int = 6379):
        self.app_id = app_id
        self.market_data_uri = f"wss://wss.staging.woox.io/ws/stream/{self.app_id}"
        self.private_uri = f"wss://wss.staging.woox.io/v2/ws/private/stream/{self.app_id}"
        self.api_key = api_key
        self.api_secret = api_secret
        self.private_connection = None
        self.private_connection = None
        self.orderbooks = {}
        self.bbo_data = {}
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_client = None
        self.redis_channel = None

    def generate_signature(self, body):
        key_bytes = bytes(self.api_secret, 'utf-8')
        body_bytes = bytes(body, 'utf-8')
        return hmac.new(key_bytes, body_bytes, hashlib.sha256).hexdigest()

    async def connect_redis(self):
        """Connects to Redis server."""
        self.redis_client = await aioredis.from_url(
            f"redis://{self.redis_host}:{self.redis_port}", 
            encoding='utf-8', 
            decode_responses=True
        )
        print(f"[Private data publisher] Connected to Redis server at {self.redis_host}:{self.redis_port}")

    async def publish_to_redis(self, channel, data):
        """Publish data to Redis channel."""
        if self.redis_client:
            await self.redis_client.publish(channel, json.dumps(data))
            print(f"[Private data publisher] Published to Redis channel: {channel}")

    async def connect_private(self):
        """Establish the WebSocket connection."""
        if self.private_connection is None:
            self.private_connection = await websockets.connect(self.private_uri)
            print(f"[Private data publisher] Connected to {self.private_uri}")
        return self.private_connection

    async def authenticate(self):
        """Send the authentication message."""
        connection = await self.connect_private()
        timestamp = int(time.time() * 1000)  # Current timestamp in milliseconds
        data = f"|{timestamp}"
        # Generate the signature
        signature = self.generate_signature(data)

        auth_message = {
            "event": "auth",
            "params": {
                "apikey": self.api_key,
                "sign": signature,
                "timestamp": timestamp
            }
        }
        await connection.send(json.dumps(auth_message))
        response = json.loads(await connection.recv())

        if response.get("success"):
            print("[Private data publisher] Authentication successful.")
        else:
            print(f"[Private data publisher] Authentication failed: {response.get('errorMsg')}")

    async def subscribe(self, websocket, config):
        """Subscribe to executionreport, position."""
        if config.get("executionreport"):
            subscribe_message = {
                "event": "subscribe",
                "topic": "executionreport",
            }
            await websocket.send(json.dumps(subscribe_message))
            print(f"[Private data publisher] Subscribed to executionreport")
        
        if config.get("position"):
            subscribe_message = {
                "event": "subscribe",
                "topic": "position",
            }
            await websocket.send(json.dumps(subscribe_message))
            print(f"[Private data publisher] Subscribed to position")

        if config.get("balance"):
            subscribe_message = {
                "event": "subscribe",
                "topic": "balance",
            }
            await websocket.send(json.dumps(subscribe_message))
            print(f"[Private data publisher] Subscribed to balance")

    async def respond_pong(self, websocket):
        """Responds to server PINGs with a PONG."""
        pong_message = {
            "event": "pong",
            "ts": int(asyncio.get_event_loop().time() * 1000)
        }
        await websocket.send(json.dumps(pong_message))

    async def process_market_data(self, message):
        """Process market data and publish it to Redis."""
        data = json.loads(message)
        if 'topic' in data:
            # Assuming message contains 'executionreport', 'position', 'balance' data
            if data['topic'] == "executionreport":
                print(f"[Private data publisher] Received execution report: {data['data']}")
                await self.publish_to_redis(f"executionreport", data['data'])

            if data['topic'] == "position":
                # print(f"[Private data publisher] Received position data: {data['data']}")
                await self.publish_to_redis(f"position", data['data'])

            if data['topic'] == "balance":
                # print(f"[Private data publisher] Received balance data: {data['data']}")
                await self.publish_to_redis(f"balance", data['data'])

    async def listen_for_data(self, websocket, config):
        """Listen for incoming market data and publish to Redis."""
        async for message in websocket:
            print(f"[Private data publisher] Received message: {message}")
            await self.process_market_data(message)

    async def close_connection(self):
        """Gracefully closes the WebSocket connection."""
        if self.private_connection is not None:
            await self.private_connection.close()
            self.private_connection = None
            print("[Private data publisher] Market WebSocket connection closed")

        if self.private_connection is not None:
            await self.private_connection.close()
            self.private_connection = None
            print("[Private data publisher] Private WebSocket connection closed")

    async def start(self, config):
        """Start the WebSocket connection and market data subscription."""
        await self.connect_redis()  # Connect to Redis
        auth_connection = await self.authenticate()
        websocket = await self.connect_private()
        await self.subscribe(websocket, config)
        await self.listen_for_data(websocket, config)


# Example usage
async def main():
    app_id = "460c97db-f51d-451c-a23e-3cce56d4c932"
    api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
    api_secret = 'FWQGXZCW4P3V4D4EN4EIBL6KLTDA'
    api = PrivateWooXStagingAPI(app_id=app_id, api_key=api_key, api_secret=api_secret, redis_host="localhost")
    await api.start(config={"executionreport": True, "position": True, "balance": True})

if __name__ == "__main__":
    asyncio.run(main())