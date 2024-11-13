# Q2
# Simulator/Backtest Framework
Designed to simulate and evaluate trading strategies using Binance market data.
https://data.binance.vision/

Framework Overview
This framework processes Binance market data to simulate real market conditions and evaluate trading strategy performance.

## I use PlantText(an Online version of PlantUML) to construct the framework.
1. I save the framework as "backtest.png" and "backtest.svg" in src folder.
2. I save the content as planttext.txt. 

## Architecture Components
### I. Binance Data Source
Handles various types of market data from Binance:
* Raw Market Data :
    1. aggTrades: Aggregated trade data with price, volume, and direction
    2. bookDepth: Order book depth data (L1-L1000)
    3. bookTicker: Real-time best bid/ask updates
    4. trades: Original trade records

* Price & Kline Data :
    1. klines: OHLCV (Open, High, Low, Close, Volume) data
    2. indexPriceKlines: Index price information
    3. markPriceKlines: Mark price data
    4. premiumIndexKlines: Premium index data

* Market Metrics :
    1. metrics: Market statistics and indicators
    2. liquidationSnapshot: Liquidation event data

### II. Backtest Framework
* Data Processing Layer
    1. Data Parser: Converts raw data into standardized format
    2. Data Queue: Maintains time-ordered event sequence
    3. OrderBook Cache: Maintains order book snapshots
    4. Trade Cache: Buffers trade data
    5. Kline Cache: Builds and stores kline data

* Market Reconstruction
    1. Market Indicators: Calculates volatility and liquidity metrics
    2. Trade Flow: Analyzes trade directions and patterns
    3. Limit Order Book: Reconstructs full order book state

* Strategy Engine
    1. Signal Generator: Implements trading logic and generates signals
    2. Risk Manager: Controls position sizes and risk exposure
    3. Position Manager: Tracks positions and calculates PnL

* Order Management
    1. Order Type: Creates orders with specific parameters
    2. Order Manager: Maintains order status and lifecycle
    3. Matching Engine: Simulates order execution

* Simulation Engine
    1. Impact Simulator: Models market impact and slippage
    2. Exchange Simulator: Implements trading rules and fees
    3. Latency Simulator: Simulates network and exchange delays

### III. Analysis & Reporting
    1. PnL Analysis: Calculates profit/loss metrics
    2. Performance Report: Generates strategy statistics
    3. Visualization: Provides chart analysis and trade visualization