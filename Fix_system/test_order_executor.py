import json
import asyncio
import time
import pandas as pd
from redis import asyncio as aioredis
import aiohttp
from WooX_REST_API_Client import WooX_REST_API_Client
import logging

from io import StringIO

# 設置日誌記錄，方便追蹤程式執行情況
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('OrderExecutor')

class OrderExecutor:
    def __init__(self, api_key, api_secret, redis_url="redis://localhost:6379"):
        """初始化訂單執行器"""
        self.redis_url = redis_url
        self.redis_client = None
        self.api = WooX_REST_API_Client(api_key, api_secret)
        self.order_tasks = []
        self.ask_market_order = dict()
        self.bid_market_order = dict()
        self.condition = asyncio.Condition()
        self.current_position = None
        self.position_size = 0.0
        self.entry_price = None
        self.current_atr = None
        logger.info("OrderExecutor initialized")

    async def connect_redis(self):
        """建立Redis連接"""
        self.redis_client = await aioredis.from_url(self.redis_url)
        logger.info(f"Connected to Redis at {self.redis_url}")

    async def subscribe_to_signals(self, signal_channel):
        """訂閱訂單信號頻道"""
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(signal_channel)
        logger.info(f"Subscribed to signal channel: {signal_channel}")
        return pubsub

    async def subscribe_to_private_data(self, private_data_channel):
        """訂閱私有數據頻道"""
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(private_data_channel)
        logger.info(f"Subscribed to private data channel: {private_data_channel}")
        return pubsub

    async def subscribe_to_strategy_signals(self, strategy_channel):
        """訂閱策略信號頻道"""
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(strategy_channel)
        logger.info(f"Subscribed to strategy channel: {strategy_channel}")
        return pubsub

    async def subscribe_to_processed_klines(self):
        """訂閱並監控已處理的K線數據"""
        while True:
            try:
                processed_klines = await self.redis_client.get('processed_klines')
                if processed_klines:
                    # 使用 StringIO 來正確處理 JSON 字符串
                    klines_str = processed_klines.decode('utf-8') if isinstance(processed_klines, bytes) else processed_klines
                    df = pd.read_json(StringIO(klines_str))
                    if not df.empty:
                        self.current_atr = df['atr'].iloc[-1]
                        current_price = df['close'].iloc[-1]
                        await self.check_exit_conditions(current_price)
            except Exception as e:
                logger.error(f"Error processing klines: {str(e)}")
            await asyncio.sleep(1)

    async def check_exit_conditions(self, current_price):
        """檢查是否達到平倉條件"""
        if not self.current_position or not self.entry_price or not self.current_atr:
            return

        async with aiohttp.ClientSession() as session:
            if self.current_position == 'LONG':
                take_profit = self.entry_price + (self.current_atr * 9)
                stop_loss = self.entry_price - (self.current_atr * 3)
                
                if current_price >= take_profit or current_price <= stop_loss:
                    close_signal = {
                        "target": "send_order",
                        "order_quantity": self.position_size,
                        "side": "SELL",
                        "position_side": "LONG",
                        "symbol": "PERP_BTC_USDT",
                        "reduce_only": True
                    }
                    result = await self.execute_order(close_signal, int(time.time()*1000), session)
                    if not result.get('error'):
                        logger.info(f"已平多倉 - 原因: {'停利' if current_price >= take_profit else '停損'}")
                        self.current_position = None
                        self.entry_price = None
                        self.position_size = 0.0

            elif self.current_position == 'SHORT':
                take_profit = self.entry_price - (self.current_atr * 9)
                stop_loss = self.entry_price + (self.current_atr * 3)
                
                if current_price <= take_profit or current_price >= stop_loss:
                    close_signal = {
                        "target": "send_order",
                        "order_quantity": self.position_size,
                        "side": "BUY",
                        "position_side": "SHORT",
                        "symbol": "PERP_BTC_USDT",
                        "reduce_only": True
                    }
                    result = await self.execute_order(close_signal, int(time.time()*1000), session)
                    if not result.get('error'):
                        logger.info(f"已平空倉 - 原因: {'停利' if current_price <= take_profit else '停損'}")
                        self.current_position = None
                        self.entry_price = None
                        self.position_size = 0.0

    async def listen_for_strategy_signals(self, pubsub):
        """監聽策略信號"""
        logger.info("Started listening for strategy signals")
        async for message in pubsub.listen():
            if message["type"] == "message":
                strategy_signal = json.loads(message["data"])
                await self.process_strategy_signal(strategy_signal)

    async def listen_for_execution_report(self, pubsub):
        """監聽執行報告"""
        logger.info("Started listening for execution reports")
        async for message in pubsub.listen():
            if message["type"] == "message":
                execution_report = json.loads(message["data"])
                await self.process_execution_report(execution_report)

    async def process_execution_report(self, execution_report):
        """處理執行報告"""
        logger.info(f"Processing execution report: {execution_report}")
        if execution_report.get('msgType') == 0 and execution_report.get('status') == 'FILLED':
            client_order_id = execution_report.get('client_order_id')
            if execution_report.get('side') == 'SELL':
                self.ask_market_order.pop(client_order_id, None)
            elif execution_report.get('side') == 'BUY':
                self.bid_market_order.pop(client_order_id, None)

    async def execute_order(self, signal, client_order_id, session):
        """執行訂單"""
        if signal['target'] == 'send_order':
            logger.info(f"Preparing hedge mode market order: {signal}")
            
            params = {
                'client_order_id': client_order_id,
                'order_quantity': signal['order_quantity'],
                'order_type': 'MARKET',
                'side': signal['side'],
                'symbol': signal['symbol'],
                'margin_mode': 'CROSS',
                'position_side': signal['position_side'],
                'reduce_only': signal.get('reduce_only', False)
            }

            logger.info(f"Sending order with parameters: {params}")
            try:
                result = await self.api.send_order(session, params)
                logger.info(f"Order result: {result}")
                return result
            except Exception as e:
                logger.error(f"Error executing order: {e}")
                return {'error': str(e)}

    async def process_strategy_signal(self, strategy_signal):
        """處理策略信號"""
        signal = strategy_signal['signal']
        price = strategy_signal.get('price')
        quantity = 0.0001

        async with aiohttp.ClientSession() as session:
            try:
                if self.current_position is None:
                    if signal == 1:
                        signal_data = {
                            "target": "send_order",
                            "order_quantity": quantity,
                            "side": "BUY",
                            "position_side": "LONG",
                            "symbol": "PERP_BTC_USDT",
                            "reduce_only": False
                        }
                        result = await self.execute_order(signal_data, int(time.time()*1000), session)
                        if not result.get('error'):
                            self.current_position = 'LONG'
                            self.position_size = quantity
                            self.entry_price = price
                            
                    elif signal == -1:
                        signal_data = {
                            "target": "send_order",
                            "order_quantity": quantity,
                            "side": "SELL",
                            "position_side": "SHORT",
                            "symbol": "PERP_BTC_USDT",
                            "reduce_only": False
                        }
                        result = await self.execute_order(signal_data, int(time.time()*1000), session)
                        if not result.get('error'):
                            self.current_position = 'SHORT'
                            self.position_size = quantity
                            self.entry_price = price

                elif self.current_position == 'LONG' and signal == -1:
                    close_signal = {
                        "target": "send_order",
                        "order_quantity": self.position_size,
                        "side": "SELL",
                        "position_side": "LONG",
                        "symbol": "PERP_BTC_USDT",
                        "reduce_only": True
                    }
                    result = await self.execute_order(close_signal, int(time.time()*1000), session)
                    if not result.get('error'):
                        await asyncio.sleep(1)
                        open_signal = {
                            "target": "send_order",
                            "order_quantity": quantity,
                            "side": "SELL",
                            "position_side": "SHORT",
                            "symbol": "PERP_BTC_USDT",
                            "reduce_only": False
                        }
                        result = await self.execute_order(open_signal, int(time.time()*1000), session)
                        if not result.get('error'):
                            self.current_position = 'SHORT'
                            self.position_size = quantity
                            self.entry_price = price

                elif self.current_position == 'SHORT' and signal == 1:
                    close_signal = {
                        "target": "send_order",
                        "order_quantity": self.position_size,
                        "side": "BUY",
                        "position_side": "SHORT",
                        "symbol": "PERP_BTC_USDT",
                        "reduce_only": True
                    }
                    result = await self.execute_order(close_signal, int(time.time()*1000), session)
                    if not result.get('error'):
                        await asyncio.sleep(1)
                        open_signal = {
                            "target": "send_order",
                            "order_quantity": quantity,
                            "side": "BUY",
                            "position_side": "LONG",
                            "symbol": "PERP_BTC_USDT",
                            "reduce_only": False
                        }
                        result = await self.execute_order(open_signal, int(time.time()*1000), session)
                        if not result.get('error'):
                            self.current_position = 'LONG'
                            self.position_size = quantity
                            self.entry_price = price

            except Exception as e:
                logger.error(f"Error in strategy signal processing: {e}")

