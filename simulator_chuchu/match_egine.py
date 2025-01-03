import time
import asyncio
import logging
import aiofiles
from concurrent.futures import ThreadPoolExecutor
from collections import deque
import os

class MatchingEngine:
    def __init__(self, server):
        self.server = server
        self.order_book = {}
        self.trade = {}
        self.markprice = {}
        self.position = {"LONG": {}, "SHORT": {}} # hedge mode
        self.order_id_counter = 0
        self.trade_reports = deque()
        self.client_orders = {}
        self.spot_taker_fee = 0.001
        self.spot_maker_fee = 0.0008
        self.future_taker_fee = 0.0005
        self.future_maker_fee = 0.0002
        self.lock = asyncio.Lock()
        self.executor = ThreadPoolExecutor()
        logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger("MatchingEngine")

        # save file path
        self.trade_data_file_path = "trade_data.csv"
        self.position_data_file_path = "position_data.csv"
        self.running = True
        # initialuze trade_data.csv
        self.save_trade_data_to_csv_initialization = False 

    def generate_order_id(self):
        self.order_id_counter += 1
        return self.order_id_counter

    async def handle_order(self, order_data):
        try:
            symbol = order_data.get("symbol")
            client_order_id = order_data.get("client_order_id", 0)
            margin_mode = order_data.get("margin_mode", "CROSS")
            order_tag = order_data.get("order_tag", "default")
            order_type = order_data.get("order_type")
            price = order_data.get("order_price",0)
            quantity = order_data.get("order_quantity")
            amount = order_data.get("order_amount",0)
            reduce_only = order_data.get("reduce_only", False)
            visible_quantity = order_data.get("visible_quantity", quantity)
            side = order_data.get("side")
            position_side = order_data.get("position_side")

            if not all([symbol, side, order_type, quantity]):
                raise ValueError("Missing required parameters.")
            
            if symbol and side and order_type:
                order_id = self.generate_order_id()
                order = {
                    "order_id": order_id,
                    "client_order_id": client_order_id,
                    "symbol": symbol,
                    "margin_mode": margin_mode,
                    "order_tag": order_tag,
                    "side": side,
                    "position_side": position_side,
                    "order_type": order_type,
                    "price": price,
                    "quantity": quantity,
                    "visible_quantity": visible_quantity,
                    "amount": amount,
                    "filled_quantity": 0,
                    "filled_amount": 0,
                    "status": "open",
                    "reduce_only": reduce_only
                }

                if symbol not in self.order_book:
                    self.order_book[symbol] = {"buy": [], "sell": []}

                # order confirmation
                confirmation = {
                    "success": True,
                    "order_id": order_id,
                    "client_order_id": client_order_id,
                    "symbol": symbol,
                    "margin_mode": margin_mode,
                    "order_tag": order_tag,
                    "order_type": order_type,
                    "order_price": price,
                    "order_quantity": quantity,
                    "order_amount": amount,
                    "visible_quantity": visible_quantity,
                    "reduce_only": reduce_only,
                    "side": side,
                    "position_side": position_side,
                    "timestamp": str(time.time())
                }

                self.client_orders[client_order_id] = order
                asyncio.create_task(self.process_order(order))  

                # trade report
                trade_report = {
                    "msgType": 0,
                    "symbol": symbol,
                    "clientOrderId": client_order_id,
                    "orderId": order_id,
                    "type": order_type,
                    "side": side,
                    "position_side":position_side,
                    "quantity": quantity,
                    "price": price,
                    "tradeId": order_id,  # assume tradeId  == orderId 
                    "executedPrice": 0,
                    "executedQuantity": 0,
                    "fee": 0,
                    "feeAsset": "",  # 假設沒有手續費資產
                    "totalExecutedQuantity": 0,
                    "avgPrice": 0,
                    "status": "NEW",
                    "reason": "",
                    "orderTag": order_tag,
                    "totalFee":0,  
                    "feeCurrency": "",  # 假設沒有手續費幣種
                    "totalRebate": 0,  # 假設沒有回扣
                    "rebateCurrency": "",  # 假設沒有回扣幣種
                    "visible": visible_quantity,
                    "timestamp": int(time.time() * 1000),
                    "reduceOnly": reduce_only,
                    "maker": False,  
                    "leverage": 1,  # 假設沒有槓桿
                    "marginMode": margin_mode,
                }

                # update trade report
                self.trade_reports.append(trade_report)
                return confirmation

        except Exception as e:
            self.logger.exception(f"Error handling order: {e}")
            return {"success": False, "error": str(e)}

    async def process_order(self, order):
        try:
            order_type = order["order_type"]
            client_order_id = order["client_order_id"]
            self.logger.info(f"Start processing order: {client_order_id}, type: {order_type}")
            
            if order_type in ["MARKET", "ASK", "BID"]:
                await self.match_market_order(order)  
            elif order_type in ["LIMIT", "POST_ONLY"]:
                await self.match_limit_order(order)   
            elif order_type in ["IOC", "FOK"]:
                await self.match_ioc_fok_order(order) 
        except Exception as e:
            self.logger.exception(f"Error processing order: {e}")

    async def match_market_order(self, order):
        try:
            client_order_id = order["client_order_id"]
            self.logger.info(f"Start matching market order: {client_order_id}")
            symbol = order["symbol"]
            side = order["side"]
            quantity = order["quantity"]
            position_side = order["position_side"]
            
            if side == "BUY":
                trades = sorted(self.trade[symbol]["data"], key=lambda x: x["price"], reverse=True)
            else:
                trades = sorted(self.trade[symbol]["data"], key=lambda x: x["price"])
            
            remaining_quantity = quantity
            filled_quantity = 0
            filled_amount = 0
            trading_fees = 0
            total_fees = 0
            last_trade_timestamp = 0

            while remaining_quantity > 0: 
                # Wait for the trade to be updated
                while self.trade[symbol].get("ts", 0) == last_trade_timestamp:
                    await asyncio.sleep(0.1)  # Adjust the sleep time as needed

                # Update the last_trade_timestamp
                last_trade_timestamp = self.trade[symbol].get("ts", 0) 

                for trade in trades:       
                    if side == "BUY" and trade["side"] == "BUY":
                        trade_price = trade["price"]
                        trade_size = min(remaining_quantity, trade["size"])
                        trade_amount = trade_price * trade_size
                        
                        filled_quantity += trade_size
                        filled_amount += trade_amount
                        remaining_quantity -= trade_size
                    
                    elif side == "SELL" and trade["side"] == "SELL":
                        trade_price = trade["price"]
                        trade_size = min(remaining_quantity, trade["size"])
                        trade_amount = trade_price * trade_size
                        
                        filled_quantity += trade_size
                        filled_amount += trade_amount
                        remaining_quantity -= trade_size
            
                if filled_quantity > 0:
                    # weighted average
                    weighted_average_price = filled_amount / filled_quantity
                    
                    order["filled_quantity"] += filled_quantity
                    order["filled_amount"] += filled_amount
                    order["price"] = 0 # market order doesn't need price
                    
                    if remaining_quantity == 0:
                        order["status"] = "FILLED"
                    else:
                        order["status"] = "partially_FILLED"
                    
                    # update position
                    if side == "BUY":
                        if position_side == "LONG":
                            if symbol not in self.position["LONG"]:
                                self.position["LONG"][symbol] = 0
                            self.position["LONG"][symbol] += filled_quantity
                        elif position_side == "SHORT":
                            if symbol not in self.position["SHORT"]:
                                self.position["SHORT"][symbol] = 0
                            self.position["SHORT"][symbol] -= filled_quantity
                    else:  # side == "SELL"
                        if position_side == "LONG":
                            if symbol not in self.position["LONG"]:
                                self.position["LONG"][symbol] = 0
                            self.position["LONG"][symbol] -= filled_quantity
                        elif position_side == "SHORT":
                            if symbol not in self.position["SHORT"]:
                                self.position["SHORT"][symbol] = 0
                            self.position["SHORT"][symbol] += filled_quantity

                    # calculate fee
                    if "SPOT" in symbol:
                        trading_fees = self.spot_taker_fee*filled_amount
                    if "PERP" in symbol:
                        trading_fees = self.future_taker_fee*filled_amount
                    total_fees += trading_fees

                    # update orders
                    order = self.client_orders.get(client_order_id)
                    if order is not None:
                        self.client_orders[order["client_order_id"]] = order

                    # trade report
                    trade_report = {
                        "msgType": 0,
                        "symbol": symbol,
                        "clientOrderId": order["client_order_id"],
                        "orderId": order["order_id"],
                        "type": order["order_type"],
                        "side": side,
                        "position_side":position_side,
                        "quantity": order["quantity"],
                        "price": order["price"],
                        "tradeId": order["order_id"],  # assume tradeId  == orderId 
                        "executedPrice": weighted_average_price,
                        "executedQuantity": filled_quantity,
                        "fee": trading_fees,
                        "feeAsset": "",  # 假設沒有手續費資產
                        "totalExecutedQuantity": quantity - remaining_quantity,
                        "avgPrice": weighted_average_price,
                        "status": order["status"],
                        "reason": "",
                        "orderTag": order["order_tag"],
                        "totalFee": total_fees,  
                        "feeCurrency": "",  # 假設沒有手續費幣種
                        "totalRebate": 0,  # 假設沒有回扣
                        "rebateCurrency": "",  # 假設沒有回扣幣種
                        "visible": order["visible_quantity"],
                        "timestamp": int(time.time() * 1000),
                        "reduceOnly": order["reduce_only"],
                        "maker": False,  
                        "leverage": 1,  # 假設沒有槓桿
                        "marginMode": order["margin_mode"],
                    }

                    # update trade report
                    self.trade_reports.append(trade_report)
                    # save data
                    await self.save_trade_data_to_csv(trade_report, self.trade_data_file_path)

                    filled_quantity = 0
                    filled_amount = 0
                    trading_fees = 0

                # yield execution to other coroutines
                await asyncio.sleep(0)

            # remove orders
            order = self.client_orders.get(client_order_id)
            if order is not None:
                del self.client_orders[order["client_order_id"]]
                self.logger.info(f"Finish matching limit order: {client_order_id}")

        except Exception as e:
            self.logger.exception(f"Error matching market order: {e}")
    
    async def match_limit_order(self, order):
        try:
            client_order_id = order["client_order_id"]
            self.logger.info(f"Start matching limit order: {client_order_id}")
            symbol = order["symbol"]
            side = order["side"]
            price = order["price"]
            quantity = order["quantity"]
            position_side = order['position_side']

            remaining_quantity = quantity
            filled_quantity = 0
            filled_amount = 0
            trading_fees = 0
            total_fees = 0
            last_orderbook_timestamp = 0
            is_maker = False

            while remaining_quantity > 0:
                if order["client_order_id"] not in self.client_orders:
                    self.logger.info(f"Order {client_order_id} canceled or edited, stopping match.")
                    break
                # Wait for the orderbook to be updated
                while self.order_book[symbol].get("ts", 0) == last_orderbook_timestamp:
                    await asyncio.sleep(0.1)  # Adjust the sleep time as needed

                # Get the updated order (if edited)
                order = self.client_orders.get(client_order_id)
                if order is None:
                    self.logger.warning(f"Order with client_order_id {client_order_id} not found.")
                    break

                remaining_quantity = order["quantity"] - order["filled_quantity"]
                price = order["price"]

                # Update the last_orderbook_timestamp
                last_orderbook_timestamp = self.order_book[symbol].get("ts", 0)

                if side == "BUY":
                    ask_prices = [ask[0] for ask in self.order_book[symbol]["data"]["asks"]]
                    ask_quantities = [ask[1] for ask in self.order_book[symbol]["data"]["asks"]]

                    if len(ask_prices) == 0 or price < ask_prices[0]:
                        is_maker = True

                    for ask_price, ask_quantity in zip(ask_prices, ask_quantities):
                        if price >= ask_price:
                            trade_price = ask_price
                            trade_size = min(remaining_quantity, ask_quantity)
                            trade_amount = trade_price * trade_size

                            filled_quantity += trade_size
                            filled_amount += trade_amount
                            remaining_quantity -= trade_size
                        else:
                            break

                elif side == "SELL":
                    bid_prices = [bid[0] for bid in self.order_book[symbol]["data"]["bids"]][::-1]
                    bid_quantities = [bid[1] for bid in self.order_book[symbol]["data"]["bids"]][::-1]

                    if len(bid_prices) == 0 or price > bid_prices[0]:
                        is_maker = True
        
                    for bid_price, bid_quantity in zip(bid_prices, bid_quantities):
                        if price <= bid_price:
                            trade_price = bid_price
                            trade_size = min(remaining_quantity, bid_quantity)
                            trade_amount = trade_price * trade_size

                            filled_quantity += trade_size
                            filled_amount += trade_amount
                            remaining_quantity -= trade_size
                        else:
                            break

                if filled_quantity > 0:
                    # weighted average
                    weighted_average_price = filled_amount / filled_quantity
                    
                    order["filled_quantity"] += filled_quantity
                    order["filled_amount"] += filled_amount

                    if filled_quantity == quantity:
                        order["status"] = "FILLED"
                    else:
                        order["status"] = "partially_FILLED"

                    # update position
                    if side == "BUY":
                        if position_side == "LONG":
                            if symbol not in self.position["LONG"]:
                                self.position["LONG"][symbol] = 0
                            self.position["LONG"][symbol] += filled_quantity
                        elif position_side == "SHORT":
                            if symbol not in self.position["SHORT"]:
                                self.position["SHORT"][symbol] = 0
                            self.position["SHORT"][symbol] -= filled_quantity
                    else:  # side == "SELL"
                        if position_side == "LONG":
                            if symbol not in self.position["LONG"]:
                                self.position["LONG"][symbol] = 0
                            self.position["LONG"][symbol] -= filled_quantity
                        elif position_side == "SHORT":
                            if symbol not in self.position["SHORT"]:
                                self.position["SHORT"][symbol] = 0
                            self.position["SHORT"][symbol] += filled_quantity

                    # calculate fee
                    if "SPOT" in symbol:
                        trading_fees = self.spot_maker_fee * filled_amount if is_maker else self.spot_taker_fee * filled_amount
                    if "PERP" in symbol:
                        trading_fees = self.future_maker_fee * filled_amount if is_maker else self.future_taker_fee * filled_amount
                    total_fees += trading_fees

                    # update orders
                    order = self.client_orders.get(client_order_id)
                    if order is not None:
                        self.client_orders[order["client_order_id"]] = order

                    # trade report
                    trade_report = {
                        "msgType": 0,
                        "symbol": symbol,
                        "clientOrderId": order["client_order_id"],
                        "orderId": order["order_id"],
                        "type": order["order_type"],
                        "side": side,
                        "position_side":position_side,
                        "quantity": order["quantity"],
                        "price": order["price"],
                        "tradeId": order["order_id"],
                        "executedPrice": weighted_average_price,
                        "executedQuantity": filled_quantity,
                        "fee": trading_fees,
                        "feeAsset": "",
                        "totalExecutedQuantity": quantity - remaining_quantity,
                        "avgPrice": weighted_average_price,
                        "status": order["status"],
                        "reason": "",
                        "orderTag": order["order_tag"],
                        "totalFee": total_fees,
                        "feeCurrency": "",
                        "totalRebate": 0,
                        "rebateCurrency": "",
                        "visible": order["visible_quantity"],
                        "timestamp": int(time.time() * 1000),
                        "reduceOnly": order["reduce_only"],
                        "maker": is_maker,
                        "leverage": 1,
                        "marginMode": order["margin_mode"],
                    }

                    # update trade report
                    self.trade_reports.append(trade_report)
                    # save data
                    await self.save_trade_data_to_csv(trade_report, self.trade_data_file_path)
    
                    filled_quantity = 0
                    filled_amount = 0
                    trading_fees = 0

            # remove orders
            order = self.client_orders.get(client_order_id)
            if order is not None:
                del self.client_orders[order["client_order_id"]]
                self.logger.info(f"Finish matching limit order: {client_order_id}")

        except Exception as e:
            self.logger.exception(f"Error matching limit order: {e}")
    
    async def match_ioc_fok_order(self, order):
        try:
            client_order_id = order["client_order_id"]
            self.logger.info(f"Start matching IOC/FOK order: {client_order_id}")
            symbol = order["symbol"]
            side = order["side"]
            price = order["price"]
            quantity = order["quantity"]
            order_type = order["order_type"]
            position_side = order["position_side"]

            remaining_quantity = quantity
            filled_quantity = 0
            filled_amount = 0
            trading_fees = 0

            if side == "BUY":
                ask_prices = [ask[0] for ask in self.order_book[symbol]["data"]["asks"]]
                ask_quantities = [ask[1] for ask in self.order_book[symbol]["data"]["asks"]]

                for ask_price, ask_quantity in zip(ask_prices, ask_quantities):
                    if price >= ask_price:
                        trade_price = ask_price
                        trade_size = min(remaining_quantity, ask_quantity)
                        trade_amount = trade_price * trade_size

                        filled_quantity += trade_size
                        filled_amount += trade_amount
                        remaining_quantity -= trade_size

            elif side == "SELL":
                bid_prices = [bid[0] for bid in self.order_book[symbol]["data"]["bids"]][::-1]
                bid_quantities = [bid[1] for bid in self.order_book[symbol]["data"]["bids"]][::-1]

                for bid_price, bid_quantity in zip(bid_prices, bid_quantities):
                    if price <= bid_price:
                        trade_price = bid_price
                        trade_size = min(remaining_quantity, bid_quantity)
                        trade_amount = trade_price * trade_size

                        filled_quantity += trade_size
                        filled_amount += trade_amount
                        remaining_quantity -= trade_size

            non_trade_report = False
            if filled_quantity > 0:
    
                order["filled_quantity"] = filled_quantity
                order["filled_amount"] = filled_amount
                order["price"] = price

                if filled_quantity == quantity:
                    order["status"] = "FILLED"
                elif filled_quantity < quantity and filled_quantity>0:
                    order["status"] = "partially_FILLED"
                    if order_type == "FOK":
                        non_trade_report = True
                else:
                    non_trade_report = True

                if not non_trade_report:
                    # update position
                    if side == "BUY":
                        if position_side == "LONG":
                            if symbol not in self.position["LONG"]:
                                self.position["LONG"][symbol] = 0
                            self.position["LONG"][symbol] += filled_quantity
                        elif position_side == "SHORT":
                            if symbol not in self.position["SHORT"]:
                                self.position["SHORT"][symbol] = 0
                            self.position["SHORT"][symbol] -= filled_quantity
                    else:  # side == "SELL"
                        if position_side == "LONG":
                            if symbol not in self.position["LONG"]:
                                self.position["LONG"][symbol] = 0
                            self.position["LONG"][symbol] -= filled_quantity
                        elif position_side == "SHORT":
                            if symbol not in self.position["SHORT"]:
                                self.position["SHORT"][symbol] = 0
                            self.position["SHORT"][symbol] += filled_quantity

                # calculate fee
                if "SPOT" in symbol:
                    trading_fees =  self.spot_taker_fee * filled_amount
                if "PERP" in symbol:
                    trading_fees =  self.future_taker_fee * filled_amount

            # trade report
            if not non_trade_report:
                trade_report = {
                    "msgType": 0,
                    "symbol": symbol,
                    "clientOrderId": order["client_order_id"],
                    "orderId": order["order_id"],
                    "type": order["order_type"],
                    "side": side,
                    "position_side":position_side,
                    "quantity": order["quantity"],
                    "price": order["price"],
                    "tradeId": order["order_id"],
                    "executedPrice": order["price"],
                    "executedQuantity": order["filled_quantity"],
                    "fee": trading_fees if filled_quantity > 0 else 0,
                    "feeAsset": "",
                    "totalExecutedQuantity": order["filled_quantity"],
                    "avgPrice": order["price"],
                    "status": order["status"],
                    "reason": "",
                    "orderTag": order["order_tag"],
                    "totalFee": trading_fees if filled_quantity > 0 else 0,
                    "feeCurrency": "",
                    "totalRebate": 0,
                    "rebateCurrency": "",
                    "visible": order["visible_quantity"],
                    "timestamp": int(time.time() * 1000),
                    "reduceOnly": order["reduce_only"],
                    "leverage": 1,
                    "marginMode": order["margin_mode"],
                }

                # update trade report
                self.trade_reports.append(trade_report)
                # save data
                await self.save_trade_data_to_csv(trade_report, self.trade_data_file_path)

            # remove orders
            order = self.client_orders.get(client_order_id)
            if order is not None:
                del self.client_orders[order["client_order_id"]]
                self.logger.info(f"Finish matching limit order: {client_order_id}")

        except Exception as e:
            self.logger.exception(f"Error matching IOC/FOK order: {e}")


    def get_trade_reports(self):
        trade_reports = list(self.trade_reports)
        self.trade_reports.clear()
        return trade_reports

    # update real time orderbook and trade data
    async def handle_market_data(self, data):    
        try:
            async with self.lock:
                topic = data.get("topic")

                if topic:
                    symbol = topic.split("@")[0]
                    sub_type = None

                    if "orderbook" in topic:
                        sub_type = "orderbook"
                        # save raw data
                        self.order_book[symbol] = data
                    elif "trades" in topic:
                        sub_type = "trades"
                        # save raw data
                        self.trade[symbol] = data
                    elif "markprice" in topic:
                        sub_type = "markprice"
                        # save raw data
                        self.markprice[symbol] = data["data"]

        except Exception as e:
            print(f"Error handling market data: {e}")

    async def handle_cancel_order(self, params):
        try:
            order_id = params.get('order_id')
            symbol = params.get('symbol')
            self.logger.info(f"Cancelling order with id: {order_id}, symbol: {symbol}")
            for client_id, client_order in list(self.client_orders.items()):
                if client_order["order_id"] == order_id and client_order["symbol"] == symbol:
                    del self.client_orders[client_id]
                    self.logger.info(f"Order cancelled: {order_id}")
                    return {"success": True, "status": "CANCEL_SENT"}
            
            self.logger.warning(f"Order not found: {order_id}")
            return {"success": False, "error": "Order not found"}
        except Exception as e:
            self.logger.exception(f"Error cancelling order: {e}")
            return {"success": False, "error": str(e)}

    async def handle_cancel_order_by_client_order_id(self, params):
        try:
            client_order_id = params.get('client_order_id')
            symbol = params.get('symbol')
            self.logger.info(f"Cancelling order with client order id: {client_order_id}, symbol: {symbol}")
            if client_order_id in self.client_orders:
                client_order = self.client_orders[client_order_id]
                if client_order["symbol"] == symbol:
                    del self.client_orders[client_order_id]
                    self.logger.info(f"Order cancelled: {client_order_id}")
                    return {"success": True, "status": "CANCEL_SENT"}
            
            self.logger.warning(f"Order not found: {client_order_id}")
            return {"success": False, "error": "Order not found"}
        except Exception as e:
            self.logger.exception(f"Error cancelling order by client order id: {e}")
            return {"success": False, "error": str(e)}

    async def handle_cancel_orders(self, params):
        try:
            symbol = params.get("symbol")
            self.logger.info(f"Cancelling all orders for symbol: {symbol}")
            client_ids_to_remove = []
            for client_id, client_order in list(self.client_orders.items()):
                if client_order["symbol"] == symbol and client_order["status"] == "open":
                    client_ids_to_remove.append(client_id)
            
            for client_id in client_ids_to_remove:
                del self.client_orders[client_id]
            
            self.logger.info(f"All orders cancelled for symbol: {symbol}")
            return {"success": True, "status": "CANCEL_ALL_SENT"}
        except Exception as e:
            self.logger.exception(f"Error cancelling orders: {e}")
            return {"success": False, "error": str(e)}

    async def handle_cancel_all_pending_orders(self):
        try:
            self.logger.info("Cancelling all pending orders")
            self.client_orders.clear()  
            self.logger.info("All pending orders cancelled")
            return {"success": True, "status": "CANCEL_ALL_SENT"}
        except Exception as e:
            self.logger.exception(f"Error cancelling all orders: {e}")
            return {"success": False, "error": str(e)}
        
    async def handle_edit_order_by_client_order_id(self, params):
        try:
            client_order_id = params.get('client_order_id')
            new_price = params.get('price')
            new_quantity = params.get('quantity')
            self.logger.info(f"Editing order with client_order_id: {client_order_id}")

            if client_order_id not in self.client_orders:
                self.logger.warning(f"Order not found: {client_order_id}")
                return {"success": False, "error": "Order not found"}

            order = self.client_orders[client_order_id]

            # Update price if provided
            if new_price is not None:
                order["price"] = float(new_price)
                self.logger.info(f"Updated price for client_order_id {client_order_id} to {new_price}")

            # Update quantity if provided
            if new_quantity is not None:
                new_quantity = float(new_quantity)
                if new_quantity < order["filled_quantity"]:
                    self.logger.warning(f"New quantity less than filled quantity for client_order_id: {client_order_id}")
                    return {"success": False, "error": "New quantity cannot be less than filled quantity"}
                order["quantity"] = new_quantity
                order["visible_quantity"] = new_quantity - order["filled_quantity"]
                self.logger.info(f"Updated quantity for client_order_id {client_order_id} to {new_quantity}")

            # Reflect the edited order back in the order book or client orders
            self.client_orders[client_order_id] = order

            # Return success response
            return {"success": True, "status": "EDIT_SENT"}

        except Exception as e:
            self.logger.exception(f"Error editing order by client order id: {e}")
            return {"success": False, "error": str(e)}
        
    async def initialize_file(self, file_path, header):
        """清空文件並寫入表頭"""
        async with aiofiles.open(file_path, mode='w') as file:
            await file.write(','.join(header) + '\n')

    async def save_trade_data_to_csv(self, trade_report, file_path):
        try:
            header = ["symbol", "executedPrice", "executedQuantity", "fee", "side", "position_side", "timestamp", "leverage"]
             
            # 初始化文件
            if not self.save_trade_data_to_csv_initialization:
                await self.initialize_file(file_path, header)
                self.save_trade_data_to_csv_initialization = True
            
            async with aiofiles.open(file_path, mode='a') as file:
                row = f"{trade_report['symbol']},{trade_report['executedPrice']},{trade_report['executedQuantity']},{trade_report['fee']},{trade_report['side']},{trade_report['position_side']},{trade_report['timestamp']},{trade_report['leverage']}\n"
                await file.write(row)

        except Exception as e:
            print(f"Error saving trade data to CSV: {e}")

    async def continuously_save_position_and_markprice(self):
        try:
            header = ["symbol", "holding", "position_side", "mark_price", "timestamp"]
            
            # 初始化文件
            await self.initialize_file(self.position_data_file_path, header)

            while self.running:
                async with aiofiles.open(self.position_data_file_path, mode='a') as file:
                    current_timestamp = int(time.time() * 1000)
                    
                    # 遍歷 position 和 mark price 數據
                    for position_side, positions in self.position.items():
                        for symbol, holding in positions.items():
                            mark_price = self.markprice.get(symbol, {}).get("price", None)
                            row = f"{symbol},{holding},{position_side},{mark_price},{current_timestamp}\n"
                            await file.write(row)

                await asyncio.sleep(1)  

        except Exception as e:
            print(f"Error continuously saving position and mark price to CSV: {e}")

    async def stop_continuous_saving(self):
        self.running = False