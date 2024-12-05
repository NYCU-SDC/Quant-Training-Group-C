import asyncio
import aiohttp
import time
import datetime
import json
import hmac, hashlib, base64
import logging
import sys
import os
from decimal import Decimal
from typing import Dict, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from WooX_REST_API_Client import WooX_REST_API_Client
from WooX_WebSocket_API_Client import WooXWebSocketStagingAPI


class ChaseOrderMaker:
    def __init__(self, rest_client, ws_client, symbol: str, max_size: float, max_order_size: float):
        self.rest_client = rest_client
        self.ws_client = ws_client
        self.symbol = symbol
        self.max_size = max_size
        self.max_order_size = max_order_size
        
        # Track current orders and market state
        self.current_orders: Dict[str, dict] = {}
        self.last_bid = None
        self.last_ask = None
        self.position_size = 0
        self.logger = logging.getLogger(__name__)
        
    async def start(self):
        """Start the chase order maker strategy"""
        # Subscribe to required market data
        config = {
            'bbo': True,  # Best bid/offer data
            'executionreport': True  # Order execution updates
        }
        
        try:
            await self.ws_client.subscribe(self.symbol, config)
            await self.monitor_market()
        except Exception as e:
            self.logger.error(f"Error starting strategy: {e}")
            raise

    async def monitor_market(self):
        """Monitor market data and manage orders"""
        while True:
            try:
                if self.ws_client.bbo_data.get(self.symbol):
                    bbo = self.ws_client.bbo_data[self.symbol]
                    await self.process_market_update(bbo)
                await asyncio.sleep(0.1)  # Prevent tight loop
                
            except Exception as e:
                self.logger.error(f"Error in market monitoring: {e}")
                await asyncio.sleep(1)  # Back off on error

    async def process_market_update(self, bbo_data):
        """Process market data updates and adjust orders"""
        if not bbo_data:
            return

        bid_price = Decimal(str(bbo_data.get('bid', 0)))
        ask_price = Decimal(str(bbo_data.get('ask', 0)))
        
        # Check if prices have changed
        if bid_price != self.last_bid or ask_price != self.last_ask:
            await self.adjust_orders(bid_price, ask_price)
            
        self.last_bid = bid_price
        self.last_ask = ask_price

    async def adjust_orders(self, bid_price: Decimal, ask_price: Decimal):
        """Adjust orders based on new market prices"""
        # Cancel existing orders
        await self.cancel_all_orders()
        
        # Calculate order sizes based on position
        available_size = self.max_size - abs(self.position_size)
        order_size = min(self.max_order_size, available_size)
        
        if order_size <= 0:
            return

        # Place new orders at touch
        tasks = []
        
        # Bid order
        bid_params = {
            'symbol': self.symbol,
            'side': 'BUY',
            'order_type': 'POST_ONLY',
            'order_price': float(bid_price),
            'order_quantity': float(order_size),
            'client_order_id': f"bid_{int(time.time() * 1000)}"
        }
        tasks.append(self.place_order(bid_params))
        
        # Ask order
        ask_params = {
            'symbol': self.symbol,
            'side': 'SELL',
            'order_type': 'POST_ONLY',
            'order_price': float(ask_price),
            'order_quantity': float(order_size),
            'client_order_id': f"ask_{int(time.time() * 1000)}"
        }
        tasks.append(self.place_order(ask_params))
        
        await asyncio.gather(*tasks)

    async def place_order(self, params):
        """Place a new order"""
        try:
            response = await self.rest_client.send_order(params)
            if response.get('status') == 'success':
                self.current_orders[params['client_order_id']] = params
                self.logger.info(f"Order placed successfully: {params}")
            else:
                self.logger.error(f"Order placement failed: {response}")
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")

    async def cancel_all_orders(self):
        """Cancel all existing orders"""
        try:
            await self.rest_client.cancel_all_pending_orders()
            self.current_orders.clear()
        except Exception as e:
            self.logger.error(f"Error cancelling orders: {e}")

    def update_position(self, size_delta: float):
        """Update the current position size"""
        self.position_size += size_delta
        self.logger.info(f"Position updated: {self.position_size}")

async def main():
    # Initialize API clients
    app_id = '460c97db-f51d-451c-a23e-3cce56d4c932'
    api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
    api_secret = 'FWQGXZCW4P3V4D4EN4EIBL6KLTDA'
    rest_client = WooX_REST_API_Client(api_key, api_secret)
    ws_client = WooXWebSocketStagingAPI(app_id, api_key, api_secret)
    
    # Create and start the strategy
    strategy = ChaseOrderMaker(
        rest_client=rest_client,
        ws_client=ws_client,
        symbol='PERP_BTC_USDT',
        max_size=0.009,  # Maximum position size in BTC
        max_order_size=0.0002  # Maximum size per order
    )
    
    await strategy.start()