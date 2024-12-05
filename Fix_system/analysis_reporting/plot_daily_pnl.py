import pandas as pd
import matplotlib.pyplot as plt

def plot_daily_pnl(df):
    plt.figure(figsize=(16, 8))
    # 設置背景顏色為白色
    plt.gca().set_facecolor('white')
    plt.bar(df['date'], df['net_PnL'], color='lightblue', alpha=0.7, edgecolor='blue')
    plt.xlabel('Date', fontsize=14)
    plt.ylabel('Net PnL', fontsize=14)
    plt.title('Net PnL Over Time', fontsize=16)
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)
    plt.xticks(rotation=45)
    fig = plt.gcf()
    return fig