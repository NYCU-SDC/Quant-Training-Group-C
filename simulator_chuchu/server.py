import asyncio
import websockets
import json
import hmac
import hashlib
from redis import asyncio as aioredis
from match_egine import MatchingEngine
import numpy as np
from asyncio import Queue
import time

class ExchangeSimulatorServer:
    def __init__(self, host, port, app_id, api_key, api_secret, redis_host, redis_port=6379):
        self.host = host
        self.port = port
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.private_subscriptions = {}
        self.market_subscriptions = {}
        self.matching_engine = MatchingEngine(self)
        self.message_cache = Queue() 
        
        self.market_data_url = f"wss://wss.staging.woox.io/ws/stream/{self.app_id}"
        self.market_connection = None
        # 分開存儲市場和私有連接
        self.market_connections = set()
        self.private_connections = {}
        self.tasks = []

    async def market_connect(self):
        self.market_connection = await websockets.connect(self.market_data_url)
        print(f"Connected to WooX market data at {self.market_data_url}")
    
    def generate_signature(self, data):
        key_bytes = bytes(self.api_secret, 'utf-8')
        data_bytes = bytes(data, 'utf-8')
        return hmac.new(key_bytes, data_bytes, hashlib.sha256).hexdigest()
    
    async def subscribe_market(self, symbol, sub_type, params):
        request = {
            "event": "subscribe",
            "topic": params['topic'],
            "symbol": symbol
        }

        if "type" in params:
             request["type"] = params["type"]
        await self.market_connection.send(json.dumps(request))
        print(f"Subscribed to {sub_type} for {symbol}")
    
    async def unsubscribe_market(self, symbol, sub_type):
        topic = self.market_subscriptions[symbol]["topic"]
        request = {
            "event": "unsubscribe",
            "topic": topic,
        }
        await self.market_connection.send(json.dumps(request))
        print(f"Unsubscribed from {sub_type} for {symbol}")
    
    async def start(self):
        # 使用 route_handler 來處理不同的 URL
        server = await websockets.serve(self.route_handler, self.host, self.port)
        print(f"Exchange Simulator Server started on {self.host}:{self.port}")

        # 啟動其他協程
        self.tasks.append(asyncio.create_task(self.matching_engine.continuously_save_position_and_markprice()))
        self.tasks.append(asyncio.create_task(self.generate_private_data()))
        self.tasks.append(asyncio.create_task(self.relay_market_data()))

        await server.wait_closed()

    async def stop(self):
        print("Stopping Exchange Simulator Server...")
        # 停止 MatchingEngine 的持續保存
        await self.matching_engine.stop_continuous_saving()

        # 取消所有啟動的協程
        for task in self.tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # 關閉所有 WebSocket 連接
        for connection in self.market_connections:
            await connection.close()
        for connection in self.private_connections.values():
            await connection.close()

        print("Exchange Simulator Server stopped.")

    async def route_handler(self, websocket, path):
        """根據 URL 路徑路由到不同的處理函數"""
        try:
            # 解析路徑
            path_parts = path.strip('/').split('/')
            
            if len(path_parts) >= 3:
                if path_parts[0] == "ws" and path_parts[1] == "stream":
                    #  /ws/stream/{app_id}
                    await self.handle_market_connection(websocket, path_parts[2])
                elif path_parts[0] == "v2" and path_parts[1] == "ws" and \
                     path_parts[2] == "private" and path_parts[3] == "stream":
                    #  /v2/ws/private/stream/{app_id}
                    await self.handle_private_connection(websocket, path_parts[4])
                elif path_parts[0] == "api":
                     # /api
                    await self.handle_api_request(websocket)
                else:
                    await websocket.send(json.dumps({"error": "Invalid path"}))
            else:
                await websocket.send(json.dumps({"error": "Invalid URL format"}))
                
        except Exception as e:
            await websocket.send(json.dumps({"error": str(e)}))
    
    async def handle_market_connection(self, websocket, app_id):
        """處理市場數據連接"""
        print(f"Market data client connected: {websocket.remote_address}")
        self.market_connections.add(websocket)
        try:
            async for message in websocket:
                data = json.loads(message)
                if data.get("event") == "subscribe":
                    await self.handle_subscription(websocket, data)
                elif data.get("event") == "unsubscribe":
                    await self.handle_unsubscription(websocket, data)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.market_connections.remove(websocket)
            print(f"Market data client disconnected: {websocket.remote_address}")
    
    async def handle_private_connection(self, websocket, app_id):
        """處理私有數據連接"""
        print(f"Private data client connected: {websocket.remote_address}")
        try:
            async for message in websocket:
                data = json.loads(message)
                if "id" in data:
                    client_id = data["id"]
                    self.private_connections[client_id] = websocket
                else:
                    client_id = str(len(self.private_connections) + 1)
                    self.private_connections[client_id] = websocket
                if "method" in data:
                    if data["method"] == "subscribe":
                        await self.handle_private_subscription(client_id, data)
                    elif data["method"] == "unsubscribe":
                        await self.handle_private_unsubscription(client_id, data)

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            del self.private_connections[client_id]
            print(f"Private data client disconnected: {websocket.remote_address}")
    
    async def handle_subscription(self, websocket, data):
        topic = data.get("topic")
        symbol = data.get("symbol")
        sub_type = data.get("type")
        
        if topic and symbol:
            if symbol not in self.market_subscriptions:
                self.market_subscriptions[symbol] = {}
            
            params = {"topic": topic}
            if sub_type:
                if sub_type == "orderbook":
                    params["type"] = "orderbook"
                elif sub_type == "bbo":
                    params["type"] = "bbo"
            
            self.market_subscriptions[symbol] = params
            await self.subscribe_market(symbol, sub_type, params)
            
            response = {
                "event": "subscribe",
                "topic": topic,
                "symbol": symbol,
                "sub_type": sub_type,
                "success": True
            }
            await websocket.send(json.dumps(response))
    
    async def handle_unsubscription(self, websocket, data):
        topic = data.get("topic")
        symbol = data.get("symbol")
        sub_type = data.get("sub_type")
        
        if topic and symbol and sub_type:
            if symbol in self.market_subscriptions and sub_type in self.market_subscriptions[symbol]:
                await self.unsubscribe_market(symbol, sub_type)
                del self.market_subscriptions[symbol][sub_type]
                
                response = {
                    "event": "unsubscribe",
                    "topic": topic,
                    "symbol": symbol,
                    "sub_type": sub_type,
                    "success": True
                }
                await websocket.send(json.dumps(response))

    async def handle_private_subscription(self, client_id, data):
        topic = data["params"]
        if client_id not in self.private_subscriptions:
            self.private_subscriptions[client_id] = set()
        self.private_subscriptions[client_id].add(topic)

    async def handle_private_unsubscription(self, client_id, data):
        topic = data["params"]
        if client_id in self.private_subscriptions:
            self.private_subscriptions[client_id].discard(topic)
            if not self.private_subscriptions[client_id]:
                del self.private_subscriptions[client_id]

    async def handle_api_request(self, websocket):
        try:
            request = await websocket.recv()
            data = json.loads(request)
            
            method = data.get("method")
            params = data.get("params", {})

            if method == "send_order":
                response = await self.send_order(params)
            elif method == "send_algo_order":
                response = await self.send_algo_order(params)
            elif method == "edit_order_by_client_order_id":
                response = await self.edit_order_by_client_order_id(params)
            elif method == "cancel_order":
                response = await self.cancel_order(params)
            elif method == "cancel_order_by_client_order_id":
                response = await self.cancel_order_by_client_order_id(params)
            elif method == "cancel_orders":
                response = await self.cancel_orders(params)
            elif method == "cancel_all_pending_orders":
                response = await self.cancel_all_pending_orders(params)
            elif method == "get_open_orders":
                response = await self.get_open_orders(params)
            elif method == "get_order_info":
                response = await self.get_order_info(params)
            elif method == "get_positions":
                response = await self.get_positions(params)
            elif method == "get_account_info":
                response = await self.get_account_info(params)
            elif method == "get_balance":
                response = await self.get_balance(params)
            elif method == "transfer":
                response = await self.transfer(params)
            else:
                response = {"error": f"Invalid method: {method}"}

            await websocket.send(json.dumps(response))
        except Exception as e:
            await websocket.send(json.dumps({"error": str(e)}))


    async def send_order(self, params):
        response = await self.matching_engine.handle_order(params)
        return response

    async def send_algo_order(self, params):
        return {"result": "success", "order_id": "simulated_algo_order_id"}

    async def edit_order_by_client_order_id(self, params):
        response = await self.matching_engine.handle_edit_order_by_client_order_id(params)
        return response
    
    async def cancel_order_by_client_order_id(self, params):
        response = await self.matching_engine.handle_cancel_order_by_client_order_id(params)
        return response

    async def cancel_order(self, params):
        response = await self.matching_engine.handle_cancel_order(params)
        return response
    
    async def cancel_orders(self, params):
        response = await self.matching_engine.handle_cancel_orders(params)
        return response
    
    async def cancel_all_pending_orders(self, params):
        response = await self.matching_engine.handle_cancel_all_pending_orders(params)
        return response

    async def cancel_all_orders(self, params):
        # 實現取消所有訂單的邏輯
        # 返回模擬的回應
        return {"result": "success"}

    async def get_open_orders(self, params):
        # 實現獲取當前未成交訂單的邏輯
        # 返回模擬的訂單資料
        return {"result": "success", "data": []}

    async def get_order_info(self, params):
        # 實現獲取訂單資訊的邏輯
        # 返回模擬的訂單資訊
        return {"result": "success", "data": {}}

    async def get_positions(self, params):
        # 實現獲取持倉資訊的邏輯
        # 返回模擬的持倉資料
        return {"result": "success", "data": []}

    async def get_account_info(self, params):
        # 實現獲取帳戶資訊的邏輯
        # 返回模擬的帳戶資訊
        return {"result": "success", "data": {}}

    async def get_balance(self, params):
        # 實現獲取餘額資訊的邏輯
        # 返回模擬的餘額資料
        return {"result": "success", "data": {}}

    async def transfer(self, params):
        # 實現資產轉移的邏輯
        # 返回模擬的回應
        return {"result": "success"}

    async def send_private_data(self, client_id, message):
        if client_id in self.private_connections:
            await self.private_connections[client_id].send(json.dumps(message))

    async def generate_private_data(self):
        while True:
            for client_id, topics in self.private_subscriptions.items():
                if "executionreport" in topics:
                    trade_reports = self.matching_engine.get_trade_reports()
                    for trade_report in trade_reports:
                        data = {
                            "topic": "executionreport",
                            "ts": int(time.time() * 1000),
                            "data": trade_report
                        }
                        await self.send_private_data(client_id, data)
                if "position" in topics:
                    data = {
                        "topic": "position",
                        "data": {
                            # 持倉的資料
                        }
                    }
                    await self.send_private_data(client_id, data)
                if "balance" in topics:
                    data = {
                        "topic": "balance",
                        "data": {
                            # 餘額的資料
                        }
                    }
                    await self.send_private_data(client_id, data)
            
            await asyncio.sleep(1)
    
    async def relay_market_data(self):
        await self.market_connect()

        while True:
            try:
                message = await self.market_connection.recv()
                data = json.loads(message)
                topic = data.get("topic")
                timestamp = data.get("ts")  
                await self.matching_engine.handle_market_data(data)

                if topic:
                    symbol = topic.split("@")[0]
                    sub_type = None
                    if "orderbook" in topic:
                        sub_type = "orderbook"
                    elif "bbo" in topic:
                        sub_type = "bbo"
                    elif "trade" in topic:
                        sub_type = "trade"
                    elif "kline" in topic:
                        sub_type = "kline"
                    elif "markprice" in topic:
                        sub_type = "markprice"

                    await self.message_cache.put(
                        {
                            "timestamp": timestamp,
                            "message": message,
                            "symbol": symbol,
                            "sub_type": sub_type
                        }
                    )
   
                    if sub_type == "orderbook":
                        orderbook_timestamp = timestamp
                        delay_time = max(0, np.random.normal(loc=35, scale=5)) # 到 echange 的延遲
                        publish_time = orderbook_timestamp - delay_time     
                        print(f'orderbook stamp : {orderbook_timestamp}') 
                        print(f'teoretical : {publish_time}')      

                        await self.process_and_publish(publish_time)
            except Exception as e:
                print(f"Error relaying market data: {e}")

    async def process_and_publish(self, publish_time):
        while not self.message_cache.empty():
            cached_message = await self.message_cache.get()

            if cached_message["timestamp"] <= publish_time:
                print(f'cache message timestamp : {cached_message["timestamp"]}')
                symbol = cached_message["symbol"]
                sub_type = cached_message["sub_type"]

                if symbol in self.market_subscriptions and sub_type:
                    for client in self.market_connections:
                        try:
                            await client.send(cached_message["message"])
                        except Exception as e:
                            print(f"Error sending message to client: {e}")
            else:
                await self.message_cache.put(cached_message)
                break  

async def main():
    app_id = "460c97db-f51d-451c-a23e-3cce56d4c932"
    api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
    api_secret = 'FWQGXZCW4P3V4D4EN4EIBL6KLTDA'

    server = ExchangeSimulatorServer("localhost", 8765, app_id, api_key, api_secret, redis_host="localhost")

    try:
        # 啟動伺服器和其他任務
        await server.start()
    except KeyboardInterrupt:
        print("KeyboardInterrupt detected. Stopping server...")
        await server.stop()

if __name__ == "__main__":
    asyncio.run(main())