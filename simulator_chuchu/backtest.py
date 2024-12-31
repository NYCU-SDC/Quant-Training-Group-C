import pandas as pd
import numpy as np

class PerformanceAnalyzer:
    def __init__(self, trade_file_path, position_file_path):
        self.trade_data = pd.read_csv(trade_file_path)
        self.position_data = pd.read_csv(position_file_path)

    def calculate_metrics(self):
        self.trade_data['timestamp'] = pd.to_datetime(self.trade_data['timestamp'], unit='ms')
        self.position_data['timestamp'] = pd.to_datetime(self.position_data['timestamp'], unit='ms')

        self.trade_data.set_index('timestamp', inplace=True)
        self.position_data.set_index('timestamp', inplace=True)

        pnl, leverage_adjusted_pnl = self._calculate_pnl()
        total_return = self._calculate_total_return(pnl)
        sharpe_ratio = self._calculate_sharpe_ratio(leverage_adjusted_pnl)
        calmar_ratio = self._calculate_calmar_ratio(leverage_adjusted_pnl)
        max_drawdown, max_drawdown_duration = self._calculate_drawdown(leverage_adjusted_pnl)
        win_rate = self._calculate_win_rate()

        return {
            'PnL': pnl,
            'Total Return': total_return,
            'Sharpe Ratio': sharpe_ratio,
            'Calmar Ratio': calmar_ratio,
            'Max Drawdown': max_drawdown,
            'Max Drawdown Duration': max_drawdown_duration,
            'Win Rate': win_rate
        }

    def _calculate_pnl(self):
        pnl = pd.DataFrame(index=self.trade_data.index, columns=self.trade_data['symbol'].unique())
        leverage_adjusted_pnl = pd.DataFrame(index=self.trade_data.index, columns=self.trade_data['symbol'].unique())

        for symbol in self.trade_data['symbol'].unique():
            symbol_trades = self.trade_data[self.trade_data['symbol'] == symbol]
            symbol_position = self.position_data[self.position_data['symbol'] == symbol]

            symbol_trades = symbol_trades.join(symbol_position[['holding']], how='left').fillna(method='ffill')

            # single trade pnl
            symbol_trades['single_trade_pnl'] = (
                symbol_trades['executedPrice'] * symbol_trades['executedQuantity'] *
                np.where(symbol_trades['side'] == 'BUY', 1, -1)
            ) - symbol_trades['fee']

            # leverage adjust
            symbol_trades['single_trade_pnl'] = symbol_trades['single_trade_pnl'] * symbol_trades['leverage']

            # realized pnl
            realized_pnl = symbol_trades['pnl'].cumsum()

            
            # 累积 PnL
            pnl[symbol] = symbol_trades['pnl'].cumsum()
            leverage_adjusted_pnl[symbol] = symbol_trades['leverage_adjusted_pnl'].cumsum()

        pnl['Total'] = pnl.sum(axis=1)
        leverage_adjusted_pnl['Total'] = leverage_adjusted_pnl.sum(axis=1)

        return pnl, leverage_adjusted_pnl

    def _calculate_total_return(self, pnl):
        """
        总回报率：最终 PnL / 初始总投资
        """
        total_holding_value = self.position_data.groupby('symbol')['holding'].first().sum()
        return pnl['Total'].iloc[-1] / total_holding_value

    def _calculate_sharpe_ratio(self, pnl, risk_free_rate=0.02):
        """
        Sharpe 比率：年化收益 / 年化波动率
        """
        daily_returns = pnl['Total'].pct_change().dropna()
        annual_return = daily_returns.mean() * 252
        annual_volatility = daily_returns.std() * np.sqrt(252)
        sharpe_ratio = (annual_return - risk_free_rate) / annual_volatility
        return sharpe_ratio

    def _calculate_calmar_ratio(self, pnl):
        """
        Calmar 比率：年化收益 / 最大回撤
        """
        annual_return = pnl['Total'].pct_change().mean() * 252
        max_drawdown = self._calculate_drawdown(pnl)[0]
        calmar_ratio = annual_return / abs(max_drawdown)
        return calmar_ratio

    def _calculate_drawdown(self, pnl):
        """
        最大回撤和最大回撤持续时间
        """
        cumulative_returns = (1 + pnl['Total'].pct_change()).cumprod()
        peak = cumulative_returns.expanding(min_periods=1).max()
        drawdown = (cumulative_returns / peak) - 1
        max_drawdown = drawdown.min()
        max_drawdown_duration = drawdown[drawdown == 0].index.to_series().diff().max().days
        return max_drawdown, max_drawdown_duration

    def _calculate_win_rate(self):
        """
        胜率：盈利交易的数量 / 总交易数量
        """
        winning_trades = (
            ((self.trade_data['side'] == 'BUY') & (self.trade_data['executedPrice'].shift(-1) > self.trade_data['executedPrice'])) |
            ((self.trade_data['side'] == 'SELL') & (self.trade_data['executedPrice'].shift(-1) < self.trade_data['executedPrice']))
        )
        win_rate = winning_trades.sum() / len(self.trade_data)
        return win_rate

# 使用方法
trade_file_path = 'path/to/trade_data.csv'
position_file_path = 'path/to/position_data.csv'

analyzer = PerformanceAnalyzer(trade_file_path, position_file_path)
metrics = analyzer.calculate_metrics()
print(metrics)