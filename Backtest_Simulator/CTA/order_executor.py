import pandas as pd
import logging
from tqdm import tqdm  # 引入進度條模組
from collections import deque


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('OrderExecutor')


class OrderExecutor:
    def __init__(self, strategy_file, output_file, trades_file):
        """Initialize order executor for backtesting"""
        self.strategy_file = strategy_file
        self.output_file = output_file

        # 讀取資料並提前過濾交易資料
        self.df = pd.read_csv(strategy_file)
        self.df['timestamp'] = pd.to_datetime(self.df['timestamp']).astype('int64') // 10**6  # 轉為毫秒數
        trades_df = pd.read_csv(trades_file)
        trades_df['time'] = pd.to_datetime(trades_df['time'], unit='ms').astype('int64') // 10**6

        # 過濾交易資料，僅保留可能需要處理的時間範圍
        min_time = self.df['timestamp'].min()
        filtered_trades = trades_df[(trades_df['time'] >= min_time) &
                                    (trades_df['isBestMatch'] == True) &
                                    (trades_df['symbol'] == 'SPOT_BTC_USDT')]

        # 排序並轉換為 deque 加速操作
        filtered_trades.sort_values('time', inplace=True)
        self.trades_deque = deque(filtered_trades.to_dict('records'))

        # 其他變數初始化
        self.current_position = None
        self.position_size = 0.0
        self.entry_price = None
        self.orders = []
        self.fee_rate = 0.0000  # 0.04% fee
        logger.info("OrderExecutorBacktest initialized")

    def get_trade_price(self, timestamp, is_buy):
        """線性搜尋取得最接近的交易價格，並刪除無效資料"""
        trade_price = None
        while len(self.trades_deque) > 0:
            trade = self.trades_deque[0]
            if trade['time'] < timestamp:
                self.trades_deque.popleft()  # 移除舊資料
            elif trade['isBuyerMaker'] == is_buy:
                trade_price = trade['price']
                break
            else:
                break
        return trade_price

    def check_exit_conditions(self, current_price, current_atr):
        """檢查是否符合平倉條件"""
        if not self.current_position or not self.entry_price:
            return None

        if self.current_position == 'LONG':
            take_profit = self.entry_price + (current_atr * 9)
            stop_loss = self.entry_price - (current_atr * 3)
            if current_price >= take_profit:
                return 'Take Profit'
            elif current_price <= stop_loss:
                return 'Stop Loss'
        elif self.current_position == 'SHORT':
            take_profit = self.entry_price - (current_atr * 9)
            stop_loss = self.entry_price + (current_atr * 3)
            if current_price <= take_profit:
                return 'Take Profit'
            elif current_price >= stop_loss:
                return 'Stop Loss'
        return None

    def process_signal(self, timestamp, signal, price, atr):
        """處理交易訊號"""
        quantity = 0.0001
        profit_or_loss = 0
        turnover = quantity * price
        fee = turnover * self.fee_rate
        gross_pnl = 0.0
        long_gross_pnl = 0.0
        short_gross_pnl = 0.0
        long_position_usd = 0.0
        short_position_usd = 0.0
        long_turnover = 0.0
        short_turnover = 0.0

        # 判斷是買或賣單
        is_buy = signal == 1
        trade_price = self.get_trade_price(timestamp, is_buy)
        taipei_time = pd.to_datetime(timestamp, unit='ms') + pd.Timedelta(hours=8)
        if trade_price is not None:
            price = trade_price

        # 建立持倉
        if self.current_position is None:
            if signal == 1:  # Buy signal
                self.current_position = 'LONG'
                self.position_size = quantity
                self.entry_price = price
                long_position_usd = turnover
                long_turnover = turnover
                self.orders.append([taipei_time, 'BUY', quantity, price, 'LONG', 'ENTER', profit_or_loss, atr, gross_pnl, fee, turnover, long_gross_pnl, long_position_usd, long_turnover, short_gross_pnl, short_position_usd, short_turnover])
            elif signal == -1:  # Sell signal
                self.current_position = 'SHORT'
                self.position_size = quantity
                self.entry_price = price
                short_position_usd = -turnover
                short_turnover = turnover
                self.orders.append([taipei_time, 'SELL', quantity, price, 'SHORT', 'ENTER', profit_or_loss, atr, gross_pnl, fee, turnover, long_gross_pnl, long_position_usd, long_turnover, short_gross_pnl, short_position_usd, short_turnover])
        else:
            # 平倉條件
            exit_reason = self.check_exit_conditions(price, atr)
            if exit_reason:
                if self.current_position == 'LONG':
                    gross_pnl = (price - self.entry_price) * self.position_size
                    profit_or_loss = gross_pnl - fee
                    long_gross_pnl = gross_pnl
                elif self.current_position == 'SHORT':
                    gross_pnl = (self.entry_price - price) * self.position_size
                    profit_or_loss = gross_pnl - fee
                    short_gross_pnl = gross_pnl

                self.orders.append([taipei_time, 'SELL' if self.current_position == 'LONG' else 'BUY',
                                    self.position_size, price, self.current_position, exit_reason,
                                    profit_or_loss, atr, gross_pnl, fee, turnover, long_gross_pnl, long_position_usd, long_turnover, short_gross_pnl, short_position_usd, short_turnover])

                self.current_position = None
                self.entry_price = None
                self.position_size = 0.0

    def run_backtest(self):
        """執行回測"""
        logger.info("Starting backtest")
        for _, row in tqdm(self.df.iterrows(), total=len(self.df), desc="Processing kline"):
            self.process_signal(row['timestamp'], row['signal'], row['Close'], row['atr'])
        logger.info("Backtest completed")
        self.save_orders()

    def save_orders(self):
        """儲存交易紀錄"""
        orders_df = pd.DataFrame(self.orders, columns=['timestamp', 'side', 'quantity', 'price', 'position', 'reason', 'profit_or_loss', 'atr', 'gross_pnl', 'fee', 'turnover', 'long_gross_pnl', 'long_position_usd', 'long_turnover', 'short_gross_pnl', 'short_position_usd', 'short_turnover'])
        orders_df.to_csv(self.output_file, index=False)
        logger.info(f"Orders saved to {self.output_file}")


if __name__ == "__main__":
    executor = OrderExecutor('backtest_results.csv', 'orders.csv', 'Preprocess/trades.csv')
    executor.run_backtest()
