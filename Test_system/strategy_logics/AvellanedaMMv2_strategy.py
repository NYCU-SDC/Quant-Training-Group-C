"""
AvellanedaMMv2.py

改良版Avellaneda–Stoikov策略:
1) 監聽 [MD]PERP_ETH_USDT-bbo => 只有當bid/ask差異或時間超過 threshold 才更新掛單
2) 監聽 [PD]executionreport => 若有成交 => 更新 position_q => 視需要重新掛單或平倉
3) Log 只顯示關鍵事件: 策略開始/停止、下單、成交回報、倉位變動, 不印BBO
"""

import os
import math
import time
import json
import logging
import pytz
import numpy as np
from typing import Dict, Optional
from datetime import datetime
from collections import deque
from redis import asyncio as aioredis

#   Strategy, SignalData, (OrderType, PositionSide, OrderAction)
from strategy_logics.strategy_init import (
    Strategy,
    SignalData,
    OrderType,
    PositionSide,
    OrderAction
)

class AvellanedaMMv2(Strategy):
    """
    Avellaneda–Stoikov Market Making, WooX Hedge Mode
    - 僅在BBO變動超過閾值/或每隔N秒後 才重掛單(避免過度撤單/下單)
    - 監聽executionreport => 更新 position_q
    - Log僅記錄: start/stop, order發出, 成交, pos改變
    """

    def __init__(self, signal_channel: str, config: Dict = None):
        super().__init__(signal_channel, config)

        # 設置專屬logger => logs/avellaneda_mm_v2.log
        self.logger = logging.getLogger("AvellanedaMMv2")
        self.logger.setLevel(logging.INFO)
        os.makedirs("logs", exist_ok=True)
        fh = logging.FileHandler("logs/avellaneda_mm_v2.log")
        fh.setFormatter(logging.Formatter('%(asctime)s - AvellanedaMMv2 - %(levelname)s - %(message)s'))
        self.logger.addHandler(fh)

        self.strategy_name = "AvellanedaMMv2"

        if config is None:
            config = {}
        tp = config.get("trading_params", {})

        self.symbol       = tp.get("symbol", "PERP_ETH_USDT")
        self.max_position = tp.get("max_position", 0.15)
        self.order_size   = tp.get("order_size", 0.015)
        self.gamma        = tp.get("gamma", 0.3)
        self.sigma        = tp.get("sigma", 0.02)
        self.kappa        = tp.get("kappa", 1.5)
        # Crypto市場 => T=24*3600( 24h不關市, 假設1天週期 )
        self.T            = tp.get("T", 24*3600)

        # 庫存
        self.position_q   = 0.0  # ETH
        self.last_bbo_update_time = 0.0
        self.last_bid = None
        self.last_ask = None

        self.last_order_update_ts = 0.0  # 上次重掛單時間
        self.order_update_interval = 2.0 # e.g. 每2秒 允許做一次撤/重掛

        self.redis_client = None
        self.logger.info(f"[{self.strategy_name}] Initialized. symbol={self.symbol}, max_pos={self.max_position}, "
                         f"size={self.order_size}, gamma={self.gamma}, sigma={self.sigma}, kappa={self.kappa}, T={self.T}")

    def start(self):
        self.logger.info(f"Strategy {self.strategy_name} started")

    def stop(self):
        self.logger.info(f"Strategy {self.strategy_name} stopped")

    async def execute(self, channel: str, data: dict, redis_client: aioredis.Redis) -> None:
        """
        同時監聽2種channel:
        1) [MD]...-bbo => 用於更新bid/ask, 計算中間價, 只有當價格差超過閾值or時間>2s -> 重掛單
        2) [PD]executionreport => 成交回報 => 更新position_q => 記錄log => or re-quote
        """
        try:
            self.redis_client = redis_client

            # 決定 channel 類型
            if "[MD]" in channel and "bbo" in channel:
                await self.on_bbo_update(data)
            elif "[PD]" in channel and "executionreport" in channel:
                await self.on_execution_report(data)
            else:
                # 不處理
                return

        except Exception as e:
            self.logger.error(f"Error in {self.strategy_name} execute: {e}")

    async def on_bbo_update(self, raw_data: dict):
        """
        處理 bbo => bid / ask
        只在 diff>某閾值 或時間>2秒 => 重新掛單
        """
        try:
            if isinstance(raw_data, str):
                raw_data = json.loads(raw_data)
            bbo_data = raw_data.get("data", {})
            if not bbo_data:
                return
            
            bid = float(bbo_data.get("bid", 0))
            ask = float(bbo_data.get("ask", 0))
            if bid<=0 or ask<=0:
                return

            # for debug (不寫info, 以免log太多)
            self.logger.debug(f"Received BBO: bid={bid}, ask={ask}")

            now_ts = time.time()
            # 1) 若上次掛單時間 + 2秒後 => 可以考慮重掛
            # 2) 或 bid/ask 與上次差距 > X => 重掛
            #   e.g. X=1.0
            price_diff_threshold = 1.0

            is_time_ok = (now_ts - self.last_order_update_ts) >= self.order_update_interval
            price_changed = (self.last_bid is None or abs(bid - self.last_bid) > price_diff_threshold 
                             or abs(ask - self.last_ask) > price_diff_threshold)

            if is_time_ok or price_changed:
                self.logger.debug("BBO changed enough or time is up => re-quote now.")
                self.last_order_update_ts = now_ts
                self.last_bid = bid
                self.last_ask = ask
                await self.do_requote(bid, ask)

        except Exception as e:
            self.logger.error(f"[on_bbo_update] error: {e}")

    async def on_execution_report(self, raw_data: dict):
        """
        處理私有成交 => 更新 position_q => log => (可再re-quote)
        raw_data 可能包含 fill size, side=BUY/SELL, pos_side=LONG/SHORT, ...
        """
        try:
            if isinstance(raw_data, str):
                raw_data = json.loads(raw_data)
            rep_data = raw_data.get("data", {})
            if not rep_data:
                return

            status = rep_data.get("status")
            # 只在 FILLED / PARTIALLY_FILLED 時更新
            if status not in ("FILLED", "PARTIALLY_FILLED"):
                return

            # side= "BUY"/"SELL", position_side= "LONG"/"SHORT"
            side = rep_data.get("side")
            pos_side = rep_data.get("position_side")
            fill_qty = float(rep_data.get("executedQuantity", 0))
            if fill_qty<=0:
                return

            # 方向 => 影響 self.position_q
            #  * Hedge mode: LONG => position_q += fill_qty, SHORT => position_q -= fill_qty
            old_q = self.position_q
            if pos_side=="LONG":
                self.position_q += fill_qty if side=="BUY" else -fill_qty
            elif pos_side=="SHORT":
                self.position_q -= fill_qty if side=="SELL" else +fill_qty

            self.logger.info(f"[exec_report] status={status}, side={side}, pos_side={pos_side}, fill_qty={fill_qty}, "
                             f"pos_q from {old_q} => {self.position_q}")

            # 若 position_q 變化 => 需檢查是否超過 max_position => 可能要 re-quote
            # 這裡直接 do_requote
            now_ts = time.time()
            if (now_ts - self.last_order_update_ts) > 1.0:
                # 1秒後可 re-quote
                self.last_order_update_ts = now_ts
                # 這裡需要最新 bid/ask => self.last_bid/self.last_ask (可能略舊),
                #   或您可以等下次 on_bbo_update 來re-quote. 
                if self.last_bid and self.last_ask:
                    await self.do_requote(self.last_bid, self.last_ask)

        except Exception as e:
            self.logger.error(f"[on_execution_report] error: {e}")

    async def do_requote(self, bid: float, ask: float):
        """
        依 Avellaneda–Stoikov 公式計算掛單
        (簡化: mid=(bid+ask)/2, remain=T(24h?), r, big_spread, ...
        => emit 2 or 1 signals
        => 只記錄下單log, 不記錄 bid/ask
        """
        try:
            mid = 0.5*(bid + ask)

            # remain = T - current_time ??? => for demonstration: remain= T
            remain = float(self.T)
            # r = mid - position_q*g*sigma^2*remain
            r = mid - self.position_q * self.gamma * (self.sigma**2)*remain
            # δ= gamma*sigma^2*remain + 2/gamma ln(1+ gamma/kappa)
            big_spread = self.gamma*(self.sigma**2)*remain + (2.0/self.gamma)*math.log(1.0 + (self.gamma/self.kappa))
            half_spread = big_spread*0.5

            my_bid = round(r - half_spread, 2)
            my_ask = round(r + half_spread, 2)

            # 建立掛單
            new_orders = []
            if abs(self.position_q)< self.max_position:
                # 買
                buy_sig = SignalData(
                    timestamp=int(time.time()*1000),
                    action=OrderAction.OPEN,
                    position_side=PositionSide.LONG,
                    order_type=OrderType.LIMIT,
                    symbol=self.symbol,
                    quantity=self.order_size,
                    price=my_bid,
                    reduce_only=False,
                    margin_mode="CROSS"
                )
                new_orders.append(buy_sig)

                # 賣
                sell_sig = SignalData(
                    timestamp=int(time.time()*1000),
                    action=OrderAction.OPEN,
                    position_side=PositionSide.SHORT,
                    order_type=OrderType.LIMIT,
                    symbol=self.symbol,
                    quantity=self.order_size,
                    price=my_ask,
                    reduce_only=False,
                    margin_mode="CROSS"
                )
                new_orders.append(sell_sig)
            else:
                # 只掛反向
                if self.position_q>0:
                    # 只掛賣
                    sell_sig = SignalData(
                        timestamp=int(time.time()*1000),
                        action=OrderAction.OPEN,
                        position_side=PositionSide.SHORT,
                        order_type=OrderType.LIMIT,
                        symbol=self.symbol,
                        quantity=self.order_size,
                        price=my_ask,
                        reduce_only=False,
                        margin_mode="CROSS"
                    )
                    new_orders.append(sell_sig)
                else:
                    # 只掛買
                    buy_sig = SignalData(
                        timestamp=int(time.time()*1000),
                        action=OrderAction.OPEN,
                        position_side=PositionSide.LONG,
                        order_type=OrderType.LIMIT,
                        symbol=self.symbol,
                        quantity=self.order_size,
                        price=my_bid,
                        reduce_only=False,
                        margin_mode="CROSS"
                    )
                    new_orders.append(buy_sig)

            # 寫log (策略只顯示發送訂單, 不顯示 BBO detail)
            for sig in new_orders:
                await self.publish_signal(sig)
                self.logger.info(f"[do_requote] Place LimitOrder => {sig.to_dict()}")

            # done
        except Exception as e:
            self.logger.error(f"[do_requote] error: {e}")
