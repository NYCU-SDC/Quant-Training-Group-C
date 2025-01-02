import os
import time
import logging
import asyncio
import json
from typing import Dict, Optional


# 其中包含 Strategy, SignalData, OrderType, PositionSide, OrderAction
from strategy_logics.strategy_init import (
    Strategy,
    SignalData,
    OrderType,
    PositionSide,
    OrderAction
)

class TestLimitStrategy(Strategy):
    """
    一個最簡單的測試策略：
    - 每 5 秒送一次限價單 (SELL, SHORT, CROSS)
    - order_price=98200, order_quantity=0.00012
    - 用於測試「為何市價單可成功、限價單卻被拒」的狀況
    """

    def __init__(self, signal_channel: str, config: Dict = None):
        super().__init__(signal_channel, config)
        
        # 策略 logger, 輸出到 logs/test_simple_limit_strategy.log
        self.logger = logging.getLogger("TestLimitStrategy")
        self.logger.setLevel(logging.INFO)
        os.makedirs("logs", exist_ok=True)
        file_handler = logging.FileHandler("logs/test_simple_limit_strategy.log")
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(file_handler)

        self.strategy_name = "TestLimitStrategy"
        self.logger.info(f"{self.strategy_name} initialized.")
        
        # 每 5 秒下一次單
        self.interval_sec = 5.0
        self.last_order_time = 0.0

        # 固定參數
        self.symbol         = "PERP_WOO_USDT"
        self.side           = "BUY"
        self.position_side  = PositionSide.LONG
        self.margin_mode    = "CROSS"
        self.order_price    = 0.22
        self.order_qty      = 190
        # 需檢查交易所最小下單量、最小名義金額、及是否允許 CROSS

    def start(self):
        self.logger.info(f"{self.strategy_name} started.")

    def stop(self):
        self.logger.info(f"{self.strategy_name} stopped.")

    async def execute(self, channel: str, data: dict, redis_client):
        """
        每當從 [MD]...kline / processed-kline 來的任何消息，就檢查是否超過 5 秒 => 送固定參數的限價單
        """
        try:
            self.redis_client = redis_client

            # 如果不是kline相關頻道, 直接return
            if "kline" not in channel and "processed-kline" not in channel:
                return

            now_time = time.time()
            if (now_time - self.last_order_time) >= self.interval_sec:
                # 準備Order Signal
                signal_obj = SignalData(
                    timestamp=int(now_time*1000),   # ms
                    action=OrderAction.OPEN,        # 開倉
                    position_side=self.position_side,
                    order_type=OrderType.LIMIT,
                    symbol=self.symbol,
                    quantity=self.order_qty,
                    price=self.order_price,
                    reduce_only=False,
                    margin_mode=self.margin_mode   # 指定 CROSS
                )

                # 發送signal
                await self.publish_signal(signal_obj)

                self.logger.info(
                    f"[{self.strategy_name}] Sent LIMIT order => side={self.side}, position_side={self.position_side.value}, "
                    f"margin_mode={self.margin_mode}, price={self.order_price}, qty={self.order_qty}"
                )

                self.last_order_time = now_time

        except Exception as e:
            self.logger.error(f"Error in {self.strategy_name} execute: {e}")
