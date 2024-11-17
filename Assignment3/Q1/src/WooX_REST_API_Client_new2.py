import datetime
import hmac, hashlib, base64
import requests
import json
import aiohttp
import asyncio
import random
import logging


# After learning Blocking & Non-blocking concepts from Lesson 4
# I rewrite the functions in class WooX_REST_API_Client, adding async, await
# Use busy-loop to handle non-blocking message, such as Public/Private message
# Public: Get orderbook, Get position, Get Kline
# Private: Send Taker/Maker order (Check the order type), Cancel
# Seperate v1, v3 API
# 將/v1 & /v3 保留在 endpoint!
# check it's v1 or v3 to return make_request_v1 or make_request_v3

class WooXStagingAPI:
    def __init__(self, api_key, api_secret, base_url = 'https://api.staging.woox.io'):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

    # https://docs.woox.io/#authentication
    async def make_request_v1(self, session, request_method, endpoint, params=None):
        milliseconds_since_epoch = round(datetime.datetime.now().timestamp() * 1000)
        timestamp = str(milliseconds_since_epoch)
        params = params or {}

        async def _generate_signature(params):
            key = self.api_secret
            key_bytes = bytes(key, 'utf-8')
            params_bytes = bytes(params, 'utf-8')
            return await hmac.new(key_bytes, params_bytes , hashlib.sha256).hexdigest()

        # V1 Signature
        params['timestamp'] = timestamp
        body = '&'.join(f'{key}={value}' for key, value in sorted(params.items()))
        body = body + '|' + timestamp

        signature = await _generate_signature(body)

        # Set headers
        headers = {
            'x-api-timestamp': str(milliseconds_since_epoch),
            'x-api-key': self.api_key,
            'x-api-signature': signature,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Cache-Control': 'no-cache'
        }

        url = f'{self.base_url}{endpoint}'

        if request_method == 'GET':
            async with session.get(url, params=params, headers=headers) as response:
                return await self._handle_response(response)
        elif request_method == 'POST':
            async with session.post(url, data=params, headers=headers) as response:
                return await self._handle_response(response)
        elif request_method == 'PUT':
            async with session.put(url, params=params, headers=headers) as response:
                return await self._handle_response(response)
        elif request_method == 'DELETE':
            async with session.delete(url, params=params, headers=headers) as response:
                return await self._handle_response(response)

    # https://docs.woox.io/#authentication
    async def make_request_v3(self, session, request_method, endpoint, params=None):
        milliseconds_since_epoch = round(datetime.datetime.now().timestamp() * 1000)
        timestamp = str(milliseconds_since_epoch)
        params = params or {}

        async def _generate_signature(params):
            key = self.api_secret
            key_bytes = bytes(key, 'utf-8')
            params_bytes = bytes(params, 'utf-8')
            return await hmac.new(key_bytes, params_bytes , hashlib.sha256).hexdigest()

        # V3 Signature
        body = json.dumps(params) if params else ''
        signature_payload = f'{timestamp}{request_method}{endpoint}{body}'
        signature = await _generate_signature(signature_payload)
        
        # Set headers
        headers = {
            'x-api-timestamp': str(milliseconds_since_epoch),
            'x-api-key': self.api_key,
            'x-api-signature': signature,
            'Content-Type': 'application/json',
            'Cache-Control': 'no-cache'
        }

        url = f'{self.base_url}{endpoint}'

        if request_method == 'GET':
            async with session.get(url, params=params, headers=headers) as response:
                return await self._handle_response(response)
        elif request_method == 'POST':
            async with session.post(url, json=params, headers=headers) as response:
                return await self._handle_response(response)
        elif request_method == 'PUT':
            async with session.put(url, params=params, headers=headers) as response:
                return await self._handle_response(response)
        elif request_method == 'DELETE':
            async with session.delete(url, params=params, headers=headers) as response:
                return await self._handle_response(response)
        
    # https://docs.woox.io/#error-codes
    async def _handle_response(self, response):
        try:
            response.raise_for_status()
            return await response.json()
        
        except aiohttp.ClientResponseError as e:
            error_response = await response.json()
            error_code = error_response.get('code', 0)
            error_message = error_response.get('message', 'Unknown error')

            # 500 Unknown
            if e.status == 500: 
                if error_code == -1000:
                    self.logger.error(f"Unknown error occurred: {error_message}")
                    raise Exception("Unknown error occurred while processing the request")

            # 401 Unauthorized
            elif e.status == 401: 
                if error_code == -1001:
                    self.logger.error("Invalid Signature")
                    raise ValueError("The api key or secret is in wrong format")
                elif error_code == -1002:
                    self.logger.error('Unauthorized')
                    raise ValueError("API key or secret is invalid, insufficient permission or expired/revoked")
                
            # 429 Too many requests
            elif e.status == 429:
                if error_code == -1003:
                    self.logger.error('Too many requests')
                    raise Exception('Rate limit exceed')
                
            # 400 Bad Request
            elif e.status == 400:
                if error_code == -1004:
                    self.logger.error(f"Unknown parameter: {error_message}")
                    raise ValueError("An unknown parameter was sent")
                elif error_code == -1005:
                    self.logger.error(f"Invalid parameters: {error_message}")
                    raise ValueError("Some parameters are in the wrong format")
                elif error_code == -1006:
                    self.logger.error(f"Resource not found: {error_message}")
                    raise ValueError("The data is not found in the server")
                elif error_code == -1008:
                    self.logger.error("Quantity too high")
                    raise ValueError("The quantity of settlement is higher than you can request")
                elif error_code == -1009:
                    self.logger.error("Cannot withdraw")
                    raise ValueError("Cannot request withdrawal settlement, deposit other arrears first")
                elif error_code == -1011:
                    self.logger.error("RPC connection error")
                    raise ConnectionError("Cannot place/cancel orders due to internal network error")
                elif error_code == -1012:
                    self.logger.error("RPC rejected")
                    raise ValueError("The place/cancel order request is rejected by internal module")
                elif error_code == -1101:
                    self.logger.error("Risk too high")
                    raise ValueError("The risk exposure for the client is too high")
                elif error_code == -1102:
                    self.logger.error("Minimum notional not met")
                    raise ValueError("The order value (price * size) is too small")
                elif error_code == -1103:
                    self.logger.error("Price filter failed")
                    raise ValueError("The order price is not following the tick size rule")
                elif error_code == -1104:
                    self.logger.error("Size filter failed")
                    raise ValueError("The order quantity is not following the step size rule")
                elif error_code == -1105:
                    self.logger.error("Percentage filter failed")
                    raise ValueError("Price is X% too high or X% too low from the mid price")
        
            # 409 Conflict
            elif e.status == 409:
                if error_code == -1007:
                    self.logger.error("Duplicate request")
                    raise ValueError("The data already exists or your request is duplicated")
            
            # Default error handling
            self.logger.error(f"Unhandled error: Status {e.status}, Code {error_code}, Message: {error_message}")
            raise Exception(f"Unhandled API error: {error_message}")
        
        except Exception as e:
            self.logger.error(f"Request failed: {str(e)}")
            raise

    # https://docs.woox.io/#orderbook-snapshot-public
    async def get_orderbook(self, session, symbol, max_level=100):
        endpoint = f'/v1/public/orderbook/{symbol}'
        params = {
            'max_level': max_level
        }
        return await self.make_request_v1(session, endpoint, params)
    
    # https://docs.woo.org/#market-trades-public
    async def get_trades(self, session, symbol, limit=10):
        endpoint = f'/v1/public/market_trades'
        params = {
            'symbol': symbol,
            'limit': limit
        }
        return await self.make_request_v1(session, endpoint, params)
    
    # https://docs.woo.org/#kline-public
    async def get_kline(self, session, symbol, interval='1m', limit=100):
        endpoint = f'/v1/public/kline'
        params = {
            'symbol': symbol,
            'type' : interval,
            'limit': limit
        }
        return await self.make_request_v1(session, endpoint, params)
    
    # https://docs.woox.io/#send-order
    async def send_order(self, session, symbol, order_type, side, client_order_id= None,
                         order_price=None, order_quantity=None, order_amount=None, 
                         visible_quantity=None, reduce_only=False, margin_mode=None,
                         position_side=None):
        # validate order_type
        valid_order_types = {'LIMIT', 'MARKET', 'IOC', 'FOK', 'POST_ONLY', 'ASK', 'BID'}
        if order_type not in valid_order_types:
            raise ValueError(f"Invalid order_type. Must be one of {valid_order_types}")
        
        # validate side
        if side not in {'BUY', 'SELL'}:
            raise ValueError("Invalid side. Must be either 'BUY' or 'SELL'")
        
         # validate LIMIT Order price
        if order_type == 'LIMIT' and order_price is None:
            raise ValueError("Order Price is required for LIMIT orders")
        
        # add optional parameters: order_price
        if order_price is not None:
            params['order_price'] = order_price
        
        # quantity & order_amount 
        if order_quantity is not None and order_amount is not None:
            raise ValueError("Cannot specify both quantity and order_amount")
        
        if order_quantity is not None:
            params['order_quantity'] = order_quantity
        if order_amount is not None:
            params['order_amount'] = order_amount
        
         # Other optional parameters
        if client_order_id is not None:
            if not 0 <= client_order_id <= 922337203685477580:
                raise ValueError("client_order_id must be between 0 and 922337203685477580")
            params['client_order_id'] = client_order_id
        
        if visible_quantity is not None:
            if order_type not in {'LIMIT', 'POST_ONLY'}:
                raise ValueError("visible_quantity is only valid for LIMIT and POST_ONLY orders")
            params['visible_quantity'] = str(visible_quantity)
            
        if reduce_only:
            params['reduce_only'] = True
            
        if margin_mode is not None:
            if margin_mode not in {'CROSS', 'ISOLATED'}:
                raise ValueError("margin_mode must be either 'CROSS' or 'ISOLATED'")
            params['margin_mode'] = margin_mode
            
        if position_side is not None:
            if position_side not in {'LONG', 'SHORT'}:
                raise ValueError("position_side must be either 'LONG' or 'SHORT'")
            params['position_side'] = position_side
        
        endpoint = f'/v1/order' 
        params = {
            'symbol': symbol,
            'order_type': order_type,
            'side': side
        }
        return await self.make_request_v1(session, 'POST', endpoint, params)
    
    # https://docs.woox.io/#cancel-order
    async def cancel_order(self, session, order_id, symbol):
        endpoint = f'/v1/order'
        params = {
            'order_id': order_id,
            'symbol': symbol
        }
        return await self.make_request_v1(session, 'DELETE', endpoint, params)
    
    # https://docs.woox.io/#cancel-order-by-client_order_id
    async def cancel_order_by_client_order_id(self, session, client_order_id, symbol):
        endpoint = f'/v1/client/order'
        params = {
            'client_order_id': client_order_id,
            'symbol': symbol
        }
        return await self.make_request_v1(session, 'DELETE', endpoint, params)
    
    # https://docs.woox.io/#cancel-orders
    async def cancel_orders(self, session, symbol, page=None, size=None):
        # validate page
        if page is not None:
            params['page']= page
        # validate size
        if size is not None:
            params['size']=size

        endpoint = f'/v1/orders'
        params = {
            'symbol': symbol,
        }
        return await self.make_request_v1(session, 'DELETE', endpoint, params)
    
    # https://docs.woox.io/#get-order
    async def get_order(self, session, oid):
        # The order_id oid that you wish to query
        endpoint = f'/v1/order/:oid'
        params={
            'oid':oid
        }
        return await self.make_request_v1(session, 'GET', endpoint, params)
    
    # https://docs.woox.io/#get-order-by-client_order_id
    async def get_order_by_client_id(self, session, client_order_id):
        endpoint= f'/v1/client/order/:client_order_id'
        params = {
            'client_order_id': client_order_id
        }
        return await self.make_request_v1(session, 'GET', endpoint, params)
    
    # https://docs.woox.io/#edit-order
    async def edit_order(self, session, order_id, price=None, quantity=None):
        # validate
        if price is not None:
            params['price'] = str(price)
        if quantity is not None:
            params['quantity'] = str(quantity)
        
        endpoint = f'/v3/order/:order_id'
        params = {
            'order_id': order_id
        }
        return await self.make_request_v3(session, 'PUT', endpoint, params)
    
    # https://docs.woox.io/#edit-order-by-client_order_id
    async def edit_order_by_client_id(self, session, client_order_id, price=None, quantity=None):
        # validate
        if price is not None:
            params['price'] = str(price)
        if quantity is not None:
            params['quantity'] = str(quantity)

        endpoint = f'/v3/order/client/:client_order_id'
        params = {
            'client_order_id': client_order_id
        }
        return await self.make_request_v3(session, 'PUT', endpoint, params)
    
    # https://docs.woox.io/#send-algo-order
    async def send_algo_order(self, session, algoType, symbol, side, type,
                              order_quantity=None, order_price=None, client_order_id=None,
                              position_side=None, reduce_only=False, margin_mode=None,
                              trigger_price=None, stop_price=None, trailing_distance=None,
                              limit_price=None, start_time=None, expire_time=None):
        # Validate algo type
        valid_algo_types = {'STOP', 'OCO', 'TRAILING_STOP', 'BRACKET','POSITIONAL_TP_SL'}
        if algoType not in valid_algo_types:
            raise ValueError(f"Invalid algo type. Must be one of {valid_algo_types}")
        # Validate side
        if side not in {'BUY', 'SELL'}:
            raise ValueError("Invalid side. Must be either 'BUY' or 'SELL'")
        
        # Validate type
        if type not in {'LIMIT', 'MARKET'}:
            raise ValueError("Invalid type. Must be either 'LIMIT' or 'SELL'")
        
    
        # Add optional parameters
        if order_quantity is not None:
            params['orderQuantity'] = order_quantity
        if order_price is not None:
            params['orderPrice'] = order_price
        if client_order_id is not None:
            params['clientOrderId'] = client_order_id
        if position_side is not None:
            if position_side not in {'LONG', 'SHORT'}:
                raise ValueError("position_side must be either 'LONG' or 'SHORT'")
            params['positionSide'] = position_side
        if reduce_only:
            params['reduceOnly'] = True
        if margin_mode is not None:
            if margin_mode not in {'CROSS', 'ISOLATED'}:
                raise ValueError("margin_mode must be either 'CROSS' or 'ISOLATED'")
            params['marginMode'] = margin_mode

        # Algo specific parameters
        if trigger_price is not None:
            params['triggerPrice'] = trigger_price
        if stop_price is not None:
            params['stopPrice'] = stop_price
        if trailing_distance is not None:
            params['trailingDistance'] = trailing_distance
        if limit_price is not None:
            params['limitPrice'] = limit_price
        if start_time is not None:
            params['startTime'] = start_time
        if expire_time is not None:
            params['expireTime'] = expire_time

        endpoint = f'v3/algo/order'
        params = {
            'algoType': algoType,
            'symbol': symbol,
            'side': side,
            'type': type
        }
        return await self.make_request_v3(session, 'POST', endpoint, params)


