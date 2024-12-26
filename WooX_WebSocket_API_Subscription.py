
from data_processing.Orderbook import OrderBook
from data_processing.BBO import BBO

import json
import asyncio
import time
import datetime
import asyncio


class WooXStagingAPI:
    def __init__(self, app_id, api_key, api_secret, server_port):
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.server_port = server_port
        self.orderbooks = {}
        self.bbo_data = {}
        self.print_orderbook_update_lock = None

    async def send_params(self, params):
        """Send params to the simulated server using a socket connection."""
        try:
            params["api_key"] = self.api_key
            params["timestamp"] = int(time.time() * 1000)

            print(f"Sending params: {params}")

            reader, writer = await asyncio.open_connection('localhost', self.server_port)
            writer.write(json.dumps(params).encode('utf-8'))
            await writer.drain()

            response = await reader.read(4096)
            writer.close()
            await writer.wait_closed()

            if response:
                print(f'response is {response}')
                decoded_response = json.loads(response.decode('utf-8'))
                print(f"Received response from action {params['action']}: {decoded_response}")
                return decoded_response
            else:
                print("No response received from server")
                return {"error": "No response received"}

        except Exception as e:
            print(f"Error while sending params: {e}")
            return {"error": str(e)}
    
    async def print_orderbook_update(self, symbol):
        async with self.print_orderbook_update_lock:
            current_time = time.time()
            now_time = datetime.datetime.fromtimestamp(time.time())
            if current_time - self.orderbooks[symbol].timestamp >= 10:
                print("now: ", now_time)
                print(f"Orderbook ask mean for {symbol}: {self.orderbooks[symbol].asks_mean}")
                self.orderbooks[symbol].timestamp = current_time
    
    # error !!!!!!
    async def subscribe(self, symbol, config, interval):
        """Subscribes to orderbook and/or BBO for a given symbol based on the config."""
        # Initialize the OrderBook for the symbol if subscribing to orderbook
        if config.get("orderbook"):
            self.orderbooks[symbol] = OrderBook(symbol)
            params = {
                'action': 'subscribe_orderbook',
                "symbol": symbol,
            }

            subscribe_orderbook_response = None
            print("Sending subscribe_orderbook request...")
            subscribe_orderbook_response = await self.send_params(params)

            while True:
                if subscribe_orderbook_response:
                    print(f"Received response: {subscribe_orderbook_response}")
                    break
                print("No response, retrying...")
                await asyncio.sleep(0.1)

            if not subscribe_orderbook_response:
                subscribe_orderbook_response = {"error": "No response from subscribe_orderbook"}
                print("Error: No response received.")
            else:
                print(f"Final response: {subscribe_orderbook_response}")

        if config.get("kline"):
            params = {
                'action': 'subscribe_kline',
                "topic": f"{symbol}@kline_{interval}",
                'symbol': symbol,
                "interval": interval,
            }
            subscribe_kline_response = await self.send_params(params)
            if subscribe_kline_response is None:
                subscribe_kline_response = {"error": "No response from subscribe_kline send_params"}
            else:
                print(f'subscribe_kline_response is {subscribe_kline_response}')

        if config.get("executionreport"):
            params = {
                'action': "subscribe_executionreport",
            }
            subscribe_executionreport_response = await self.send_params(params)
            if subscribe_executionreport_response is None:
                subscribe_executionreport_response = {"error": "No response from executionreport send_params"}
            else:
                print(f'subscribe_executionreport_response is {subscribe_executionreport_response}')
        
        

async def main():
    api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
    api_secret = 'FWQGXZCW4P3V4D4EN4EIBL6KLTDA'
    app_id = "460c97db-f51d-451c-a23e-3cce56d4c932"
    server_port = 10001

    woox_api = WooXStagingAPI(app_id, api_key, api_secret, server_port)
    config = {
        'orderbook': True,
        # 'bbo': True,
        # 'kline': True,
        # "executionreport": True
    }
    
    symbol = 'SPOT_BTC_USDT'
    interval = '1m'
    await woox_api.subscribe(symbol, config, interval)

if __name__ == "__main__":
    asyncio.run(main())