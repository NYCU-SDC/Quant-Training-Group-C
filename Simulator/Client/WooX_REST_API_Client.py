# don't change
import asyncio
import json
import time
from config import load_config

class WooX_REST_API_Client:
    def __init__(self, api_key, api_secret, server_port):
        self.api_key = api_key
        self.api_secret = api_secret
        self.server_port = server_port

        config = load_config("config.json")
        self.simulate_speed = config['simulator']['simulate_speed']
        self.start_timestamp = config['simulator']['start_timestamp']
        self.base_timestamp = config['simulator']['base_timestamp']

    def get_timestamp(self):
        return (time.time() - self.start_timestamp) * self.simulate_speed  + self.base_timestamp

    async def send_params(self, params):
        """Send params to the simulated server using a TCP socket connection."""
        try:
            # 添加 API 金鑰和時間戳
            params["api_key"] = self.api_key
            params["timestamp"] = self.get_timestamp()

            print(f"Sending params: {params}")

            # 建立 TCP 連線
            reader, writer = await asyncio.open_connection(
                host='localhost',          # 替換為您的伺服器主機名或IP
                port=self.server_port,     # 使用指定的埠號
                local_addr=('127.0.0.1', 0)      # 可指定本地來源 IP 和埠號 (這裡讓系統自動分配)
            )

            # 將參數轉換為 JSON 字串並編碼後發送
            writer.write(json.dumps(params).encode('utf-8') + b'\n')  # 添加換行符號
            await writer.drain()  # 確保資料已經寫入並傳送

            # 等待伺服器回應
            response = await reader.read(4096)

            # 關閉連線
            writer.close()
            await writer.wait_closed()

            # 解碼回應
            if response:
                decoded_response = json.loads(response.decode('utf-8'))
                print(f"Received response from action {params['action']}: {decoded_response}")
                return decoded_response
            else:
                print("No response received from server")
                return {"error": "No response received"}

        except Exception as e:
            print(f"Error while sending params: {e}")
            return {"error": str(e)}


    async def get_bbo(self, symbol):
        params = {
            'action': "get_bbo",
            "symbol": symbol
        }
        bbo_response = await self.send_params(params)
        if bbo_response is None:
            bbo_response = {"error": "No response from send_params"}
        return bbo_response

    async def get_market_trades(self, symbol):
        params = {
            "action": "get_market_trades",
            "symbol": symbol
        }
        market_trades_response = await self.send_params(params)
        if market_trades_response is None:
            market_trades_response = {"error": "No response from send_params"}
        return market_trades_response
    
    async def get_orderbook(self, symbol):
        params = {
            "action": "get_orderbook",
            "symbol": symbol
        }
        market_trades_response = await self.send_params(params)
        if market_trades_response is None:
            market_trades_response = {"error": "No response from send_params"}
        return market_trades_response

    async def get_kline(self, symbol, interval="1m"):
        params = {
            "action": "get_kline",
            "symbol": symbol,
            "interval": interval,
        }
        kline_response = await self.send_params(params)
        if kline_response is None:
            kline_response = {"error": "No response from send_params"}
        return kline_response


    async def send_order(self, params):
        params = {
            "event": "send_order",
            **params
        }
        print(f"Event: send_order with params {params}")
        order_response = await self.send_params(params)
        if order_response is None:
            order_response = {"error": "No response from send_params"}
        return order_response

async def busy_loop(client, symbol):
    tasks = [
        asyncio.create_task(client.get_bbo(symbol)),
        asyncio.create_task(client.get_market_trades(symbol)),
        asyncio.create_task(client.get_kline(symbol))
    ]

    order_tasks = []
    # task_names = ["Orderbook", "Trades", "Kline"]
    # task_names = ['Orderbook']
    last_order_time = time.time()
    count = 0

    while True:
        print(f"\nPolling for {symbol} data...\n")
        # for i, task in enumerate(tasks):
        #     if task.done():
        #         try:
        #             result = await task
        #             print(f"[{task_names[i]}] done.")
        #             if task_names[i] == "Orderbook":
        #                 tasks[i] = asyncio.create_task(client.get_orderbook(symbol))
        #             elif task_names[i] == "Trades":
        #                 tasks[i] = asyncio.create_task(client.get_market_trades(symbol))
        #             elif task_names[i] == "Kline":
        #                 tasks[i] = asyncio.create_task(client.get_kline(symbol))
        #         except Exception as e:
        #             print(f"[{task_names[i]} Error] {e}")

        current_time = time.time()
        if current_time - last_order_time >= 2:  # 2 seconds have passed
            count += 1
            print("[Condition Met] Sending an order...")
            order_params = {
                'client_order_id': count,
                'order_price': 3190,
                'order_quantity': 0.1,
                'order_type': 'MARKET',
                'side': 'BUY',
                'symbol': 'SPOT_ETH_USDT'
            }
            print(f"Action: send_order initiated with params {order_params}")
            order_tasks.append(
                asyncio.create_task(client.send_order(order_params))
            )
            await asyncio.sleep(1)
            order_params['order_quantity'] = 0.2
            order_tasks.append(
                asyncio.create_task(client.send_order(order_params))
            )
            await asyncio.sleep(1)
            order_params['side'] = 'SELL'
            order_tasks.append(
                asyncio.create_task(client.send_order(order_params))
            )
            last_order_time = current_time  # Update the last order time

        # Process order tasks
        for order_task in list(order_tasks):
            if order_task.done():
                try:
                    result = await order_task
                    print("[Order Task Completed] Result:", result)
                except Exception as e:
                    print("[Order Task Error]:", e)
                finally:
                    order_tasks.remove(order_task)  # Clean up completed task

        await asyncio.sleep(1)

async def main():
    api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
    api_secret = 'FWQGXZCW4P3V4D4EN4EIBL6KLTDA'
    server_port = 10001
    client = WooX_REST_API_Client(api_key, api_secret, server_port)

    symbol = 'SPOT_BTC_USDT'
    await busy_loop(client, symbol)

if __name__ == "__main__":
    asyncio.run(main())