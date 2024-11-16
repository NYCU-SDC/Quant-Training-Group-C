import json
import asyncio
import websockets
from Data_preprocessor import DataProcessor

class WooXStagingAPI(DataProcessor):
    def __init__(self, app_id: str, model_path: str, time_sequence=10, time_interval=1):
        super().__init__(model_path, time_sequence, time_interval)
        self.app_id = app_id
        self.uri = f"wss://wss.staging.woox.io/ws/stream/{self.app_id}"
        self.connection = None
        self.running = True
        self.processing_task = None

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

        if config.get("trades"):
            bbo_params = {
                "id": self.app_id,
                "event": "subscribe",
                "success": True,
                "ts": int(asyncio.get_event_loop().time() * 1000),
                "topic": f"{symbol}@trades"
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

        if config.get("indexprice"):
            bbo_params = {
                "id": self.app_id,
                "event": "subscribe",
                "success": True,
                "ts": int(asyncio.get_event_loop().time() * 1000),
                "topic": f"{symbol}@indexprice"
            }
            await websocket.send(json.dumps(bbo_params))

         # 啟動數據處理任務
        self.processing_task = asyncio.create_task(self.run_processing())

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
                    topic = data.get("topic", "")
                    if topic == f"{symbol}@orderbook":
                        await self.process_orderbooks(data)
                    elif topic == f"{symbol}@bbo":
                        await self.process_bbo(data)
                    elif topic == f"{symbol}@trades":
                        await self.process_trades(data)
                    elif topic == f"{symbol}@indexprice":
                        await self.process_indexprices(data)

        except websockets.ConnectionClosed as e:
            print(f"Connection closed for {symbol}: {e}")
        except Exception as e:
            print(f"Error in subscription handler: {e}")
        finally:
            if self.processing_task:
                self.processing_task.cancel()
                try:
                    await self.processing_task
                except asyncio.CancelledError:
                    pass

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
            tasks = [self.subscribe(symbol, config) for symbol in symbols]
            await asyncio.gather(*tasks)
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
    config = {"orderbook": True, "bbo": True, "trades": True, "indexprice": True}
    
    try:
        await api.start(symbols, config)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    finally:
        await api.close_connection()

if __name__ == "__main__":
    asyncio.run(main())
