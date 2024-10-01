#2024/10/01/Han Yanc 楊瀚 for problem1,2,4,5
import json
import asyncio
import websockets
import redis
import time
from pymongo import MongoClient
import pandas as pd
import numpy as np

class WooXStagingAPI:
    def __init__(self, app_id: str):
        self.app_id = app_id
        self.uri = f"wss://wss.staging.woox.io/ws/stream/{self.app_id}"
        self.orderbooks_data = {}
        self.bbo_data = {}
        self.orderbook_timestamps = {}
        self.bbo_timestamps = {}
        self.slippage_data = {}
        self.stop_event = asyncio.Event()  # 初始化 stop_event

        self.redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)
        self.mongo_client = MongoClient('localhost', 27017)
        self.db = self.mongo_client['woox_data']
        self.orderbooks_collection = self.db['orderbooks']
        self.bbo_collection = self.db['bbo']

    async def connect(self):
        self.websocket = await websockets.connect(self.uri)
        print(f"Connected to {self.uri}")

    async def subscribe(self, symbol, config):
        if not hasattr(self, 'websocket') or self.websocket.closed:
            await self.connect()

        if config.get("orderbook"):
            order_book_params = {
                "id": self.app_id,
                "event": "subscribe",
                "success": True,
                "ts": int(asyncio.get_event_loop().time() * 1000),
                "topic": f"{symbol}@orderbook"
            }
            await self.websocket.send(json.dumps(order_book_params))

        if config.get("bbo"):
            bbo_params = {
                "id": self.app_id,
                "event": "subscribe",
                "success": True,
                "ts": int(asyncio.get_event_loop().time() * 1000),
                "topic": f"{symbol}@bbo"
            }
            await self.websocket.send(json.dumps(bbo_params))

    async def receive_messages(self, config):
        try:
            while not self.stop_event.is_set():
                message = await self.websocket.recv()
                data = json.loads(message)
                data['received_ts'] = int(time.time() * 1000)

                if data.get("event") == "ping":
                    await self.respond_pong()
                elif data.get("event") == "subscribe" and data.get("success"):
                    print(f"Subscription successful for {data.get('data')}")

                topic = data.get("topic")
                if topic is None or not isinstance(topic, str):
                    print(f"Invalid message format or missing topic: {data}")
                    continue

                symbol = topic.split('@')[0]

                if config.get("orderbook") and topic.endswith("@orderbook"):
                    self.orderbooks_data[symbol] = data['data']
                    self.orderbook_timestamps[symbol] = data['received_ts']
                    self.redis_client.set(f"{symbol}_orderbook", json.dumps(data))
                    self.orderbooks_collection.insert_one(data)
                    print(f"Stored orderbook data for {symbol} in Redis and MongoDB with timestamp {data['received_ts']}")

                elif config.get("bbo") and topic.endswith("@bbo"):
                    self.bbo_data[symbol] = data['data']
                    self.bbo_timestamps[symbol] = data['received_ts']
                    self.redis_client.set(f"{symbol}_bbo", json.dumps(data))
                    self.bbo_collection.insert_one(data)
                    print(f"Stored BBO data for {symbol} in Redis and MongoDB with timestamp {data['received_ts']}")

                if symbol in self.orderbooks_data:
                    self.analyze_slippage(symbol)

        except websockets.ConnectionClosed as e:
            print(f"Connection closed: {e}")

        except Exception as e:
            print(f"Error receiving data: {e}")

    def analyze_slippage(self, symbol):
        orderbook = self.orderbooks_data.get(symbol)
        if not orderbook:
            print(f"No orderbook data for {symbol}")
            return

        bid_orders = orderbook.get('bids', [])
        ask_orders = orderbook.get('asks', [])

        def calculate_slippage(orders, trade_size):
            total_qty = 0
            slippage = 0
            for price, qty in orders:
                total_qty += qty
                slippage += (price - orders[0][0]) * qty
                if total_qty >= trade_size:
                    break
            return slippage / trade_size

        available_buy_qty = sum(qty for price, qty in ask_orders)
        available_sell_qty = sum(qty for price, qty in bid_orders)
        trade_size = min(available_buy_qty, available_sell_qty)

        if bid_orders and ask_orders:
            buy_slippage = calculate_slippage(ask_orders, trade_size)
            sell_slippage = calculate_slippage(bid_orders, trade_size)

            print(f"{symbol} - Buy Slippage: {buy_slippage}, Sell Slippage: {sell_slippage}")

            if symbol not in self.slippage_data:
                self.slippage_data[symbol] = {'buy_slippage': [], 'sell_slippage': []}
            self.slippage_data[symbol]['buy_slippage'].append(buy_slippage)
            self.slippage_data[symbol]['sell_slippage'].append(sell_slippage)

    async def perform_statistical_analysis(self, interval=60):
        while not self.stop_event.is_set():
            await asyncio.sleep(interval)

            for symbol, slippage_info in self.slippage_data.items():
                buy_slippage = slippage_info['buy_slippage']
                sell_slippage = slippage_info['sell_slippage']

                if buy_slippage and sell_slippage:
                    buy_mean = np.mean(buy_slippage)
                    sell_mean = np.mean(sell_slippage)

                    buy_25_quantile = np.percentile(buy_slippage, 25)
                    buy_50_quantile = np.percentile(buy_slippage, 50)
                    buy_75_quantile = np.percentile(buy_slippage, 75)

                    sell_25_quantile = np.percentile(sell_slippage, 25)
                    sell_50_quantile = np.percentile(sell_slippage, 50)
                    sell_75_quantile = np.percentile(sell_slippage, 75)

                    print(f"Statistical analysis for {symbol}:")
                    print(f"  Buy Slippage - Mean: {buy_mean}, 25th: {buy_25_quantile}, 50th: {buy_50_quantile}, 75th: {buy_75_quantile}")
                    print(f"  Sell Slippage - Mean: {sell_mean}, 25th: {sell_25_quantile}, 50th: {sell_50_quantile}, 75th: {sell_75_quantile}")

            self.slippage_data = {}

    async def start(self, symbols, config):
        await self.connect()
        for symbol in symbols:
            await self.subscribe(symbol, config)
        await self.receive_messages(config)

    async def respond_pong(self):
        pong_message = {"event": "pong", "ts": int(asyncio.get_event_loop().time() * 1000)}
        await self.websocket.send(json.dumps(pong_message))
        print(f"Sent PONG: {pong_message}")

    async def close_connection(self):
        if hasattr(self, 'websocket') and not self.websocket.closed:
            await self.websocket.close()
            print("WebSocket connection closed")

    async def run(self, symbols, config):
        try:
            await self.start(symbols, config)

            await self.perform_statistical_analysis(interval=300)
        except asyncio.CancelledError:
            pass
        finally:
            self.stop_event.set()
            await self.close_connection()
            print("Shutting down gracefully...")

if __name__ == "__main__":
    app_id = "460c97db-f51d-451c-a23e-3cce56d4c932"
    woox_api = WooXStagingAPI(app_id)
    symbols = ['SPOT_WOO_USDT', 'SPOT_BTC_USDT', 'SPOT_ETH_USDT', 'PERP_BTC_USDT', 'PERP_ETH_USDT', 'PERP_WOO_USDT']
    config = {"orderbook": True, "bbo": True}
    try:
        asyncio.run(woox_api.run(symbols, config))
    except KeyboardInterrupt:
        print("Interrupted by user")

