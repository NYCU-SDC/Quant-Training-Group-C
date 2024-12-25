import pandas as pd
import requests
import json
import time
from datetime import datetime, timedelta
import numpy as np

########################
# 從您提供的原code開始
########################
class WooXPublicAPI:
    def __init__(self, api_key, base_url='https://api-pub.woo.org'):
        self.api_key = api_key
        self.base_url = base_url
    
    def make_request(self, endpoint, params={}):
        headers = {
            'Authorization': f'Bearer {self.api_key}'
        }
        response = requests.get(self.base_url + endpoint, params=params, headers = headers)
        response.raise_for_status()
        return response.json()
    
    # https://docs.woox.io/?python#kline-historical-data-public
    def get_kline_data(self, symbol, interval, start_time, end_time):
        endpoint = '/v1/hist/kline'
        params = {
            'symbol': symbol,
            'type': interval,
            'start_time': int(start_time.timestamp()*1000),
            'end_time': int(end_time.timestamp()*1000)
        }
        data = self.make_request(endpoint, params)
        if data['success']:
            return pd.DataFrame(
                data['data']['rows'], 
                columns=['open', 'close', 'low', 'high', 'volume', 'amount', 'symbol', 'type', 'start_timestamp', 'end_timestamp']
            )
        return None

def download_historical_data(api, symbols, interval, start_date, end_date):
    for symbol in symbols:
        all_data = []
        current_date = start_date
        while current_date < end_date:
            slice_end = min(current_date + timedelta(days=1), end_date)
            df = api.get_kline_data(symbol, interval, current_date, slice_end)
            if df is not None:
                all_data.append(df)
                print(f"Downloaded data for {symbol} from {current_date} to {slice_end}")
            else:
                print(f"Failed to download data for {symbol} from {current_date} to {slice_end}")
            current_date = slice_end
            time.sleep(1)  # Rate limiting

        if all_data:
            final_df = pd.concat(all_data, ignore_index=True)
            final_df['start_timestamp'] = pd.to_datetime(final_df['start_timestamp'], unit='ms')
            final_df['end_timestamp']   = pd.to_datetime(final_df['end_timestamp'], unit='ms')
            csv_name = f"{symbol}_kline_from_{start_date.date()}_to_{end_date.date()}_data.csv"
            final_df.to_csv(csv_name, index=False)
            print(f"Data for {symbol} has been saved to {csv_name}")
        else:
            print(f"No data was downloaded for {symbol}")
        
        time.sleep(5)

def download_historical_data_chunked(api, symbols, interval, start_date, end_date, chunk_size=30000):
    for symbol in symbols:
        all_data = []
        current_start = start_date
        
        while current_start < end_date:
            chunk_end = min(current_start + timedelta(minutes=5*chunk_size), end_date)
            chunk_data = []
            current_date = current_start
            
            while current_date < chunk_end:
                slice_end = min(current_date + timedelta(days=1), chunk_end)
                df = api.get_kline_data(symbol, interval, current_date, slice_end)
                if df is not None:
                    chunk_data.append(df)
                    print(f"Downloaded data for {symbol} from {current_date} to {slice_end}")
                else:
                    print(f"Failed to download data for {symbol} from {current_date} to {slice_end}")
                current_date = slice_end
                time.sleep(1)  # Rate limiting

            if chunk_data:
                chunk_df = pd.concat(chunk_data, ignore_index=True)
                all_data.append(chunk_df)
                print(f"Completed chunk from {current_start} to {chunk_end}")
            
            current_start = chunk_end
            time.sleep(5)

        if all_data:
            final_df = pd.concat(all_data, ignore_index=True)
            final_df['start_timestamp'] = pd.to_datetime(final_df['start_timestamp'], unit='ms')
            final_df['end_timestamp']   = pd.to_datetime(final_df['end_timestamp'], unit='ms')
            csv_name = f"{symbol}_kline_{interval}_from_{start_date.date()}_to_{end_date.date()}_data.csv"
            final_df.to_csv(csv_name, index=False)
            print(f"Data for {symbol} has been saved to {csv_name}")
        else:
            print(f"No data was downloaded for {symbol}")


