import pandas as pd
import numpy as np
import logging


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('PairTradingStrategy')


class BacktestPTStrategy:
    def __init__(self):
        self.df = pd.DataFrame()
        logger.info("Pair Trading Strategy Initialized")
        self.T = 400  # 設定觀察窗口大小
        self.threshold = 2  # 使用標準差作為門檻

    def load_data(self, file_path):
        """Load data from CSV file"""
        try:
            df = pd.read_csv(file_path)
            df['timestamp'] = pd.to_datetime(df['Open time'], unit='ms')
            df = df[['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']]
            df[['Open', 'High', 'Low', 'Close', 'Volume']] = df[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)
            df.sort_values('timestamp', inplace=True)
            df.reset_index(drop=True, inplace=True)
            return df
        except Exception as e:
            logger.error(f"Error loading data: {str(e)}")
            return pd.DataFrame()

    def calculate_price_difference(self, df1, df2):
        """計算兩個資產之間的價格差異"""
        df = pd.DataFrame()
        df['timestamp'] = df1['timestamp']
        df['Open'] = df1['Open']
        df['High'] = df1['High']
        df['Low'] = df1['Low']
        df['Close'] = df1['Close']
        df['diff'] = df1['Close'] - df2['Close']
        return df

    def calculate_statistics(self, df):
        """計算期望值與變異數"""
        df['mean_diff'] = df['diff'].rolling(window=self.T).mean()
        # df['mean_diff'] = df['diff'].ewm(span=3, adjust=False).mean()
        df['var_diff'] = df['diff'].rolling(window=self.T).var()
        df['std_diff'] = np.sqrt(df['var_diff'])
        return df

    def generate_signals(self, df):
        """根據價格差與變異數計算交易訊號"""
        df['signal'] = 0
        df.loc[df['diff'] < (df['mean_diff'] - self.threshold * df['std_diff']), 'signal'] = 1  # Buy
        df.loc[df['diff'] > (df['mean_diff'] + self.threshold * df['std_diff']), 'signal'] = -1  # Sell
        return df

    def run_backtest(self, file1, file2, output_file='backtest_results.csv'):
        """執行配對交易回測"""
        df1 = self.load_data(file1)
        df2 = self.load_data(file2)

        if df1.empty or df2.empty:
            logger.error("No data available for backtesting.")
            return

        df = self.calculate_price_difference(df1, df2)
        df = self.calculate_statistics(df)
        df = self.generate_signals(df)

        logger.info("Backtest completed. Results:")
        print(df[['timestamp', 'diff', 'mean_diff', 'var_diff', 'std_diff', 'signal']].tail(10))
        df.to_csv(output_file, index=False)
        logger.info(f"Data saved to {output_file}")


if __name__ == "__main__":
    strategy = BacktestPTStrategy()
    strategy.run_backtest('Preprocess/BTC_kline.csv', 'Preprocess/ETH_kline.csv', 'backtest_results.csv')
