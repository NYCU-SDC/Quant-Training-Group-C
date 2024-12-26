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

logger = logging.getLogger('Maker strategy')

class MakerStrategy(Strategy):
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
        print(f"position size: {self.single_position_size}")

        # 其他初始化
        
        self.time = int(time.time() * 1000)
        self.order_book = dict()
        self.mid_price = None
        self.last_update_time = None
        self.redis_client = None
        self.trading_symbol = trading_params.get('symbol', "PERP_BTC_USDT")
        self.order_number = 1000

        # 設定台灣時區
        self.tz = pytz.timezone('Asia/Taipei')

        # Set up logger
        self.logger = self.setup_logger(name='MakerStrategy', log_file='maker_strategy.log')
        self.logger.info("maker Strategy initialization completed")
    
    async def process_market_data(self, channel: str, data: dict, redis_client: aioredis.Redis) -> None:
        if channel == f"[MD]{self.trading_symbol}-orderbook" and data['ts'] >= self.time + self.time_interval:
            # cancel all orders
            cancel_all_signal = SignalData(target='cancel_all_orders', timestamp=int(time.time() * 1000))
            print("cancel all orders: ", cancel_all_signal)
            await self.publish_signal(cancel_all_signal)
            self.time = data['ts']
            self.order_book = data['data']
            self.mid_price = (self.order_book.get('asks')[0][0] + self.order_book.get('bids')[0][0]) / 2
            print(f"mid price: {self.mid_price}, ts: {self.time}")
            print(f"spread: {self.order_book.get('asks')[0][0] - self.order_book.get('bids')[0][0]}")
            best_ask = self.order_book.get('asks')[0][0]
            best_bid = self.order_book.get('bids')[0][0]
            
            for i in range(2):
                ask_price = best_ask - i * self.tick_size
                bid_price = best_bid + i * self.tick_size
                if ask_price > self.mid_price:
                    print("position size: ", self.single_position_size)
                    quantity = round((self.single_position_size / ask_price), self.limit_quantity_demical)
                    print(f"quantity: {quantity}")
                    open_short_signal = SignalData(
                        timestamp=int(time.time() * 1000),
                        target='send_order',
                        action=OrderAction.OPEN,
                        position_side=PositionSide.SHORT,
                        order_type=OrderType.LIMIT,
                        symbol=self.trading_symbol,
                        price=round(ask_price, 4),
                        quantity=quantity,
                        order_number=self.order_number,
                        reduce_only=False,
                    )
                    self.order_number += 1
                    await self.publish_signal(open_short_signal)
                if bid_price < self.mid_price:
                    print("position size: ", self.single_position_size)
                    quantity = round((self.single_position_size / bid_price), self.limit_quantity_demical)
                    print(f"quantity: {quantity}")
                    open_long_signal = SignalData(
                        timestamp=int(time.time() * 1000),
                        target="send_order",
                        action=OrderAction.OPEN,
                        position_side=PositionSide.LONG,
                        order_type=OrderType.LIMIT,
                        symbol=self.trading_symbol,
                        price=round(bid_price, 4),
                        quantity=quantity,
                        order_number=self.order_number,
                        reduce_only=False,
                    )
                    self.order_number += 1
                    await self.publish_signal(open_long_signal)

            
            # self.logger.info(f"Processing orderbook data: {self}")
    
    async def execute(self, channel: str, data: dict, redis_client: aioredis.Redis) -> None:
        self.redis_client = redis_client
        await asyncio.sleep(0.1)
        if channel.startswith("[MD]"):
            await self.process_market_data(channel, data, redis_client)
        elif channel.startswith("[PD]"):
            await self.process_private_data(channel, data, redis_client)
        else:
            self.logger.warning(f"[{self.strategy_name}] Unknown channel: {channel}")
            
