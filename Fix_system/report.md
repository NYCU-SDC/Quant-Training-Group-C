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
