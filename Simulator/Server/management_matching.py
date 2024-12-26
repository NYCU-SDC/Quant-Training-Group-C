import csv
import time
import os


class MatchingManager:
    def __init__(self, simulate_speed, start_timestamp, base_timestamp, base_path=None):
        if base_path is None or not os.path.isdir(base_path):
            base_path = os.path.join(os.getcwd(), "Preprocess")
        self.base_path = base_path
        self.count = 0

        self.simulate_speed = simulate_speed
        self.start_timestamp = start_timestamp
        self.base_timestamp = base_timestamp

    def get_timestamp(self):
        return (time.time() - self.start_timestamp) * self.simulate_speed  + self.base_timestamp

    def handle_market_order(self, params):
        timestamp = self.get_timestamp()
        symbol = params.get('symbol')
        csv_file = os.path.join(self.base_path, "bbo.csv")

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
                self.count += 1
                return {
                    'success': True,
                    'timestamp': closest_row['timestamp'],
                    'order_id': closest_row.get('order_id', self.count),
                    'client_order_id': closest_row.get('client_order_id', 0),
                    'order_type': closest_row.get('order_type', 'LIMIT'),
                    'order_price': closest_row['ask'] if params['side'] == 'BUY' else closest_row['bid'],
                    'order_quantity': closest_row.get('order_quantity', None),
                    'order_amount': closest_row.get('order_amount', None),
                    'reduce_only': closest_row.get('reduce_only', False),
                }
            else:
                return {
                    'success': False,
                }
        
if __name__ == "__main__":
    matching_manager = MatchingManager()

    # Test get_bbo function
    params = {
        'order_price' : 0.21,
        'order_quantity': 10,
        'order_type': 'MARKET',
        'side':'BUY',
        'symbol': 'SPOT_BTC_USDT'
    }
    result = matching_manager.handle_market_order(params)
    print(result)