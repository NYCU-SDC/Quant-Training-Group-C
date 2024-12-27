# async_connection_handler.py
import os
import csv
import json
import asyncio
import time
import datetime
from collections import deque
from datetime import datetime
from utils import send_message, receive_message, log_event

class AsyncConnectionHandler:
    def __init__(self, data_manager, subscribe_manager, matching_manager,
                 simulate_speed, start_timestamp, base_timestamp):
        self.data_manager = data_manager
        self.subscribe_manager = subscribe_manager
        self.matching_manager = matching_manager
        self.fee_rate = 0.04
        self.lock = asyncio.Lock()
        self.orders = deque(maxlen=1000)
        self.balance = 0.0
        self.realized_pnl = 0.0
        self.simulate_speed = simulate_speed
        self.start_timestamp = start_timestamp
        self.base_timestamp = base_timestamp

    def get_timestamp(self):
        return (time.time() - self.start_timestamp) * self.simulate_speed + self.base_timestamp

    async def handle_client_connection(self, client_socket):
        try:
            tasks = []
            while True:
                message = await receive_message(client_socket)
                if not message:
                    break
                try:
                    request = json.loads(message)
                except json.JSONDecodeError:
                    await send_message(client_socket, "invalid_message_format")
                    continue

                event = request.get("event")
                print(f"event received: {event}")
                if event == 'get_bbo':
                    tasks.append(asyncio.create_task(self.handle_get_bbo(client_socket, request)))

                elif event == 'get_kline':
                    tasks.append(asyncio.create_task(self.handle_get_kline(client_socket, request)))

                elif event == 'get_market_trades':
                    tasks.append(asyncio.create_task(self.handle_get_market_trades(client_socket, request)))

                elif event == 'get_orderbook':
                    tasks.append(asyncio.create_task(self.handle_get_orderbook(client_socket, request)))

                elif event == 'subscribe':
                    # 根據 topic 判斷要訂閱哪種行情
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
                    tasks.append(asyncio.create_task(self.handle_subscribe_executionreport(client_socket, request)))
                elif event == 'subscribe_position':
                    tasks.append(asyncio.create_task(self.handle_subscribe_position(client_socket, request)))
                elif event == 'subscribe_balance':
                    tasks.append(asyncio.create_task(self.handle_subscribe_balance(client_socket, request)))

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
        loop = asyncio.get_event_loop()
        kline_response = await loop.run_in_executor(None, self.data_manager.get_kline, request)
        await send_message(client_socket, json.dumps(kline_response))

    async def handle_get_market_trades(self, client_socket, request):
        loop = asyncio.get_event_loop()
        market_trades_response = await loop.run_in_executor(None, self.data_manager.get_market_trades, request)
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
                "ts": self.get_timestamp(),
                "data": request['topic']
            }
            response_message = json.dumps(subscribe_bbo_response) + "\n"
            await send_message(client_socket, response_message)
            print(f"[Server Response] Sent response to client: {response_message}")

            asyncio.create_task(self.stream_bbo_data(client_socket, request))

        except Exception:
            subscribe_bbo_response = {
                "success": False
            }
            response_message = json.dumps(subscribe_bbo_response) + "\n"
            await send_message(client_socket, response_message)
            print(f"[Server Response] Sent response to client: {response_message}")

    async def stream_bbo_data(self, client_socket, request):
        while True:
            try:
                if client_socket.fileno() == -1:
                    print("[Server] Client disconnected. Stopping BBO stream.")
                    break
                print("[Request] Processing BBO request")
                data = await self.subscribe_manager.get_bbo(request)
                print("[Response] Received BBO data")

                data_timestamp = None
                if 'timestamp' in data:
                    try:
                        data_timestamp = int(data['timestamp'])
                    except ValueError:
                        data_timestamp = None
                    del data['timestamp']

                if data['success'] and data_timestamp is not None:
                    bbo_response = {
                        "topic": request['topic'],
                        "ts": data_timestamp,
                        "data": data
                    }
                    response_message = json.dumps(bbo_response) + "\n"
                    await send_message(client_socket, response_message)
                    print(f"[Server BBO Update] Sent: {response_message}")

                    request['timestamp'] = data_timestamp + 1
                else:
                    print("[Server BBO] No valid data or error occurred.")

                await asyncio.sleep(0.1 / self.simulate_speed)

            except Exception as e:
                print(f"[Server BBO Error] {str(e)}")
                break

    async def handle_subscribe_kline(self, client_socket, request):
        try:
            subscribe_kline_response = {
                "event": "subscribe",
                "success": True,
                "ts": self.get_timestamp(),
                "data": request['topic']
            }
            response_message = json.dumps(subscribe_kline_response) + "\n"
            await send_message(client_socket, response_message)
            print(f"[Server Response] Sent response to client: {response_message}")

            asyncio.create_task(self.stream_kline_data(client_socket, request))
        except Exception:
            subscribe_kline_response = {
                "success": False
            }
            response_message = json.dumps(subscribe_kline_response) + "\n"
            await send_message(client_socket, response_message)
            print(f"[Server Response] Sent response to client: {response_message}")

    async def stream_kline_data(self, client_socket, request):
        interval = request['topic'].split('_')[-1]
        wait_time = 60
        if interval == "1m":
            wait_time = 60
        elif interval == "5m":
            wait_time = 300
        elif interval == "15m":
            wait_time = 900
        elif interval == "30m":
            wait_time = 1800
        elif interval == "1h":
            wait_time = 3600
        elif interval == "4h":
            wait_time = 14400
        elif interval == "12h":
            wait_time = 43200
        elif interval == "1d":
            wait_time = 86400
        elif interval == "1w":
            wait_time = 604800
        elif interval == "1mon":
            wait_time = 2592000
        elif interval == "1y":
            wait_time = 31536000

        while True:
            try:
                if client_socket.fileno() == -1:
                    print("[Server] Client disconnected. Stopping Kline stream.")
                    break
                print("[Request] Processing kline request:", request)
                data = await self.subscribe_manager.get_kline(request)
                print("[Response] Received kline data:", data)

                data_timestamp = None
                try:
                    data_timestamp = int(data['endTime'])
                except (ValueError, KeyError):
                    data_timestamp = None

                if data.get('success') and data_timestamp is not None:
                    kline_response = {
                        "topic": request['topic'],
                        "ts": data_timestamp,
                        "data": data
                    }
                    response_message = json.dumps(kline_response) + "\n"
                    await send_message(client_socket, response_message)
                    print(f"[Server kline Update] Sent: {response_message}")

                    request['timestamp'] = data_timestamp + 1
                else:
                    print("No valid data or error occurred.")

                await asyncio.sleep(wait_time / self.simulate_speed)

            except Exception as e:
                print(f"[Server kline Error] {str(e)}")
                break

    async def handle_subscribe_orderbook(self, client_socket, request):
        try:
            subscribe_orderbook_response = {
                "event": "subscribe",
                "success": True,
                "ts": self.get_timestamp(),
                "data": request['topic']
            }
            response_message = json.dumps(subscribe_orderbook_response) + "\n"
            await send_message(client_socket, response_message)
            print(f"[Server Response] Sent response to client: {response_message}")

            asyncio.create_task(self.stream_orderbook_data(client_socket, request))
        except Exception:
            subscribe_orderbook_response = {
                "success": False
            }
            response_message = json.dumps(subscribe_orderbook_response) + "\n"
            await send_message(client_socket, response_message)

    async def stream_orderbook_data(self, client_socket, request):
        while True:
            try:
                if client_socket.fileno() == -1:
                    print("[Server] Client disconnected. Stopping orderbook stream.")
                    break
                print("[Request] Processing orderbook request")
                data = await self.subscribe_manager.get_orderbook(request)
                print("[Response] Received orderbook data:")

                data_timestamp = None
                if 'timestamp' in data:
                    try:
                        data_timestamp = int(data['timestamp'])
                    except ValueError:
                        data_timestamp = None
                    del data['timestamp']

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

                await asyncio.sleep(0.1 / self.simulate_speed)

            except Exception as e:
                print(f"[Server orderbook Error] {str(e)}")
                break

    async def handle_subscribe_trade(self, client_socket, request):
        pass

    async def handle_subscribe_executionreport(self, client_socket, request):
        pass

    async def handle_subscribe_position(self, client_socket, request):
        pass

    async def handle_subscribe_balance(self, client_socket, request):
        pass

    async def handle_send_order(self, client_socket, request):
        print(f"\n[REQUEST] {request}\n")
        try:
            if request['order_type'] == 'MARKET':
                print('[INFO] Processing MARKET order...')

                loop = asyncio.get_event_loop()
                order_response = await loop.run_in_executor(
                    None, self.matching_manager.handle_market_order, request
                )
                print(f"[RESPONSE] {order_response}\n")

                executed_price = float(order_response.get('order_price', 0.0))
                quantity = float(request.get('order_quantity', 0.0))
                symbol = request['symbol']
                side = request['side']

                print(f"[INFO] Executed {side} Order - Price: {executed_price}, "
                      f"Quantity: {quantity}, Symbol: {symbol}")

                async with self.lock:
                    # ---------------------------
                    # PnL + 餘額計算邏輯
                    # ---------------------------
                    turnover = 0.0
                    gross_pnl = 0.0
                    taker_fee = 0.0
                    maker_fee = 0.0
                    pnl = 0.0
                    long_gross_pnl = 0.0
                    short_gross_pnl = 0.0
                    long_position_usd = 0.0
                    short_position_usd = 0.0

                    if side == 'BUY':
                        turnover = executed_price * quantity
                        taker_fee = turnover * self.fee_rate
                        fee = taker_fee

                        self.balance -= (turnover + fee)


                        self.orders.append({
                            'timestamp': int(datetime.now().timestamp() * 1000),
                            'symbol': symbol,
                            'quantity': quantity,
                            'executed_price': executed_price
                        })

                        pnl = 0.0
                        gross_pnl = 0.0
                        long_gross_pnl = 0.0
                        long_position_usd = turnover

                        print(f"[BUY] Deducting cost: {turnover:.2f}, Fee: {fee:.2f}, "
                              f"New Balance: {self.balance:.2f}")

                    elif side == 'SELL':
                        turnover = executed_price * quantity
                        taker_fee = turnover * self.fee_rate
                        fee = taker_fee

                        sorted_orders = sorted(
                            (o for o in self.orders if o['symbol'] == symbol),
                            key=lambda x: x['executed_price']
                        )
                        remaining_quantity = quantity

                        for order in sorted_orders:
                            if remaining_quantity <= 0:
                                break

                            sold_quantity = min(remaining_quantity, order['quantity'])
                            remaining_quantity -= sold_quantity
                            order['quantity'] -= sold_quantity

                            buy_price = order['executed_price']
                            single_gross_pnl = (executed_price - buy_price) * sold_quantity
                            gross_pnl += single_gross_pnl

                            sell_proceeds = executed_price * sold_quantity
                            self.balance += sell_proceeds

                            if order['quantity'] == 0:
                                self.orders.remove(order)

                            print(f"[SELL] Sold {sold_quantity:.6f} from {order}, "
                                  f"Remaining to sell: {remaining_quantity:.6f}")

                        self.balance -= fee
                        short_gross_pnl = gross_pnl

                        pnl = gross_pnl - fee
                        self.realized_pnl += pnl
                        short_position_usd = turnover

                        print(f"[SELL] total SELL turnover: {turnover:.2f}, Fee: {fee:.2f}, "
                              f"gross_pnl: {gross_pnl:.2f}, realized_pnl: {pnl:.2f}, "
                              f"Updated Balance: {self.balance:.2f}")


                    result = {
                        "pnl": pnl,
                        "gross_pnl": gross_pnl,
                        "taker_fee": taker_fee,
                        "maker_fee": maker_fee,
                        "turnover": turnover,
                        "benchmark_price": executed_price,
                        "fee": taker_fee,
                        "ts_ms": int(datetime.now().timestamp() * 1000),
                        "long_gross_pnl": long_gross_pnl,
                        "long_position_usd": long_position_usd,
                        "long_turnover": turnover if side == 'BUY' else 0.0,
                        "short_gross_pnl": short_gross_pnl,
                        "short_position_usd": short_position_usd,
                        "short_turnover": turnover if side == 'SELL' else 0.0
                    }

                    csv_file = 'pnl_log.csv'
                    headers = [
                        "pnl", "gross_pnl", "taker_fee", "maker_fee", "turnover",
                        "benchmark_price", "fee", "ts_ms", "long_gross_pnl",
                        "long_position_usd", "long_turnover", "short_gross_pnl",
                        "short_position_usd", "short_turnover"
                    ]
                    file_exists = os.path.isfile(csv_file)
                    with open(csv_file, mode='a', newline='') as file:
                        writer = csv.DictWriter(file, fieldnames=headers)
                        if not file_exists:
                            writer.writeheader()
                        writer.writerow(result)
                    print(f"[LOG] PnL data saved to {csv_file}")

                    print(f"[SUMMARY] Balance: {self.balance:.2f}, \n"
                          f"RealizedPnL: {self.realized_pnl:.2f}, \n"
                          f"Orders: {list(self.orders)}\n")

                    order_response.update({
                        "pnl": pnl,
                        "gross_pnl": gross_pnl,
                        "fee": taker_fee,
                        "balance": self.balance,
                        "realized_pnl_total": self.realized_pnl
                    })

                await send_message(client_socket, json.dumps(order_response))

        except Exception as e:
            print(f"[ERROR] Exception in handle_send_order: {e}")
            await send_message(client_socket, json.dumps({'success': False, 'error': str(e)}))
