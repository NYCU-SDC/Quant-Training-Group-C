# Quant-Training-Group-C
## 利用woox-restful-api-get-historical-data.py 抓取Spot BTC_USDT & Spot ETH_USDT的歷史資料
## 利用woox-analyzer-correlation.py 來分析Spot BTC_USDT與Spot ETH_USDT價格變化的相關性
1. 由於要分析的是長期下，價格波動的百分比的相關性，所以我用RestFul API抓取Kline的資料，Interval為5min
2. 將BTC的漲跌百分比依照不同範圍分成group，利於分析不同group下，ETH的平均價格變化量
3. 由資料顯示，30000多筆資料中，有33筆資料是BTC價格變化量接近1% (正負0.1%之間)
4. BTC與ETH之價格變化的相關係數約為：0.83
5. 最後將資料視覺化，作出相關性的圖表。
