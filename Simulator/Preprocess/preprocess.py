import pandas as pd

# Define file names and headers
kline_file_path = 'kline.csv'
kline_columns = [
    "Open time", "Open", "High", "Low", "Close", "Volume",
    "Close time", "Quote asset volume", "Number of trades",
    "Taker buy base asset volume", "Taker buy quote asset volume", "Ignore", "symbol"
]

trades_file_path = 'trades.csv'
trades_columns = [
    "trade Id", "price", "qty", "quoteQty", "time",
    "isBuyerMaker", "isBestMatch", "symbol"
]

# Define symbol value
symbol_value = 'SPOT_BTC_USDT'

# Remove duplicate headers in kline.csv and add symbol column
data_kline = pd.read_csv(kline_file_path, dtype=str, low_memory=False)
if data_kline.iloc[0].tolist()[:12] == kline_columns[:-1]:
    data_kline = data_kline[1:]
data_kline['symbol'] = symbol_value
data_kline.to_csv(kline_file_path, index=False, header=kline_columns)

# Remove duplicate headers in trades.csv and add symbol column
data_trades = pd.read_csv(trades_file_path, dtype=str, low_memory=False)
if data_trades.iloc[0].tolist()[:7] == trades_columns[:-1]:
    data_trades = data_trades[1:]
data_trades['symbol'] = symbol_value
data_trades.to_csv(trades_file_path, index=False, header=trades_columns)
