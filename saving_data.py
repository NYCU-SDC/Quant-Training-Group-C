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
        orderbooks_file = None
        orderbooks_file_index = 0
        bbo_file = None
        bbo_file_index = 0

        while not self.stop_event.is_set():
            print("Checking for data in the queues...")
            # orderbook
            try:
                data = self.orderbooks_data_queue.get(block=False)
                print(f"Writing orderbooks data to file")

                if orderbooks_file is None or os.path.getsize(orderbooks_file.name) >= max_file_size:
                    if orderbooks_file is not None:
                        orderbooks_file.close()
                    os.makedirs("data/orderbooks", exist_ok=True)
                    file_name = f"data/orderbooks/orderbooks_data_{orderbooks_file_index}.json"
                    orderbooks_file = open(file_name, "a")
                    orderbooks_file_index += 1

                json.dump(data, orderbooks_file)
                orderbooks_file.write("\n")
                self.orderbooks_data_queue.task_done()
            except queue.Empty:
                print("No orderbooks data available in the queue.")

            # bbo
            try:
                data = self.bbo_data_queue.get(block=False)
                print(f"Writing bbo data to file")

                if bbo_file is None or os.path.getsize(bbo_file.name) >= max_file_size:
                    if bbo_file is not None:
                        bbo_file.close()
                    os.makedirs("data/bbo", exist_ok=True)
                    file_name = f"data/bbo/bbo_data_{bbo_file_index}.json"
                    bbo_file = open(file_name, "a")
                    bbo_file_index += 1

                json.dump(data, bbo_file)
                bbo_file.write("\n")
                self.bbo_data_queue.task_done()
            except queue.Empty:
                print("No bbo data available in the queue.")

        if orderbooks_file is not None:
            orderbooks_file.close()
        if bbo_file is not None:
            bbo_file.close()

if __name__ == "__main__":
    app_id = "460c97db-f51d-451c-a23e-3cce56d4c932"
    woox_api = WooXStagingAPI(app_id)

    symbols = ['SPOT_WOO_USDT', 'SPOT_BTC_USDT', 'SPOT_ETH_USDT']
    config = {"orderbook": True, "bbo": True}

    try:
        asyncio.run(woox_api.start_subscriptions(symbols, config))
    except KeyboardInterrupt:
        print("Shutting down gracefully...")
    finally:
        asyncio.run(woox_api.close_connection())