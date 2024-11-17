import datetime
import hmac, hashlib, base64
import requests
import json

class WooX_REST_API_Client:
    def __init__(self, api_key, api_secret_key, base_url='https://api.staging.woo.org'):
        print(api_key, api_secret_key)
        self.api_key = api_key
        self.api_secret_key = api_secret_key
        self.base_url = base_url


    # https://docs.woox.io/#authentication
    def make_request(self, endpoint, params, requests_type="get", version="v1", signature=True):
        
        # https://docs.woox.io/#authentication
        def _generate_signature(params):
            key = self.api_secret_key # Defined as a simple string.
            key_bytes= bytes(key, 'utf-8')
            params_bytes = bytes(params, 'utf-8')
            return hmac.new(key_bytes, params_bytes, hashlib.sha256).hexdigest()
        
        milliseconds_since_epoch = round(datetime.datetime.now().timestamp() * 1000)
        url = self.base_url + endpoint
        print("\nurl", url, "\n")

        # timestamp, http request method, request_path and request_body
        if version == "v1":
            if params:
                body = "&".join(f"{key}={value}" for key, value in params.items())
                body = body + "|"+str(milliseconds_since_epoch)
            else:
                body = str(milliseconds_since_epoch)
        else:
            body = json.dumps(params)
            body = f'{milliseconds_since_epoch}{requests_type.upper()}{endpoint}{body}'

        # Set headers
        headers = {
            'x-api-timestamp': str(milliseconds_since_epoch),
            'x-api-key': self.api_key,
            'x-api-signature': _generate_signature(body),
            'Content-Type': 'application/json' if version == "v3" else 'application/x-www-form-urlencoded',
            'Cache-Control': 'no-cache'
        }
        print("body", body)

        if requests_type == "get":
            if signature == False:
                response = requests.get(url, params=params)
            else:
                if not params:
                    print(url)
                    response = requests.get(url, headers=headers, json=params)
                    print("there 1")
                if version == "v1":
                    response = requests.get(url, headers=headers, params=params)
                else:
                    response = requests.get(url, headers=headers, json=params)
        elif requests_type == "post":
            if version == "v1":
                response = requests.post(url, headers=headers, params=params)
            else:
                response = requests.post(url, headers=headers, json=params)
        elif requests_type == "put":
            if version == "v1":
                response = requests.put(url, headers=headers, params=params)
            else:
                response = requests.put(url, headers=headers, json=params)
        elif requests_type == "delete":
            if version == "v1":
                response = requests.delete(url, headers=headers, params=params)
            else:
                response = requests.delete(url, headers=headers, json=params)
        return response.json()
        
    
    # https://docs.woox.io/#orderbook-snapshot-public
    def get_orderbook(self, symbol, max_level=100):
        endpoint = f'/v1/public/orderbook/{symbol}'
        params = {
            'max_level': max_level,
        }
        return self.make_request(endpoint, params)
        # pass


    # https://docs.woo.org/#market-trades-public
    def get_trades(self, symbol, limit=100):
        endpoint = f'/v1/public/market_trades'
        params = {
            'symbol': symbol,
            'limit': limit,
        }
        return self.make_request(endpoint, params)
        # pass


    # https://docs.woo.org/#kline-public
    def get_kline(self, symbol, interval="1m", limit=100):
        endpoint = f'/v1/public/kline'
        params = {
            'symbol': symbol,
            "type": interval,
            'limit': limit,
        }
        return self.make_request(endpoint, params)
    

    # https://docs.woox.io/?python#send-order
    def send_order(self, params):
        endpoint = '/v1/order'
        return self.make_request(endpoint, params, "post")

    # https://docs.woox.io/#send-algo-order
    def send_algo_order(self, params):
        endpoint = '/v3/algo/order'
        return self.make_request(endpoint, params, requests_type="post", version="v3")


    # https://docs.woox.io/#edit-order-by-client_order_id
    def edit_order_by_client_order_id(self, params, client_order_id):
        endpoint = f'/v3/order/client/{client_order_id}'
        return self.make_request(endpoint, params, requests_type="put", version="v3", signature=True)


    # https://docs.woox.io/#cancel-order-by-client_order_id
    def cancel_order_by_client_order_id(self, params):
        endpoint = '/v1/client/order'
        print("params", params)
        return self.make_request(endpoint, params, requests_type="delete", version="v1")
    

    # https://docs.woox.io/#cancel-all-pending-orders
    def cancel_all_pending_orders(self):
        endpoint = '/v3/orders/pending'
        return self.make_request(endpoint, params={}, requests_type="delete", version="v3")


if __name__ == "__main__":
    api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
    api_secret_key = 'FWQGXZCW4P3V4D4EN4EIBL6KLTDA'
    woox_api = WooX_REST_API_Client(api_key, api_secret_key)
    
    # test post_send_order
    params = {
        'client_order_id': 3,
        'order_price': 3190,
        'order_quantity': 0.001,
        'order_type': 'MARKET',
        'side':'BUY',
        'symbol': 'SPOT_ETH_USDT'
    }
    response = woox_api.send_order(params)
    print(response)

    # test edit_order_by_client_order_id
    params = {
        "client_order_id": "3",
        "quantity": "5"
    }
    response = woox_api.edit_order_by_client_order_id(params, 3)
    print(response)

    # # # test cancel_all_pending_orders
    response = woox_api.cancel_all_pending_orders()
    print(response)

    # test cancel_order_by_client_order_id
    # params = {
    #     "client_order_id": 3,
    #     'symbol': 'SPOT_BTC_USDT'
    # }
    # response = woox_api.cancel_order_by_client_order_id(params)
    # print(response)

    # test post_send_order
    # params = {
    #     'clientOrderId': 4,
    #     "symbol": "SPOT_BTC_USDT",
    #     "algoType": "STOP",
    #     "type": "MARKET",
    #     "side": "BUY",
    #     "quantity": "0.0001",
    #     "triggerPrice": "0.21"
    # }
    # response = woox_api.send_algo_order(params)
    # print(response)