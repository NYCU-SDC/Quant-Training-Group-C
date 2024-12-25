import json
import asyncio
import pandas as pd
import numpy as np
from collections import deque
from redis import asyncio as aioredis
from strategy_init import Strategy
import datetime
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ExampleStrategy')

class ExampleStrategy(Strategy):
    def __init__(self, signal_channel, max_records=500):
        """
        Initialize strategy
        Args:
            signal_channel: Redis signal channel
            max_records: Maximum number of kline records to maintain
        """
        super().__init__(signal_channel)
        self.kline_data = deque(maxlen=max_records)
        self.df = pd.DataFrame()

        self.atr_period = 14
        self.threshold = 0.05
        self.atr_mode = True
        self.chart_type = 'OHLC'

        self.last_update_time = None
        self.redis_client = None
        logger.info("Strategy initialization completed")

    def create_dataframe(self):
        """Convert kline data to DataFrame with Taipei timezone"""
        if not self.kline_data:
            return pd.DataFrame()
        
        try:
            # Create DataFrame using startTime as timestamp
            df = pd.DataFrame(list(self.kline_data))
            
            # Convert timestamp from milliseconds to datetime and add 8 hours for Taipei time
            df['timestamp'] = pd.to_datetime(df['startTime'], unit='ms') + pd.Timedelta(hours=8)
            
            # Keep and rename required columns
            keep_columns = {
                'timestamp': 'timestamp',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume'
            }
            df = df.rename(columns=keep_columns)[keep_columns.values()].copy()
            
            # Convert price and volume columns to float type
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
            # Sort by timestamp
            df.sort_values('timestamp', inplace=True)
            df.reset_index(drop=True, inplace=True)
            return df
            
        except Exception as e:
            logger.error(f"Error creating DataFrame: {str(e)}")
            return pd.DataFrame()

    def calculate_tr(self, df):
        """Calculate True Range"""
        if len(df) == 0:
            return pd.Series()
        
        tr_list = []
        for i in range(len(df)):
            if i == 0:
                # For the first data point, TR is simply High - Low
                tr = df['high'].iloc[i] - df['low'].iloc[i]
            else:
                # For subsequent points, TR is the greatest of:
                # Current High - Current Low
                # |Current High - Previous Close|
                # |Current Low - Previous Close|
                previous_close = df['close'].iloc[i-1]
                tr = max(
                    df['high'].iloc[i] - df['low'].iloc[i],
                    abs(df['high'].iloc[i] - previous_close),
                    abs(df['low'].iloc[i] - previous_close)
                )
            tr_list.append(tr)
        
        return pd.Series(tr_list, index=df.index)

    def calculate_atr(self, df, period=14):
        """Calculate ATR using Wilder's Smoothing Method with proper handling of initial periods"""
        if len(df) < 1:
            return pd.Series([0] * len(df))
        
        tr_list = self.calculate_tr(df).values.tolist()
        atr_list = []
        
        for i in range(len(tr_list)):
            if i < period:
                # For initial periods, use simple moving average of TR
                atr = np.mean(tr_list[max(0, i-period+1):i+1])
            else:
                # Use Wilder's smoothing
                previous_atr = atr_list[-1]
                atr = (previous_atr * (period - 1) + tr_list[i]) / period
            atr_list.append(atr)
        
        return pd.Series(atr_list, index=df.index)

    def get_direction(self, df):
        """
        Determine trend direction using ATR or fixed threshold
        """
        if len(df) < 1:
            return df

        up_trend = True
        last_high_i = 0
        last_low_i = 0
        last_high = df.iloc[0]['high']
        last_low = df.iloc[0]['low']
        tops = []
        bottoms = []
        directions = []

        for i in range(len(df)):
            # whether use atr mode or not
            threshold = df.iloc[i]['atr'] * 3 if self.atr_mode else self.threshold

            if up_trend:
                if df.iloc[i]['high'] > last_high:
                    last_high_i = i
                    last_high = df.iloc[i]['high']
                elif (not self.atr_mode and (df.iloc[i]['close'] < last_high * (1 - threshold))) or \
                     (self.atr_mode and (df.iloc[i]['close'] < last_high - threshold)):
                    if self.chart_type == 'OHLC':
                        tops.append([i, last_high_i, last_high])
                    if self.chart_type == 'line':
                        tops.append([i, i, df.iloc[i]['high']])
                    up_trend = False
                    last_low_i = i
                    last_low = df.iloc[i]['low']
            else:
                if df.iloc[i]['low'] < last_low:
                    last_low_i = i
                    last_low = df.iloc[i]['low']
                elif (not self.atr_mode and (df.iloc[i]['close'] > last_low * (1 + threshold))) or \
                     (self.atr_mode and (df.iloc[i]['close'] > last_low + threshold)):
                    if self.chart_type == 'OHLC':
                        bottoms.append([i, last_low_i, last_low])
                    if self.chart_type == 'line':
                        bottoms.append([i, i, df.iloc[i]['low']])
                    up_trend = True
                    last_high_i = i
                    last_high = df.iloc[i]['high']

            directions.append('up' if up_trend else 'down')

        df['direction'] = directions
        # store tops and bottoms data 
        df['tops'] = [tops] * len(df)
        df['bottoms'] = [bottoms] * len(df)
        return df

    async def print_dataframe_info(self):
        """Print DataFrame information for testing"""
        print("\n" + "="*50)
        print("DataFrame Structure:")
        print("-"*20)
        print("\nLast 5 records:")
        with pd.option_context('display.max_rows', 5, 'display.max_columns', None):
            print(self.df.tail().to_string())
        
        print("\nDataFrame Info:")
        print("-"*20)
        print(self.df.info())
        
        if len(self.df) > 0:
            latest = self.df.iloc[-1]
            print("\nLatest Data Point:")
            print("-"*20)
            formatted_time = datetime.datetime.fromtimestamp(latest['timestamp'])
            print(f"Time: {formatted_time}")
            print(f"Open: {latest['open']:.2f}")
            print(f"High: {latest['high']:.2f}")
            print(f"Low: {latest['low']:.2f}")
            print(f"Close: {latest['close']:.2f}")
            print(f"Volume: {latest['volume']:.6f}")
            if 'atr' in latest:
                print(f"ATR: {latest['atr']:.2f}")
            if 'direction' in latest:
                print(f"Direction: {latest['direction']}")
        print("="*50 + "\n")
    
    def generate_signal(self, df):
        """
        Generate trading signals based on direction changes.
        
        Args:
            df (pd.DataFrame): DataFrame containing direction column
        
        Returns:
            pd.DataFrame: DataFrame with new signals column
        """
        # Initialize signals column with zeros
        df['signal'] = 0
        
        # Skip signal generation if not enough data
        if len(df) < 2:
            return df
        
        # Compare current direction with previous direction
        for i in range(1, len(df)):
            prev_direction = df['direction'].iloc[i-1]
            curr_direction = df['direction'].iloc[i]
            
            if prev_direction != curr_direction:
                if curr_direction == 'down':
                    df.loc[df.index[i], 'signal'] = -1  # Sell signal
                else:  # curr_direction == 'up'
                    df.loc[df.index[i], 'signal'] = 1   # Buy signal
        
        return df

    async def execute(self, channel, data, redis_client):
        """Process received kline data and generate signals"""
        try:
            self.redis_client = redis_client
            kline_data = json.loads(data) if isinstance(data, str) else data
            current_time = kline_data.get('endTime')
            
            if self.last_update_time and current_time <= self.last_update_time:
                return
            
            self.kline_data.append(kline_data)
            self.last_update_time = current_time
            
            self.df = self.create_dataframe()
            if len(self.df) > 0:
                self.df['atr'] = self.calculate_atr(self.df, self.atr_period)
                self.df = self.get_direction(self.df)
                self.df = self.generate_signal(self.df)
                
                if len(self.df) > 0 and self.df['signal'].iloc[-1] != 0:
                    signal_data = {
                        'timestamp': int(self.df.iloc[-1].timestamp.timestamp() * 1000),  
                        'signal': int(self.df['signal'].iloc[-1]),
                        'price': float(self.df['close'].iloc[-1]),
                        'direction': self.df['direction'].iloc[-1]
                    }
                    await self.publish_signal(signal_data, self.redis_client)
                
                await self.redis_client.set('processed_klines', self.df.to_json())
                
        except Exception as e:
            logger.error(f"Execution error: {str(e)}")

async def main():
    strategy = ExampleStrategy("strategy_signals")
    strategy.threshold = 0.05  # initial threshold
    strategy.atr_mode = True  # change atr mode, if it is True, threshold = 3 atr
    strategy.chart_type = 'line'  # change type

    redis_client = await aioredis.from_url(
        'redis://localhost:6379',
        encoding='utf-8',
        decode_responses=True
    )
    
    try:
        logger.info("Starting to monitor kline data...")
        last_processed_time = None
        
        while True:
            # Get latest kline data from Redis
            latest_kline = await redis_client.get('latest_kline')
            if latest_kline:
                try:
                    kline_data = json.loads(latest_kline)
                    current_time = kline_data.get('endTime')
                    
                    # Process only new data
                    if current_time != last_processed_time:
                        await strategy.execute('latest_kline', kline_data, redis_client)
                        last_processed_time = current_time
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
            
            await asyncio.sleep(0.1)
            
    except asyncio.CancelledError:
        logger.info("Shutting down strategy...")
    except Exception as e:
        logger.error(f"Runtime error: {str(e)}")
    finally:
        await redis_client.aclose()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program terminated by user")
    except Exception as e:
        logger.error(f"Program error: {str(e)}")