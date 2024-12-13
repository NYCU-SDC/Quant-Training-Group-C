import json
import asyncio
import logging
from redis import asyncio as aioredis  # Redis client for async operations


class Strategy:
    """Base class for strategies."""

    def __init__(self, signal_channel, config=None):
        self.signal_channel = signal_channel
        self.strategy_name = "BaseStrategy"
        self.order_id = []
        self.ask_limit_order = {}
        self.bid_limit_order = {}
        self.number = 0

        # Configuration for strategy
        self.config = config or {
            "default_price": 96900,
            "default_quantity": 0.0001,
            "symbol": "SPOT_BTC_USDT",
        }

        # General logger
        self.logger = self.setup_logger(self.strategy_name)

        # Configure logger for filled orders
        self.fill_order_logger = self.setup_logger(
            f"{self.strategy_name}_fills", f"{self.strategy_name}_fill_orders.log"
        )

    def setup_logger(self, name, log_file=None, level=logging.INFO):
        """Setup and return a logger."""
        logger = logging.getLogger(name)
        logger.setLevel(level)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
        logger.addHandler(console_handler)

        # File handler (if specified)
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
            logger.addHandler(file_handler)

        return logger

    async def execute(self, channel, data, redis_client):
        """Main execution method."""
        await asyncio.sleep(0.1)

        if channel.startswith("[MD]"):
            await self.process_market_data(channel, data, redis_client)
        elif channel.startswith("[PD]"):
            await self.process_private_data(channel, data, redis_client)
        else:
            self.logger.warning(f"[{self.strategy_name}] Unknown channel: {channel}")

    async def process_market_data(self, channel, data, redis_client):
        """Handle market data (e.g., price updates)."""
        self.logger.info(f"[{self.strategy_name}] Processing market data from {channel}: {data}")

        # Example signal generation
        signal = self.create_order_signal(
            price=self.config["default_price"],
            quantity=self.config["default_quantity"],
            side="BUY",
            symbol=self.config["symbol"],
        )
        self.order_id.append(self.number)
        self.number += 1

        await self.publish_signal(signal, redis_client)

    async def process_private_data(self, channel, data, redis_client):
        """Handle private data (e.g., execution reports)."""
        self.logger.info(f"[{self.strategy_name}] Processing private data from {channel}: {data}")

        if channel == "[PD]executionreport":
            await self.handle_execution_report(data)
        elif channel == "[PD]position":
            self.logger.info(f"[{self.strategy_name}] Position update: {data}")
        elif channel == "[PD]balance":
            self.logger.info(f"[{self.strategy_name}] Balance update: {data}")
        else:
            self.logger.warning(f"[{self.strategy_name}] Unhandled private data channel: {channel}")

    async def handle_execution_report(self, execution_report):
        """Process an execution report."""
        try:
            client_order_id = execution_report["clientOrderId"]
            if (
                client_order_id in self.order_id
                or client_order_id in self.ask_limit_order
                or client_order_id in self.bid_limit_order
            ):
                msg_type = execution_report.get("msgType")
                if msg_type == 0:  # New order or fill
                    await self.handle_order_status_update(client_order_id, execution_report)
                elif msg_type == 1:  # Other messages
                    pass
                self.order_id.remove(client_order_id)
        except KeyError as e:
            self.logger.error(f"[{self.strategy_name}] Missing key in execution report: {e}")
        except Exception as e:
            self.logger.exception(f"[{self.strategy_name}] Error handling execution report: {e}")

    async def handle_order_status_update(self, client_order_id, execution_report):
        """Update order status based on execution report."""
        status = execution_report.get("status")
        side = execution_report.get("side")
        quantity = execution_report.get("executedQuantity", 0)
        price = execution_report.get("price", 0)

        if status == "FILLED":
            order_book = self.ask_limit_order if side == "SELL" else self.bid_limit_order
            if client_order_id in order_book:
                # Log the fill order details
                self.log_fill_order(client_order_id, side, price, quantity)

                # Update the order book
                order_book[client_order_id]["quantity"] -= quantity
                if order_book[client_order_id]["quantity"] <= 0:
                    del order_book[client_order_id]
                    self.logger.info(f"[{self.strategy_name}] Order {client_order_id} fully filled and removed.")
        elif status == "NEW":
            new_order = {"price": price, "quantity": execution_report["quantity"], "status": "PENDING"}
            if side == "BUY":
                self.bid_limit_order[client_order_id] = new_order
            elif side == "SELL":
                self.ask_limit_order[client_order_id] = new_order
            self.logger.info(f"[{self.strategy_name}] Added new order: {new_order}")

    def create_order_signal(self, price, quantity, side, symbol):
        """Generate an order signal."""
        return {
            "target": "send_order",
            "order_price": price,
            "order_quantity": quantity,
            "order_type": "LIMIT",
            "side": side,
            "symbol": symbol,
            "strategy_name": self.strategy_name,
            "order_id": self.number,
        }

    async def publish_signal(self, signal, redis_client):
        """Publish the generated signal to the Redis signal channel."""
        try:
            await redis_client.publish(self.signal_channel, json.dumps(signal))
            self.logger.info(f"[{self.strategy_name}] Published signal: {signal}")
        except Exception as e:
            self.logger.exception(f"[{self.strategy_name}] Error publishing signal: {e}")

    def log_fill_order(self, order_id, side, price, quantity):
        """Log the filled order details."""
        fill_details = {
            "order_id": order_id,
            "side": side,
            "price": price,
            "quantity": quantity,
            "strategy": self.strategy_name,
        }
        self.fill_order_logger.info(json.dumps(fill_details))
        self.logger.info(f"[{self.strategy_name}] Filled order logged: {fill_details}")
