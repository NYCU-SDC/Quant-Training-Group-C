# Q2
# Simulator/Backtest Framework
Designed to simulate and evaluate trading strategies using Binance market data.
https://data.binance.vision/

Framework Overview
This framework processes Binance market data to simulate real market conditions and evaluate trading strategy performance.

## I use PlantText(an Online version of PlantUML) to construct the framework.
1. I save the backtest framework as "backtest.png" and "backtest.svg" in output folder.
2. I also focus on designing the order management system, which named as Order Management System as below.
2. I save the contents as backtest_sys.txt and order_management_sys.txt in src folder.
3. I save the order management system framework as "order_management_sys.png" and "order_management_sys.svg" in output folder.

## Main Architecture Components
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

## Detailed Order Management System Design
The Order Management System is a crucial component designed to handle various order types and simulate realistic market execution scenarios.

#### Order Types
1. **Market Order**
   - Executes at current market price
   - Properties:
     * Order size
     * Side (Buy/Sell)
     * Estimated execution price
     * Slippage tolerance

2. **Limit Order**
   - Executes at specified price or better
   - Properties:
     * Order size
     * Limit price
     * Time in force
     * Queue position estimation

3. **IOC (Immediate or Cancel) Order**
   - Executes immediately at specified price or better
   - Cancels any unfilled portion
   - Properties:
     * Minimum fill size
     * Partial fill handling
     * Expiration logic

4. **FOK (Fill or Kill) Order**
   - Must be filled completely or cancelled
   - Properties:
     * Full fill validation
     * Rejection handling

#### Key Components
1. **Order Manager**
   - Maintains active and historical orders
   - Handles order lifecycle:
     * Submission
     * Cancellation
     * Modification
     * Status tracking

2. **Order Validator**
   - Validates order parameters:
     * Size validation
     * Price validation
     * Balance checks
     * Risk limit verification

3. **Order Executor**
   - Manages order execution:
     * Order matching
     * Partial fill processing
     * Rejection handling

4. **Order Book**
   - Maintains market depth
   - Provides:
     * Best bid/ask prices
     * Spread calculation
     * Depth updates

5. **Matching Engine**
   - Processes order matching
   - Manages execution queue
   - Handles cancellations

6. **Latency Simulator**
   - Simulates realistic market conditions:
     * Network delays
     * Exchange processing time
     * Queue processing delays

#### Implementation Considerations

1. **Maker Order Execution**
   - Price-time priority implementation
   - Queue position simulation
   - Fill probability estimation

2. **IOC Order Pricing**
   - Market impact assessment
   - Slippage calculation
   - Partial fill optimization

3. **Latency Simulation**
   - Network round-trip time (RTT)
   - Exchange processing delays
   - Order queue processing time

4. **Market Impact Modeling**
   - Order size impact
   - Market depth consideration
   - Realistic fill rates

5. **Performance Optimization**
   - Efficient order book updates
   - Quick order matching
   - Memory-efficient data structures