from Assignment3.Q2.src.market_data_publisher import WooXStagingAPIWebsocket
from WooX_REST_API_Client import WooXStagingAPIRset
from private_data_publisher import WooXStagingAPIPrivateMessage
from Data_preprocessor import DataProcessor

import json
import asyncio
import websockets
import time
import asyncio
import math
import aiohttp

class TransformerCTAStrategy(WooXStagingAPIRset):
    def __init__(self, app_id: str, api_key: str, api_secret: str, data_processor, private_message, symbol, cash):
        super().__init__(app_id, api_key, api_secret)
        self.data_processor = data_processor
        self.private_message = private_message
        self.symbol = symbol
        self.cash = cash
        self.quantity = None
        self.position = 0
        self.check_position_lock = asyncio.Lock()
        self.last_order_id = None

    async def on_prediction(self):
        # await asyncio.sleep(10)   # wait for time sequence data
        try:
            while True:
                prediction, price = await self.data_processor.get_prediction()
                async with self.check_position_lock:
                    if prediction == 2:  # 預測價格上漲
                        if self.position == 0:
                            # 檢查上一個訂單的狀態
                            if self.last_order_id is not None:
                                response = await self.get_order_by_client_id(self.last_order_id)
                                if response['status'] != 'FILLED':
                                    await self.cancel_order_by_client_order_id(self.last_order_id, self.symbol)
                                    print(f"Cancelled order {self.last_order_id}")
                                self.last_order_id = None

                            # 若當前無持倉,則按市價買入
                            self.quantity = float(self.cash / price)
                            self.last_order_id = int(time.time() * 1000)
                            async with aiohttp.ClientSession() as session:
                                response = self.send_order(session=session, symbol=self.symbol, order_type='LIMIT', side='BUY', client_order_id=self.last_order_id,
                                                            order_price=price, order_amount=self.quantity,
                                                            visible_quantity=self.quantity)
                            print(f"Buy order sent: {response}")
                        else:
                            print("Already in a long position, no action taken.")

                    elif prediction == 1:  # 預測價格下跌
                        if self.position > 0:
                            # 檢查上一個訂單的狀態
                            if self.last_order_id is not None:
                                response = await self.ge
                                t_order_by_client_id(self.last_order_id)
                                if response['status'] != 'FILLED':
                                    await self.cancel_order_by_client_order_id(self.last_order_id, self.symbol)
                                    print(f"Cancelled order {self.last_order_id}")
                                self.last_order_id = None

                            # 若當前有持倉,則按市價賣出
                            self.last_order_id = int(time.time() * 1000)
                            async with aiohttp.ClientSession() as session:
                                response = await self.send_order(session=session, symbol=self.symbol, order_type='LIMIT', side='SELL', client_order_id=self.last_order_id,
                                                                 order_price=price, order_amount=self.quantity,
                                                                 visible_quantity=self.quantity)
                            self.cash = price * self.position
                            print(f"Sell order sent: {response}")
                        else:
                            print("No long position to close, no action taken.")
                    '''
                    else:  # 預測價格持平
                        print("Price predicted to stay flat, no action taken.")
                    '''
                    await asyncio.sleep(1)
        except Exception as e:
            print(f"Error in on_prediction: {e}")
        
        await asyncio.sleep(0.1) 

    async def on_execution_report(self, data):
        print(f"Received execution report: {data}")
        if data['orderId'] == self.last_order_id:
            if data['status'] == 'FILLED':
                if data['side'] == 'BUY':
                    self.position += float(data['executedQuantity'])
                elif data['side'] == 'SELL':
                    self.position -= float(data['executedQuantity'])

    '''
    async def on_position(self, data):
        print(f"Received position data: {data}")
        for position in data['positions']:
            if position['symbol'] == self.symbol:
                self.position = float(position['holding'])
    '''
    async def start(self):
        try:
            privatemesssage_task = asyncio.create_task(self.private_message.start(config={"executionreport": True, "position": True, "balance": False}))
            processing_task = asyncio.create_task(self.data_processor.start(self.symbol, config = {"orderbook": True,"orderbookupdate": True,"trades": True,"ticker": True,"bbo": True,"kline": False,"indexprice": True,"markprice": True}))
            on_prediction_task = asyncio.create_task(self.on_prediction())
            await asyncio.gather(privatemesssage_task, processing_task, on_prediction_task)
        except Exception as e:
            print(f"Error in start: {e}")
    '''
    async def start(self):
        try:
            asyncio.create_task(self.private_message.start(config={"executionreport": True, "position": True, "balance": False}))
            asyncio.create_task(self.data_processor.start(self.symbol, config={"orderbook": True, "orderbookupdate": True, "trades": True, "ticker": True, "bbo": True, "kline": False, "indexprice": True, "markprice": True}))
            await self.on_prediction()
        except Exception as e:
            print(f"Error in start: {e}")
    '''
    async def strategy_offline(self):
        await self.data_processor.close_connection()
        await self.private_message.close_connection()


async def main():
    app_id = "460c97db-f51d-451c-a23e-3cce56d4c932"
    api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
    api_secret = 'FWQGXZCW4P3V4D4EN4EIBL6KLTDA'
    model_path = 'SPOT_BTC_USDT_model.pth'
    symbol = ['SPOT_BTC_USDT']
    cash = 100

    data_processor = WooXStagingAPIWebsocket(app_id=app_id, model_path=model_path, time_sequence=10, time_interval=1)
    private_message = WooXStagingAPIPrivateMessage(app_id=app_id, api_key=api_key, api_secret=api_secret)
    strategy = TransformerCTAStrategy(app_id, api_key, api_secret, data_processor, private_message, symbol, cash)

    try:
        await strategy.start()
    except KeyboardInterrupt:
        print("Shutting down gracefully...")
    finally:
        await strategy.strategy_offline()

if __name__ == "__main__":
    asyncio.run(main())
