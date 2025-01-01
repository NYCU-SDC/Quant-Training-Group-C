import json
import logging
import asyncio
from typing import Optional, Dict
from redis import asyncio as aioredis
from enum import Enum
from datetime import datetime
from dataclasses import dataclass
import os

class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    POST_ONLY = "POST_ONLY"

# order 的 side
class PositionSide(Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class OrderAction(Enum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"

@dataclass
class SignalData:
    timestamp: int
    target: str
    action: Optional[OrderAction] = None
    position_side: Optional[PositionSide] = None
    order_type: Optional[OrderType] = None
    symbol: Optional[str] = None
    quantity: Optional[float] = None
    price: Optional[float] = None
    reduce_only: bool = False
    margin_mode: str = 'CROSS'
    order_number: Optional[int] = None

    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp,
            'target': self.target,
            'action': self.action.value if self.action is not None else None,
            'position_side': self.position_side.value if self.position_side is not None else None,
            'order_type': self.order_type.value if self.order_type is not None else None,
            'symbol': self.symbol,
            'quantity': self.quantity,
            'price': self.price,
            'order_id': self.order_number,
            'reduce_only': self.reduce_only,
            'margin_mode': self.margin_mode
        }

class Strategy:
    """Base class for all trading strategies"""
    
    def __init__(self, signal_channel: str, config: Dict = None):
        """
        Initialize strategy with configuration
        Args:
            signal_channel: Redis channel for publishing signals
            config: Strategy configuration dictionary
        """
        self.signal_channel = signal_channel
        self.strategy_name = self.__class__.__name__
        self.config = config or {}
        
        # Basic strategy states
        self.current_position: Optional[PositionSide] = None
        self.position_size: float = 0.0
        self.net_position_value: float = 0.0
        self.entry_price: Optional[float] = None
        self.init_capital = 0.0
        self.capital = self.init_capital
        self.cash = self.capital
        self.position_ratio = 0.0
        
        # Order tracking
        self.order_id = []
        self.ask_limit_order = {}
        self.bid_limit_order = {}
        self.order_number = 0
        # Managers and logging can be defined here or in subclass
        # For simplicity, assume self.redis_client 在 subclass 中賦值
        self.redis_client = None
        
        self.logger = self.setup_logger(self.strategy_name)

    def setup_logger(self, name: str, log_file: Optional[str] = 'maker_strategy.log', level: int = logging.INFO) -> logging.Logger:
        """
        Sets up a logger that logs both to the console and a log file.

        Args:
            name: Name of the logger.
            log_file: Path to the log file where logs should be stored (default is 'maker_strategy.log').
            level: Logging level (default is logging.INFO).

        Returns:
            Logger instance.
        """
        logger = logging.getLogger(name)
        logger.setLevel(level)

        # Avoid adding duplicate handlers
        if not logger.handlers:
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            
            # Console handler for logging to console
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

            # File handler for logging to a file
            if log_file:
                print("!!!!!!!!!!!!!!!!!!!!!!!!!!")
                # If log_file is just a filename, join it with 'logs/'
                if not os.path.dirname(log_file):  # If no directory specified
                    log_file = os.path.join('logs', log_file)  # Join with 'logs/' folder

                print("Log file path:", log_file)

                # Ensure the directory exists before creating the log file
                log_dir = os.path.dirname(log_file)
                if not os.path.exists(log_dir):
                    print("Creating directory:", log_dir)
                    os.makedirs(log_dir)  # Create the directory if it doesn't exist


                # Create or append the log file
                file_handler = logging.FileHandler(log_file)
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)

        return logger

    async def publish_signal(self, signal_data: SignalData) -> None:
        """
        Publish trading signal to Redis.
        Also update current_position status here since this is a good place to confirm the action.
        """
        # Update internal position state before publishing the signal
        if signal_data.target == "send_order" and signal_data.action is not None:  
            if signal_data.position_side == PositionSide.LONG and signal_data.order_type == "LIMIT":
                self.bid_limit_order[signal_data.order_number] = {
                    "price": signal_data.price,
                    "quantity": signal_data.quantity,
                    "status": "PENDING"
                }
            elif signal_data.position_side == PositionSide.SHORT and signal_data.order_type == "LIMIT":
                self.ask_limit_order[signal_data.order_number] = {
                    "price": signal_data.price,
                    "quantity": signal_data.quantity,
                    "status": "PENDING"
                }
            self.order_id.append(signal_data.order_number)
            # if signal_data.action == OrderAction.CLOSE:
            #     self.current_position = None
            #     self.position_size = 0.0
            #     self.entry_price = None
            # elif signal_data.action == OrderAction.OPEN:
            #     self.current_position = signal_data.position_side
            #     self.position_size = signal_data.quantity
            #     # 如果有需要設定 entry_price，可以在此處加入邏輯
            #     # self.entry_price = signal_data.price or current market price if needed
            

        if self.redis_client:
            signal_dict = signal_data.to_dict()
            await self.redis_client.publish(self.signal_channel, json.dumps(signal_dict))
            self.logger.info(f"Published signal to {self.signal_channel}: {signal_dict}")
        else:
            self.logger.warning("Redis client not available, cannot publish signal.")


    async def process_market_data(self, channel: str, data: dict, redis_client: aioredis.Redis) -> None:
        raise NotImplementedError("Subclass must implement process_market_data")

    async def process_private_data(self, channel: str, data: dict, redis_client: aioredis.Redis) -> None:
        """Handle private data (e.g., execution reports)."""
        # self.logger.info(f"[{self.strategy_name}] Processing private data from {channel}: {data}")

        if channel == "[PD]executionreport":
            print(f"Execution report: {data}")
            await self.handle_execution_report(data['data'])
        elif channel == "[PD]position":
            self.logger.info(f"[{self.strategy_name}] Position update: {data}")
        elif channel == "[PD]balance":
            self.logger.info(f"[{self.strategy_name}] Balance update: {data}")
        else:
            self.logger.warning(f"[{self.strategy_name}] Unhandled private data channel: {channel}")

    async def handle_execution_report(self, execution_report: dict) -> None:
        """Process an execution report."""
        try:
            
            client_order_id = execution_report["clientOrderId"]

            if (
                client_order_id in self.order_id
                or client_order_id in self.ask_limit_order
                or client_order_id in self.bid_limit_order
            ):
                msg_type = execution_report.get("msgType")
                if msg_type == 0:  # New order or filled
                    await self.handle_order_status_update(client_order_id, execution_report)
                elif msg_type == 1:  # Edit rejected
                    print(f"[{self.strategy_name}] Edit rejected: {execution_report}")
                    #inform order manager
                elif msg_type == 2:  # Cancel rejected
                    print(f"[{self.strategy_name}] Cancel rejected: {execution_report}")
                    #inform order manager
                elif msg_type == 3:  # Cancelled
                    print(f"[{self.strategy_name}] Order cancelled: {execution_report}")
                    #inform order manager
                
        except KeyError as e:
            self.logger.error(f"[{self.strategy_name}] Missing key in execution report: {e}")
        except Exception as e:
            self.logger.exception(f"[{self.strategy_name}] Error handling execution report: {e}")

    async def handle_order_status_update(self, client_order_id: int, execution_report: dict) -> None:
        """Update order status based on execution report."""
        status = execution_report.get("status")
        side = execution_report.get("side")
        quantity = execution_report.get("executedQuantity", 0)
        price = execution_report.get("price", 0)
        print(f"hadle_order_status_update: {execution_report}")
        if status == "FILLED":
            order_book = self.ask_limit_order if side == "SELL" else self.bid_limit_order
            if client_order_id in order_book:
                # self.logger.info(f"[{self.strategy_name}] Filled order: {execution_report}")
                # Update the order book
                order_book[client_order_id]["quantity"] -= quantity
                if order_book[client_order_id]["quantity"] <= 0:
                    del order_book[client_order_id]
                    self.order_id.remove(client_order_id)
                    self.logger.info(f"[{self.strategy_name}] Order {client_order_id} fully filled and removed.")
                # Update position and PnL
                self.update_filled_order_report(client_order_id, execution_report)
        elif status == "NEW":
            new_order = {"price": price, "quantity": execution_report["quantity"], "status": "PENDING"}
            if side == "BUY":
                self.bid_limit_order[client_order_id] = new_order
            elif side == "SELL":
                self.ask_limit_order[client_order_id] = new_order
            self.logger.info(f"[{self.strategy_name}] Added new order: {new_order}")
        elif status == "PARTIAL_FILLED":
            order_book = self.ask_limit_order if side == "SELL" else self.bid_limit_order
            if client_order_id in order_book:
                # self.logger.info(f"[{self.strategy_name}] Partially filled order: {execution_report}")
                # Update the order book
                order_book[client_order_id]["quantity"] -= quantity
                if order_book[client_order_id]["quantity"] <= 0:
                    del order_book[client_order_id]
                    self.logger.info(f"[{self.strategy_name}] Order {client_order_id} partially filled {quantity} remain {order_book[client_order_id][quantity]}.")
                # Update position, PnL, and NAV
                self.update_filled_order_report(client_order_id, execution_report, partial=True)
        elif status == "CANCELLED":
            order_book = self.ask_limit_order if side == "SELL" else self.bid_limit_order
            if client_order_id in order_book:
                del order_book[client_order_id]
                self.logger.info(f"[{self.strategy_name}] Order {client_order_id} cancelled and removed.")
        print(f"ask_limit_order: {self.ask_limit_order}")
        print(f"bid_limit_order: {self.bid_limit_order}")
        print(f"position_size: {self.position_size}")
        print(f"position_value: {self.net_position_value}")
        print(f"cash: {self.cash}")
        print(f"capital: {self.capital}")

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
            self.position_size += executed_quantity
            self.cash -= fill_cost
        elif side == "SELL":
            self.position_size -= executed_quantity
            self.cash += fill_cost

        # Calculate net position value and NAV
        self.net_position_value = abs(self.position_size) * executed_price
        self.capital = self.cash + self.net_position_value  # NAV calculation

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
        raise NotImplementedError("Subclass must implement execute")

    def start(self) -> None:
        self.logger.info(f"Strategy {self.strategy_name} started")

    def stop(self) -> None:
        self.logger.info(f"Strategy {self.strategy_name} stopped")
