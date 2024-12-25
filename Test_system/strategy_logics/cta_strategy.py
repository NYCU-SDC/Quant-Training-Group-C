import json
import asyncio
import pandas as pd
import numpy as np
from collections import deque
from redis import asyncio as aioredis
from strategy_logics.strategy_init import (
    Strategy,
    SignalData,
    OrderType,
    PositionSide,
    OrderAction
)
import datetime
import time
import logging
from typing import Optional, List, Dict
import pytz
import io

logger = logging.getLogger('CTA strategy')

class ExampleStrategy(Strategy):
    def __init__(self, signal_channel: str, config: Dict = None):
        """
        Initialize strategy
        Args:
            signal_channel: Redis signal channel
            config: Strategy configuration dictionary
        """
        # 先調用父類的初始化
        super().__init__(signal_channel, config)
        
        # 從配置中獲取參數
        trading_params = self.config.get('trading_params', {})
        self.max_records = trading_params.get('max_records', 500)
        self.kline_data = deque(maxlen=self.max_records)
        self.df = pd.DataFrame()

        # 策略參數設置
        self.atr_period = 14
        self.threshold = 0.05
        self.atr_mode = True
        self.chart_type = 'OHLC'

        # 其他初始化
        self.last_update_time = None
        self.redis_client = None
        self.trading_symbol = trading_params.get('symbol', "PERP_BTC_USDT")
        self.position_size = trading_params.get('position_size', 0.001)

        # 設定台灣時區
        self.tz = pytz.timezone('Asia/Taipei')
        
        self.logger.info("CTA Strategy initialization completed")
    
    def setup_logger(self, name: str, log_file: Optional[str] = None,
                     level: int = logging.INFO) -> logging.Logger:
        logger = logging.getLogger(name)
        logger.setLevel(level)

        # 避免重複添加Handler
        if not logger.handlers:
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

            if log_file:
                file_handler = logging.FileHandler(log_file)
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
        return logger

    def create_dataframe(self) -> pd.DataFrame:
        if not self.kline_data:
            return pd.DataFrame()
        
        df_data = []
        for kline in self.kline_data:
            if isinstance(kline, str):
                kline = json.loads(kline)
            if isinstance(kline, dict):
                # 原本資料是毫秒timestamp，轉為datetime
                timestamp = pd.to_datetime(kline.get('endTime', 0), unit='ms', utc=True)
                # 建立row
                row = {
                    'date': timestamp,
                    'open': float(kline.get('open', 0)),
                    'high': float(kline.get('high', 0)),
                    'low': float(kline.get('low', 0)),
                    'close': float(kline.get('close', 0)),
                    'volume': float(kline.get('volume', 0))
                }
                df_data.append(row)

        df = pd.DataFrame(df_data)
        if 'date' in df.columns:
            df.sort_values('date', inplace=True)
        
        # 將index轉換為台灣時區時間
        if 'date' in df.columns:
            df['date'] = df['date'].dt.tz_convert('Asia/Taipei')
        
        return df

    def calculate_tr(self, df: pd.DataFrame) -> pd.Series:
        if len(df) == 0:
            return pd.Series(dtype=float)
        tr_list = []
        for i in range(len(df)):
            if i == 0:
                tr = df['high'].iloc[i] - df['low'].iloc[i]
            else:
                previous_close = df['close'].iloc[i-1]
                tr = max(
                    df['high'].iloc[i] - df['low'].iloc[i],
                    abs(df['high'].iloc[i] - previous_close),
                    abs(df['low'].iloc[i] - previous_close)
                )
            tr_list.append(tr)
        return pd.Series(tr_list, index=df.index, dtype=float)

    def calculate_atr(self, df: pd.DataFrame, period: int=14) -> pd.Series:
        """Calculate ATR using Wilder's Smoothing Method"""
        if len(df) < 1:
            return pd.Series([0]*len(df), index=df.index, dtype=float)
        
        tr = self.calculate_tr(df)
        atr_list = []
        for i in range(len(tr)):
            if i < period:
                # For initial periods, use simple moving average of TR
                atr = np.mean(tr[max(0, i-period+1):i+1])
            else:
                # Use Wilder's smoothing
                previous_atr = atr_list[-1]
                atr = (previous_atr * (period - 1) + tr.iloc[i]) / period
            atr_list.append(atr)
        return pd.Series(atr_list, index=df.index, dtype=float)
        

    def get_direction(self, df: pd.DataFrame) -> pd.DataFrame:
        if len(df) < 1:
            df['direction'] = []
            return df
        up_trend = True
        last_high = df.iloc[0]['high']
        last_low = df.iloc[0]['low']
        directions = []
        for i in range(len(df)):
            # 設定閾值為幾倍ATR，要在這裡修改
            threshold = df.iloc[i]['atr'] if self.atr_mode else self.threshold
            if up_trend:
                if df.iloc[i]['high'] > last_high:
                    last_high = df.iloc[i]['high']
                elif (self.atr_mode and (df.iloc[i]['close'] < last_high - threshold)) or \
                     (not self.atr_mode and (df.iloc[i]['close'] < last_high*(1-threshold))):
                    up_trend = False
                    last_low = df.iloc[i]['low']
            else:
                if df.iloc[i]['low'] < last_low:
                    last_low = df.iloc[i]['low']
                elif (self.atr_mode and (df.iloc[i]['close'] > last_low + threshold)) or \
                     (not self.atr_mode and (df.iloc[i]['close'] > last_low*(1+threshold))):
                    up_trend = True
                    last_high = df.iloc[i]['high']

            directions.append('up' if up_trend else 'down')
        df['direction'] = directions
        return df


    async def generate_signals_and_publish(self, df: pd.DataFrame) -> pd.DataFrame:
        df['signal'] = 0
        if len(df) < 2:
            return df

        i = len(df) - 1  # 只看最後一筆
        prev_direction = df['direction'].iloc[i - 1]
        curr_direction = df['direction'].iloc[i]

        # 若方向一樣，就不動作
        if prev_direction == curr_direction:
            df.iat[i, df.columns.get_loc('signal')] = 0
            return df

        # 以下才是「方向改變」的情況
        timestamp = int(df['date'].iloc[i].timestamp() * 1000)

        if prev_direction == 'up' and curr_direction == 'down':
            # 若有多倉，先平多
            if self.current_position == PositionSide.LONG:
                close_long_signal = SignalData(
                    timestamp=timestamp,
                    action=OrderAction.CLOSE,
                    position_side=PositionSide.LONG,
                    order_type=OrderType.MARKET,
                    symbol=self.trading_symbol,
                    quantity=self.position_size,
                    reduce_only=True
                )
                await self.publish_signal(close_long_signal)
                self.current_position = None

            # 接著開空
            open_short_signal = SignalData(
                timestamp=timestamp,
                action=OrderAction.OPEN,
                position_side=PositionSide.SHORT,
                order_type=OrderType.MARKET,
                symbol=self.trading_symbol,
                quantity=self.position_size
            )
            df.iat[i, df.columns.get_loc('signal')] = -2
            await self.publish_signal(open_short_signal)
            self.current_position = PositionSide.SHORT

        elif prev_direction == 'down' and curr_direction == 'up':
            # 若有空倉，先平空
            if self.current_position == PositionSide.SHORT:
                close_short_signal = SignalData(
                    timestamp=timestamp,
                    action=OrderAction.CLOSE,
                    position_side=PositionSide.SHORT,
                    order_type=OrderType.MARKET,
                    symbol=self.trading_symbol,
                    quantity=self.position_size,
                    reduce_only=True
                )
                await self.publish_signal(close_short_signal)
                self.current_position = None

            # 接著開多
            open_long_signal = SignalData(
                timestamp=timestamp,
                action=OrderAction.OPEN,
                position_side=PositionSide.LONG,
                order_type=OrderType.MARKET,
                symbol=self.trading_symbol,
                quantity=self.position_size
            )
            df.iat[i, df.columns.get_loc('signal')] = 2
            await self.publish_signal(open_long_signal)
            self.current_position = PositionSide.LONG

        return df



    async def execute(self, channel: str, data: dict, redis_client: aioredis.Redis) -> None:
        """Process received kline data and generate signals"""
        try:
            # Debug log at the beginning of execute
            self.logger.info(f"execute() triggered - Channel: {channel}")

            self.redis_client = redis_client
            
            # 檢查是否是處理過的K線數據
            if "processed-kline" in channel:
                self.logger.info("Processing processed-kline data...")
                # 解析數據
                if isinstance(data, str):
                    kline_data = json.loads(data)
                else:
                    kline_data = data
                    
                self.logger.info(f"Kline data: {kline_data}")
                    
                # 從數據中提取K線信息
                candle_data = kline_data.get('data', {}).get('kline_data', {})
                
                if not candle_data:
                    self.logger.info("No kline_data found, skipping...")
                    return
                    
                current_time = candle_data.get('endTime')
                
                # 避免重複處理
                if self.last_update_time and current_time <= self.last_update_time:
                    self.logger.info("Received an older or same timestamp kline, skipping...")
                    return
                
                # 添加到K線數據隊列
                self.kline_data.append(candle_data)
                self.last_update_time = current_time
                
                # 創建和處理DataFrame
                self.df = self.create_dataframe()

                # Debug log after DataFrame creation
                self.logger.info(f"DataFrame created with shape: {self.df.shape}")
                self.logger.info(f"DataFrame head:\n{self.df.head()}")

                if len(self.df) > 0:
                    # 計算技術指標
                    self.df['atr'] = self.calculate_atr(self.df, self.atr_period)
                    self.df = self.get_direction(self.df)
                    self.df = await self.generate_signals_and_publish(self.df)

                    self.logger.info(f"DataFrame after calculations:\n{self.df.head()}")
                    
                    # 改用pickle序列化後存入Redis
                    buffer = io.BytesIO()
                    self.df.to_pickle(buffer)
                    buffer.seek(0)
                    await self.redis_client.set('strategy_df', buffer.read())

                    # Debug log after saving to Redis
                    self.logger.info("DataFrame saved to Redis as 'strategy_df' (pickled)")
                    
        except Exception as e:
            self.logger.error(f"Error in strategy execution: {e}")
            raise

