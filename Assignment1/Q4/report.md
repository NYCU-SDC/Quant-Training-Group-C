# Quant-Training-Group-C
## 這題是要透過 kline 資料建立視覺化圖表，顯示一天中交易量最大或波動性最高的時間，並分析這些發現對市場的影響。使用 WooX 的 orderbook 或 ticker data 來識別當前市場的leader。
## leadMA.py做的事情：(同時處理第二題跟第四題)
1.從 WooX 提取 Kline 資料：透過 API 抓取每個市場的 Kline 資料，這些資料包括每個小時的開盤價、收盤價、最高價、最低價以及交易量。

2.分析每個小時的交易量和波動性：scripts將資料整理成表格格式，並計算每個小時的交易量和波動性（最高價減去最低價），找出一天中交易量最大和波動性最高的時段。

3.視覺化圖表：利用 Matplotlib 畫出交易量和波動性的對比圖，方便看出不同時間段的市場行為。

4.計算 Spread：透過 get_leading_market 函數，腳本還計算了每個市場的買賣價差Spread，幫助確定市場的流動性和 leading 情況。

最後將分析結果存成 CSV 文件，以方便後續分析。這邊之所以會存成 CSV，是因為 RESTful 資料是歷史性資料並且固定不會更動，所以不用存到 Redis 或 MongoDB。

### 第四題分析：
#### 根據 K線數據的分析結果，我們發現 SPOT_WOO_USDT、SPOT_BTC_USDT 和 SPOT_ETH_USDT 這三個交易對的每日最高交易量和波動性都出現在第 22 小時。這表明在這個時間段，市場的交易活動特別活躍，可能是因為全球範圍內的交易者同時參與，使得流動性和波動性在這一時段達到高峰。

#### 特別是比特幣（SPOT_BTC_USDT）的波動性最大，這反映了比特幣市場本身資金量大且交易者眾多的特點。相比之下，WOO 和以太坊（SPOT_WOO_USDT 和 SPOT_ETH_USDT）的波動性雖然較小，但它們的交易量仍在第 22 小時達到峰值，顯示這一時間段的市場仍然非常活躍。

#### 這數據告訴我們特定時段（像是第 22 小時）的高交易量和波動性為交易者提供了更多機會。在這個時段流動性充足，而且價格變動幅度也大，這對於制定高頻交易策略或捕捉市場波動具有很高的參考價值。
![jdwiijdwidsss](https://github.com/user-attachments/assets/98e14d2f-554c-42f5-9c33-dc4ba2e1680f)


![my_plot](https://github.com/user-attachments/assets/9279ae28-60c9-4973-83b7-dcb2b34c145b)
