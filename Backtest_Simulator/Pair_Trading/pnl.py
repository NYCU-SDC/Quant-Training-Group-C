import pandas as pd
import matplotlib.pyplot as plt


def plot_pnl(file):
    # 讀取 orders.csv
    orders_df = pd.read_csv(file)
    # 確保 profit_or_loss 欄位為 float 類型
    orders_df['profit_or_loss'] = orders_df['profit_or_loss'].astype(float)

    # 計算累計盈虧
    orders_df['cumulative_profit'] = orders_df['profit_or_loss'].cumsum()

    # 確保 timestamp 欄位為時間格式
    orders_df['timestamp'] = pd.to_datetime(orders_df['timestamp'])

    # 設定樣式
    plt.style.use('dark_background')

    # 繪製累計盈虧走勢圖
    plt.figure(figsize=(12, 8))
    plt.plot(orders_df['timestamp'], orders_df['cumulative_profit'], color='cyan', label='Cumulative Profit')

    # 設置軸標籤與標題
    plt.xlabel('Timestamp', fontsize=12)
    plt.ylabel('Cumulative Profit or Loss', fontsize=12)
    plt.title('Cumulative Profit or Loss Trend', fontsize=14)

    # 只顯示 timestamp 頭尾標籤
    plt.xticks([orders_df['timestamp'].iloc[0], orders_df['timestamp'].iloc[-1]],
            labels=[orders_df['timestamp'].iloc[0].strftime('%Y-%m-%d %H:%M:%S'),
                    orders_df['timestamp'].iloc[-1].strftime('%Y-%m-%d %H:%M:%S')])

    # 顯示圖例與網格
    plt.legend(fontsize=10)
    plt.grid(color='gray', linestyle='--', linewidth=0.5, alpha=0.6)
    plt.tight_layout()
    plt.savefig('cumulative_pnl.png', dpi=300)
    plt.show()

    # 繪製每筆盈虧變動圖 (柱狀圖)
    plt.figure(figsize=(12, 8))
    colors = ['green' if val > 0 else 'red' for val in orders_df['profit_or_loss']]
    plt.bar(orders_df['timestamp'], orders_df['profit_or_loss'], color=colors, alpha=0.7, label='Profit or Loss')

    # 設置軸標籤與標題
    plt.xlabel('Timestamp', fontsize=12)
    plt.ylabel('Profit or Loss', fontsize=12)
    plt.title('Profit or Loss Over Time', fontsize=14)
    plt.xlim([orders_df['timestamp'].min(), orders_df['timestamp'].max()])

    # 只顯示 timestamp 頭尾標籤
    plt.xticks([orders_df['timestamp'].iloc[0], orders_df['timestamp'].iloc[-1]],
            labels=[orders_df['timestamp'].iloc[0].strftime('%Y-%m-%d %H:%M:%S'),
                    orders_df['timestamp'].iloc[-1].strftime('%Y-%m-%d %H:%M:%S')])

    # 顯示圖例與網格
    plt.legend(fontsize=10)
    plt.grid(color='gray', linestyle='--', linewidth=0.5, alpha=0.6)
    plt.tight_layout()
    plt.savefig('pnl.png', dpi=300)
    plt.show()


if __name__ == "__main__":
    plot_pnl('orders.csv')