async def background_processing_task():
    for i in range(5):
        print(f"[Background Task] Processing data... {i + 1}/5")
        await asyncio.sleep(random.uniform(0.01, 2))
    print("[Background Task] Completed background processing.")

# busy loop is to handle non-blocking 
async def busy_loop(woox_api, session, symbol):
    tasks = [
        asyncio.create_task(woox_api.get_orderbook(session, symbol)),
        asyncio.create_task(woox_api.get_trades(session, symbol)),
        asyncio.create_task(woox_api.get_kline(session, symbol))
    ]

    task_names = ["Orderbook", "Trades", "Kline"]

    while True:
        print(f"\nPolling for {symbol} data...\n")
        for i, task in enumerate(tasks):
            if task.done():
                try:
                    result = await task
                    print(f"[{task_names[i]}] done.")
                    print(f"[{task_names[i]}] result={result}")
                    if task_names[i] == "Orderbook":
                        tasks[i] = asyncio.create_task(woox_api.get_orderbook(session, symbol))
                    elif task_names[i] == "Trades":
                        tasks[i] = asyncio.create_task(woox_api.get_trades(session, symbol))
                    elif task_names[i] == "Kline":
                        tasks[i] = asyncio.create_task(woox_api.get_kline(session, symbol))

                except Exception as e:
                    print(f"[{task_names[i]} Error] {e}")

        await background_processing_task()

        await asyncio.sleep(0.1)

async def main():
    api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
    api_secret_key = 'FWQGXZCW4P3V4D4EN4EIBL6KLTDA'
    woox_api = WooXStagingAPI(api_key, api_secret_key)
    symbol = 'SPOT_BTC_USDT'

    async with aiohttp.ClientSession() as session:
        await busy_loop(woox_api, session, symbol)

asyncio.run(main())