from WooX_WebSocket_API_Client import WooXStagingAPI
from Data_preprocessor import DataProcessor

import json
import asyncio
import websockets
import time
import asyncio
import math

class TransformerCTAStrategy(WooXStagingAPI):
    def __init__(self, app_id: str, api_key: str, api_secret: str, data_processor, symbol, cash):
        super().__init__(app_id, data_processor)
        self.WooX_REST_API_Client = WooX_REST_API_Client(api_key, api_secret)
        self.symbol = symbol
        self.cash = cash
        self.quantity = None
        self.position = 0
        self.check_position_lock = asyncio.Lock()
        self.last_order_id = None

    async def on_prediction(self, prediction, price):
        async with self.check_position_lock:

            # 獲取當前持倉信息
            position_info = self.WooX_REST_API_Client.get_position_info(self.symbol)
            self.position = float(position_info['holding'])

            if prediction == 2:  # 預測價格上漲
                if self.position == 0:
                    # 檢查上一個訂單的狀態
                    if self.last_order_id is not None:
                        params = {
                        "client_order_id": self.last_order_id,
                        'symbol': self.symbol
                        }
                        response = self.WooX_REST_API_Client.cancel_order_by_client_order_id(params)
                        print(f"Cancelled order {self.last_order_id}")
                        self.last_order_id = None

                    # 若當前無持倉，則按市價買入
                    self.quantity = float(self.cash/price)
                    self.last_order_id = int(time.time() * 1000) 
                    params = {
                        'symbol': self.symbol,
                        'side': 'BUY',
                        'order_type': 'MARKET',
                        'order_amount': self.quantity,
                        'client_order_id': self.last_order_id
                    }
                    response = self.WooX_REST_API_Client.send_order(params)
                    print(f"Buy order sent: {response}")
                else:
                    print("Already in a long position, no action taken.")

            elif prediction == 1:  # 預測價格下跌
                if self.position > 0:
                    # 檢查上一個訂單的狀態
                    if self.last_order_id is not None:
                        params = {
                        "client_order_id": self.last_order_id,
                        'symbol': self.symbol
                        }
                        response = self.WooX_REST_API_Client.cancel_order_by_client_order_id(params)
                        print(f"Cancelled order {self.last_order_id}")
                        self.last_order_id = None

                    # 若當前有持倉,則按市價賣出
                    self.last_order_id = int(time.time() * 1000)  # 使用當前時間戳作為 client_order_id
                    params = {
                        'symbol': self.symbol,
                        'side': 'SELL',
                        'order_type': 'MARKET',
                        'order_amount': self.position,
                        'client_order_id': self.last_order_id
                    }
                    response = self.WooX_REST_API_Client.send_order(params)
                    self. cash = price*self.position
                    print(f"Sell order sent: {response}")
                else:
                    print("No long position to close, no action taken.")

            else:  # 預測價格持平
                print("Price predicted to stay flat, no action taken.")

    async def algorithm(self, config):
        await self.start_subscriptions(self.symbol, config)
        while True:
            try:
                prediction, price = await self.data_processor.process_data()
                await self.on_prediction(prediction, price)

            except Exception as e:
                print(f"Error in algorithm: {e}")
                break

    async def start(self, config):
        await self.algorithm(config)

if __name__ == "__main__":
    app_id = "460c97db-f51d-451c-a23e-3cce56d4c932"
    api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
    api_secret = 'FWQGXZCW4P3V4D4EN4EIBL6KLTDA'
    model_path = 'SPOT_BTC_USDT_model.pth'
    symbol = 'SPOT_BTC_USDT'
    config = {"orderbook": True, "bbo": True, "trades":True, "indexprice":True}
    cash = 50

    data_processor = DataProcessor(model_path=model_path, time_sequence=10, time_interval=1)
    strategy = TransformerCTAStrategy(app_id, api_key, api_secret, data_processor, symbol, cash)

    try:
        asyncio.run(strategy.start(data_processor))
    except KeyboardInterrupt:
        print("Shutting down gracefully...")