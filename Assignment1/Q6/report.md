# Quant-Training-Group-C

To collect historical data, we implemented web socket technology combined with multiprocessing techniques to fetch real-time snapshots of the order book, trade data, and Best Bid and Offer (BBO) data. These were saved as JSON files for subsequent analysis.

The data scraping process lasted approximately 10 hours. Given our objective to predict price movements in the next second, we established a consistent time interval of one second for data collection.

For the order book snapshots and BBO data, we aligned our records using timestamps that correspond directly to those of the price data. For trade data, we aggregated the total volume traded in the interval between two consecutive timestamps (from t-1 to t), where t is the timestamp of the price data.

This structured approach ensures that each data point is accurately synchronized with the price movements, facilitating more precise predictive analysis.

### 
