import asyncio
import torch
from collections import deque
import pandas as pd
import numpy as np
from transformer_model import transformer_forecaster
import io

class DataProcessor:
    def __init__(self, model_path, time_sequence=10, time_interval=1):

        # queue
        self.orderbooks_queue = asyncio.Queue()
        self.orderbookupdates_queue = asyncio.Queue()
        self.bbo_queue = asyncio.Queue()
        self.tickers_queue = asyncio.Queue()
        self.klines_queue = asyncio.Queue()
        self.trades_queue = asyncio.Queue()
        self.indexprices_queue = asyncio.Queue()
        self.markprices_queue = asyncio.Queue()

        # deque
        self.orderbooks_data = deque()
        self.orderbookupdates_data = deque()
        self.bbo_data = deque()
        self.tickers_data = deque()
        self.klines_data = deque()
        self.trades_data = deque()
        self.indexprices_data = deque()
        self.markprices_data = deque()

        # optional for model
        self.prediction = None
        self.current_price = None
        self.time_sequence = time_sequence
        self.time_interval = time_interval
        self.num_variables = 7
        self.model = self.load_model(model_path)

    # optional for load model
    def load_model(self, model_path):
        with open(model_path, 'rb') as f:
            buffer = io.BytesIO(f.read())
        model = transformer_forecaster(input_dim=self.num_variables, embed_size=32, num_heads=[4, 4, 4], drop_prob=0.01, num_classes=3)
        model.load_state_dict(torch.load(buffer))
        model.eval()
        return model

    async def put_orderbooks(self, data):
        await self.orderbooks_queue.put(data)

    async def put_orderbookupdates(self, data):
        await self.orderbookupdates_queue.put(data)

    async def put_bbo(self, data):
        await self.bbo_queue.put(data)

    async def put_tickers(self, data):
        await self.tickers_queue.put(data)

    async def put_klines(self, data):
        await self.klines_queue.put(data)

    async def put_trades(self, data):
        await self.trades_queue.put(data)

    async def put_indexprices(self, data):
        await self.indexprices_queue.put(data)

    async def put_markprices(self, data):
        await self.markprices_queue.put(data)

    # process data
    # order book data process
    async def process_orderbooks(self, latest_indexprice_ts):
        while not self.orderbooks_queue.empty():
            orderbook = await self.orderbooks_queue.get()
            self.orderbooks_data.append(self.parse_orderbook_data(orderbook))
        self.orderbooks_data = self.align_data(self.orderbooks_data, latest_indexprice_ts)

    # order book update data process
    async def process_orderbookupdates(self, latest_indexprice_ts):
        while not self.orderbookupdates_queue.empty():
            orderbookupdate = await self.orderbookupdates_queue.get()
            self.orderbookupdates_data.append(self.parse_orderbookupdate_data(orderbookupdate))
        self.orderbookupdates_data = self.align_data(self.orderbookupdates_data, latest_indexprice_ts)

    # bbo data process
    async def process_bbo(self, latest_indexprice_ts):
        while not self.bbo_queue.empty():
            bbo = await self.bbo_queue.get()
            self.bbo_data.append(self.parse_bbo_data(bbo))
        self.bbo_data = self.align_data(self.bbo_data, latest_indexprice_ts)

    # tickers data process
    async def process_tickers(self, latest_indexprice_ts):
        while not self.tickers_queue.empty():
            tickers = await self.tickers_queue.get()
            self.tickers_data.append(self.parse_ticker_data(tickers))
        self.tickers_data = self.align_data(self.tickers_data, latest_indexprice_ts)

    # klines data process
    async def process_klines(self, latest_indexprice_ts):
        while not self.klines_queue.empty():
            klines = await self.klines_queue.get()
            self.klines_data.append(self.parse_kline_data(klines))
        self.klines_data = self.align_data(self.klines_data, latest_indexprice_ts)

    # trades data process
    async def process_trades(self, latest_indexprice_ts):
        while not self.trades_queue.empty():
            trade = await self.trades_queue.get()
            self.trades_data.append(self.parse_trade_data(trade))
        self.trades_data = self.align_data(self.trades_data, latest_indexprice_ts)

    # markprices data process
    async def process_markprices(self, latest_indexprice_ts):
        while not self.markprices_queue.empty():
            markprices = await self.markprices_queue.get()
            self.markprices_data.append(self.parse_markprices_data(markprices))
        self.markprices_data = self.align_data(self.markprices_data, latest_indexprice_ts)

    # process data for modedl
    async def process_data(self):
        try:
            indexprices = await self.indexprices_queue.get()
            self.indexprices_data.append(self.parse_indexprices_data(indexprices))
            print(f'latest index price sequence : {self.indexprices_data[-1]}')
            
            if len(self.indexprices_data) > self.time_sequence+1:
                self.indexprices_data.popleft()
            
            if len(self.indexprices_data) >= self.time_sequence+1:
                indexprices_data_list = list(self.indexprices_data)
                latest_indexprice_ts = [data['timestamp'] for data in indexprices_data_list[-self.time_sequence-1:]]
                
                await asyncio.gather(
                    self.process_orderbooks(latest_indexprice_ts),
                    self.process_bbo(latest_indexprice_ts),
                    self.process_trades(latest_indexprice_ts)
                )
                if len(self.orderbooks_data) >= self.time_sequence + 1 and len(self.bbo_data) >= self.time_sequence + 1 and len(self.trades_data) >= self.time_sequence + 1:
                    orderbook_df = pd.DataFrame(list(self.orderbooks_data))
                    bbo_df = pd.DataFrame(list(self.bbo_data))
                    trade_df = pd.DataFrame(list(self.trades_data))
                    indexprice_df = pd.DataFrame(list(self.indexprices_data))

                    # Calculate highest order ask price change and highest order bid price change
                    orderbook_df['highest_order_ask_price_change'] = orderbook_df['highest_order_ask_price'].pct_change()
                    orderbook_df['highest_order_bid_price_change'] = orderbook_df['highest_order_bid_price'].pct_change()
                    orderbook_df['highest_order_price_flow'] = orderbook_df['highest_order_ask_price_change'] + orderbook_df['highest_order_bid_price_change']

                    # Calculate total buy volume and total sell volume for each time interval
                    trade_df['total_buy_volume'] = trade_df['total_buy'].rolling(window=self.time_interval).sum()
                    trade_df['total_sell_volume'] = trade_df['total_sell'].rolling(window=self.time_interval).sum()

                    # Merge data
                    merged_data_1 = pd.merge_asof(orderbook_df, trade_df[['timestamp', 'total_buy_volume', 'total_sell_volume']], on='timestamp', direction='nearest')
                    merged_data = pd.merge_asof(merged_data_1, bbo_df[['timestamp', 'size_spread']], on='timestamp', direction='nearest')

                    # Calculate buy order flow, sell order flow, and net order flow changes
                    merged_data['buy_order_flow_change'] = merged_data['total_ask_size'].diff(self.time_interval)
                    merged_data['sell_order_flow_change'] = merged_data['total_bid_size'].diff(self.time_interval)
                    merged_data['net_flow_change'] = merged_data['buy_order_flow_change'] - merged_data['sell_order_flow_change']

                    # Adjust buy order flow and sell order flow by dividing by total buy volume and total sell volume
                    merged_data['adjusted_buy_order_flow_change'] = merged_data['buy_order_flow_change'] / merged_data['total_buy_volume'] + 1e-9
                    merged_data['adjusted_sell_order_flow_change'] = merged_data['sell_order_flow_change'] / merged_data['total_sell_volume'] + 1e-9
                    merged_data['adjusted_net_flow_change'] = merged_data['adjusted_buy_order_flow_change'] - merged_data['adjusted_sell_order_flow_change']

                    # Remove rows with NaN or inf values
                    merged_data = merged_data.replace([np.inf, -np.inf], np.nan).fillna(0)
                    # default
                    merged_data = merged_data[-(self.time_sequence-1):]

                    # Prepare input data
                    time_series_input = np.zeros((self.time_sequence-1, self.num_variables))
                    time_series_input[:, 0] = merged_data['imbalance'].values
                    time_series_input[:, 1] = merged_data['size_spread'].values
                    time_series_input[:, 2:] = merged_data[['buy_order_flow_change', 'sell_order_flow_change',
                                                            'adjusted_buy_order_flow_change', 'adjusted_sell_order_flow_change',
                                                            'highest_order_price_flow']].values
                    # using model for prediction
                    input_tensor = torch.from_numpy(time_series_input).float().unsqueeze(0)
                    with torch.no_grad():
                        output = self.model(input_tensor)
                        prediction = output.argmax(dim=1).item()

                    current_price = indexprice_df['index_price'].iloc[-1]

                    await self.handle_prediction(prediction, current_price)

        except asyncio.QueueEmpty:
            await asyncio.sleep(0.1)
        
    async def handle_prediction(self, prediction, current_price):
        """處理模型預測結果"""
        self.prediction = prediction
        self.current_price = current_price
        print(f'Price Movement Prediction: {prediction}')
        print(f'Current Price: {current_price}')

    # align data with benchmark timestamp
    def align_data(self, data, timestamp_sequence):
        aligned_data = []
        for ts in timestamp_sequence:
            closest_data = min(data, key=lambda x: abs(x['timestamp'] - ts))
            aligned_data.append(closest_data)
        return deque(aligned_data)

    def parse_orderbook_data(self, data):
        timestamp = data['ts']
        asks = np.array(data['data']['asks'])
        bids = np.array(data['data']['bids'])
        total_ask_size = np.sum(asks[:, 1])
        total_bid_size = np.sum(bids[:, 1])
        imbalance = total_ask_size - total_bid_size
        highest_order_ask_price = asks[np.argmax(asks[:, 1])][0]
        highest_order_bid_price = bids[np.argmax(bids[:, 1])][0]

        return {
            'timestamp': timestamp,
            'total_ask_size': total_ask_size,
            'total_bid_size': total_bid_size,
            'imbalance': imbalance,
            'highest_order_ask_price': highest_order_ask_price,
            'highest_order_bid_price': highest_order_bid_price
        }

    def parse_orderbookupdate_data(self, data):
        timestamp = data['ts']
        prev_timestamp = data['data']['prevTs']
        asks = np.array(data['data']['asks'])
        bids = np.array(data['data']['bids'])
        total_ask_size = np.sum(asks[:, 1])
        total_bid_size = np.sum(bids[:, 1])
        imbalance = total_ask_size - total_bid_size
        highest_order_ask_price = asks[np.argmax(asks[:, 1])][0]
        highest_order_bid_price = bids[np.argmax(bids[:, 1])][0]

        return {
            'timestamp': timestamp,
            'previous_timestamp': prev_timestamp,
            'total_ask_size': total_ask_size,
            'total_bid_size': total_bid_size,
            'imbalance': imbalance,
            'highest_order_ask_price': highest_order_ask_price,
            'highest_order_bid_price': highest_order_bid_price
        }

    def parse_bbo_data(self, data):
        timestamp = data['ts']
        ask_price = data['data']['ask']
        ask_size = data['data']['askSize']
        bid_price = data['data']['bid']
        bid_size = data['data']['bidSize']
        size_spread = ask_size - bid_size

        return {
            'timestamp': timestamp,
            'ask_price': ask_price,
            'ask_size': ask_size,
            'bid_price': bid_price,
            'bid_size': bid_size,
            'size_spread': size_spread
        }
    
    def parse_ticker_data(self, data):
        timestamp = data['ts']
        open_price = data['data']['open']
        close_price = data['data']['close']
        high_price = data['data']['high']
        low_price = data['data']['low']
        volume = data['data']['volume']
        amount = data['data']['amount']
        aggregated_quantity = data['data']['aggregatedQuantity']
        aggregated_amount = data['data']['aggregatedAmount']
        count = data['data']['count']
        ast_timestamp = data['data']['astTs']

        return {
            'timestamp': timestamp,
            'open_price': open_price,
            'close_price': close_price,
            'high_price': high_price,
            'low_price': low_price,
            'volume': volume,
            'amount': amount,
            'aggregated_quantity': aggregated_quantity,
            'aggregated_amount': aggregated_amount,
            'count': count,
            'ast_timestamp': ast_timestamp
        }

    def parse_kline_data(self, data):
        symbol = data['data']['symbol']
        timestamp = data['ts']
        kline_type = data['data']['type']
        open_price = data['data']['open']
        close_price = data['data']['close']
        high_price = data['data']['high']
        low_price = data['data']['low']
        volume = data['data']['volume']
        amount = data['data']['amount']
        start_time = data['data']['startTime']
        end_time = data['data']['endTime']

        return {
            'symbol': symbol,
            'timestamp': timestamp,
            'kline_type': kline_type,
            'open_price': open_price,
            'close_price': close_price,
            'high_price': high_price,
            'low_price': low_price,
            'volume': volume,
            'amount': amount,
            'start_time': start_time,
            'end_time': end_time
        }

    def parse_trade_data(self, data):
        timestamp = data['ts']
        total_buy = sum(trade['a'] for trade in data['data'] if trade['b'] == 'BUY')
        total_sell = sum(trade['a'] for trade in data['data'] if trade['b'] == 'SELL')

        return {
            'timestamp': timestamp,
            'total_buy': total_buy,
            'total_sell': total_sell
        }

    def parse_indexprices_data(self, data):
        timestamp = data['ts']
        index_price = data['data']['price']

        return {
            'timestamp': timestamp,
            'index_price': index_price
        }
    
    def parse_markprices_data(self, data):
        timestamp = data['ts']
        index_price = data['data']['price']

        return {
            'timestamp': timestamp,
            'mark_price': index_price
        }