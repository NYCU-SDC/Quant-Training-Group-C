import pandas as pd
import matplotlib.pyplot as plt
import requests
import datetime
from pymongo import MongoClient 
class WooXAnalysis:
    def __init__(self):
        self.api_base_url = "https://api.woo.org"
        self.kline_endpoint = "/v1/public/kline"
        self.mongo_client = MongoClient('localhost', 27017)
        self.db = self.mongo_client['woox_data']
        self.orderbooks_collection = self.db['orderbooks']
        self.bbo_collection = self.db['bbo'] 

    def fetch_kline_data(self, symbol, type="1h", limit=1000):
        params = {
            "symbol": symbol,
            "type": type,
            "limit": limit
        }
        url = f"{self.api_base_url}{self.kline_endpoint}"
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if data.get("success"):
                kline_data = data.get("rows", [])
                return kline_data
            else:
                print(f"API returned an error for {symbol}: {data}")
                return []
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data for {symbol}: {e}")
            return []

    def get_leading_market(self, symbol):
        bbo_data = self.bbo_collection.find_one({"data.symbol": symbol}, sort=[("received_ts", -1)])
        if bbo_data:
            bid = float(bbo_data['data']['bid'])
            ask = float(bbo_data['data']['ask'])
            spread = ask - bid
            print(f"Market for {symbol}: Bid={bid}, Ask={ask}, Spread={spread}")
            return spread
        return None

    def analyze_kline_data(self, kline_data, symbol, ax1):
        data = []
        for entry in kline_data:
            timestamp = datetime.datetime.fromtimestamp(entry['start_timestamp'] / 1000)
            open_price = float(entry['open'])
            high_price = float(entry['high'])
            low_price = float(entry['low'])
            close_price = float(entry['close'])
            volume = float(entry['volume'])
            data.append([timestamp, open_price, close_price, high_price, low_price, volume])

        df = pd.DataFrame(data, columns=['timestamp', 'open', 'close', 'high', 'low', 'volume'])
        df.set_index('timestamp', inplace=True)

        if df.empty:
            print(f"No data available for {symbol}")
            return None

        df['volatility'] = df['high'] - df['low']
        df['hour'] = df.index.hour

        hourly_volatility = df.groupby('hour')['volatility'].mean()
        hourly_volume = df.groupby('hour')['volume'].sum()

        ax2 = ax1.twinx()
        ax1.bar(hourly_volume.index, hourly_volume.values, color='g', alpha=0.6, label='Volume')
        ax2.plot(hourly_volatility.index, hourly_volatility.values, 'b-', marker='o', label='Volatility')

        ax1.set_xlabel('Hour of Day')
        ax1.set_ylabel('Volume', color='g')
        ax2.set_ylabel('Volatility', color='b')
        ax1.set_title(f'Hourly Volume and Volatility for {symbol}')

        ax1.legend(loc='upper left')
        ax2.legend(loc='upper right')

        highest_volume_hour = hourly_volume.idxmax()
        highest_volatility_hour = hourly_volatility.idxmax()

        leading_market_spread = self.get_leading_market(symbol)
        if leading_market_spread is not None:
            print(f"Market {symbol} is currently leading with a spread of {leading_market_spread}")

        return {
            'symbol': symbol,
            'highest_volume_hour': highest_volume_hour,
            'highest_volume': hourly_volume.max(),
            'highest_volatility_hour': highest_volatility_hour,
            'highest_volatility': hourly_volatility.max(),
            'leading_spread': leading_market_spread
        }

    def run_analysis(self, symbols, type="1h", limit=1000):
        overall_findings = []
        fig, axs = plt.subplots(len(symbols), 1, figsize=(10, 6 * len(symbols)))

        if len(symbols) == 1:
            axs = [axs]

        for idx, symbol in enumerate(symbols):
            print(f"Analyzing data for {symbol}...")
            kline_data = self.fetch_kline_data(symbol, type=type, limit=limit)
            if not kline_data:
                print(f"No K-line data found for {symbol}.")
                continue

            ax1 = axs[idx] if len(symbols) > 1 else axs[0]
            findings = self.analyze_kline_data(kline_data, symbol, ax1)
            if findings:
                overall_findings.append(findings)

        plt.tight_layout()
        plt.show()

        if overall_findings:
            df_findings = pd.DataFrame(overall_findings)
            df_findings.to_csv('market_analysis_findings.csv', index=False)
            print("\nAnalysis Results Saved to 'market_analysis_findings.csv'")
            print(df_findings)

if __name__ == "__main__":
    analysis = WooXAnalysis()

    symbols = [
        'SPOT_WOO_USDT', 'SPOT_BTC_USDT', 'SPOT_ETH_USDT',
        'PERP_BTC_USDT', 'PERP_ETH_USDT', 'PERP_WOO_USDT'
    ]

    analysis.run_analysis(symbols, type="1h", limit=1000)

