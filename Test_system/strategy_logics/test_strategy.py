import time
import logging
from typing import Dict, Optional
from redis import asyncio as aioredis

from strategy_logics.strategy_init import (
    Strategy,
    SignalData,
    OrderType,
    PositionSide,
    OrderAction
)

logger = logging.getLogger('Test strategy')

class TestStrategy(Strategy):
    """
    一個簡易測試策略示例：
    - 每當偵測到新的一分鐘（例如 10:01、10:02、10:03），就執行一次動作：
      1) 如果目前無倉位 -> 建立一個多倉 (LONG)
      2) 如果目前是多倉 -> 平多後轉而建立一個空倉 (SHORT)
      3) 如果目前是空倉 -> 平空後轉而建立一個多倉 (LONG)
    - 下一分鐘到時，再重複上述邏輯。
    """
    def __init__(self, signal_channel: str, config: Optional[Dict] = None):
        """
        Args:
            signal_channel: 用來發交易訊號的 Redis 頻道 (e.g. "trading_signals")
            config: 策略設定
        """
        super().__init__(signal_channel, config)

        # 追蹤上一次偵測到的分鐘
        self.last_minute: Optional[int] = None

        # 可自訂要下單的數量 / 其他參數
        self.order_quantity = config.get("order_quantity", 0.001)
        self.margin_mode = config.get("margin_mode", "CROSS")

        self.logger.info("TestStrategy initialization completed")
    
    async def execute(self, channel: str, data: dict, redis_client: aioredis.Redis) -> None:
        """
        每次有任何訊息 (Market data / Private data) 時都會被呼叫。
        在這裡檢查是否進入新的一分鐘，若是，則執行建/平倉邏輯。
        """
        try:
            self.redis_client = redis_client

            current_timestamp = int(time.time())  # 取得當前 Unix time (秒)
            current_minute = current_timestamp // 60  # 整數分鐘

            # 每進入新的一分鐘，就執行一次策略邏輯
            if self.last_minute is None or current_minute != self.last_minute:
                self.last_minute = current_minute
                self.logger.info(f"--- New minute detected ({current_minute}) -> Checking position actions ---")

                # 邏輯：若無持倉 -> 開多；若有持倉 -> 先平倉，再開反向倉。
                if self.current_position is None:
                    # 建立多倉
                    await self.open_position(PositionSide.LONG)
                elif self.current_position == PositionSide.LONG:
                    # 先平多倉，再開空倉
                    await self.close_position(PositionSide.LONG)
                    await self.open_position(PositionSide.SHORT)
                elif self.current_position == PositionSide.SHORT:
                    # 先平空倉，再開多倉
                    await self.close_position(PositionSide.SHORT)
                    await self.open_position(PositionSide.LONG)

        except Exception as e:
            self.logger.error(f"Error in TestStrategy execute: {e}")
    
    async def open_position(self, side: PositionSide) -> None:
        """
        建立一個新的頭寸（多或空）
        """
        timestamp = int(time.time() * 1000)
        open_signal = SignalData(
            timestamp=timestamp,
            action=OrderAction.OPEN,
            position_side=side,
            order_type=OrderType.MARKET,  # 以 MARKET 為例
            symbol=self.config.get('symbol', 'PERP_BTC_USDT'),
            quantity=self.order_quantity,
            reduce_only=False,
            margin_mode=self.margin_mode
        )
        await self.publish_signal(open_signal)
        self.logger.info(f"Opened {side.value} position with quantity={self.order_quantity}")

    async def close_position(self, side: PositionSide) -> None:
        """
        平倉 (若策略目前在該側有倉位，則用 reduce_only=True 進行平倉)
        """
        timestamp = int(time.time() * 1000)
        close_signal = SignalData(
            timestamp=timestamp,
            action=OrderAction.CLOSE,
            position_side=side,
            order_type=OrderType.MARKET,
            symbol=self.config.get('symbol', 'PERP_BTC_USDT'),
            quantity=self.order_quantity,
            reduce_only=True,  # 平倉
            margin_mode=self.margin_mode
        )
        await self.publish_signal(close_signal)
        self.logger.info(f"Closed {side.value} position with quantity={self.order_quantity}")