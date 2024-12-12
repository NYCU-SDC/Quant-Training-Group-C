from data_processing.Orderbook import OrderBook
from data_processing.BBO import BBO

import json
import asyncio
import websockets
import time
import datetime
import asyncio
import hmac, hashlib, base64
from urllib.parse import urlencode

class WooXWebSocketStagingAPI:
    def __init__(self, app_id: str, api_key: str, api_secret_key: str):
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret_key
        
        self.market_data_url = f"wss://wss.staging.woox.io/ws/stream/{self.app_id}"
        self.private_url = f"wss://wss.staging.woox.io/v2/ws/private/stream/{self.app_id}"

        self.market_connection = None
        self.private_connection = None

        self.orderbooks = {}
        self.bbo_data = {}

    def _generate_signature(self, body) -> str:
        """Generate signature for authentication"""
        key_bytes = bytes(self.api_secret, 'utf-8')
        body_bytes = bytes(body, 'utf-8')
        return hmac.new(key_bytes, body_bytes, hashlib.sha256).hexdigest()

    async def market_connect(self):
        """Handles WebSocket connection"""
        if self.market_connection is None:
            self.market_connection = await websockets.connect(self.market_data_url)
            print(f"Connected to Public Stream {self.market_data_url}")
        return self.market_connection
    
    async def private_connect(self):
        """Establish the WebSocket connection."""
        if self.private_connection is None:
            self.private_connection = await websockets.connect(self.private_url)
            print(f"Connected to {self.private_url}")
        return self.private_connection
    
    async def authenticate(self):
        """Send the authentication message."""
        connection = await self.private_connect()
        timestamp = int(time.time() * 1000)  # Current timestamp in milliseconds
        data = f"|{timestamp}"
        method = "GET"  # WebSocket connections are always GET
        # Generate the signature
        signature = self._generate_signature(data)

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
    
    async def subscribe(self, symbol, config):
        """Subscribes to Market Data for a given symbol based on the config."""
        
        # Initialize the OrderBook for the symbol if subscribing to orderbook
        if config.get('orderbook'):
            try:
                websocket = await self.market_connect()
                self.orderbooks[symbol] = OrderBook(symbol)
                params = {
                    "id": str(asyncio.get_event_loop().time() * 1000),
                    "event": "subscribe",
                    "topic": f"{symbol}@orderbook" 
                }
                await websocket.send(json.dumps(params))
                print(f"Sent subscription request for orderbook")
            except Exception as e:
                print(f"Error subscribing to orderbook: {e}")
            print(f"Subscribed to orderbook for {symbol}")
        
        if config.get('bbo'):
            try:
                websocket = await self.market_connect()
                self.bbo_data[symbol] = BBO(symbol)
                params = {
                    "id": str(asyncio.get_event_loop().time() * 1000),
                    "event": "subscribe",
                    "topic": f"{symbol}@bbo" 
                }
                await websocket.send(json.dumps(params))
                print(f"Sent subscription request for bbo")
            except Exception as e:
                print(f"Error subcribing to bbo: {e}")
            print(f"Subscribed to bbo for {symbol}")
        
        if config.get("executionreport"):
            try:
                websocket = await self.private_connect()
                await self.authenticate()

                params = {
                    "id": str(asyncio.get_event_loop().time() * 1000),
                    "event": "subscribe",
                    "topic": "executionreport",
                }
                await websocket.send(json.dumps(params))
                print(f"Sent subscription request for execution report")

                # 等待訂閱響應
                # response = await websocket.recv()
                # data = json.loads(response)
                # print(f"Subscription response: {response}")
                # print(data)

            except Exception as e:
                print(f"Error subcribing to executionreport: {e}")
            print(f"Subscribed to executionreport for {symbol}")

    async def respond_pong(self, websocket):
        """Responds to server PINGs with a PONG"""
        pong_message = {
            "event": "pong",
            "ts": int(asyncio.get_event_loop().time() * 1000)  # Current timestamp in milliseconds
        }
        await websocket.send(json.dumps(pong_message))

    async def receive_messages(self):
        """Receives Response and processes WebSocket messages"""
        while True:
            try:
                # Listen market_connection and private_connection simultaneously
                connections = []
                if self.market_connection is not None:
                    connections.append((self.market_connection,'market'))
                if self.private_connection is not None:
                    connections.append((self.private_connection,'private'))
                
                if not connections:
                    print("No active connections")
                    break
                
                # use asyncio.gather 來同時處理多個連接
                tasks = [asyncio.create_task(conn[0].recv(), name=conn[1]) for conn in connections]
                done, pending = await asyncio.wait(
                    tasks,
                    return_when=asyncio.FIRST_COMPLETED
                )
                # cancel pending tasks
                for task in pending:
                    task.cancel()
                
                # deal with done task
                for task in done:
                    try:
                        message = await task
                        data = json.loads(message)
                        
                        if 'topic' in data:  # 處理市場數據
                            topic = data['topic']
                            if 'orderbook' in topic:
                                print("\nOrderbook Update:")
                                print(json.dumps(data, indent=2))
                                
                            elif 'bbo' in topic:
                                print("\nBBO Update:")
                                print(json.dumps(data, indent=2))
                            
                            elif 'executionreport' in topic:
                                print("\nExecutionreport Update:")
                                print(json.dumps(data, indent=2))
                                
                        elif data.get('event') == 'ping':  # 處理 ping 消息
                            print(f"Received ping: {data}")
                            pong_message = {
                                "event": "pong",
                                "ts": data['ts']
                            }
                            # Send pong response
                            if task.get_name() == 'private':
                                await self.private_connection.send(json.dumps(pong_message))
                                print(f"Sent pong to private connection: {pong_message}")
                            else:
                                await self.market_connection.send(json.dumps(pong_message))
                                print(f"Sent pong to market connection: {pong_message}")
                        
                        elif data.get('event') == 'subscribe':  # 處理訂閱響應
                            print(f"Subscription response: {data}")
                        
                        else:
                            print(f"Received data: {data}")

                    except Exception as e:
                        print(f"Error processing message: {e}")
                        print(f"Message: {message}")
                
            except websockets.exceptions.ConnectionClosed:
                print("Connection closed")
                break
            except Exception as e:
                print(f"Error: {e}")
                break
            

# async def main():
#     app_id = '460c97db-f51d-451c-a23e-3cce56d4c932'
#     api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
#     api_secret_key = 'FWQGXZCW4P3V4D4EN4EIBL6KLTDA'
    
#     api = WooXWebSocketStagingAPI(app_id, api_key, api_secret_key)
#     symbol = 'PERP_BTC_USDT'
#     config = {
#         'executionreport': True
#     }
    
#     try:
#         await api.subscribe(symbol, config)
#         await api.receive_messages()
#     except KeyboardInterrupt:
#         print("\nShutting down gracefully...")
#     except Exception as e:
#         print(f"Main loop error: {e}")
#     finally:
#         await api.close_connection()

# if __name__ == '__main__':
#     asyncio.run(main())