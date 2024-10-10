# Quant-Training-Group-C
## 這題是要透過 kline 資料建立視覺化圖表，顯示一天中交易量最大或波動性最高的時間，並分析這些發現對市場的影響。使用 WooX 的 orderbook 或 ticker data 來識別當前市場的leader。
## leadMA.py做的事情：(同時處理第二題跟第四題)
1.從 WooX 提取 Kline 資料：透過 API 抓取每個市場的 Kline 資料，這些資料包括每個小時的開盤價、收盤價、最高價、最低價以及交易量。

2.分析每個小時的交易量和波動性：scripts將資料整理成表格格式，並計算每個小時的交易量和波動性（最高價減去最低價），找出一天中交易量最大和波動性最高的時段。

3.視覺化圖表：利用 Matplotlib 畫出交易量和波動性的對比圖，方便看出不同時間段的市場行為。

4.計算 Spread：透過 get_leading_market 函數，腳本還計算了每個市場的買賣價差Spread，幫助確定市場的流動性和 leading 情況。

最後將分析結果存成 CSV 文件，以方便後續分析。這邊之所以會存成 CSV，是因為 RESTful 資料是歷史性資料並且固定不會更動，所以不用存到 Redis 或 MongoDB。
![jdwiijdwidsss](https://github.com/user-attachments/assets/98e14d2f-554c-42f5-9c33-dc4ba2e1680f)


![my_plot](https://github.com/user-attachments/assets/9279ae28-60c9-4973-83b7-dcb2b34c145b)
