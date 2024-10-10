# Quant-Training-Group-C
## 把爬下來的資料去整合最新的 orderbook，結合 ticker 和 orderbook source，這樣就可以提供我們當前市場狀況。
## dataGA.py 中使用了 Redis 和 MongoDB 來存取和整合 bbo（Best Bid and Offer）和 orderbook 資料，然後可以從兩個來源中提取最新的市場data。使用前請先下載好Redis跟MongoDB的包)
### 補充說明（為何用redis跟MongoDB?）：
#### 1.在高頻交易中，速度是很重要的，這就是為什麼我們要用 Redis 和 MongoDB，而不是把資料寫進CSV裡面。CSV文件讀寫速度慢，特別是處理大量數據時，它需要逐行讀寫，無法滿足毫秒級的延遲要求。但Redis是內存數據庫，讀寫速度非常快，適合實時數據更新，然後MongoDB能快速處理大規模的結構化數據，並且可以很快、很高效的去查詢。這樣相比之下，CSV只適合靜態數據，無法跟上高頻交易對速度和效率的需求。
#### 2.「為什麼不把oderbook進行整合？」：如果我們把BTC,ETH,WOO這三種幣別的資料整合成一份檔案，這樣在之後我要訓練HFT模型時會給模型錯誤資訊。這是因為不同幣種的市場動態、流動性、價格行為和交易特性都會有顯著差異，所以我認為如果將它們合併，會給模型帶來誤導的訊息，從而降低模型的預測能力。
#### step1:單獨處理每個幣種的 Orderbook 數據：我用 symbol 來標識不同的幣種（例如 SPOT_BTC_USDT 代表比特幣，SPOT_ETH_USDT 代表以太坊），並將每個幣種的 Orderbook 數據儲存在 self.orderbooks_data[symbol] 中。這樣每個幣種的 Orderbook 數據都能分開處理，不會互相混合。
#### step2:存儲 Orderbook 數據到 Redis 和 MongoDB：我把每個幣種的 Orderbook 數據存儲到 Redis 和 MongoDB 中，這樣每個幣種的最新 Orderbook 數據都能獨立保存和檢索。
#### step3:依據幣種的歷史數據存儲： self.store_orderbook_history(symbol, data['data']) 方法確保儲存每個幣種的即時 Orderbook 數據，這樣就可以供未來的分析和模型訓練使用。
