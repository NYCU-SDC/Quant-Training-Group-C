import json
import asyncio
import websockets
from Data_preprocessor import DataProcessor

class WooXStagingAPI(DataProcessor):
    def __init__(self, app_id: str, model_path: str, time_sequence=10, time_interval=1):
        super().__init__(model_path, time_sequence, time_interval)
        self.app_id = app_id
        self.uri = f"wss://wss.staging.woox.io/ws/stream/{self.app_id}"
        self.message_queue = asyncio.Queue()
        self.connection = None
        self.running = True
        self.processing_task = None

    async def connect(self):
        """Handles WebSocket connection"""
        if self.connection is None:
            self.connection = await websockets.connect(self.uri)
            print(f"Connected to {self.uri}")
        return self.connection

    async def subscribe(self, symbol, config, kline_iterval = '1m'):
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

        if config.get("orderbookupdate"):
            order_book_update_params = {
                "id": self.app_id,
                "event": "subscribe",
                "success": True,
                "ts": int(asyncio.get_event_loop().time() * 1000),
                "topic": f"{symbol}@orderbookupdate"
            }
            await websocket.send(json.dumps(order_book_update_params))

        if config.get("trades"):
            trades_params = {
                "id": self.app_id,
                "event": "subscribe",
                "success": True,
                "ts": int(asyncio.get_event_loop().time() * 1000),
                "topic": f"{symbol}@trades"
            }
            await websocket.send(json.dumps(trades_params))

        if config.get("ticker"):
            ticker_params = {
                "id": self.app_id,
                "event": "subscribe",
                "success": True,
                "ts": int(asyncio.get_event_loop().time() * 1000),
                "topic": f"{symbol}@ticker"
            }
            await websocket.send(json.dumps(ticker_params))

        if config.get("bbo"):
            bbo_params = {
                "id": self.app_id,
                "event": "subscribe",
                "success": True,
                "ts": int(asyncio.get_event_loop().time() * 1000),
                "topic": f"{symbol}@bbo"
            }
            await websocket.send(json.dumps(bbo_params))

        if config.get("kline"):
            kline_params = {
                "id": self.app_id,
                "event": "subscribe",
                "success": True,
                "ts": int(asyncio.get_event_loop().time() * 1000),
                "topic": f"{symbol}@kline_{kline_iterval}"
            }
            await websocket.send(json.dumps(kline_params))

        if config.get("indexprice"):
            bbo_params = {
                "id": self.app_id,
                "event": "subscribe",
                "success": True,
                "ts": int(asyncio.get_event_loop().time() * 1000),
                "topic": f"{symbol}@indexprice"
            }
            await websocket.send(json.dumps(bbo_params))

        if config.get("markprice"):
            bbo_params = {
                "id": self.app_id,
                "event": "subscribe",
                "success": True,
                "ts": int(asyncio.get_event_loop().time() * 1000),
                "topic": f"{symbol}@markprice"
            }
            await websocket.send(json.dumps(bbo_params))

        try:
            while self.running:
                message = await websocket.recv()
                data = json.loads(message)

                if data.get("event") == "ping":
                    await self.respond_pong(websocket)
                elif data.get("event") == "subscribe":
                    if data.get("success"):
                        print(f"Subscription successful for {data.get('data')}")
                else:
                    await self.message_queue.put(data)

        except websockets.ConnectionClosed as e:
            print(f"Connection closed for {symbol}: {e}")
        except Exception as e:
            print(f"Error in subscription handler: {e}")

    async def process_messages(self, symbol):
        while self.running:
            try:
                data = await self.message_queue.get()
                topic = data.get("topic", "")
                if topic == f"{symbol}@orderbook":
                    await self.process_orderbooks(data)
                elif topic == f"{symbol}@orderbookupdate":
                    await self.process_orderbookupdates(data)
                elif topic == f"{symbol}@bbo":
                    await self.process_bbo(data)
                elif topic == f"{symbol}@trades":
                    await self.process_trades(data)
                elif topic == f"{symbol}@ticker":
                    await self.process_tickers(data)
                elif topic.startswith(f"{symbol}@kline"):
                    await self.process_klines(data)
                elif topic == f"{symbol}@indexprice":
                    await self.process_indexprices(data)
                elif topic == f"{symbol}@markprice":
                    await self.process_markprices(data)
            except Exception as e:
                print(f"Error processing message: {e}")

    async def run_processing(self):
        """Separate task for data processing"""
        try:
            while self.running:
                await self.process_data()
                await asyncio.sleep(0.1)  
        except asyncio.CancelledError:
            print("Processing task cancelled")
        except Exception as e:
            print(f"Error in processing task: {e}")

    async def respond_pong(self, websocket):
        pong_message = {
            "event": "pong",
            "ts": int(asyncio.get_event_loop().time() * 1000)
        }
        await websocket.send(json.dumps(pong_message))

    async def start(self, symbols, config):
        try:
            tasks = [asyncio.create_task(self.subscribe(symbol, config)) for symbol in symbols]
            processing_tasks = [asyncio.create_task(self.process_messages(symbol)) for symbol in symbols]
            run_processing_task = asyncio.create_task(self.run_processing())
            await asyncio.gather(*tasks, *processing_tasks, *run_processing_task)
        except Exception as e:
            print(f"Error in start: {e}")
            raise
        finally:
            self.running = False

    async def close_connection(self):
        self.running = False
        if self.connection:
            await self.connection.close()
            self.connection = None
            print("WebSocket connection closed")

async def main():
    app_id = "460c97db-f51d-451c-a23e-3cce56d4c932"
    model_path = 'SPOT_BTC_USDT_model.pth'
    
    api = WooXStagingAPI(app_id, model_path)
    symbols = ['SPOT_BTC_USDT']
    config = {
        "orderbook": True,
        "orderbookupdate": True,
        "trades": True,
        "ticker": True,
        "bbo": True,
        "kline": False,
        "indexprice": True,
        "markprice": True
    }
    
    try:
        await api.start(symbols, config)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    finally:
        await api.close_connection()

if __name__ == "__main__":
    asyncio.run(main())
