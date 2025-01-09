import pandas as pd
from collections import deque
import logging


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('BacktestStrategy')


class BacktestCTAStrategy:
    def __init__(self, max_records=500):
        """
        Initialize strategy for backtesting
        Args:
            max_records: Maximum number of kline records to maintain
        """
        self.kline_data = deque(maxlen=max_records)
        self.df = pd.DataFrame()

        self.atr_period = 14
        self.threshold = 0.05
        self.atr_mode = True
        self.chart_type = 'OHLC'

        logger.info("Strategy initialization completed")

    def load_data(self, file_path):
        """Load data from CSV file"""
        try:
            df = pd.read_csv(file_path)
            # Filter only SPOT_BTC_USDT
            df = df[df['symbol'] == 'SPOT_BTC_USDT']
            df['timestamp'] = pd.to_datetime(df['Open time'], unit='ms')
            df = df[['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']]
            df[['Open', 'High', 'Low', 'Close', 'Volume']] = df[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)
            df.sort_values('timestamp', inplace=True)
            df.reset_index(drop=True, inplace=True)
            return df
        except Exception as e:
            logger.error(f"Error loading data: {str(e)}")
            return pd.DataFrame()

    def calculate_tr(self, df):
        """Calculate True Range"""
        tr_list = []
        for i in range(len(df)):
            if i == 0:
                tr = df['High'].iloc[i] - df['Low'].iloc[i]
            else:
                prev_close = df['Close'].iloc[i-1]
                tr = max(df['High'].iloc[i] - df['Low'].iloc[i],
                         abs(df['High'].iloc[i] - prev_close),
                         abs(df['Low'].iloc[i] - prev_close))
            tr_list.append(tr)
        return pd.Series(tr_list, index=df.index)

    def calculate_atr(self, df, period=14):
        """Calculate ATR"""
        tr_list = self.calculate_tr(df)
        atr = tr_list.rolling(window=period).mean()
        return atr

    def get_direction(self, df):
        """Determine trend direction"""
        up_trend = True
        last_high = df.iloc[0]['High']
        last_low = df.iloc[0]['Low']
        directions = []

        for i in range(len(df)):
            threshold = df['atr'].iloc[i] * 3 if self.atr_mode else self.threshold
            if up_trend:
                if df['Close'].iloc[i] < last_high - threshold:
                    up_trend = False
                    last_low = df['Low'].iloc[i]
                else:
                    last_high = max(last_high, df['High'].iloc[i])
            else:
                if df['Close'].iloc[i] > last_low + threshold:
                    up_trend = True
                    last_high = df['High'].iloc[i]
                else:
                    last_low = min(last_low, df['Low'].iloc[i])

            directions.append('up' if up_trend else 'down')

        df['direction'] = directions
        return df

    def generate_signal(self, df):
        """Generate trading signals based on direction changes"""
        df['signal'] = 0
        for i in range(1, len(df)):
            if df['direction'].iloc[i] != df['direction'].iloc[i-1]:
                df.loc[df.index[i], 'signal'] = 1 if df['direction'].iloc[i] == 'up' else -1
        return df

    def save_to_csv(self, file_path):
        """Save DataFrame to CSV with all calculated indicators"""
        try:
            self.df.to_csv(file_path, index=False)
            logger.info(f"Indicators saved to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save indicators: {str(e)}")

    def run_backtest(self, file_path, output_file):
        """Run backtest using data from CSV file"""
        self.df = self.load_data(file_path)
        if self.df.empty:
            logger.error("No data available for backtesting.")
            return

        self.df['atr'] = self.calculate_atr(self.df, self.atr_period)
        self.df = self.get_direction(self.df)
        self.df = self.generate_signal(self.df)

        logger.info("Backtest completed. Results:")
        print(self.df[['timestamp', 'Close', 'atr', 'direction', 'signal']].tail(10))
        self.save_to_csv(output_file)


if __name__ == "__main__":
    strategy = BacktestCTAStrategy()
    strategy.run_backtest('Preprocess/kline.csv', 'backtest_results.csv')
