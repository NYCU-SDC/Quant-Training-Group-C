import json
import asyncio
import websockets
import threading
import queue
import os

class WooXStagingAPI:
    def __init__(self, app_id: str):
        self.app_id = app_id
        self.uri = f"wss://wss.staging.woox.io/ws/stream/{self.app_id}"
        self.connection = None
        self.orderbooks_data_queue = queue.Queue()  
        self.bbo_data_queue = queue.Queue()
        self.trades_data_queue = queue.Queue() 
        self.index_price_data_queue = queue.Queue() 
        self.stop_event = threading.Event()
        self.write_thread = None

    async def connect(self):
        """Handles WebSocket connection"""
        if self.connection is None:
            self.connection = await websockets.connect(self.uri)
            print(f"Connected to {self.uri}")
        return self.connection
    
    async def subscribe(self, symbol, config):
        websocket = await self.connect()

        if config.get("orderbook"):
            order_book_params = {
            "id": self.app_id,
            "event": "subscribe",
            "success": True,
            "ts": int(asyncio.get_event_loop().time() * 1000),
            "topic": f"{symbol}@orderbook"
            }
            await websocket.send(json.dumps(order_book_params))

        # Initialize BBO for the symbol if subscribing to BBO
        if config.get("trades"):
            bbo_params = {
            "id": self.app_id,
            "event": "subscribe",
            "success": True,
            "ts": int(asyncio.get_event_loop().time() * 1000),
            "topic": f"{symbol}@trades"
            } 
            await websocket.send(json.dumps(bbo_params))
        
        if config.get("indexprice"):
            bbo_params = {
            "id": self.app_id,
            "event": "subscribe",
            "success": True,
            "ts": int(asyncio.get_event_loop().time() * 1000),
            "topic": f"{symbol}@indexprice"
            } 
            await websocket.send(json.dumps(bbo_params))

        if config.get("bbo"):
            bbo_params = {
            "id": self.app_id,
            "event": "subscribe",
            "success": True,
            "ts": int(asyncio.get_event_loop().time() * 1000),
            "topic": f"{symbol}@bbo"
            } 
            await websocket.send(json.dumps(bbo_params))

        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)

                if data.get("event") == "ping":
                    await self.respond_pong(websocket)
                elif data.get("event") == "subscribe":
                    if data.get("success"):
                        print(f"Subscription successful for {data.get('data')}")

                if config.get("orderbook") and data.get("topic") == f"{symbol}@orderbook":
                    self.orderbooks_data_queue.put(data)  
                elif config.get("bbo") and data.get("topic") == f"{symbol}@bbo":
                    self.bbo_data_queue.put(data)  
                elif config.get("trades") and data.get("topic") == f"{symbol}@trades":
                    self.trades_data_queue.put(data) 
                elif config.get("indexprice") and data.get("topic") == f"{symbol}@indexprice":
                    self.index_price_data_queue.put(data)   
                
            except websockets.ConnectionClosed as e:
                print(f"Connection closed for {symbol}: {e}")
                break
            except Exception as e:
                print(f"Error receiving data for {symbol}: {e}")
                break

    async def respond_pong(self, websocket):
        """Responds to server PINGs with a PONG"""
        pong_message = {
            "event": "pong",
            "ts": int(asyncio.get_event_loop().time() * 1000)  # Current timestamp in milliseconds
        }
        await websocket.send(json.dumps(pong_message))
        print(f"Sent PONG: {pong_message}")

    async def close_connection(self):
        self.stop_event.set()
        if self.connection is not None:
            await self.connection.close()
            self.connection = None
            print("WebSocket connection closed")
        self.write_thread.join()
        print("Write thread stopped")

    async def start_subscriptions(self, symbols, config):
        """Start subscriptions for multiple symbols based on the provided config"""
        tasks = [self.subscribe(symbol, config) for symbol in symbols]
        self.write_thread = threading.Thread(target=self.write_to_file)
        self.write_thread.start()
        await asyncio.gather(*tasks)

    def write_to_file(self, max_file_size=10 * 1024 * 1024):  # maximum default value 10MB
        files = {
            'orderbooks': {},
            'bbo': {},
            'trades': {},
            'index_price': {}
        }
        file_indices = {
            'orderbooks': {},
            'bbo': {},
            'trades': {},
            'index_price': {}
        }

        def get_symbol(data):
            topic = data.get('topic', '')
            return topic.split('@')[0] if '@' in topic else topic

        def write_data(data, data_type):
            symbol = get_symbol(data)
            print(f"Writing {data_type} data to file for {symbol}")

            if symbol not in files[data_type] or files[data_type][symbol] is None or os.path.getsize(files[data_type][symbol].name) >= max_file_size:
                if symbol in files[data_type] and files[data_type][symbol] is not None:
                    files[data_type][symbol].close()
                
                os.makedirs(f"test_data/{data_type}/{symbol}", exist_ok=True)
                file_index = file_indices[data_type].get(symbol, 0)
                file_name = f"test_data/{data_type}/{symbol}/{data_type}_data_{file_index}.json"
                files[data_type][symbol] = open(file_name, "a")
                file_indices[data_type][symbol] = file_index + 1

            json.dump(data, files[data_type][symbol])
            files[data_type][symbol].write("\n")

        while not self.stop_event.is_set():
            print("Checking for data in the queues...")
            
            # orderbooks
            try:
                data = self.orderbooks_data_queue.get(block=False)
                write_data(data, 'orderbooks')
                self.orderbooks_data_queue.task_done()
            except queue.Empty:
                print("No orderbooks data available in the queue.")

            # bbo
            try:
                data = self.bbo_data_queue.get(block=False)
                write_data(data, 'bbo')
                self.bbo_data_queue.task_done()
            except queue.Empty:
                print("No bbo data available in the queue.")

            # trades
            try:
                data = self.trades_data_queue.get(block=False)
                write_data(data, 'trades')
                self.trades_data_queue.task_done()
            except queue.Empty:
                print("No trades data available in the queue.")

            # index price
            try:
                data = self.index_price_data_queue.get(block=False)
                write_data(data, 'index_price')
                self.index_price_data_queue.task_done()
            except queue.Empty:
                print("No index price data available in the queue.")

        # 關閉所有文件
        for data_type in files:
            for file in files[data_type].values():
                if file is not None:
                    file.close()
if __name__ == "__main__":
    app_id = "460c97db-f51d-451c-a23e-3cce56d4c932"
    woox_api = WooXStagingAPI(app_id)

    symbols = ['SPOT_WOO_USDT', 'SPOT_BTC_USDT', 'SPOT_ETH_USDT']
    config = {"orderbook": True, "bbo": True, "trades":True, "indexprice": True}

    try:
        asyncio.run(woox_api.start_subscriptions(symbols, config))
    except KeyboardInterrupt:
        print("Shutting down gracefully...")
    finally:
        asyncio.run(woox_api.close_connection())