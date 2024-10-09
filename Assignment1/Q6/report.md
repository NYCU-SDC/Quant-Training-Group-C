# Quant-Training-Group-C

## Data scraping and preprocessing

To collect historical data, we implemented web socket technology combined with multiprocessing techniques to fetch real-time snapshots of the order book, trade data, and Best Bid and Offer (BBO) data. These were saved as JSON files for subsequent analysis.

The data scraping process lasted approximately 10 hours. Given our objective to predict price movements in the next second, we established a consistent time interval of one second for data collection.

For the order book snapshots and BBO data, we aligned our records using timestamps that correspond directly to those of the price data. For trade data, we aggregated the total volume traded in the interval between two consecutive timestamps (from t-1 to t), where t is the timestamp of the price data.

This structured approach ensures that each data point is accurately synchronized with the price movements, facilitating more precise predictive analysis.

## Factor analysis and data visualization in different classes 

Use raw data to compute some factor and visualize the distribution under different classes to see whether there is any significant differences

1. bbo bid-ask spread and bbo bid-ask size spread
   
  ![image](https://github.com/user-attachments/assets/8368a42e-519f-4ba3-a583-0f15038965c7)

  select bid-ask size spread as a factor

2. bid-ask size spread
   
   **orderbook imblance** : total ask size - total bid size
   
   **adjusted orderbook bid-ask price change(highest order)** :

\(
\frac{\text{ask_price}\left\arg\max\left[\text{ask_size}\right]\right}{\text{ask_price}\left\arg\max\left[\text{ask_size}\right]\right} + \frac{\text{bid_price}\left\arg\max\left[\text{bid_size}\right]\right}{\text{bid_price}\left\arg\max\left[\text{bid_size}\right]\right}
\)

   ![image](https://github.com/user-attachments/assets/1fd2d40d-498c-4b9a-91b4-f72ebd1edcb0)
