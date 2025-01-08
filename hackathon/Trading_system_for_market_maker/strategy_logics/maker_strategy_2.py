import json
import asyncio
import pandas as pd
import numpy as np
from collections import deque
from redis import asyncio as aioredis
from strategy_logics.strategy_init import (
    Strategy,
    SignalData,
    OrderType,
    PositionSide,
    OrderAction
)
import datetime
import time
import logging
from typing import Optional, List, Dict
import pytz
import io
import os
import math

logger = logging.getLogger('Maker strategy')

class MakerStrategy2(Strategy):
    def __init__(self, signal_channel: str, config: Dict = None):
        """
        Initialize strategy
        Args:
            signal_channel: Redis signal channel
            config: Strategy configuration dictionary
        """
        # 先調用父類的初始化
        super().__init__(signal_channel, config)
        
        # 從配置中獲取參數
        trading_params = self.config.get('trading_params', {})
        self.time_interval = trading_params.get('time_interval', 1000)
        self.tick_size = trading_params.get('tick_size', 0.0001)
        self.single_position_size = trading_params.get('single_position_size', 0.001)
        self.limit_quantity_demical = trading_params.get('limit_quantity_demical', 4)
        self.init_capital = trading_params.get('init_capital', 1000)
        self.grid_depth = trading_params.get('grid_depth', 1)
        self.capital = self.init_capital
        self.cash = self.capital
        self.position_ratio = 0.0
        print(f"position size: {self.single_position_size}")

        # 其他初始化
        
        self.time = int(time.time() * 1000)
        self.time_rolling = int(time.time() * 1000)
        self.order_book = dict()
        self.mid_price = None
        self.last_update_time = None
        self.redis_client = None
        self.trading_symbol = trading_params.get('symbol', "PERP_BTC_USDT")
        self.order_number = 1000
        self.price_list = []
        self.count = 0

        # 設定台灣時區
        self.tz = pytz.timezone('Asia/Taipei')

        # Set up logger
        self.logger = self.setup_logger(name='MakerStrategy', log_file='maker_strategy.log')
        self.logger.info("maker Strategy initialization completed")
    
    async def process_market_data(self, channel: str, data: dict, redis_client: aioredis.Redis) -> None:
        print(self.count)
        if channel == f"[MD]{self.trading_symbol}-orderbook" and data['ts'] >= self.time_rolling + 1000:
            self.count += 1
            # calculate ATR and mid price
            self.time_rolling = data['ts']
            self.order_book = data['data']
            mid_price = (self.order_book.get('asks')[0][0] + self.order_book.get('bids')[0][0]) / 2
            self.price_list.append(mid_price)
            if len(self.price_list) > 30:
                self.price_list.pop(0)

        if channel == f"[MD]{self.trading_symbol}-orderbook" and data['ts'] >= self.time + 20000:
            # cancel all orders
            cancel_all_signal = SignalData(target='cancel_all_orders', timestamp=int(time.time() * 1000))
            print("cancel all orders: ", cancel_all_signal)
            await self.publish_signal(cancel_all_signal)
            self.time = data['ts']
            # get atr
            max = np.max(self.price_list)
            min = np.min(self.price_list)
            atr = max - min
            print(f"ATR: {atr}")

            # Reduce the order book size to match grid depth
            self.order_book = data['data']
            self.delist_self_orders('ask')
            self.delist_self_orders('bid')
            
            # Process reduced order book
            # self.delist_self_orders('ask', top_asks)
            # self.delist_self_orders('bid', top_bids)
            
            # Offload delisting to a separate task
            # asyncio.create_task(self.delist_orders())

            self.mid_price = (self.order_book.get('asks')[0][0] + self.order_book.get('bids')[0][0]) / 2
            best_ask = self.order_book.get('asks')[0][0]
            best_bid = self.order_book.get('bids')[0][0]
            self.net_postiion_value = self.position_size * self.mid_price
            self.capital = abs(self.net_postiion_value) + self.cash
            print(f"mid price: {self.mid_price}, ts: {self.time}")
            print(f"spread: {self.order_book.get('asks')[0][0] - self.order_book.get('bids')[0][0]}")
            
            for i in range(self.grid_depth):
                print("!!!!!!!!!!!!!!!!!")
                ask_price = self.mid_price + (i+1) * atr / 2.0
                bid_price = self.mid_price - (i+1) * atr / 2.0
                if ask_price > self.mid_price:
                    print("position size: ", self.single_position_size)
                    quantity = round((self.single_position_size / ask_price), self.limit_quantity_demical)
                    print(f"quantity: {quantity}")
                    open_short_signal = SignalData(
                        timestamp=int(time.time() * 1000),
                        target='send_order',
                        action=OrderAction.OPEN,
                        position_side=PositionSide.SHORT,
                        order_type=OrderType.POST_ONLY,
                        symbol=self.trading_symbol,
                        price=round(ask_price, abs(int(-math.log10(self.tick_size)))),
                        quantity=quantity,
                        order_number=self.order_number,
                        reduce_only=False,
                    )
                    self.order_number += 1
                    print("open short signal: ", open_short_signal)
                    await self.publish_signal(open_short_signal)
                    # asyncio.sleep(0.5)
                if bid_price < self.mid_price:
                    print("position size: ", self.single_position_size)
                    quantity = round((self.single_position_size / bid_price), self.limit_quantity_demical)
                    print(f"quantity: {quantity}")
                    open_long_signal = SignalData(
                        timestamp=int(time.time() * 1000),
                        target="send_order",
                        action=OrderAction.OPEN,
                        position_side=PositionSide.LONG,
                        order_type=OrderType.POST_ONLY,
                        symbol=self.trading_symbol,
                        price=round(bid_price, abs(int(-math.log10(self.tick_size)))),
                        quantity=quantity,
                        order_number=self.order_number,
                        reduce_only=False,
                    )
                    self.order_number += 1
                    print("open long signal: ", open_long_signal)
                    await self.publish_signal(open_long_signal)
                # sleep 0.1s to avoid sending too many orders
                # await asyncio.sleep(1)
            
            # self.logger.info(f"Processing orderbook data: {self}")
    def delist_self_orders(self, order_type: str = "ask") -> None:
        print(f"Delisting {order_type} orders...")
        # Determine which limit orders to process
        if order_type == "ask":
            combined_orders = self.ask_limit_order
        else:
            combined_orders = self.bid_limit_order

        # Aggregate orders to delist by price, limited to grid depth
        delist_requests = {}
        for self_order in combined_orders.values():
            print(f"self_order: {self_order}")
            if self_order["status"] == "PENDING":
                price = self_order["price"]
                delist_requests[price] = delist_requests.get(price, 0) + self_order["quantity"]

        # Select top entries based on the order type
        top_entries = (
            self.order_book["asks"][:self.grid_depth]
            if order_type == "ask"
            else self.order_book["bids"][:self.grid_depth]
        )

        # Process top entries in place
        for i in range(len(top_entries)):
            price, quantity = top_entries[i]
            if price in delist_requests:
                # Adjust the quantity or mark for removal
                quantity -= delist_requests[price]
                if quantity > 0:
                    top_entries[i][1] = quantity  # Update in place
                else:
                    top_entries[i] = None  # Mark for removal

        # Remove marked entries and update the order book
        top_entries = [entry for entry in top_entries if entry is not None]
        if order_type == "ask":
            self.order_book["asks"] = top_entries + self.order_book["asks"][self.grid_depth:]
        else:
            self.order_book["bids"] = top_entries + self.order_book["bids"][self.grid_depth:]

        print(f"Delisted {order_type} orders: {list(delist_requests.keys())}")


    async def delist_orders(self):
        print("Delisting orders...")
        self.delist_self_orders('ask')
        self.delist_self_orders('bid')

    async def execute(self, channel: str, data: dict, redis_client: aioredis.Redis) -> None:
        self.redis_client = redis_client
        await asyncio.sleep(0.1)
        if channel.startswith("[MD]"):
            await self.process_market_data(channel, data, redis_client)
        elif channel.startswith("[PD]"):
            await self.process_private_data(channel, data, redis_client)
        else:
            self.logger.warning(f"[{self.strategy_name}] Unknown channel: {channel}")
            