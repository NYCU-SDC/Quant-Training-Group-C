
from data_processing.Orderbook import OrderBook
from data_processing.BBO import BBO

import json
import asyncio
import websockets
import time
import datetime
import asyncio
import aiohttp
import hmac, hashlib, base64
from urllib.parse import urlencode


class WooXStagingAPI:
    def __init__(self, app_id: str, api_key, api_secret):
        self.app_id = app_id
        # 建立與 WooX WebSocket API 的連接
        self.market_data_uri = f"wss://wss.staging.woox.io/ws/stream/{self.app_id}"
        self.private_uri = f"wss://wss.staging.woox.io/v2/ws/private/stream/{self.app_id}"
        self.api_key = api_key
        self.api_secret = api_secret
        self.market_connection = None
        self.private_connection = None
        self.orderbooks = {}  # Dictionary to hold OrderBooks for each symbol
        self.bbo_data = {}  # Dictionary to hold BBO instances for each symbols
    
    def generate_signature(self, body):
            key_bytes = bytes(self.api_secret, 'utf-8')
            body_bytes = bytes(body, 'utf-8')
            return hmac.new(key_bytes, body_bytes, hashlib.sha256).hexdigest()
    
    async def market_connect(self):
        """Handles WebSocket connection"""
        if self.market_connection is None:
            self.market_connection = await websockets.connect(self.market_data_uri)
            print(f"Connected to {self.market_data_uri}")
        return self.market_connection

    async def connect_private(self):
        """Establish the WebSocket connection."""
        if self.private_connection is None:
            self.private_connection = await websockets.connect(self.private_uri)
            print(f"Connected to {self.private_uri}")
        return self.private_connection

    async def authenticate(self):
        """Send the authentication message."""
        connection = await self.connect_private()
        timestamp = int(time.time() * 1000)  # Current timestamp in milliseconds
        data = f"|{timestamp}"
        method = "GET"  # WebSocket connections are always GET
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
            print("Authentication successful.")
        else:
            print(f"Authentication failed: {response.get('errorMsg')}")

    async def print_orderbook_update(self, symbol):
        async with self.print_orderbook_update_lock:
            current_time = time.time()
            now_time = datetime.datetime.fromtimestamp(time.time())
            if current_time - self.orderbooks[symbol].timestamp >= 10:
                print("now: ", now_time)
                print(f"Orderbook ask mean for {symbol}: {self.orderbooks[symbol].asks_mean}")
                self.orderbooks[symbol].timestamp = current_time
    

    async def subscribe(self, websocket, symbol, config, interval):
        """Subscribes to orderbook and/or BBO for a given symbol based on the config."""
        # Initialize the OrderBook for the symbol if subscribing to orderbook
        if config.get("orderbook"):
            self.orderbooks[symbol] = OrderBook(symbol)
            # 新增想要訂閱的資訊
            subscribe_message = {
                "event": "subscribe",
                "topic": f"{symbol}@orderbook",
                "symbol": symbol,
                "type": "orderbook"
            }
            await websocket.send(json.dumps(subscribe_message))
            print(f"Subscribed to orderbook for {symbol}")

        # Initialize BBO for the symbol if subscribing to BBO
        if config.get("bbo"):
            self.bbo_data[symbol] = BBO(symbol)
            # 新增想要訂閱的資訊
            subscribe_message = {
                "event": "subscribe",
                "topic": f"{symbol}@bbo",
                "symbol": symbol,
                "type": "bbo"
            }
            await websocket.send(json.dumps(subscribe_message))
            print(f"Subscribed to BBO for {symbol}")

        if config.get("executionreport"):
            subscribe_message = {
                "event": "subscribe",
                "topic": "executionreport",
            }
            await websocket.send(json.dumps(subscribe_message))
            print(f"Subscribed to executionreport")
        
        if config.get("kline"):
            params = {
                "id": str(self.app_id),
                "topic": f"{symbol}@kline_{interval}",
                "event": "subscribe"
            }
            await websocket.send(json.dumps(params))
            response = json.loads(await websocket.recv())
            print(response)


    async def respond_pong(self, websocket):
        """Responds to server PINGs with a PONG"""
        pong_message = {
            "event": "pong",
            "ts": int(asyncio.get_event_loop().time() * 1000)  # Current timestamp in milliseconds
        }
        await websocket.send(json.dumps(pong_message))


    async def close_connection(self):
        """Gracefully closes the WebSocket connection"""
        if self.market_connection is not None:
            await self.market_connection.close()
            self.market_connection = None
            print("market WebSocket connection closed")

        if self.private_connection is not None:
            await self.private_connection.close()
            self.private_connection = None
            print("market WebSocket connection closed")

async def main():
    api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
    api_secret = 'FWQGXZCW4P3V4D4EN4EIBL6KLTDA'
    app_id = "460c97db-f51d-451c-a23e-3cce56d4c932"
    woox_api = WooXStagingAPI(app_id, api_key, api_secret)

    websocket = await woox_api.market_connect()
    
    config = {
            "kline": True
        }
    
    symbol = 'SPOT_BTC_USDT'
    interval = '1m'

    await woox_api.subscribe(websocket, symbol, config, interval)
    message = await websocket.recv()
    print(message)

if __name__ == "__main__":
    asyncio.run(main())