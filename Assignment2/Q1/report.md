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
