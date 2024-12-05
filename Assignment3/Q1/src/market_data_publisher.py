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
        self.market_connection = None
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

    async def market_connect(self):
        """Handles WebSocket connection to market data."""
        if self.market_connection is None:
            self.market_connection = await websockets.connect(self.market_data_url)
            print(f"Connected to {self.market_data_uri}")
        return self.market_connection

    async def subscribe(self, websocket, symbol, config):
        """Subscribe to orderbook and/or BBO for a given symbol."""
        if config.get("orderbook"):
            self.orderbooks[symbol] = OrderBook(symbol)
            subscribe_message = {
                "event": "subscribe",
                "topic": f"{symbol}@orderbook",
                "symbol": symbol,
                "type": "orderbook"
            }
            await websocket.send(json.dumps(subscribe_message))
            print(f"Subscribed to orderbook for {symbol}")

        if config.get("bbo"):
            self.bbo_data[symbol] = BBO(symbol)
            subscribe_message = {
                "event": "subscribe",
                "topic": f"{symbol}@bbo",
                "symbol": symbol,
                "type": "bbo"
            }
            await websocket.send(json.dumps(subscribe_message))
            print(f"Subscribed to BBO for {symbol}")
        
        if config.get("trade"):
            subscribe_message = {
                "event": "subscribe",
                "topic": f"{symbol}@trade",
            }
            await websocket.send(json.dumps(subscribe_message))
            print(f"Subscribed to trade for {symbol}")

    async def respond_pong(self, websocket):
        """Responds to server PINGs with a PONG."""
        pong_message = {
            "event": "pong",
            "ts": int(asyncio.get_event_loop().time() * 1000)
        }
        await websocket.send(json.dumps(pong_message))

    async def process_market_data(self, symbol, message):
        """Process market data and publish it to Redis."""
        websocket = await self.market_connect()
        message = await websocket.recv()
        data = json.loads(message)
        print(data)
        
        # Assuming message contains 'orderbook' or 'bbo' data
        if 'orderbook' in data:
            self.orderbooks[symbol].update(data['orderbook'])
            # Publish the updated orderbook to Redis
            await self.publish_to_redis(f"{symbol}-orderbook", data['orderbook'])

        if 'bbo' in data:
            self.bbo_data[symbol].update(data['bbo'])
            # Publish the updated BBO to Redis
            await self.publish_to_redis(f"{symbol}-bbo", data['bbo'])
        
        if 'trade' in data:
            # Publish the trade data to Redis
            print(data['trade'])
            await self.publish_to_redis(f"{symbol}-trade", data['trade'])

    async def listen_for_data(self, websocket, symbol, config):
        """Listen for incoming market data and publish to Redis."""
        async for message in websocket:
            print(f"Received message: {message}")
            await self.process_market_data(symbol, message)

    async def close_connection(self):
        """Gracefully closes the WebSocket connection."""
        if self.market_connection is not None:
            await self.market_connection.close()
            self.market_connection = None
            print("Market WebSocket connection closed")

        if self.private_connection is not None:
            await self.private_connection.close()
            self.private_connection = None
            print("Private WebSocket connection closed")

    async def start(self, symbol, config):
        """Start the WebSocket connection and market data subscription."""
        await self.connect_redis()  # Connect to Redis
        websocket = await self.market_connect()
        await self.subscribe(websocket, symbol, config)
        await self.listen_for_data(websocket, symbol, config)

# Example usage
async def main():
    app_id = '460c97db-f51d-451c-a23e-3cce56d4c932'
    api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
    api_secret = 'FWQGXZCW4P3V4D4EN4EIBL6KLTDA'
    api = WooXStagingAPI(app_id, api_key, api_secret, redis_host="localhost")
    await api.start(symbol="SPOT_ETH_USDT", config={"orderbook": True, "bbo": False, "trade": False})

if __name__ == "__main__":
    asyncio.run(main())