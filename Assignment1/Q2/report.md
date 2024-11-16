# Quant-Training-Group-C
## 這題是要透過 kline 資料建立視覺化圖表，顯示一天中交易量最大或波動性最高的時間，並分析這些發現對市場的影響。使用 WooX 的 orderbook 或 ticker data 來識別當前市場的leader。
## leadMA.py做的事情：(同時處理第二題跟第四題)
1.從 WooX 提取 Kline 資料：透過 API 抓取每個市場的 Kline 資料，這些資料包括每個小時的開盤價、收盤價、最高價、最低價以及交易量。

2.分析每個小時的交易量和波動性：scripts將資料整理成表格格式，並計算每個小時的交易量和波動性（最高價減去最低價），找出一天中交易量最大和波動性最高的時段。

3.視覺化圖表：利用 Matplotlib 畫出交易量和波動性的對比圖，方便看出不同時間段的市場行為。

4.計算 Spread：透過 get_leading_market 函數，腳本還計算了每個市場的買賣價差Spread，幫助確定市場的流動性和 leading 情況。

最後將分析結果存成 CSV 文件，以方便後續分析。這邊之所以會存成 CSV，是因為 RESTful 資料是歷史性資料並且固定不會更動，所以不用存到 Redis 或 MongoDB。

### 第二題分析：
#### 根據 K線數據分析，SPOT_WOO_USDT、SPOT_BTC_USDT 和 SPOT_ETH_USDT 這三個交易對在第 22 小時的交易量和波動性達到最高點。這顯示出這個時間段是市場活動最為活躍的時刻，可能是由於全球交易者在此時段同時參與交易，使得市場的流動性和價格波動都變得非常明顯。

#### 從 WooX 的數據來看，SPOT_WOO_USDT 的買賣價差最小，數據是 0.00137，表示說該市場的流動性相對較好，且交易成本較低。相比之下SPOT_BTC_USDT 的價差為 24.91，顯示出比特幣市場在這段時間波動較大，但流動性可能相對較差。這意味著在 WooX上，WOO/USDT 可能是當前的 leading 市場。

#### 所以第 22 小時的高交易量和高波動性為交易者就可以給我們更多機會，而 WOO/USDT 憑藉其低價差和高流動性，成為目前的 leading 市場。這些結果對於交易策略的調整我覺得很重要，特別是對於希望在短時間內進行交易的trader。
![jdwiijdwidsss](https://github.com/user-attachments/assets/98e14d2f-554c-42f5-9c33-dc4ba2e1680f)


![my_plot](https://github.com/user-attachments/assets/9279ae28-60c9-4973-83b7-dcb2b34c145b)
