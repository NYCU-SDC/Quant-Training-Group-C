import json
import asyncio
from redis import asyncio as aioredis
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"

class PositionType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class OrderAction(Enum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"

@dataclass
class SignalData:
    timestamp: int
    action: OrderAction
    position_type: PositionType
    order_type: OrderType
    symbol: str
    quantity: float
    price: Optional[float] = None  # Only Limit Order needed
    reduce_only: bool = False


class Strategy:
    """Base class for strategies."""
    def __init__(self, signal_channel: str):
        self.signal_channel = signal_channel
        self.current_position: Optional[PositionType] = None
        self.position_size: float = 0.0
        self.entry_price: Optional[float] = None

    async def execute(self, channel: str, data: dict, redis_client: aioredis.Redis):
        """Override this method in derived classes to implement specific strategy logic."""
        raise NotImplementedError("Strategy must implement the execute method")

    async def publish_signal(self, signal: SignalData, redis_client: aioredis.Redis):
        """Publish the generated signal to the Redis signal channel."""
        signal_dict = {
            "timestamp": signal.timestamp,
            "action": signal.action.value,
            "position_type": signal.position_type.value,
            "order_type": signal.order_type.value,
            "symbol": signal.symbol,
            "quantity": signal.quantity,
            "price": signal.price,
            "reduce_only": signal.reduce_only
        }
        await redis_client.publish(self.signal_channel, json.dumps(signal_dict))
        print(f"Published signal to channel {self.signal_channel}: {signal_dict}")

