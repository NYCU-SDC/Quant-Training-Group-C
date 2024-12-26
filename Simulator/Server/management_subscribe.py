import csv
import os
import time


class SubscribeManager:
    def __init__(self, simulate_speed, start_timestamp, base_timestamp, base_path=None):
        if base_path is None or not os.path.isdir(base_path):
            base_path = os.path.join(os.getcwd(), "Preprocess")
        self.base_path = base_path

        self.simulate_speed = simulate_speed
        self.start_timestamp = start_timestamp
        self.base_timestamp = base_timestamp

    def get_timestamp(self):
        return (time.time() - self.start_timestamp) * self.simulate_speed  + self.base_timestamp

    async def get_bbo(self, params):
        try:
            # 檢查參數完整性
            if 'timestamp' not in params or 'symbol' not in params:
                return {'success': False, 'error': 'Missing required parameters: timestamp or symbol'}

            # 獲取參數
            timestamp = float(params['timestamp'])
            symbol = params['symbol']
            csv_file = os.path.join(self.base_path, "bbo.csv")

            # 檢查檔案是否存在
            if not os.path.exists(csv_file):
                return {'success': False, 'error': f"File not found: {csv_file}"}

            # 打開並讀取 CSV 文件
            with open(csv_file, 'r') as file:
                reader = csv.DictReader(file)

                # 初始化變量
                closest_row = None
                closest_time_diff = float('inf')

                for row in reader:
                    try:
                        # 嘗試解析時間戳
                        row_timestamp = float(row['timestamp'])

                        # 過濾符合條件的數據
                        if row['symbol'] == symbol and row_timestamp >= timestamp:
                            time_diff = row_timestamp - timestamp
                            if time_diff < closest_time_diff:
                                closest_time_diff = time_diff
                                closest_row = row
                    except (ValueError, KeyError) as e:
                        continue  # 忽略無效行

                # 返回匹配的行或錯誤訊息
                if closest_row:
                    return {
                        'success': True,
                        'timestamp': closest_row['timestamp'],
                        'symbol': symbol,
                        'bid': closest_row['bid'],
                        'bidSize': closest_row['bidSize'],
                        'ask': closest_row['ask'],
                        'askSize': closest_row['askSize']
                    }
                else:
                    return {
                        'success': False, 
                        'message': "No matching timestamp found."
                    }

        except Exception as e:
            # 捕捉所有異常
            return {'success': False, 'error': str(e)}

    async def get_kline(self, params):
        try:
            # 檢查參數完整性
            if 'timestamp' not in params or 'symbol' not in params:
                return {'success': False, 'error': 'Missing required parameters: timestamp or symbol'}

            # 獲取參數
            timestamp = float(params['timestamp'])
            symbol = params['symbol']
            csv_file = os.path.join(self.base_path, "kline.csv")
        
            # 檢查檔案是否存在
            if not os.path.exists(csv_file):
                return {'success': False, 'error': f"File not found: {csv_file}"}

            # 打開並讀取 CSV 文件
            with open(csv_file, 'r') as file:
                reader = csv.DictReader(file)

                # 初始化變量
                closest_row = None
                closest_time_diff = float('inf')

                for row in reader:
                    try:
                        # 嘗試解析時間戳
                        row_timestamp = float(row['startTime'])

                        # 過濾符合條件的數據
                        if row['symbol'] == symbol and row_timestamp >= timestamp:
                            time_diff = row_timestamp - timestamp
                            if time_diff < closest_time_diff:
                                closest_time_diff = time_diff
                                closest_row = row
                    except (ValueError, KeyError) as e:
                        continue  # 忽略無效行

                if closest_row:
                    return {
                        'success': True,
                        'symbol': closest_row['symbol'],
                        'open': closest_row['open'],
                        'close': closest_row['close'],
                        'low': closest_row['low'],
                        'high': closest_row['high'],
                        'volume': closest_row['volume'],
                        'amount': closest_row['amount'],
                        'type': closest_row['type'],
                        'startTime': closest_row['startTime'],
                        'endTime': closest_row['endTime'],
                    }
                else:
                    return {
                        'success': False, 
                        'message': "No matching timestamp found."
                    }

        except Exception as e:
            # 捕捉所有異常
            return {'success': False, 'error': str(e)}
    
    def get_market_trades(self, params):
        timestamp = self.get_timestamp()
        symbol = params.get('symbol')

        csv_file = os.path.join(self.base_path, "trades.csv")
        # print(f"\nReading csv_file: {csv_file}\n")
        # print(f"\nBase path is: {self.base_path}\n")

        try:
            with open(csv_file, 'r') as file:
                reader = csv.DictReader(file)

                closest_row = None
                closest_time_diff = float('inf')

                for row in reader:
                    row_timestamp = float(row['timestamp'])
                    if row['symbol'] == symbol and row_timestamp >= timestamp:
                        time_diff = row_timestamp - timestamp
                        if time_diff < closest_time_diff:
                            closest_time_diff = time_diff
                            closest_row = row

                if closest_row:
                    return {
                        'success': True,
                        'timestamp': closest_row['timestamp'],
                        'symbol': closest_row['symbol'],
                        'price': closest_row['price'],
                        'size': closest_row['size'],
                        'side': closest_row['side'],
                        'source': closest_row['source']
                    }
                else:
                    return {
                        'success': False,
                        'message': "No matching timestamp found."
                    }

        except FileNotFoundError:
            return {
                'error': f"File not found: {csv_file}"
            }
        except Exception as e:
            return {
                'error': f"An error occurred: {e}"
            }
        
    async def get_orderbook(self, params):
        try:
            # 檢查參數完整性
            if 'timestamp' not in params or 'symbol' not in params:
                return {'success': False, 'error': 'Missing required parameters: timestamp or symbol'}
            
            # 獲取參數
            timestamp = float(params['timestamp'])
            symbol = params['symbol']
            csv_file = os.path.join(self.base_path, "orderbook.csv")

            # 檢查檔案是否存在
            if not os.path.exists(csv_file):
                return {'success': False, 'error': f"File not found: {csv_file}"}

            # 打開並讀取 CSV 文件
            with open(csv_file, 'r') as file:
                reader = csv.DictReader(file)

                closest_row = None
                closest_time_diff = float('inf')

                for row in reader:
                    try:
                        # 嘗試解析時間戳
                        row_timestamp = float(row['timestamp'])

                        # 過濾符合條件的數據
                        if row['symbol'] == symbol and row_timestamp >= timestamp:
                            time_diff = row_timestamp - timestamp
                            if time_diff < closest_time_diff:
                                closest_time_diff = time_diff
                                closest_row = row
                    except (ValueError, KeyError) as e:
                        continue  # 忽略無效行

                if closest_row:
                    return {
                        'success': True,
                        'timestamp': closest_row['timestamp'],
                        'asks': closest_row['asks'],
                        'bids': closest_row['bids'],
                    }
                else:
                    return {
                        'success': False, 
                        'message': "No matching timestamp found."
                    }

        except Exception as e:
                # 捕捉所有異常
                return {'success': False, 'error': str(e)}


if __name__ == "__main__":
    data_manager = SubscribeManager()

    # Test get_bbo function
    params = {
        'timestamp': 1733876519707,
        'symbol': 'SPOT_ETH_USDT'
    }
    result = data_manager.get_bbo(params)
    print(result)
