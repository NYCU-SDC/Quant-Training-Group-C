# Quant-Training-Group-C
## 把爬下來的資料去整合最新的 orderbook，結合 ticker 和 orderbook source，這樣就可以提供我們當前市場狀況。
## dataGA.py 中使用了 Redis 和 MongoDB 來存取和整合 bbo（Best Bid and Offer）和 orderbook 資料，然後可以從兩個來源中提取最新的市場data。使用前請先下載好Redis跟MongoDB的包)
### 補充說明（為何用redi跟MongoDB?）：在高頻交易中，速度是很重要的，這就是為什麼我們要用 Redis 和 MongoDB，而不是把資料寫進CSV裡面。CSV文件讀寫速度慢，特別是處理大量數據時，它需要逐行讀寫，無法滿足毫秒級的延遲要求。但Redis是內存數據庫，讀寫速度非常快，適合實時數據更新，然後MongoDB能快速處理大規模的結構化數據，並且可以很快、很高效的去查詢。這樣相比之下，CSV只適合靜態數據，無法跟上高頻交易對速度和效率的需求。
