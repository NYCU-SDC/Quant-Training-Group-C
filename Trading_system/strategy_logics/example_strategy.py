import json
import asyncio
import websockets
import time
import datetime
import hmac
import hashlib
from redis import asyncio as aioredis  # Redis client for async operations
from strategy_logics.strategy_init import Strategy
import logging

class ExampleStrategy(Strategy):
    """Example: send order each 1 sec."""
    def __init__(self, signal_channel):
        self.signal_channel = signal_channel
        self.strategy_name = "ExampleStrategy"
        self.order_id = []
        self.ask_limit_order = dict()
        self.bid_limit_order = dict()
        self.number = 0
        # General logger
        self.logger = self.setup_logger(self.strategy_name)

        # Configure logger for filled orders
        self.fill_order_logger = self.setup_logger(
            f"{self.strategy_name}_fills", f"{self.strategy_name}_fill_orders.log"
        )
    async def process_market_data(self, channel, data, redis_client):
        """Handle market data (e.g., price updates)."""
        self.logger.info(f"[{self.strategy_name}] Processing market data from {channel}: {data}")

        # Example signal generation
        signal = self.create_order_signal(
            price=96900,
            quantity=0.0001,
            side="BUY",
            symbol='SPOT_BTC_USDT',
        )

        self.order_id.append(self.number)
        self.number += 1

        await self.publish_signal(signal, redis_client)
                
            
