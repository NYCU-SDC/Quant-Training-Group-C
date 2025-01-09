import json
import pandas as pd
import logging
import time


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('OrderExecutorBacktest')


class OrderExecutorBacktest:
    def __init__(self, strategy_file, output_file):
        """Initialize order executor for backtesting"""
        self.strategy_file = strategy_file
        self.output_file = output_file
        self.df = pd.read_csv(strategy_file)
        self.current_position = None
        self.position_size = 0.0
        self.entry_price = None
        self.orders = []
        self.fee_rate = 0  # 0.04% fee
        logger.info("OrderExecutorBacktest initialized")

    def check_exit_conditions(self, current_price, current_atr):
        """Check if position closing conditions are met"""
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
        """Process trading signals and execute orders"""
        quantity = 0.0001
        profit_or_loss = 0  # Initialize profit or loss
        turnover = quantity * price
        fee = turnover * self.fee_rate
        gross_pnl = 0.0
        long_gross_pnl = 0.0
        short_gross_pnl = 0.0
        long_position_usd = 0.0
        short_position_usd = 0.0
        long_turnover = 0.0
        short_turnover = 0.0

        if self.current_position is None:
            if signal == 1:  # Buy signal
                self.current_position = 'LONG'
                self.position_size = quantity
                self.entry_price = price
                long_position_usd = turnover
                long_turnover = turnover
                self.orders.append([timestamp, 'BUY', quantity, price, 'LONG', 'ENTER', profit_or_loss, atr, gross_pnl, fee, turnover, price, fee, long_gross_pnl, long_position_usd, long_turnover, short_gross_pnl, short_position_usd, short_turnover])
            elif signal == -1:  # Sell signal
                self.current_position = 'SHORT'
                self.position_size = quantity
                self.entry_price = price
                short_position_usd = -turnover
                short_turnover = turnover
                self.orders.append([timestamp, 'SELL', quantity, price, 'SHORT', 'ENTER', profit_or_loss, atr, gross_pnl, fee, turnover, price, fee, long_gross_pnl, long_position_usd, long_turnover, short_gross_pnl, short_position_usd, short_turnover])
        else:
            exit_reason = self.check_exit_conditions(price, atr)
            if exit_reason:
                if self.current_position == 'LONG':
                    gross_pnl = (price - self.entry_price) * self.position_size
                    fee = (self.entry_price + price) * self.position_size * self.fee_rate
                    profit_or_loss = gross_pnl - fee
                    long_gross_pnl = gross_pnl
                    long_position_usd = turnover
                    long_turnover = turnover
                    self.orders.append([timestamp, 'SELL', self.position_size, price, 'LONG', exit_reason, profit_or_loss, atr, gross_pnl, fee, turnover, price, fee, long_gross_pnl, long_position_usd, long_turnover, short_gross_pnl, short_position_usd, short_turnover])
                elif self.current_position == 'SHORT':
                    gross_pnl = (self.entry_price - price) * self.position_size
                    fee = (self.entry_price + price) * self.position_size * self.fee_rate
                    profit_or_loss = gross_pnl - fee
                    short_gross_pnl = gross_pnl
                    short_position_usd = -turnover
                    short_turnover = turnover
                    self.orders.append([timestamp, 'BUY', self.position_size, price, 'SHORT', exit_reason, profit_or_loss, atr, gross_pnl, fee, turnover, price, fee, long_gross_pnl, long_position_usd, long_turnover, short_gross_pnl, short_position_usd, short_turnover])
                self.current_position = None
                self.entry_price = None
                self.position_size = 0.0

    def run_backtest(self):
        """Run the backtest simulation"""
        logger.info("Starting backtest")
        for index, row in self.df.iterrows():
            self.process_signal(row['timestamp'], row['signal'], row['Close'], row['atr'])
        logger.info("Backtest completed")
        self.save_orders()

    def save_orders(self):
        """Save executed orders to CSV"""
        orders_df = pd.DataFrame(self.orders, columns=['timestamp', 'side', 'quantity', 'price', 'position', 'reason', 'profit_or_loss', 'atr', 'gross_pnl', 'fee', 'turnover', 'benchmark_price', 'maker_fee', 'long_gross_pnl', 'long_position_usd', 'long_turnover', 'short_gross_pnl', 'short_position_usd', 'short_turnover'])
        orders_df.to_csv(self.output_file, index=False)
        logger.info(f"Orders saved to {self.output_file}")


if __name__ == "__main__":
    executor = OrderExecutorBacktest('backtest_results.csv', 'orders.csv')
    executor.run_backtest()