import pandas as pd
import matplotlib.pyplot as plt
from backtest_PT_strategy import BacktestPTStrategy
from order_executor import OrderExecutor
from pnl import plot_pnl


if __name__ == "__main__":
    strategy = BacktestPTStrategy()
    strategy.run_backtest('Preprocess/BTC_kline.csv', 'Preprocess/ETH_kline.csv', 'backtest_results.csv')
    executor = OrderExecutor('backtest_results.csv', 'orders.csv', 'Preprocess/BTC_trades.csv')
    executor.run_backtest()
    plot_pnl('orders.csv')