async def main():
    """主程序入口"""
    try:
        api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
        api_secret = 'FWQGXZCW4P3V4D4EN4EIBL6KLTDA'
        
        redis_client = await aioredis.from_url("redis://localhost:6379")
        logger.info("Connected to Redis")

        executor = OrderExecutor(api_key=api_key, api_secret=api_secret)
        await executor.connect_redis()
        logger.info("Order executor initialized")

        strategy_signal = await executor.subscribe_to_strategy_signals("strategy_signals")
        execution_report = await executor.subscribe_to_private_data("execution-reports")
        logger.info("Subscribed to necessary channels")

        listen_tasks = asyncio.gather(
            executor.listen_for_strategy_signals(strategy_signal),
            executor.listen_for_execution_report(execution_report),
            executor.subscribe_to_processed_klines()
        )

        await listen_tasks
        
    except asyncio.CancelledError:
        logger.info("Program shutdown initiated")
    except Exception as e:
        logger.error(f"Error in main program: {e}")
        raise
    finally:
        logger.info("Cleaning up resources...")
        await redis_client.aclose()
        logger.info("Program terminated")

if __name__ == "__main__":
    try:
        # 使用 new_event_loop 來避免警告
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        main_task = loop.create_task(main())
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
        tasks = asyncio.all_tasks(loop)
        for task in tasks:
            task.cancel()
        
        group = asyncio.gather(*tasks, return_exceptions=True)
        loop.run_until_complete(group)
        loop.close()
        logger.info("Shutdown complete")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise