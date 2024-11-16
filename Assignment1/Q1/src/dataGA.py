#2024/10/01/Han Yanc 楊瀚 for problem1,5
import json
import asyncio
import websockets
import redis
import time
from pymongo import MongoClient
import numpy as np

class WooXStagingAPI:
    def __init__(self, app_id: str, verbose=True):
        self.app_id = app_id
        self.uri = f"wss://wss.staging.woox.io/ws/stream/{self.app_id}"
        self.orderbooks_data = {}
        self.bbo_data = {}
        self.orderbook_history = {}
        self.bbo_history = {}
        self.orderbook_timestamps = {}
        self.bbo_timestamps = {}
        self.slippage_data = {}
        self.depth_data = {}
        self.stop_event = asyncio.Event()
        self.verbose = verbose
        self.redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)
        self.mongo_client = MongoClient('localhost', 27017)
        self.db = self.mongo_client['woox_data']
        print(f"Connected to MongoDB database: {self.db.name}")
        self.orderbooks_collection = self.db['orderbooks']
        self.bbo_collection = self.db['bbo']

    def store_bbo_history(self, symbol, bbo_data):
        if symbol not in self.bbo_history:
            self.bbo_history[symbol] = []
        self.bbo_history[symbol].append(bbo_data)
        if len(self.bbo_history[symbol]) > 1000:
            self.bbo_history[symbol].pop(0)

        try:
            self.bbo_collection.insert_one({
                'symbol': symbol,
                'bbo_data': bbo_data,
                'timestamp': time.time()
            })
            if self.verbose:
                print(f"Inserted BBO data for {symbol} into MongoDB")
        except Exception as e:
            print(f"Error inserting BBO data for {symbol} into MongoDB: {e}")


    def store_orderbook_history(self, symbol, orderbook_data):
        if symbol not in self.orderbook_history:
            self.orderbook_history[symbol] = []
        self.orderbook_history[symbol].append(orderbook_data)
        if len(self.orderbook_history[symbol]) > 1000:
            self.orderbook_history[symbol].pop(0)

        try:
            self.orderbooks_collection.insert_one({
                'symbol': symbol,
                'orderbook_data': orderbook_data,
                'timestamp': time.time()
            })
            if self.verbose:
                print(f"Inserted orderbook data for {symbol} into MongoDB")
        except Exception as e:
            print(f"Error inserting orderbook data for {symbol} into MongoDB: {e}")


    def get_bbo_history(self, symbol):
        return self.bbo_history.get(symbol, [])

    def get_orderbook_history(self, symbol):
        return self.orderbook_history.get(symbol, [])

    async def receive_messages(self, config):
        try:
            while not self.stop_event.is_set():
                message = await self.websocket.recv()
                data = json.loads(message)
                data['received_ts'] = int(time.time() * 1000)

                if data.get("event") == "ping":
                    await self.respond_pong()
                elif data.get("event") == "subscribe" and data.get("success"):
                    if self.verbose:
                        print(f"Subscription successful for {data.get('data')}")

                topic = data.get("topic")
                if topic is None or not isinstance(topic, str):
                    if self.verbose:
                        print(f"Invalid message format or missing topic: {data}")
                    continue

                symbol = topic.split('@')[0]

                if config.get("orderbook") and topic.endswith("@orderbook"):
                    self.orderbooks_data[symbol] = data['data']
                    self.orderbook_timestamps[symbol] = data['received_ts']
                    self.store_orderbook_history(symbol, data['data'])
                    self.redis_client.set(f"{symbol}_orderbook", json.dumps(data))
                    if self.verbose:
                        print(f"Stored orderbook data for {symbol} with timestamp {data['received_ts']}")

                elif config.get("bbo") and topic.endswith("@bbo"):
                    self.bbo_data[symbol] = data['data']
                    self.bbo_timestamps[symbol] = data['received_ts']
                    self.store_bbo_history(symbol, data['data'])
                    self.redis_client.set(f"{symbol}_bbo", json.dumps(data))
                    if self.verbose:
                        print(f"Stored BBO data for {symbol} with timestamp {data['received_ts']}")

                if symbol in self.orderbooks_data:
                    self.analyze_slippage_and_depth(symbol)

        except websockets.ConnectionClosed as e:
            if self.verbose:
                print(f"Connection closed: {e}")
        except Exception as e:
            if self.verbose:
                print(f"Error receiving data: {e}")

    async def connect(self):
        self.websocket = await websockets.connect(self.uri)
        if self.verbose:
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

    def analyze_slippage_and_depth(self, symbol):
        orderbook = self.orderbooks_data.get(symbol)
        if not orderbook:
            if self.verbose:
                print(f"No orderbook data for {symbol}")
            return

        bid_orders = orderbook.get('bids', [])
        ask_orders = orderbook.get('asks', [])

        if not bid_orders or not ask_orders:
            if self.verbose:
                print(f"Incomplete orderbook data for {symbol}")
            return

        def calculate_slippage(orders, trade_size):
            total_qty = 0
            slippage = 0
            for price, qty in orders:
                total_qty += qty
                slippage += (price - orders[0][0]) * qty
                if total_qty >= trade_size:
                    break
            return slippage / trade_size if trade_size != 0 else 0

        def calculate_depth(orders):
            depth = sum(qty for price, qty in orders)
            price_range = orders[-1][0] - orders[0][0] if orders else 0
            return depth, price_range

        available_buy_qty = sum(qty for price, qty in ask_orders)
        available_sell_qty = sum(qty for price, qty in bid_orders)
        trade_size = min(available_buy_qty, available_sell_qty)

        if bid_orders and ask_orders:
            buy_slippage = calculate_slippage(ask_orders, trade_size)
            sell_slippage = calculate_slippage(bid_orders, trade_size)

            buy_depth, buy_price_range = calculate_depth(ask_orders)
            sell_depth, sell_price_range = calculate_depth(bid_orders)

            if self.verbose:
                print(f"{symbol} - Buy Slippage: {buy_slippage}, Sell Slippage: {sell_slippage}")
                print(f"{symbol} - Buy Depth: {buy_depth}, Sell Depth: {sell_depth}")
                print(f"{symbol} - Buy Price Range: {buy_price_range}, Sell Price Range: {sell_price_range}")

            if symbol not in self.slippage_data:
                self.slippage_data[symbol] = {'buy_slippage': [], 'sell_slippage': []}
            self.slippage_data[symbol]['buy_slippage'].append(buy_slippage)
            self.slippage_data[symbol]['sell_slippage'].append(sell_slippage)

            if symbol not in self.depth_data:
                self.depth_data[symbol] = {'buy_depth': [], 'sell_depth': [], 'buy_price_range': [], 'sell_price_range': []}
            self.depth_data[symbol]['buy_depth'].append(buy_depth)
            self.depth_data[symbol]['sell_depth'].append(sell_depth)
            self.depth_data[symbol]['buy_price_range'].append(buy_price_range)
            self.depth_data[symbol]['sell_price_range'].append(sell_price_range)

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

                    depth_info = self.depth_data.get(symbol, {})
                    buy_depth_mean = np.mean(depth_info.get('buy_depth', []))
                    sell_depth_mean = np.mean(depth_info.get('sell_depth', []))

                    if self.verbose:
                        print(f"Statistical analysis for {symbol}:")
                        print(f"  Buy Slippage - Mean: {buy_mean}, 25th: {buy_25_quantile}, 50th: {buy_50_quantile}, 75th: {buy_75_quantile}")
                        print(f"  Sell Slippage - Mean: {sell_mean}, 25th: {sell_25_quantile}, 50th: {sell_50_quantile}, 75th: {sell_75_quantile}")
                        print(f"  Buy Depth Mean: {buy_depth_mean}, Sell Depth Mean: {sell_depth_mean}")

            self.slippage_data = {}
            self.depth_data = {}

    async def start(self, symbols, config):
        await self.connect()
        for symbol in symbols:
            await self.subscribe(symbol, config)
        await self.receive_messages(config)

    async def respond_pong(self):
        pong_message = {"event": "pong", "ts": int(asyncio.get_event_loop().time() * 1000)}
        await self.websocket.send(json.dumps(pong_message))
        if self.verbose:
            print(f"Sent PONG: {pong_message}")

    async def close_connection(self):
        if hasattr(self, 'websocket') and not self.websocket.closed:
            await self.websocket.close()
            if self.verbose:
                print("WebSocket connection closed")

    async def run(self, symbols, config):
        try:
            await self.start(symbols, config)
        except asyncio.CancelledError:
            pass
        finally:
            self.stop_event.set()
            await self.close_connection()
            if self.verbose:
                print("Shutting down gracefully...")

if __name__ == "__main__":
    app_id = "460c97db-f51d-451c-a23e-3cce56d4c932"
    woox_api = WooXStagingAPI(app_id)
    symbols = ['SPOT_WOO_USDT', 'SPOT_BTC_USDT', 'SPOT_ETH_USDT']
    config = {"orderbook": True, "bbo": True}
    try:
        asyncio.run(woox_api.run(symbols, config))
    except KeyboardInterrupt:
        print("Interrupted by user")
