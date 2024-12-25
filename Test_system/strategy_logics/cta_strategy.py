import json
import asyncio
import logging
import time
import pytz
import pandas as pd
import numpy as np
import io 
from datetime import datetime
from collections import deque
from typing import Optional, Dict
from redis import asyncio as aioredis

# 假設您在同專案有一個 woox_data_loader.py
# 其中包含 WooXPublicAPI / fetch_recent_kline_woo
from strategy_logics.Woox_loader_for_cta import WooXPublicAPI, fetch_recent_kline_woo

from strategy_logics.strategy_init import (
    Strategy,
    SignalData,
    OrderType,
    PositionSide,
    OrderAction
)

logger = logging.getLogger(__name__)


class ExampleStrategy(Strategy):
    """
    每次程式啟動:
      1) 清空self.kline_data, self.df
      2) 從現在(本地UTC+8)往前14根抓K線 => 生成df
      3) 後續由WebSocket => execute => 追加新的row => 計算ATR/direction/signal

    不再從Redis或檔案載入舊DataFrame，以免「繼承上一輪程式」的紀錄。
    """

    def __init__(self, signal_channel: str, config: Dict = None):
        super().__init__(signal_channel, config)

        # === 讀取配置
        trading_params = self.config.get('trading_params', {})
        self.max_records = trading_params.get('max_records', 500)
        self.trading_symbol = trading_params.get('symbol', "PERP_BTC_USDT")
        self.position_size  = trading_params.get('position_size', 0.001)

        # === 清空, 從零開始
        self.df = pd.DataFrame()
        self.kline_data = deque(maxlen=self.max_records)

        self.atr_period = 14
        self.threshold_multiplier = 3.0   # direction翻轉閾值 = 3*ATR
        self.take_profit_atr = 9.0       # 停利
        self.stop_loss_atr   = 3.0       # 停損
        self.current_position: Optional[PositionSide] = None
        self.entry_price: Optional[float] = None
        self.last_update_time: Optional[int] = None
        self.redis_client = None

        # 本地(UTC+8)
        self.local_tz = pytz.timezone("Asia/Taipei")

        # === 在初始化時, 透過REST抓取前14根K線
        try:
            # 這裡請改成您的WooX API key
            api_key = "sdFgbf5mnyDD/wahfC58Kw"
            woo_api = WooXPublicAPI(api_key=api_key, base_url="https://api-pub.woo.org")
            
            # interval由 config 決定, 預設 "5m"
            interval = self.config.get('timeframe', '5m')
            
            warmup_df = fetch_recent_kline_woo(
                api=woo_api,
                symbol=self.trading_symbol,
                interval=interval,
                warmup_bars=self.atr_period  # 14
            )
            if not warmup_df.empty:
                # 將 warmup_df 轉為 self.kline_data
                for _, row in warmup_df.iterrows():
                    candle = {
                        "date":   row['date'],   # 這是本地(UTC+8) datetime
                        "open":   row['open'],
                        "high":   row['high'],
                        "low":    row['low'],
                        "close":  row['close'],
                        "volume": row['volume']
                    }
                    self.kline_data.append(candle)
                self.logger.info(f"Warmup loaded {len(warmup_df)} bars for {self.trading_symbol}")
                
                # 建立 df
                self.df = self._kline_data_to_df()
                self.logger.info(f"Initial DF shape: {self.df.shape}")
            else:
                self.logger.warning("Warmup DF is empty => no historical bars fetched.")

        except Exception as e:
            self.logger.error(f"Error fetching warmup bars: {e}")

        self.logger.info("CTA Strategy init complete, no old data loaded.")

    def _kline_data_to_df(self) -> pd.DataFrame:
        """
        將 self.kline_data 轉成 DataFrame(columns=[date, open, high, low, close, volume]),
        依 date 排序
        """
        rows = []
        for cdl in self.kline_data:
            rows.append({
                'date':   cdl['date'],
                'open':   cdl['open'],
                'high':   cdl['high'],
                'low':    cdl['low'],
                'close':  cdl['close'],
                'volume': cdl['volume']
            })
        df_out = pd.DataFrame(rows)
        df_out.sort_values('date', inplace=True)
        df_out.reset_index(drop=True, inplace=True)
        return df_out

    def calculate_tr(self, df: pd.DataFrame) -> pd.Series:
        tr_list = []
        for i in range(len(df)):
            if i == 0:
                tr_val = df['high'].iloc[i] - df['low'].iloc[i]
            else:
                prev_close = df['close'].iloc[i-1]
                hi = df['high'].iloc[i]
                lo = df['low'].iloc[i]
                tr_val = max(hi - lo, abs(hi - prev_close), abs(lo - prev_close))
            tr_list.append(tr_val)
        return pd.Series(tr_list, index=df.index, dtype=float)

    def calculate_atr(self, df: pd.DataFrame, period: int=14) -> pd.Series:
        if df.empty:
            return pd.Series([0]*len(df), index=df.index)
        tr = self.calculate_tr(df)
        atr = tr.rolling(period).mean()
        return atr

    def get_direction(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        up-> if close < (last_high - threshold) => down
        down-> if close > (last_low + threshold) => up
        threshold = threshold_multiplier * df['atr']
        """
        if df.empty:
            df['direction'] = []
            return df

        up_trend = True
        last_high = df['high'].iloc[0]
        last_low  = df['low'].iloc[0]
        directions = []
        for i in range(len(df)):
            threshold = self.threshold_multiplier * df.loc[i, 'atr']
            if up_trend:
                if df.loc[i, 'high'] > last_high:
                    last_high = df.loc[i, 'high']
                elif df.loc[i, 'close'] < (last_high - threshold):
                    up_trend = False
                    last_low = df.loc[i, 'low']
            else:
                if df.loc[i, 'low'] < last_low:
                    last_low = df.loc[i, 'low']
                elif df.loc[i, 'close'] > (last_low + threshold):
                    up_trend = True
                    last_high = df.loc[i, 'high']
            directions.append('up' if up_trend else 'down')
        df['direction'] = directions
        return df

    async def generate_signals_and_publish(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        1) 預設 signal=0
        2) 若 current_position=None => up->down => signal=-2 (開空), down->up => signal=2 (開多)
        3) 若 current_position=LONG => dist = (close - entry_price)
             if dist>=9*atr => signal=9 => 平倉
             if dist<=-3*atr => signal=-3 => 平倉
             if direction翻轉 => 先平多 => 再開空 => signal=-2
        4) SHORT => dist=(entry_price - close), 同理
        """
        if df.empty:
            return df

        # 若 df 裏沒有 'signal' 欄位 => 建立. 
        if 'signal' not in df.columns:
            df['signal'] = 0
        else:
            df['signal'] = df['signal'].fillna(0)

        i = len(df) - 1
        prev_dir = df.loc[i-1, 'direction'] if i>=1 else None
        curr_dir = df.loc[i, 'direction']

        current_close = df.loc[i, 'close']
        current_atr   = df.loc[i, 'atr'] if 'atr' in df.columns else 0
        signal_val    = 0

        if self.current_position is None:
            # 沒倉 => 方向翻轉 => 開倉
            if prev_dir=='up' and curr_dir=='down':
                signal_val = -2  # 開空
                # publish open short
                ts_ms = int(df.loc[i, 'date'].timestamp()*1000)
                open_short = SignalData(
                    timestamp=ts_ms,
                    action=OrderAction.OPEN,
                    position_side=PositionSide.SHORT,
                    order_type=OrderType.MARKET,
                    symbol=self.trading_symbol,
                    quantity=self.position_size
                )
                await self.publish_signal(open_short)
                self.current_position = PositionSide.SHORT
                self.entry_price = current_close

            elif prev_dir=='down' and curr_dir=='up':
                signal_val = 2   # 開多
                ts_ms = int(df.loc[i, 'date'].timestamp()*1000)
                open_long = SignalData(
                    timestamp=ts_ms,
                    action=OrderAction.OPEN,
                    position_side=PositionSide.LONG,
                    order_type=OrderType.MARKET,
                    symbol=self.trading_symbol,
                    quantity=self.position_size
                )
                await self.publish_signal(open_long)
                self.current_position = PositionSide.LONG
                self.entry_price = current_close

        else:
            # 有倉 => 檢查停利停損
            if self.current_position == PositionSide.LONG:
                dist = current_close - (self.entry_price or 0)
                # take profit
                if dist >= self.take_profit_atr * current_atr:
                    signal_val = 9
                    await self.close_position(PositionSide.LONG, reason="TP by 9*ATR")
                # stop loss
                elif dist <= -self.stop_loss_atr * current_atr:
                    signal_val = -3
                    await self.close_position(PositionSide.LONG, reason="SL by 3*ATR")
                else:
                    # direction翻轉 => 先平多 => 開空
                    if prev_dir=='up' and curr_dir=='down':
                        signal_val = -2
                        await self.close_position(PositionSide.LONG, reason="direction up->down")
                        ts_ms = int(df.loc[i, 'date'].timestamp()*1000)
                        open_short = SignalData(
                            timestamp=ts_ms,
                            action=OrderAction.OPEN,
                            position_side=PositionSide.SHORT,
                            order_type=OrderType.MARKET,
                            symbol=self.trading_symbol,
                            quantity=self.position_size
                        )
                        await self.publish_signal(open_short)
                        self.current_position = PositionSide.SHORT
                        self.entry_price = current_close

            elif self.current_position == PositionSide.SHORT:
                dist = (self.entry_price or 0) - current_close
                # take profit
                if dist >= self.take_profit_atr * current_atr:
                    signal_val = 9
                    await self.close_position(PositionSide.SHORT, reason="TP by 9*ATR")
                # stop loss
                elif dist <= -self.stop_loss_atr * current_atr:
                    signal_val = -3
                    await self.close_position(PositionSide.SHORT, reason="SL by 3*ATR")
                else:
                    # direction翻轉 => 先平空 => 開多
                    if prev_dir=='down' and curr_dir=='up':
                        signal_val = 2
                        await self.close_position(PositionSide.SHORT, reason="direction down->up")
                        ts_ms = int(df.loc[i, 'date'].timestamp()*1000)
                        open_long = SignalData(
                            timestamp=ts_ms,
                            action=OrderAction.OPEN,
                            position_side=PositionSide.LONG,
                            order_type=OrderType.MARKET,
                            symbol=self.trading_symbol,
                            quantity=self.position_size
                        )
                        await self.publish_signal(open_long)
                        self.current_position = PositionSide.LONG
                        self.entry_price = current_close

        df.loc[i, 'signal'] = signal_val
        return df

    async def close_position(self, pos_side: PositionSide, reason: str=""):
        if self.current_position == pos_side:
            ts_ms = int(time.time()*1000)
            close_signal = SignalData(
                timestamp=ts_ms,
                action=OrderAction.CLOSE,
                position_side=pos_side,
                order_type=OrderType.MARKET,
                symbol=self.trading_symbol,
                quantity=self.position_size,
                reduce_only=True
            )
            await self.publish_signal(close_signal)
            self.logger.info(f"[CTA] Close {pos_side.value} => {reason}, entry_price={self.entry_price}")
            self.current_position = None
            self.entry_price = None

    def rebuild_df(self):
        """
        重新由 self.kline_data -> df, 計算 ATR + direction
        """
        self.df = self._kline_data_to_df()
        if not self.df.empty:
            self.df['atr'] = self.calculate_atr(self.df, self.atr_period)
            self.df = self.get_direction(self.df)
            if 'signal' not in self.df.columns:
                self.df['signal'] = 0
            else:
                self.df['signal'] = self.df['signal'].fillna(0)

    async def execute(self, channel: str, data: dict, redis_client: aioredis.Redis) -> None:
        """
        即時階段: WebSocket => parse => append => rebuild => generate_signals => pickled => Redis
        """
        try:
            self.redis_client = redis_client

            # 只處理 kline
            if "kline" not in channel:
                return

            self.logger.info(f"execute => channel={channel}")

            if isinstance(data, str):
                kline_data = json.loads(data)
            else:
                kline_data = data

            cdata = kline_data.get('data', {}).get('kline_data', {})
            if not cdata:
                return

            new_start = cdata.get('startTime')
            if not new_start:
                return

            if self.last_update_time and new_start <= self.last_update_time:
                return
            self.last_update_time = new_start

            # candle
            dt_utc = pd.to_datetime(new_start, unit='ms', utc=True)
            dt_local = dt_utc.tz_convert(self.local_tz)

            new_candle = {
                "date":   dt_local,
                "open":   float(cdata.get('open', 0)),
                "high":   float(cdata.get('high', 0)),
                "low":    float(cdata.get('low', 0)),
                "close":  float(cdata.get('close', 0)),
                "volume": float(cdata.get('volume', 0))
            }
            self.kline_data.append(new_candle)

            self.rebuild_df()
            if not self.df.empty:
                self.df = await self.generate_signals_and_publish(self.df)

                # pickled => redis
                buf = io.BytesIO()
                self.df.to_pickle(buf)
                buf.seek(0)
                await self.redis_client.set('strategy_df', buf.read())

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