########################
# 2. 加入 cta 計算 ATR / direction / signal
########################
def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    if len(df) == 0:
        return pd.Series([])
    
    tr = []
    for i in range(len(df)):
        if i == 0:
            tr_val = df.loc[df.index[i], 'high'] - df.loc[df.index[i], 'low']
        else:
            prev_close = df.loc[df.index[i-1], 'close']
            tr_val = max(
                df.loc[df.index[i], 'high'] - df.loc[df.index[i], 'low'],
                abs(df.loc[df.index[i], 'high'] - prev_close),
                abs(df.loc[df.index[i], 'low'] - prev_close)
            )
        tr.append(tr_val)
    tr_series = pd.Series(tr, index=df.index)
    
    # 這裡簡單用rolling mean
    atr = tr_series.rolling(period).mean()
    return atr

def get_direction(df: pd.DataFrame) -> pd.Series:
    directions = []
    if len(df) == 0:
        return pd.Series([])
    up_trend = True
    last_high = df.loc[df.index[0], 'high']
    last_low  = df.loc[df.index[0], 'low']
    for i in range(len(df)):
        threshold = df.loc[df.index[i], 'atr']  # 用ATR做threshold
        if up_trend:
            if df.loc[df.index[i], 'high'] > last_high:
                last_high = df.loc[df.index[i], 'high']
            elif df.loc[df.index[i], 'close'] < last_high - threshold:
                up_trend = False
                last_low = df.loc[df.index[i], 'low']
        else:
            if df.loc[df.index[i], 'low'] < last_low:
                last_low = df.loc[df.index[i], 'low']
            elif df.loc[df.index[i], 'close'] > last_low + threshold:
                up_trend = True
                last_high = df.loc[df.index[i], 'high']
        directions.append('up' if up_trend else 'down')
    return pd.Series(directions, index=df.index)

def generate_signals(df: pd.DataFrame) -> pd.Series:
    signals = [0]*len(df)
    for i in range(1, len(df)):
        prev_dir = df.loc[df.index[i-1], 'direction']
        curr_dir = df.loc[df.index[i],   'direction']
        if prev_dir == 'up' and curr_dir == 'down':
            signals[i] = -2
        elif prev_dir == 'down' and curr_dir == 'up':
            signals[i] = 2
        else:
            signals[i] = 0
    return pd.Series(signals, index=df.index)

########################
# 3. 主程式: 下載 -> 合併 -> 計算 -> 輸出
########################
if __name__ == '__main__':
    # 1) 下載歷史資料
    api_key = 'sdFgbf5mnyD/wahfC58Kw=='  # 請填你的Token
    woox_api = WooXPublicAPI(api_key)

    symbols = ["PERP_BTC_USDT"]  # 以一個symbol示範
    interval = "5m"
    start_date = datetime(2024, 12, 15)
    end_date   = datetime(2024, 12, 25)

    # 這裡用 chunked 函式為例
    download_historical_data_chunked(woox_api, symbols, interval, start_date, end_date)

    # 2) 假設下載後產出: "PERP_BTC_USDT_kline_5m_from_2024-12-15_to_2024-12-25_data.csv"
    #    我們將讀進此CSV計算ATR/direction/signal
    csv_file = f"PERP_BTC_USDT_kline_{interval}_from_{start_date.date()}_to_{end_date.date()}_data.csv"
    try:
        df = pd.read_csv(csv_file)
    except FileNotFoundError:
        print(f"File {csv_file} not found, please check download step.")
        exit()

    # 3) 下載時的欄位順序: ['open','close','low','high','volume','amount','symbol','type','start_timestamp','end_timestamp']
    #    我們要先把這些轉成我們CTA計算需要的欄位: 'open','high','low','close' (float), 另外時間欄位可用end_timestamp當K線結束
    #    轉成 DataFrame 時區分 bar 順序
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low']  = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    
    # 時間欄位
    df['end_timestamp'] = pd.to_datetime(df['end_timestamp'])
    df.sort_values('end_timestamp', inplace=True)
    df.reset_index(drop=True, inplace=True)

    # 4) 計算 ATR
    df['atr'] = calculate_atr(df)

    # 5) 計算 direction
    df['direction'] = get_direction(df)

    # 6) 產生 signal
    df['signal'] = generate_signals(df)

    # 7) 輸出最終csv
    out_file = f"PERP_BTC_USDT_kline_{interval}_CTA_result.csv"
    df.to_csv(out_file, index=False)
    print(f"Final CTA result saved to {out_file}")
