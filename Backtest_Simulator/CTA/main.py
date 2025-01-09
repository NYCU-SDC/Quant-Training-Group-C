import pandas as pd
import matplotlib.pyplot as plt
from backtest_CTA_strategy import BacktestCTAStrategy
from order_executor import OrderExecutor
from pnl import plot_pnl


if __name__ == "__main__":
    strategy = BacktestCTAStrategy()
    strategy.run_backtest('Preprocess/kline.csv', 'backtest_results.csv')
    executor = OrderExecutor('backtest_results.csv', 'orders.csv', 'Preprocess/trades.csv')
    executor.run_backtest()
    plot_pnl('orders.csv')
