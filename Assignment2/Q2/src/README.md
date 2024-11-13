# Simulator/Backtest Framework
Designed to simulate and evaluate trading strategies using Binance market data.
https://data.binance.vision/
Framework Overview
This framework processes Binance market data to simulate real market conditions and evaluate trading strategy performance.
## Architecture Components
1. Binance Data Source
Handles various types of market data from Binance:
Raw Market Data

aggTrades: Aggregated trade data with price, volume, and direction
bookDepth: Order book depth data (L1-L1000)
bookTicker: Real-time best bid/ask updates
trades: Original trade records

Price & Kline Data

klines: OHLCV (Open, High, Low, Close, Volume) data
indexPriceKlines: Index price information
markPriceKlines: Mark price data
premiumIndexKlines: Premium index data

Market Metrics

metrics: Market statistics and indicators
liquidationSnapshot: Liquidation event data

2. Backtest Framework
Data Processing Layer

Data Parser: Converts raw data into standardized format
Data Queue: Maintains time-ordered event sequence
Data Cache:

OrderBook Cache: Maintains order book snapshots
Trade Cache: Buffers trade data
Kline Cache: Builds and stores kline data



Market Reconstruction

Market Indicators: Calculates volatility and liquidity metrics
Trade Flow: Analyzes trade directions and patterns
Limit Order Book: Reconstructs full order book state

Strategy Engine

Signal Generator: Implements trading logic and generates signals
Risk Manager: Controls position sizes and risk exposure
Position Manager: Tracks positions and calculates PnL

Order Management

Order Type: Creates orders with specific parameters
Order Manager: Maintains order status and lifecycle
Matching Engine: Simulates order execution

Simulation Engine

Impact Simulator: Models market impact and slippage
Exchange Simulator: Implements trading rules and fees
Latency Simulator: Simulates network and exchange delays

3. Analysis & Reporting

PnL Analysis: Calculates profit/loss metrics
Performance Report: Generates strategy statistics
Visualization: Provides chart analysis and trade visualization

