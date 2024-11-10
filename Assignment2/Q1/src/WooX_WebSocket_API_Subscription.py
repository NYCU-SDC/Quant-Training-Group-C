
from Orderbook import OrderBook  # Import the OrderBook class
from BBO import BBO

import json
import asyncio
import websockets
import time
import datetime
import asyncio

class WooXStagingAPI:
    def __init__(self, app_id: str):
        self.app_id = app_id
        # 建立與 WooX WebSocket API 的連接
        self.uri = f"wss://wss.staging.woox.io/ws/stream/{self.app_id}"
        self.connection = None
        self.orderbooks = {}  # Dictionary to hold OrderBooks for each symbol
        self.bbo_data = {}  # Dictionary to hold BBO instances for each symbols
        self.print_orderbook_update_lock = asyncio.Lock()
        

    async def connect(self):
        """Handles WebSocket connection"""
        if self.connection is None:
            self.connection = await websockets.connect(self.uri)
            print(f"Connected to {self.uri}")
        return self.connection


    async def print_orderbook_update(self, symbol):
        async with self.print_orderbook_update_lock:
            current_time = time.time()
            now_time = datetime.datetime.fromtimestamp(time.time())
            if current_time - self.orderbooks[symbol].timestamp >= 10:
                print("now: ", now_time)
                print(f"Orderbook ask mean for {symbol}: {self.orderbooks[symbol].asks_mean}")
                self.orderbooks[symbol].timestamp = current_time
    

    async def subscribe(self, websocket, symbol, config):
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


    async def respond_pong(self, websocket):
        """Responds to server PINGs with a PONG"""
        pong_message = {
            "event": "pong",
            "ts": int(asyncio.get_event_loop().time() * 1000)  # Current timestamp in milliseconds
        }
        await websocket.send(json.dumps(pong_message))


    async def close_connection(self):
        """Gracefully closes the WebSocket connection"""
        if self.connection is not None:
            await self.connection.close()
            self.connection = None
            print("WebSocket connection closed")
