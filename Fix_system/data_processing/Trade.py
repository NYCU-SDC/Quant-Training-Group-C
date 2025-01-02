import time
from datetime import datetime

class TradeData:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.last_trade_id = None
        self.last_trade_price = None
        self.last_trade_time = None
    
    def format_timestamp(self, ts: int) -> str:
        if ts:
            return datetime.fromtimestamp(ts/1000).strftime('%Y-%m-%d %H:%M:%S.%f')
        return 'N/A'
    
    def process_trade_data(self, message_data: dict) -> dict:
        try:
            ts = message_data.get('ts')
            data = message_data.get('data', {})

            # validate the keys
            required_fields = ['symbol', 'price', 'size', 'side', 'source']
            if not all(field in data for field in required_fields):
                raise ValueError("Missing required fields in trade data")
            
            # check the symbol
            if data['symbol'] != self.symbol:
                raise ValueError(f"Symbol mismatch: expected {self.symbol}, got {data['symbol']}")

            # update the trade messages
            self.last_trade_price = float(data['price'])
            self.last_trade_time = ts

            processed_data = {
                "message_time": self.format_timestamp(ts),
                "current_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
                "trade_data": {
                    "symbol": data['symbol'],
                    "price": float(data['price']),
                    "size": float(data['size']),
                    "side": data['side'],         # BUY or SELL
                    "source": data['source']      # trade source
                },
                "message_timestamp": ts
            }
            return processed_data
        
        except Exception as e:
            print(f"Error processing trade data: {e}")
            # return error messages
            return {
                "message_time": self.format_timestamp(ts) if ts else 'N/A',
                "current_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
                "error": str(e),
                "trade_data": {
                    "symbol": self.symbol,
                    "status": "error"
                }
            }
        
    def get_last_trade(self) -> dict:
        return {
            "symbol": self.symbol,
            "last_price": self.last_trade_price,
            "last_time": self.format_timestamp(self.last_trade_time) if self.last_trade_time else 'N/A'
        }