# async_connection_handler.py
import json
import asyncio
import time
from utils import send_message, receive_message, log_event

class AsyncConnectionHandler:
    def __init__(self, data_manager, subscribe_manager, matching_manager):
        self.data_manager = data_manager
        self.subscribe_manager = subscribe_manager
        self.matching_manager = matching_manager

    async def handle_client_connection(self, client_socket):
        try:
            tasks = []  # 任務列表
            while True:
                message = await receive_message(client_socket)
                if not message:
                    break
                try:
                    request = json.loads(message)
                    # print(f"request is {request}")
                except json.JSONDecodeError:
                    await send_message(client_socket, "invalid_message_format")
                    continue
                event = request.get("event")
                print(f"event received: {event}")
                
                if event == 'get_bbo':
                    await self.handle_get_bbo(client_socket, request)
                elif event == 'get_kline':
                    await self.handle_get_kline(client_socket, request)
                elif event == 'get_market_trades':
                    await self.handle_get_market_trades(client_socket, request)
                elif event == 'get_orderbook':
                    await self.handle_get_orderbook(client_socket, request)
                
                elif event == 'subscribe':
                    topic = request.get('topic')
                    if 'bbo' in topic:
                        tasks.append(asyncio.create_task(self.handle_subscribe_bbo(client_socket, request)))
                    elif 'kline' in topic:
                        tasks.append(asyncio.create_task(self.handle_subscribe_kline(client_socket, request)))
                    elif 'orderbook' in topic:
                        tasks.append(asyncio.create_task(self.handle_subscribe_orderbook(client_socket, request)))
                    elif 'trade' in topic:
                        tasks.append(asyncio.create_task(self.handle_subscribe_trade(client_socket, request)))
                # elif event == 'subscribe_executionreport':
                #     await self.handle_subscribe_executionreport(client_socket, request)

                elif event == 'subscribe_executionreport':
                    await self.handle_subscribe_executionreport(client_socket, request)
                elif event == 'subscribe_position':
                    await self.handle_subscribe_position(client_socket, request)
                elif event == 'subscribe_balance':
                    await self.handle_subscribe_balance(client_socket, request)

                elif event == 'send_order':
                    tasks.append(asyncio.create_task(self.handle_send_order(client_socket, request)))
                
                else:
                    await send_message(client_socket, json.dumps({"error": "invalid_event"}))


        except asyncio.CancelledError:
            log_event("Connection handler task cancelled.")
        finally:
            client_socket.close()

    async def handle_get_bbo(self, client_socket, request):
        loop = asyncio.get_event_loop()
        bbo_response = await loop.run_in_executor(None, self.data_manager.get_bbo, request)

        if not bbo_response or 'data' not in bbo_response:
            error_response = {"error": "invalid_bbo_response"}
            await send_message(client_socket, json.dumps(error_response))
            return
        
        await send_message(client_socket, json.dumps(bbo_response))

    async def handle_get_kline(self, client_socket, request):
        # print(f"\nrequest: {request}\n")
        loop = asyncio.get_event_loop()
        kline_response = await loop.run_in_executor(None, self.data_manager.get_kline, request)
        # print(f"\nget_kline: {kline_response}\n")
        await send_message(client_socket, json.dumps(kline_response))

    async def handle_get_market_trades(self, client_socket, request):
        # print(f"\nrequest: {request}\n")
        loop = asyncio.get_event_loop()
        market_trades_response = await loop.run_in_executor(None, self.data_manager.get_market_trades, request)
        # print(f"\nget_market_trades: {market_trades_response}\n")
        await send_message(client_socket, json.dumps(market_trades_response))

    async def handle_get_orderbook(self, client_socket, request):
        loop = asyncio.get_event_loop()
        orderbook_response = await loop.run_in_executor(None, self.data_manager.get_orderbook, request)
        if not orderbook_response or 'data' not in orderbook_response:
            error_response = {"error": "invalid_bbo_response"}
            await send_message(client_socket, json.dumps(error_response))
            return
        await send_message(client_socket, json.dumps(orderbook_response))

    async def handle_subscribe_bbo(self, client_socket, request):
        try:
            subscribe_bbo_response = {
                "event": "subscribe",
                "success": True,
                "ts": int(time.time() * 1000),
                "data": request['topic']
            }
            # 加入換行符號並發送訊息
            response_message = json.dumps(subscribe_bbo_response) + "\n"
            await send_message(client_socket, response_message)
            print(f"[Server Response] Sent response to client: {response_message}")

            # 啟動背景任務處理資料流
            asyncio.create_task(self.stream_bbo_data(client_socket, request))
        except:
            subscribe_bbo_response = {
                "success": False
            }
            # 加入換行符號並發送訊息
            response_message = json.dumps(subscribe_bbo_response) + "\n"
            await send_message(client_socket, response_message)
            print(f"[Server Response] Sent response to client: {response_message}")

    async def stream_bbo_data(self, client_socket, request):
        while True:
            try:
                # 檢查連線是否有效
                if client_socket.fileno() == -1:
                    print("[Server] Client disconnected. Stopping BBO stream.")
                    break
                # 處理請求
                print("[Request] Processing BBO request")
                data = await self.subscribe_manager.get_bbo(request)
                print("[Response] Received BBO data")

                # 確保 'timestamp' 是整數格式
                data_timestamp = None
                if 'timestamp' in data:
                    try:
                        data_timestamp = int(data['timestamp'])  # 轉換為整數
                    except ValueError:
                        data_timestamp = None
                    del data['timestamp']

                # 傳送資料
                if data['success'] and data_timestamp is not None:
                    bbo_response = {
                        "topic": request['topic'],
                        "ts": data_timestamp,
                        "data": data
                    }
                    response_message = json.dumps(bbo_response) + "\n"
                    await send_message(client_socket, response_message)
                    print(f"[Server BBO Update] Sent: {response_message}")

                    # 更新時間戳
                    request['timestamp'] = data_timestamp + 1
                else:
                    print("[Server BBO] No valid data or error occurred.")

                # 等待 0.1 秒
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"[Server BBO Error] {str(e)}")
                break

    async def handle_subscribe_kline(self, client_socket, request):
        try:
            subscribe_kline_response = {
                "event": "subscribe",
                "success": True,
                "ts": int(time.time() * 1000),
                "data": request['topic']
            }
            # 加入換行符號並發送訊息
            response_message = json.dumps(subscribe_kline_response) + "\n"
            await send_message(client_socket, response_message)
            print(f"[Server Response] Sent response to client: {response_message}")

             # 啟動背景任務處理資料流
            asyncio.create_task(self.stream_kline_data(client_socket, request))
        except:
            subscribe_kline_response = {
                "success": False
            }
            # 加入換行符號並發送訊息
            response_message = json.dumps(subscribe_kline_response) + "\n"
            await send_message(client_socket, response_message)
            print(f"[Server Response] Sent response to client: {response_message}")

    async def stream_kline_data(self, client_socket, request):
        while True:
            try:
                # 檢查連線是否有效
                if client_socket.fileno() == -1:
                    print("[Server] Client disconnected. Stopping BBO stream.")
                    break
                # 處理請求
                print("[Request] Processing kline request:", request)
                data = await self.subscribe_manager.get_kline(request)
                print("[Response] Received kline data:", data)

                # 確保 'timestamp' 是整數格式
                data_timestamp = None
                try:
                    data_timestamp = int(data['endTime'])  # 轉換為整數
                except ValueError:
                    data_timestamp = None
                if data['success'] and data_timestamp is not None:
                    kline_response = {
                        "topic": request['topic'],
                        "ts": data_timestamp,
                        "data": data
                    }
                    response_message = json.dumps(kline_response) + "\n"
                    await send_message(client_socket, response_message)

                    # 在伺服器端打印傳送的訊息
                    print(f"[Server kline Update] Sent: {response_message}")
                    #  更新先前資料，確保下一次請求時間更新
                    request['timestamp'] = data_timestamp + 1  # 更新為下一個時間點
                else:
                    print("No valid data or error occurred.")
                # 等待 0.1 秒後繼續下一次請求
                await asyncio.sleep(0.1)
                
            except Exception as e:
                print(f"[Server BBO Error] {str(e)}")
                break
    
    async def handle_subscribe_orderbook(self, client_socket, request):
        try:
            subscribe_orderbook_response = {
                "event": "subscribe",
                "success": True,
                "ts": int(time.time() * 1000),
                "data": request['topic']
            }
            # 加入換行符號並發送訊息
            response_message = json.dumps(subscribe_orderbook_response) + "\n"
            await send_message(client_socket, response_message)
            print(f"[Server Response] Sent response to client: {response_message}")
            # 啟動背景任務處理資料流
            asyncio.create_task(self.stream_orderbook_data(client_socket, request))
        except:
            subscribe_orderbook_response = {
                "success": False
            }
            # 加入換行符號並發送訊息
            response_message = json.dumps(subscribe_orderbook_response) + "\n"
            await send_message(client_socket, response_message)

    async def stream_orderbook_data(self, client_socket, request):
        while True:
            try:
                # 檢查連線是否有效
                if client_socket.fileno() == -1:
                    print("[Server] Client disconnected. Stopping orderbook stream.")
                    break
                # 處理請求
                print("[Request] Processing orderbook request")
                data = await self.subscribe_manager.get_orderbook(request)
                print("[Response] Received orderbook data:")

                # 確保 'timestamp' 是整數格式
                data_timestamp = None
                if 'timestamp' in data:
                    try:
                        data_timestamp = int(data['timestamp'])  # 轉換為整數
                    except ValueError:
                        data_timestamp = None
                    del data['timestamp']
                
                # 傳送資料
                if data['success'] and data_timestamp is not None:
                    orderbook_response = {
                        "topic": f"{request['symbol']}@orderbook",
                        "ts": data_timestamp,
                        "data": data
                    }
                    response_message = json.dumps(orderbook_response) + "\n"
                    await send_message(client_socket, response_message)
                    print(f"[Server orderbook Update] Sent")

                    request['timestamp'] = data_timestamp + 1
                else:
                    print("No valid data or error occurred.")

                # 等待 0.1 秒後繼續下一次請求
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"[Server BBO Error] {str(e)}")
                break

    async def handle_subscribe_trade(self, client_socket, request):
        pass
    
    async def handle_subscribe_executionreport(self, client_socket, request):
        # {
        #     "event": "subscribe",
        #     "success": true,
        #     "ts": 1609924478533,
        #     "data": "executionreport"
        # }
        # print(f"\nrequest: {request}\n")
        try:
            subscribe_executionreport_response = {
                'event': "subscribe",
                'success': True,
                'ts': int(time.time() * 1000),
                'data': 'executionreport'
            }
            await send_message(client_socket, json.dumps(subscribe_executionreport_response))
        except:
            subscribe_bbo_response = {
                "success": False
            }
            await send_message(client_socket, json.dumps(subscribe_bbo_response))

    async def handle_subscribe_position(self, client_socket, request):
        pass
    async def handle_subscribe_balance(self, client_socket, request):
        pass

    async def handle_send_order(self, client_socket, request):
        print(f"\nrequest: {request}\n")
        if request['order_type'] == 'MARKET':
            loop = asyncio.get_event_loop()
            order_response = await loop.run_in_executor(None, self.matching_manager.handle_send_order, request)
            print(f"\order_response: {order_response}\n")
            await send_message(client_socket, json.dumps(order_response))
