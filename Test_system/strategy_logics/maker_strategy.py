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
        self.init_capital = trading_params.get('init_capital', 1000)
        self.grid_depth = trading_params.get('grid_depth', 1)
        self.spread_percentage = trading_params.get('spread_percentage', 0.1)
        self.capital = self.init_capital
        self.cash = 0
        self.position_size = -0.4345
        self.net_position_value = 0.0
        self.position_ratio = 0.0
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
            self.best_ask = self.order_book.get('asks')[0][0]
            self.best_bid = self.order_book.get('bids')[0][0]
            print(f"best ask: {self.best_ask}, best bid: {self.best_bid}")
            self.adjust_tick_size()
            self.net_position_value = self.position_size * self.mid_price
            self.cash = self.capital - abs(self.net_position_value)
            print(f"mid price: {self.mid_price}, ts: {self.time}")
            print(f"spread: {self.order_book.get('asks')[0][0] - self.order_book.get('bids')[0][0]}")
            
            
            for i in range(self.grid_depth):
                self.ask_price = self.mid_price + (self.grid_depth - i+1) * self.tick_size 
                self.bid_price = self.mid_price - (self.grid_depth - i+1) * self.tick_size 
                if i == 0:
                    self.closest_ask = self.ask_price
                    self.closest_bid = self.bid_price
                self.adjust_prices()
                if self.ask_price > self.mid_price:
                    print("position size: ", self.single_position_size)
                    quantity = round((self.single_position_size / self.ask_price), self.limit_quantity_demical)
                    print(f"quantity: {quantity}")
                    open_short_signal = SignalData(
                        timestamp=int(time.time() * 1000),
                        target='send_order',
                        action=OrderAction.OPEN,
                        position_side=PositionSide.SHORT,
                        order_type=OrderType.POST_ONLY,
                        symbol=self.trading_symbol,
                        price=round(self.ask_price, 1),
                        quantity=quantity,
                        order_number=self.order_number,
                        reduce_only=False,
                    )
                    self.order_number += 1
                    await self.publish_signal(open_short_signal)
                    # asyncio.sleep(0.5)
                if self.bid_price < self.mid_price:
                    print("position size: ", self.single_position_size)
                    quantity = round((self.single_position_size / self.bid_price), self.limit_quantity_demical)
                    print(f"quantity: {quantity}")
                    open_long_signal = SignalData(
                        timestamp=int(time.time() * 1000),
                        target="send_order",
                        action=OrderAction.OPEN,
                        position_side=PositionSide.LONG,
                        order_type=OrderType.POST_ONLY,
                        symbol=self.trading_symbol,
                        price=round(self.bid_price, 1),
                        quantity=quantity,
                        order_number=self.order_number,
                        reduce_only=False,
                    )
                    self.order_number += 1
                    await self.publish_signal(open_long_signal)
                # sleep 0.1s to avoid sending too many orders
                await asyncio.sleep(1.5)

            open_short_signal = SignalData(
                timestamp=int(time.time() * 1000),
                target='send_order',
                action=OrderAction.OPEN,
                position_side=PositionSide.SHORT,
                order_type=OrderType.POST_ONLY,
                symbol=self.trading_symbol,
                price=round(self.mid_price + 0.3, 1),
                quantity=0.01,
                order_number=self.order_number,
                reduce_only=False,
            )
            self.order_number += 1
            await self.publish_signal(open_short_signal)
            open_long_signal = SignalData(
                timestamp=int(time.time() * 1000),
                target="send_order",
                action=OrderAction.OPEN,
                position_side=PositionSide.LONG,
                order_type=OrderType.POST_ONLY,
                symbol=self.trading_symbol,
                price=round(self.mid_price - 0.3, 1),
                quantity=0.01,
                order_number=self.order_number,
                reduce_only=False,
            )
            self.order_number += 1
            await self.publish_signal(open_long_signal)
            
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
            self.order_book["asks"][:3]
            if order_type == "ask"
            else self.order_book["bids"][:3]
        )

        # Process top entries in place
        for i in range(len(top_entries)):
            price, quantity = top_entries[i]
            if price in delist_requests:
                # Adjust the quantity or mark for removal
                quantity -= delist_requests[price]
                if quantity > 0.15:
                    top_entries[i][1] = quantity  # Update in place
                else:
                    top_entries[i] = None  # Mark for removal
            elif quantity < 0.13:
                top_entries[i] = None

        # Remove marked entries and update the order book
        top_entries = [entry for entry in top_entries if entry is not None]
        if order_type == "ask":
            self.order_book["asks"] = top_entries + self.order_book["asks"][self.grid_depth:]
        else:
            self.order_book["bids"] = top_entries + self.order_book["bids"][self.grid_depth:]

        print(f"Delisted {order_type} orders: {list(delist_requests.keys())}")

    def adjust_tick_size(self):
        """
        Adjust tick size as a percentage of the current bid-ask spread, respecting a minimum tick size.
        """
        self.spread = self.best_ask - self.best_bid

        # Ensure spread is non-zero to avoid division errors
        if self.spread <= 0:
            self.tick_size = 0.1  # Fallback to the minimum tick size
        else:
            # Use a percentage of the spread for the tick size
            calculated_tick_size = self.spread * self.spread_percentage

            # Enforce the minimum tick size
            self.tick_size = max(0.1, round(calculated_tick_size, 1))

        print(f"Adjusted tick size (percentage of spread, min 0.1): {self.tick_size}")

    def adjust_prices(self) -> None:
        """
        Adjust bid and ask prices based on tick size and position ratio.
        """
        if not self.mid_price or not self.tick_size:
            return None, None

        # Adjustment factor for position ratio
        ask_spread = abs(self.best_ask - self.ask_price)
        bid_spread = abs(self.bid_price - self.best_bid)
        self.position_ratio = self.net_position_value / self.capital
        # Adjust prices
        if self.position_ratio < 0:
            # Adjust ask price
            self.ask_price = self.ask_price + ask_spread * abs(self.position_ratio)
            self.bid_price = self.bid_price + self.tick_size * abs(self.position_ratio)
            print(f"Adjusted Ask Price: {self.ask_price}, len: {self.ask_price - self.mid_price}")
            print(f"mid price: {self.mid_price}")
            print(f"Adjusted Bid Price: {self.bid_price}, len: {self.bid_price - self.mid_price}")
        elif self.position_ratio > 0:
            # Adjust bid price
            self.bid_price = self.bid_price - bid_spread * abs(self.position_ratio)
            self.ask_price = self.ask_price - self.tick_size * abs(self.position_ratio)

        # Ensure bid is below mid_price and ask is above mid_price
        self.bid_price = round(self.bid_price, 1)
        self.ask_price = round(self.ask_price, 1)

        self.bid_price = min(self.bid_price, self.mid_price)
        self.ask_price = max(self.ask_price, self.mid_price)
        print(f"Adjusted Bid Price: {self.bid_price}, Adjusted Ask Price: {self.ask_price}")

    async def delist_orders(self):
        print("Delisting orders...")
        self.delist_self_orders('ask')
        self.delist_self_orders('bid')
    
    def update_filled_order_report(self, client_order_id: int, execution_report: dict, partial: bool = False) -> None:
        """
        Updates the filled order report JSON file with position, net position, PnL, and NAV.

        Args:
            client_order_id: ID of the filled order.
            execution_report: Execution report dictionary.
            partial: Flag indicating if this is a partial fill (default is False).
        """
        timestamp = datetime.now().isoformat()
        side = execution_report.get("side")
        executed_price = float(execution_report.get("price", 0))
        executed_quantity = float(execution_report.get("executedQuantity", 0))
        fill_cost = executed_price * executed_quantity

        # Update position and cash
        if side == "BUY":
            if executed_quantity > 0.01:
                open_short_signal = SignalData(
                    timestamp=int(time.time() * 1000),
                    target='send_order',
                    action=OrderAction.OPEN,
                    position_side=PositionSide.SHORT,
                    order_type=OrderType.POST_ONLY,
                    symbol=self.trading_symbol,
                    price=round(executed_price + self.tick_size, 1),
                    quantity=0.01,
                    order_number=self.order_number,
                    reduce_only=False,
                )
                self.order_number += 1
                self.publish_signal(open_short_signal)
            self.position_size += executed_quantity
        elif side == "SELL":
            if executed_quantity > 0.01:
                open_long_signal = SignalData(
                    timestamp=int(time.time() * 1000),
                    target="send_order",
                    action=OrderAction.OPEN,
                    position_side=PositionSide.LONG,
                    order_type=OrderType.POST_ONLY,
                    symbol=self.trading_symbol,
                    price=round(executed_price - self.tick_size, 1),
                    quantity=0.01,
                    order_number=self.order_number,
                    reduce_only=False,
                )
                self.order_number += 1
                self.publish_signal(open_long_signal)
            self.position_size -= executed_quantity

        # Calculate net position value and NAV
        self.net_position_value = abs(self.position_size) * executed_price

        # Calculate realized PnL for this fill
        realized_pnl = 0
        if side == "SELL":
            realized_pnl = executed_quantity * (executed_price - (self.entry_price or executed_price))
        elif side == "BUY":
            self.entry_price = (
                (self.entry_price * (self.position_size - executed_quantity) + fill_cost) / self.position_size
                if self.position_size > 0
                else executed_price
            )

        pnl = self.capital - self.init_capital  # Total PnL is NAV - initial capital

        # Prepare data to save
        report_data = {
            "timestamp": timestamp,
            "position_size": self.position_size,
            "net_position_value": self.net_position_value,
            "realized_pnl": realized_pnl,
            "total_pnl": pnl,
            "strategy_nav": self.capital,
            "partial_fill": partial
        }

        # Ensure the 'configs/' directory exists
        config_dir = "configs"
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        # Write to the JSON file in the 'configs/' folder
        json_file = os.path.join(config_dir, "filled_order_report.json")
        try:
            if os.path.exists(json_file):
                with open(json_file, "r") as f:
                    existing_data = json.load(f)
            else:
                existing_data = []

            existing_data.append(report_data)

            with open(json_file, "w") as f:
                json.dump(existing_data, f, indent=4)
            self.logger.info(f"[{self.strategy_name}] Updated filled order report in configs: {report_data}")
        except Exception as e:
            self.logger.exception(f"[{self.strategy_name}] Error writing filled order report in configs: {e}")

    async def execute(self, channel: str, data: dict, redis_client: aioredis.Redis) -> None:
        self.redis_client = redis_client
        await asyncio.sleep(0.1)
        if channel.startswith("[MD]"):
            await self.process_market_data(channel, data, redis_client)
        elif channel.startswith("[PD]"):
            await self.process_private_data(channel, data, redis_client)
        else:
            self.logger.warning(f"[{self.strategy_name}] Unknown channel: {channel}")
            
