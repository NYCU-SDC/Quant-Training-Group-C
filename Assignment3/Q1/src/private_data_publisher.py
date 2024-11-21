import json
import asyncio
import websockets
import time
import datetime
import hmac
import hashlib
from redis.asyncio import Redis  # Redis client for async operations

# Import your existing classes
from data_processing.Orderbook import OrderBook
from data_processing.BBO import BBO

class WooXStagingAPI:
    def __init__(self, app_id: str, api_key, api_secret, redis_host: str, redis_port: int = 6379):
        self.app_id = app_id
        self.market_data_url = f"wss://wss.staging.woox.io/ws/stream/{self.app_id}"
        self.private_url = f"wss://wss.staging.woox.io/v2/ws/private/stream/{self.app_id}"
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

    def _generate_signature(self, body):
        key_bytes = bytes(self.api_secret, 'utf-8')
        body_bytes = bytes(body, 'utf-8')
        return hmac.new(key_bytes, body_bytes, hashlib.sha256).hexdigest()

    async def connect_redis(self):
        """Connects to Redis server."""
        self.redis_client = Redis(
                host=self.redis_host,
                port=self.redis_port,
                decode_responses=True
            )
        # Test the connection
        await self.redis_client.ping()
        print(f"Connected to Redis server at {self.redis_host}:{self.redis_port}")

    async def publish_to_redis(self, channel, data):
        """Publish data to Redis channel."""
        if self.redis_client:
            await self.redis_client.publish(channel, json.dumps(data))
            print(f"Published to Redis channel: {channel}")

    async def connect_private(self):
        """Establish the WebSocket connection."""
        if self.private_connection is None:
            self.private_connection = await websockets.connect(self.private_url)
            print(f"Connected to {self.private_url}")
        return self.private_connection

    async def authenticate(self):
        """Send the authentication message."""
        connection = await self.connect_private()
        timestamp = int(time.time() * 1000)  # Current timestamp in milliseconds
        data = f"|{timestamp}"
        # Generate the signature
        signature = self._generate_signature(data)

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
            print("Authentication successful.")
        else:
            print(f"Authentication failed: {response.get('errorMsg')}")

    async def subscribe(self, websocket, config):
        """Subscribe to executionreport, position."""
        if config.get("executionreport"):
            subscribe_message = {
                "event": "subscribe",
                "topic": "executionreport",
            }
            await websocket.send(json.dumps(subscribe_message))
            print(f"Subscribed to executionreport")
        
        if config.get("position"):
            subscribe_message = {
                "event": "subscribe",
                "topic": "position",
            }
            await websocket.send(json.dumps(subscribe_message))
            print(f"Subscribed to position")

        if config.get("balance"):
            subscribe_message = {
                "event": "subscribe",
                "topic": "balance",
            }
            await websocket.send(json.dumps(subscribe_message))
            print(f"Subscribed to balance")

    async def respond_pong(self, websocket):
        """Responds to server PINGs with a PONG."""
        pong_message = {
            "event": "pong",
            "ts": int(asyncio.get_event_loop().time() * 1000)
        }
        await websocket.send(json.dumps(pong_message))

    async def process_market_data(self, message, websocket):
        """Process market data and publish it to Redis."""
        try:
            data = json.loads(message)
            
            # 處理 WebSocket message
            if 'topic' in data:  # 檢查是否是數據消息
                topic = data['topic']
                if topic == 'executionreport':
                    execution_data = data.get('data', {})
                    print("\nExecution Report:")
                    print(json.dumps(execution_data, indent=2))
                    await self.publish_to_redis('executionreport', execution_data)
                    
                elif topic == 'position':
                    position_data = data.get('data', {})
                    print("\nPosition Update:")
                    print(json.dumps(position_data, indent=2))
                    await self.publish_to_redis('position', position_data)
                    
                elif topic == 'balance':
                    balance_data = data.get('data', {})
                    print("\nBalance Update:")
                    print(json.dumps(balance_data, indent=2))
                    await self.publish_to_redis('balance', balance_data)
                    
            elif data.get('event') == 'ping':  # 處理 ping 消息
                print(f"Received ping: {data}")
                await self.respond_pong(websocket)
                
            elif data.get('event') == 'subscribe':  # 處理訂閱響應
                print(f"Subscription response: {data}")
                
            else:
                print(f"Unhandled message type: {data}")
                
        except Exception as e:
            print(f"Error processing message: {str(e)}")
            print(f"Original message: {message}")

    async def listen_for_data(self, websocket, config):
        """Listen for incoming market data and publish to Redis."""
        async for message in websocket:
            print(f"Received message: {message}")
            await self.process_market_data(message, websocket)

    async def close_connection(self):
        """Gracefully closes the WebSocket connection."""
        if self.private_connection is not None:
            await self.private_connection.close()
            self.private_connection = None
            print("Market WebSocket connection closed")

        if self.private_connection is not None:
            await self.private_connection.close()
            self.private_connection = None
            print("Private WebSocket connection closed")

    async def start(self, config):
        """Start the WebSocket connection and market data subscription."""
        await self.connect_redis()  # Connect to Redis
        websocket = await self.connect_private()
        auth_connection = await self.authenticate()
        await self.subscribe(websocket, config)

        while True:
            try:
                message = await websocket.recv()
                # 將 websocket 物件傳入 process_market_data
                await self.process_market_data(message, websocket)
            except websockets.exceptions.ConnectionClosed:
                print("Connection closed, attempting to reconnect...")
                websocket = await self.connect_private()
                await self.authenticate()
                await self.subscribe(websocket, config)
                continue
       

# Example usage
async def main():
    app_id = "460c97db-f51d-451c-a23e-3cce56d4c932"
    api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
    api_secret = 'FWQGXZCW4P3V4D4EN4EIBL6KLTDA'
    api = WooXStagingAPI(app_id=app_id, api_key=api_key, api_secret=api_secret, redis_host="localhost")
    await api.start(config={"executionreport": True, "position": True, "balance": True})

if __name__ == "__main__":
    asyncio.run(main())