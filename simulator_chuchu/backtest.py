import asyncio
from rich.live import Live
from rich.table import Table
from rich.layout import Layout
from rich.console import Console
from rich import box
import pandas as pd
import numpy as np
import time
from datetime import datetime
import os
import matplotlib.pyplot as plt

class PerformanceAnalyzer:
    def __init__(self, trade_file_path, position_file_path, init_cash_holding, 
                 pnl_interval_minutes=1, metrics_interval_minutes=5):
        self.trade_file_path = trade_file_path
        self.position_file_path = position_file_path
        self.init_cash_holding = init_cash_holding
        self.pnl_interval = pnl_interval_minutes
        self.metrics_interval = metrics_interval_minutes
        self.pnl_time_series = []
        self.latest_metrics = {}
        self.console = Console()
        

    def calculate_metrics(self):
        pnl_df = pd.DataFrame(self.pnl_time_series, columns=['timestamp', 'pnl'])
        pnl_df['timestamp'] = pd.to_datetime(pnl_df['timestamp'], unit='s')
        pnl_df.set_index('timestamp', inplace=True)

        total_return = self.calculate_total_return(pnl_df['pnl'])
        sharpe_ratio = self.calculate_sharpe_ratio(pnl_df['pnl'])
        calmar_ratio = self.calculate_calmar_ratio(pnl_df['pnl'])
        max_drawdown, max_drawdown_duration = self.calculate_drawdown(pnl_df['pnl'])

        return {
            'PnL Series': pnl_df,
            'Total Return': total_return,
            'Sharpe Ratio': sharpe_ratio,
            'Calmar Ratio': calmar_ratio,
            'Max Drawdown': max_drawdown,
            'Max Drawdown Duration (Minute)': max_drawdown_duration,
        }

    def calculate_pnl(self):

        trade_data = pd.read_csv(self.trade_file_path)
        position_data = pd.read_csv(self.position_file_path)

        trade_data['timestamp'] = pd.to_datetime(trade_data['timestamp'], unit='ms')
        position_data['timestamp'] = pd.to_datetime(position_data['timestamp'], unit='ms')

        trade_data.set_index('timestamp', inplace=True)
        position_data.set_index('timestamp', inplace=True)

        pnl_data = []

        for symbol in trade_data['symbol'].unique():
            symbol_trades = trade_data[trade_data['symbol'] == symbol]
            symbol_positions = position_data[position_data['symbol'] == symbol]

            leverage = symbol_trades.iloc[-1]['leverage'] if not symbol_trades.empty else 1

            # Realized PnL
            symbol_trades['single_trade_pnl'] = (
                symbol_trades['executedPrice'] * symbol_trades['executedQuantity'] *
                np.where(symbol_trades['side'] == 'SELL', 1, -1) -
                symbol_trades['fee']
            ) * leverage

            realized_pnl = symbol_trades['single_trade_pnl'].sum() if not symbol_trades.empty else 0

            # Unrealized PnL
            if not symbol_positions.empty:
                avg_long_price = symbol_trades[(symbol_trades['side'] == 'BUY') & (symbol_trades['position_side'] == 'LONG')]['executedPrice'].mean()
                avg_short_price = symbol_trades[(symbol_trades['side'] == 'SELL') & (symbol_trades['position_side'] == 'SHORT')]['executedPrice'].mean()

                unrealized_long_pnl = (
                    (symbol_positions[symbol_positions['position_side'] == 'LONG'].iloc[-1]['mark_price']) *
                    symbol_positions[symbol_positions['position_side'] == 'LONG'].iloc[-1]['holding'] *
                    leverage
                ) if not symbol_positions[symbol_positions['position_side'] == 'LONG'].empty else 0

                unrealized_short_pnl = (
                    (- symbol_positions[symbol_positions['position_side'] == 'SHORT'].iloc[-1]['mark_price']) *
                    symbol_positions[symbol_positions['position_side'] == 'SHORT'].iloc[-1]['holding'] *
                    leverage
                ) if not symbol_positions[symbol_positions['position_side'] == 'SHORT'].empty else 0

                pnl = realized_pnl + unrealized_long_pnl + unrealized_short_pnl
            else:
                pnl = realized_pnl

            pnl_data.append(pnl)

        total_pnl = sum(pnl_data)
        return total_pnl

    def calculate_total_return(self, pnl):
        total_holding_value = self.init_cash_holding
        return pnl.iloc[-1] / total_holding_value if not pnl.empty else 0

    def calculate_sharpe_ratio(self, pnl, risk_free_rate=0.02):
        # Calculate returns based on the PnL series
        total_value = pnl + self.init_cash_holding  
        returns = total_value.pct_change().dropna()
        
        # Calculate annualized return and volatility
        annual_return = returns.mean() * (252 * (60 / self.pnl_interval) * 24)
        annual_volatility = returns.std() * np.sqrt(252 * (60 / self.pnl_interval) * 24)
        
        # Calculate Sharpe ratio
        if annual_volatility > 0:
            sharpe_ratio = (annual_return - risk_free_rate) / annual_volatility
        else:
            sharpe_ratio = 0
        
        return sharpe_ratio

    def calculate_calmar_ratio(self, pnl):
        total_value = pnl + self.init_cash_holding 
        returns = total_value.pct_change().dropna()
        annual_return = returns.mean() * (252 * (60 / self.pnl_interval) * 24)
        max_drawdown = self.calculate_drawdown(pnl)[0]
        calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown < 0 else 0
        return calmar_ratio

    def calculate_drawdown(self, pnl):
        total_value = pnl + self.init_cash_holding  
        cumulative_returns = total_value / total_value.iloc[0]  
        peak = cumulative_returns.expanding(min_periods=1).max()  
        drawdown = (cumulative_returns / peak) - 1  
        max_drawdown = drawdown.min()  

        recovery_points = drawdown[drawdown == 0].index.to_series().diff()  
        max_duration_minutes = recovery_points.max().total_seconds() / 60 if not recovery_points.empty else 0

        return max_drawdown, max_duration_minutes

    async def calculate_pnl_loop(self):
        while True:
            current_pnl = self.calculate_pnl()  
            current_timestamp = int(time.time())
            self.pnl_time_series.append((current_timestamp, current_pnl))
            await asyncio.sleep(self.pnl_interval * 60)

    async def calculate_metrics_loop(self):
        while True:
            self.latest_metrics = self.calculate_metrics()  
            await asyncio.sleep(self.metrics_interval * 60)

    def generate_display(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header"),
            Layout(name="main"),
            Layout(name="pnl")
        )

        # Header
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header_table = Table(box=box.SIMPLE)
        header_table.add_column(f"Performance Monitor - Last Updated: {current_time}")
        layout["header"].update(header_table)

        # Main metrics table
        metrics_table = Table(box=box.SIMPLE)
        metrics_table.add_column("Metric")
        metrics_table.add_column("Value")

        if self.latest_metrics:
            metrics_table.add_row("Total Return", f"{self.latest_metrics['Total Return']:.2%}")
            metrics_table.add_row("Sharpe Ratio", f"{self.latest_metrics['Sharpe Ratio']:.2f}")
            metrics_table.add_row("Calmar Ratio", f"{self.latest_metrics['Calmar Ratio']:.2f}")
            metrics_table.add_row("Max Drawdown", f"{self.latest_metrics['Max Drawdown']:.2%}")
            metrics_table.add_row("Max Drawdown Duration", 
                                f"{self.latest_metrics['Max Drawdown Duration (Minute)']:.0f} min")

        layout["main"].update(metrics_table)

        # Latest PnL
        pnl_table = Table(box=box.SIMPLE)
        pnl_table.add_column("Latest PnL")
        if self.pnl_time_series:
            latest_pnl = self.pnl_time_series[-1][1]
            pnl_table.add_row(f"[{'green' if latest_pnl >= 0 else 'red'}]{latest_pnl:,.2f}")
        layout["pnl"].update(pnl_table)

        return layout

    def save_pnl_history(self):
        """Save PnL time series and plot"""
        # Save PnL data
        os.makedirs('result', exist_ok=True)
        current_date = datetime.now().strftime("%Y%m%d")
        pnl_df = pd.DataFrame(self.pnl_time_series, columns=['timestamp', 'pnl'])
        pnl_df['timestamp'] = pd.to_datetime(pnl_df['timestamp'], unit='s')
        pnl_df.to_csv(f'result/pnl_{current_date}.csv', index=False)
        
        # Plot PnL
        plt.figure(figsize=(12, 6))
        plt.plot(pnl_df['timestamp'], pnl_df['pnl'])
        plt.title('PnL Over Time')
        plt.xlabel('Time')
        plt.ylabel('PnL')
        plt.grid(True)
        plt.savefig(f'result/pnl_{current_date}.png')
        plt.close()

    async def run_monitor(self):
        try:
            pnl_task = asyncio.create_task(self.calculate_pnl_loop())
            metrics_task = asyncio.create_task(self.calculate_metrics_loop())

            with Live(self.generate_display(), refresh_per_second=1) as live:
                while True:
                    live.update(self.generate_display())
                    await asyncio.sleep(1)
            
        except asyncio.CancelledError:
            print("Monitor stopped.")

        finally:
            pnl_task.cancel()
            metrics_task.cancel()
            await asyncio.gather(pnl_task, metrics_task, return_exceptions=True)
            self.save_pnl_history()  # Save and plot before exit

async def main():
    analyzer = PerformanceAnalyzer(
        'test_trade_data.csv',
        'test_position_data.csv',
        100000,
        pnl_interval_minutes=1,
        metrics_interval_minutes=1
    )
    try:
        await analyzer.run_monitor()
    except KeyboardInterrupt:
        print("Stopping monitor...")

if __name__ == "__main__":
    asyncio.run(main())