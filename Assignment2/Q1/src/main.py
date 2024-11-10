from WooX_WebSocket_API_Subscription import WooXStagingAPI
from WooX_REST_API_Client import WooX_REST_API_Client

import json
import asyncio
import websockets
import time
import asyncio
import math

class algorithm(WooXStagingAPI):
    def __init__(self, app_id: str, api_key: str, api_secret: str):
        super().__init__(app_id)
        self.WooX_REST_API_Client = WooX_REST_API_Client(api_key, api_secret)
        print(api_key, api_secret)
        self.check_symbol_isVaild_lock = asyncio.Lock()
        self.trade_amount = 0
        self.revenue = 0


    async def strategy(self, symbol, asks_mean, bids_mean):
        async with self.check_symbol_isVaild_lock:
            if time.time() - self.orderbooks[symbol].start_time < 5 or self.revenue >= 6:
                return
            else:
                if (asks_mean < self.orderbooks[symbol].asks_mean) and self.trade_amount < 6:
                    params = {
                        'client_order_id': int(time.time() * 1000),
                        'order_amount': 10,
                        'order_type': 'MARKET',
                        'side':'BUY',
                        'symbol': symbol
                    }
                    response = self.WooX_REST_API_Client.send_order(params)
                    self.trade_amount +=  1
                    print("response BUY", response)
                    time.sleep(1)
                    return
            
                if bids_mean > self.orderbooks[symbol].bids_mean:
                    params = {
                        'client_order_id': int(time.time() * 1000),
                        'order_amount': 10,
                        'order_type': 'MARKET',
                        'side':'SELL',
                        'symbol': symbol
                    }
                    response = self.WooX_REST_API_Client.send_order(params)
                    print("response SELL", response)
                    time.sleep(1)
                    return
                else:
                    print(bids_mean, self.orderbooks[symbol].bids_mean)
                    
        
    async def algorithm(self, websocket, symbol, config):
        await self.subscribe(websocket, symbol, config)
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
                    # print(data["data"]['ask'])
                    asks_mean, bids_mean = self.orderbooks[symbol].update(data["data"])
                    await self.strategy(symbol, asks_mean, bids_mean)
                    await self.print_orderbook_update(symbol)
                    # print(asks_mean, bids_mean)
                elif config.get("bbo") and data.get("topic") == f"{symbol}@bbo":
                    self.bbo_data[symbol].update(data["data"]["bid"], data["data"]["bidSize"],
                                            data["data"]["ask"], data["data"]["askSize"])

            except websockets.ConnectionClosed as e:
                print(f"Connection closed for {symbol}: {e}")
                break
            except Exception as e:
                print(f"Error receiving data for {symbol}: {e}")
                break
    

    async def start_subscriptions(self, symbols, config):
        """Start subscriptions for multiple symbols based on the provided config"""
        websocket = await self.connect()
        tasks = [self.algorithm(websocket, symbol, config) for symbol in symbols]
        await asyncio.gather(*tasks)



if __name__ == "__main__":
    app_id = "460c97db-f51d-451c-a23e-3cce56d4c932"
    api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
    api_secret = 'FWQGXZCW4P3V4D4EN4EIBL6KLTDA'
    woox_api = algorithm(app_id, api_key, api_secret)

    # 選擇關心的產品
    # symbols = ['SPOT_WOO_USDT', 'SPOT_BTC_USDT', 'SPOT_ETH_USDT']  # Example of subscribing to multiple symbols
    symbols = ['SPOT_ETH_USDT']
    config = {"orderbook": True, "bbo": False}  # Choose what to subscribe to
    # config = {"orderbook": False, "bbo": True}  # Choose what to subscribe to

    try:
        asyncio.run(woox_api.start_subscriptions(symbols, config))
    except KeyboardInterrupt:
        # 例外處理
        print("Shutting down gracefully...")
    finally:
        # 關閉連線
        asyncio.run(woox_api.close_connection())