# async def main():
#     strategy = ExampleStrategy("strategy_signals")
#     strategy.threshold = 0.05  # initial threshold
#     strategy.atr_mode = True  # change atr mode, if it is True, threshold = 3 atr
#     strategy.chart_type = 'line'  # change type

#     redis_client = await aioredis.from_url(
#         'redis://localhost:6379',
#         encoding='utf-8',
#         decode_responses=True
#     )
    
#     try:
#         logger.info("Starting to monitor kline data...")
#         last_processed_time = None
        
#         while True:
#             # Get latest kline data from Redis
#             processed_kline = await redis_client.get('[MD]PERP_BTC_USDT-processed-kline_1m')
#             if processed_kline:
#                 try:
#                     kline_data = json.loads(processed_kline)
#                     current_time = kline_data.get('endTime')
                    
#                     # Process only new data
#                     if current_time != last_processed_time:
#                         await strategy.execute('[MD]PERP_BTC_USDT-processed-kline_1m', kline_data, redis_client)
#                         last_processed_time = current_time
#                 except json.JSONDecodeError as e:
#                     logger.error(f"JSON decode error: {e}")
            
#             await asyncio.sleep(0.1)
            
#     except asyncio.CancelledError:
#         logger.info("Shutting down strategy...")
#     except Exception as e:
#         logger.error(f"Runtime error: {str(e)}")
#     finally:
#         await redis_client.aclose()

# if __name__ == "__main__":
#     try:
#         asyncio.run(main())
#     except KeyboardInterrupt:
#         logger.info("Program terminated by user")
#     except Exception as e:
#         logger.error(f"Program error: {str(e)}")