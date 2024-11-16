import json
import asyncio
import websockets
from Orderbook import OrderBook  # Import the OrderBook class
from BBO import BBO


class WooXStagingAPI:
    def __init__(self, app_id: str):
        self.app_id = app_id
        self.uri = f"wss://wss.staging.woox.io/ws/stream/{self.app_id}"
        self.connection = None
        self.orderbooks = {}  # Dictionary to hold OrderBooks for each symbol
        self.bbo_data = {}  # Dictionary to hold BBO instances for each symbol

    async def connect(self):
        """Handles WebSocket connection"""
        if self.connection is None:
            self.connection = await websockets.connect(self.uri)
            print(f"Connected to {self.uri}")
        return self.connection

    async def subscribe(self, symbol, config):
        """Subscribes to orderbook and/or BBO for a given symbol based on the config."""
        websocket = await self.connect()

        # Initialize the OrderBook for the symbol if subscribing to orderbook
        if config.get("orderbook"):
            self.orderbooks[symbol] = OrderBook(symbol)
            order_book_params = {
            "id": self.app_id,
            "event": "subscribe",
            "success": True,
            "ts": int(asyncio.get_event_loop().time() * 1000),
            "topic": f"{symbol}@orderbookupdate"
            }
            await websocket.send(json.dumps(order_book_params))

        # Initialize BBO for the symbol if subscribing to BBO
        if config.get("bbo"):
            self.bbo_data[symbol] = BBO(symbol)
            bbo_params = {
            "id": self.app_id,
            "event": "subscribe",
            "success": True,
            "ts": int(asyncio.get_event_loop().time() * 1000),
            "topic": f"{symbol}@bbo"
            } 
            await websocket.send(json.dumps(bbo_params))

        
        # TODO: Add code to subscribe to orderbook and/or BBO
        # 1. Prepare and send subscription messages for orderbook and/or BBO.
        # 2. Handle incoming messages, update the orderbook and BBO as per the data received.
        # 3. Print and log the updates.

        # Here's a placeholder to remind students where to implement:
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                print(data)

                if data.get("event") == "ping":
                    await self.respond_pong(websocket)
                elif data.get("event") == "subscribe":
                    if data.get("success"):
                        print(f"Subscription successful for {data.get('data')}")

                # TODO: Handle orderbook and BBO data here
                if config.get("orderbook") and data.get("topic") == f"{symbol}@orderbook":
                    self.orderbooks[symbol].update(data.get("data"))
                    self.orderbooks[symbol].dump()
                elif config.get("bbo") and data.get("topic") == f"{symbol}@bbo":
                    bbo_data = data.get("data")
                    self.bbo_data[symbol].update(bbo_data.get('bid'), bbo_data.get('bidSize'), bbo_data.get('ask'), bbo_data.get('askSize'))
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
        """Gracefully closes the WebSocket connection"""
        if self.connection is not None:
            await self.connection.close()
            self.connection = None
            print("WebSocket connection closed")

    async def start_subscriptions(self, symbols, config):
        """Start subscriptions for multiple symbols based on the provided config"""
        tasks = [self.subscribe(symbol, config) for symbol in symbols]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    app_id = "460c97db-f51d-451c-a23e-3cce56d4c932"
    woox_api = WooXStagingAPI(app_id)

    symbols = ['SPOT_WOO_USDT', 'SPOT_BTC_USDT', 'SPOT_ETH_USDT']  # Example of subscribing to multiple symbols
    config = {"orderbook": True, "bbo": False}  # Choose what to subscribe to

    try:
        asyncio.run(woox_api.start_subscriptions(symbols, config))
    except KeyboardInterrupt:
        print("Shutting down gracefully...")
    finally:
        asyncio.run(woox_api.close_connection())

