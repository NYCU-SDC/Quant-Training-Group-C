# Q1
# Basic Part
In this section, I will provide the details of building an API model. 
The implementation can be found in [src/WooX_REST_API_Client.py](https://github.com/NYCU-SDC/Quant-Training-Group-C/blob/main/Assignment2/Q1/src/WooX_REST_API_Client.py).
We lookup how the building step.
1. Understanding the authentication process.
2. Determining the API format for "Send / Cancel / Edit Order" in the RESTful API.
3. More generally, understanding how to use the "Send Algo Order" API to implement a stop-loss mechanism.


## Authentication
First, we need to generate the plain text.
### Plain Text
We follow the [document](https://docs.woox.io/#authentication) step by step. 
Note that the plain text format differs between v1 and v3.

For v1, we need to use the format "order_price=9000&order_quantity=0.11&order_type=LIMIT&side=BUY&symbol=SPOT_BTC_USDT|1578565539808" as the plain text for encryption. 
We use the following Python code to construct the v1 plain text:
```python
body = "&".join(f"{key}={value}" for key, value in params.items())
```

For v3, the format is different: it concatenates the timestamp, HTTP request method, request path, and request body. 
We use the following Python code to construct the v3 plain text:
```python
body = f'{milliseconds_since_epoch}{requests_type.upper()}{endpoint}{body}'
```

### Generate Signature
After generating the plain text, we use SHA-256 to encrypt it. This part of the implementation is directly copied from the [document](https://docs.woox.io/#authentication).
```python
def _generate_signature(params):
        key = self.api_secret
        key_bytes= bytes(key, 'utf-8')
        params_bytes = bytes(params, 'utf-8')
        return hmac.new(key_bytes, params_bytes, hashlib.sha256).hexdigest()
```

### Header
Next, we need to construct the header. 
Note that the header format differs between v1 and v3. 
We use the following Python code to create the header:

```python
    headers = {
        'x-api-timestamp': str(milliseconds_since_epoch),
        'x-api-key': self.api_key,
        'x-api-signature': _generate_signature(body),
        'Content-Type': 'application/json' if version == "v3" 
                        else 'application/x-www-form-urlencoded',
        'Cache-Control': 'no-cache'
    }
```
### Sending Requests / Receiving Responses
Finally, we send the request to the server and receive the response.
```python
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
```

## Send / Cancel / Edit Order

In this section, we refer to the [document](https://docs.woox.io/#authentication) and implement the functionality as follows.


```python
# https://docs.woox.io/?python#send-order
def send_order(self, params):
    endpoint = '/v1/order'
    return self.make_request(endpoint, params, "post")

# https://docs.woox.io/#edit-order-by-client_order_id
def edit_order_by_client_order_id(self, params, client_order_id):
    endpoint = f'/v3/order/client/{client_order_id}'
    return self.make_request(endpoint, params, requests_type="put", version="v3", signature=True)

# https://docs.woox.io/#cancel-order-by-client_order_id
def cancel_order_by_client_order_id(self, params):
    endpoint = '/v1/client/order'
    return self.make_request(endpoint, params, requests_type="delete", version="v1")
```

## Send Algo Order
In this section, we refer to the [document](https://docs.woox.io/#authentication) and implement the functionality as follows.
```python
# https://docs.woox.io/#send-algo-order
def send_algo_order(self, params):
    endpoint = '/v3/algo/order'
    return self.make_request(endpoint, params, requests_type="post", version="v3")
```
The main difference from a "send order" is its ability to dynamically track the highest price and set a stop-loss. Setting "callbackRate" triggers a stop-loss if the price drops by a specified percentage, while "callbackValue" triggers it based on a specified amount.


# Basic part demo

We implement a naive trading strategy: buy low and sell high, as shown below. More details can be found [here](https://github.com/NYCU-SDC/Quant-Training-Group-C/blob/main/Assignment2/Q1/src/main.py). Additionally, we set an order limit to prevent excessive losses from our naive trading approach.



```python
async def strategy(self, symbol, asks_mean, bids_mean):
    async with self.check_symbol_isVaild_lock:
        if time.time() - self.orderbooks[symbol].start_time < 5:
            return
        else:
            if (asks_mean < self.orderbooks[symbol].asks_mean) and self.trade_amount < 6:
                params = {
                    'client_order_id': int(time.time() * 1000),
                    'order_amount': 10,
                    'order_type': 'MARKET',
                    'side':'BUY',
                    'symbol': symbol
                }
                response = self.WooX_REST_API_Client.send_order(params)
                self.trade_amount +=  1
                print("response BUY", response)
                time.sleep(1)
                return
            
            if bids_mean > self.orderbooks[symbol].bids_mean:
                params = {
                    'client_order_id': int(time.time() * 1000),
                    'order_amount': 10,
                    'order_type': 'MARKET',
                    'side':'SELL',
                    'symbol': symbol
                }
                response = self.WooX_REST_API_Client.send_order(params)
                print("response SELL", response)
                time.sleep(1)
                return
            else:
                print(bids_mean, self.orderbooks[symbol].bids_mean)
```
The testing results are as follows:
![algorithm](./src/algorithm.png)
