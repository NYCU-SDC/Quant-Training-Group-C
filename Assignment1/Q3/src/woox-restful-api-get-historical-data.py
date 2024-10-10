import pandas as pd
import os
import requests
import json
import time
from datetime import datetime, timedelta

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
            return pd.DataFrame(data['data']['rows'], 
                                columns=['open', 'close', 'low', 'high', 'volume', 'amount', 'symbol', 'type', 'start_timestamp', 'end_timestamp'])
        return None

# 寫成迴圈，每個chunk設定為3萬筆數據，外loop traverse每個chunk，內loop 處理日期
def download_historical_data_chunked(api, symbols, interval, start_date, end_date, chunk_size=30000):
    for symbol in symbols:
        all_data = []
        current_start = start_date
        
        while current_start < end_date:
            chunk_end = min(current_start + timedelta(minutes=5*chunk_size), end_date)
            chunk_data = []
            current_date = current_start
            
            while current_date < chunk_end:
                end_time = min(current_date + timedelta(days=1), chunk_end)
                df = api.get_kline_data(symbol, interval, current_date, end_time)
                if df is not None:
                    chunk_data.append(df)
                    print(f"Downloaded data for {symbol} from {current_date} to {end_time}")
                else:
                    print(f"Failed to download data for {symbol} from {current_date} to {end_time}")
                current_date = end_time
                time.sleep(1)  # Rate limiting

            if chunk_data:
                chunk_df = pd.concat(chunk_data, ignore_index=True)
                all_data.append(chunk_df)
                print(f"Completed chunk from {current_start} to {chunk_end}")
            
            current_start = chunk_end
            time.sleep(5)  # Pause between chunks

        if all_data:
            final_df = pd.concat(all_data, ignore_index=True)
            final_df['start_timestamp'] = pd.to_datetime(final_df['start_timestamp'], unit='ms')
            final_df['end_timestamp'] = pd.to_datetime(final_df['end_timestamp'], unit='ms')

            output_dir = os.path.join('..', 'output')
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{symbol}_kline_{interval}_from_{start_date.date()}_to_{end_date.date()}_data.csv")

            final_df.to_csv(output_file, index=False)
            print(f"Data for {symbol} has been saved to {output_file}")

        else:
            print(f"No data was downloaded for {symbol}")


if __name__ == '__main__':
    # To make sure that perform this code from src folder
    if not os.path.basename(os.getcwd()) == 'src':
        print("Please perform this code from src folder")
        exit(1)

    api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
    woox_api = WooXPublicAPI(api_key)
    symbols = ["SPOT_BTC_USDT", "SPOT_ETH_USDT"]
    interval = "5m"
    # 一次最多爬下3萬筆歷史資料，抓取不到2023/12/7以前的資料
    start_date = datetime(2023,12,7)
    end_date = datetime.now()
    
    # download_historical_data(woox_api, symbols, interval, start_date, end_date)
    download_historical_data_chunked(woox_api, symbols, interval, start_date, end_date)