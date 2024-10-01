import requests

class WooXStagingAPI:
    # how to handle n companies
    def __init__(self, base_url='https://api.staging.woox.io'):
        self.base_url = base_url

    def make_request(self, endpoint, params={}):
        response = requests.get(self.base_url + endpoint, params=params)
        response.raise_for_status()
        return response.json()

    # https://docs.woox.io/#orderbook-snapshot-public
    def get_orderbook(self, symbol, max_level=100):
        endpoint = f'/v1/public/orderbook/{symbol}'
        params = {
            'max_level': max_level,
        }
        return self.make_request(endpoint, params)
        # pass

    # https://docs.woo.org/#market-trades-public
    def get_trades(self, symbol, limit=100):
        endpoint = f'/v1/public/market_trades'
        params = {
            'symbol': symbol,
            'limit': limit,
        }
        return self.make_request(endpoint, params)
        # pass

    # https://docs.woo.org/#kline-public
    def get_kline(self, symbol, interval="1m", limit=100):
        endpoint = f'/v1/public/kline'
        params = {
            'symbol': symbol,
            "type": interval,
            'limit': limit,
        }
        return self.make_request(endpoint, params)


if __name__ == "__main__":
    woox_api = WooXStagingAPI()

    symbol = 'SPOT_BTC_USDT'
    interval = '1m'
    
    # Process and display the data
    orderbook_data = woox_api.get_orderbook(symbol)
    print("Orderbook:")
    print(orderbook_data)

    trade_data = woox_api.get_trades(symbol)
    print("\nTrades:")
    print(trade_data)

    kline_data = woox_api.get_kline(symbol, interval)
    print("\nKline (Candlestick) data:")
    print(kline_data)