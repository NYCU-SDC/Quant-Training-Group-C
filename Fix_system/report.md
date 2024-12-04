# System Structure
```
Fix_system/
|--- data_publisher.py
|--- data_subscriber.py
|--- strategy_executor.py
|--- test_order_executor.py
|--- WooX_REST_API_Client.py
|--- WooX_WebSocket_API_Subscription.py
|--- report.md
|
|-> data_processing/
|   |--- pycache
|   |--- BBO.py
|   |--- Orderbook.py
|
|-> strategy_logics/
|   |--- pycache
|   |--- cta_strategy.py
|   |--- strategy_init.py
|   |--- df.ipynb
|
|-> analysis_reporting/
|--- calc_metrices.py
|--- plot_chart.py
|--- plot_daily_pnl.py
|--- process_results.py
``` 
## First Layer
* **data_publisher.py** : Handles WooX WebSocket API connection, pub data to Redis.
* **data_subscriber.py** : Manages data subscription and processes sub data.
* **WooX_REST_API_Client.py** : Interface for REST API interactions
* **WooX_WebSocket_API_Subscription.py**: Manages WebSocket connections and subscriptions
* **test_order_executor.py** : Test order executor of the CTA strategy
* **strategy_executor.py** : the code written by my member in Folder: Trading System

## data_processing
### Purpose: Handles market data processing and orderbook management
* **BBO.py**: Best Bid and Offer processing (Written by my member)
* **Orderbook.py**: Order book management and maintenance

## strategy_logics
### Purpose: Contains trading strategy implementations and analysis
* **strategy_init.py**: Strategy initialization and setup
* **cta_strategy.py**: CTA strategy implementation
* **df.ipynb**: Jupyter notebook for looking df DataFrame, ATR, and Current Price