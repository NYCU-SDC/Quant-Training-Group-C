import json
import asyncio
import websockets
import csv
from datetime import datetime
from BBO import BBO

class DataCollector:
    def __init__(self, app_id: str):
        self.app_id = app_id
        self.uri = f"wss://wss.staging.woox.io/ws/stream/{self.app_id}"
        self.connection = None
        self.bbo_data = {}  # Dictionary to hold BBO instances for each symbol

    async def connect(self):
        """Handles WebSocket connection"""
        if self.connection is None:
            self.connection = await websockets.connect(self.uri)
            print(f"Connected to {self.uri}")
        return self.connection

    async def subscribe(self, symbol, config, interval):
        """Subscribes to BBO for a given symbol."""
        websocket = await self.connect()

        # Initialize BBO for the symbol
        if config.get("bbo"):
            self.bbo_data[symbol] = BBO(symbol)
            # 新增想要訂閱的資訊
            subscribe_message = {
                "event": "subscribe",
                "topic": f"{symbol}@bbo",
                "symbol": symbol,
                "type": "bbo"
            }
            await websocket.send(json.dumps(subscribe_message))
            print(f"Subscribed to BBO for {symbol}")

        if config.get("kline"):
            params = {
                "id": str(self.app_id),
                "topic": f"{symbol}@kline_{interval}",
                "event": "subscribe"
            }
            await websocket.send(json.dumps(params))
            response = json.loads(await websocket.recv())
            print(response)

        if config.get("orderbook"):
            params = {
                "id": str(self.app_id),
                "topic": f"{symbol}@orderbook",
                "event": "subscribe"
            }
            await websocket.send(json.dumps(params))
            response = json.loads(await websocket.recv())
            print(response)

        if config.get("trades"):
            params = {
                "id": str(self.app_id),
                "topic": f"{symbol}@trades",
                "event": "subscribe"
            }
            await websocket.send(json.dumps(params))
            response = json.loads(await websocket.recv())
            print(response)
            
        # Process incoming messages
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)

                if data.get("event") == "ping":
                    await self.respond_pong(websocket)
                elif data.get("event") == "subscribe":
                    if data.get("success"):
                        print(f"Subscription successful for {data.get('data')}")

                elif data.get("topic") == f"{symbol}@bbo":
                    bbo = data["data"]
                    data_with_timestamp = {
                        "timestamp": int(datetime.utcnow().timestamp() * 1000),
                        "symbol": symbol,
                        "bid": bbo["bid"],
                        "bidSize": bbo["bidSize"],
                        "ask": bbo["ask"],
                        "askSize": bbo["askSize"]
                    }
                    self.bbo_data[symbol].update(bbo["bid"], bbo["bidSize"], bbo["ask"], bbo["askSize"])
                    print(f"BBO updated for {symbol}")
                    await self.write_to_csv(data_with_timestamp)
                
                elif data.get("topic") ==  f"{symbol}@kline_{interval}":
                    kline = data['data']
                    data_with_timestamp = {
                        'symbol': symbol,
                        'open':  kline['open'],
                        'close': kline['close'],
                        'low': kline['low'],
                        'high': kline['high'],
                        'volume': kline['volume'],
                        'amount': kline['amount'],
                        'symbol': kline['symbol'],
                        'type': kline['type'],
                        'startTime': kline['startTime'],
                        'endTime': kline['endTime'],
                    }
                    print(f"Kline updated for {symbol}")
                    await self.write_to_csv(data_with_timestamp, fileName="kline.csv")

                elif data.get("topic") ==  f"{symbol}@trades":
                    for trades in data['data']:
                        data_with_timestamp = {
                            'timestamp': data['ts'],
                            'symbol': trades['s'],
                            'price':  trades['p'],
                            'size': trades['a'],
                            'side': trades['b'],
                            'source': trades['c']
                        }
                        print(f"Trades updated for {symbol}")
                        await self.write_to_csv(data_with_timestamp, fileName="trades.csv")
                
                elif data.get("topic") ==  f"{symbol}@orderbook":
                    # print(f"data is {data}")
                    orderbook = data['data']
                    data_with_timestamp = {
                        'timestamp': data['ts'],
                        'symbol': orderbook['symbol'],
                        'asks':  orderbook['asks'],
                        'bids': orderbook['bids'],
                    }
                    print(f"Trades updated for {symbol}")
                    await self.write_to_csv(data_with_timestamp, fileName="orderbook.csv")

            except websockets.ConnectionClosed as e:
                print(f"Connection closed for {symbol}: {e}")
                break
            except Exception as e:
                print(f"Error receiving data for {symbol}: {e}")
                break

    async def respond_pong(self, websocket):
        """Responds to server PINGs with a PONG"""
        pong_message = {
            "event": "pong",
            "ts": int(asyncio.get_event_loop().time() * 1000)
        }
        await websocket.send(json.dumps(pong_message))

    async def write_to_csv(self, data, fileName="bbo.csv"):
        """Writes BBO data to a single CSV file with a `symbol` column."""
        file_name = fileName
        if fileName == 'bbo.csv':
            fieldnames = ['timestamp', 'symbol', 'bid', 'bidSize', 'ask', 'askSize']
        elif fileName == 'kline.csv':
            fieldnames = ['symbol', 'open', 'close', 'low', 'high', 'volume', 'amount', 'type', 'startTime', 'endTime']
        elif fileName == 'trades.csv':
            fieldnames = ['timestamp', 'symbol', 'price', 'size', 'side', 'source']
        elif fileName == 'orderbook.csv':
            fieldnames = ['timestamp', 'symbol', 'asks', 'bids']

        try:
            with open(file_name, mode='a', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                if file.tell() == 0:  # Write header only if the file is empty
                    writer.writeheader()
                writer.writerow(data)
        except Exception as e:
            print(f"Error writing to CSV: {e}")

    async def close_connection(self):
        """Gracefully closes the WebSocket connection"""
        if self.connection is not None:
            await self.connection.close()
            self.connection = None
            print("WebSocket connection closed")

    async def start_subscriptions(self, symbols, config, interval):
        """Start subscriptions for multiple symbols."""
        tasks = [self.subscribe(symbol, config, interval) for symbol in symbols]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    app_id = "460c97db-f51d-451c-a23e-3cce56d4c932"
    woox_api = DataCollector(app_id)

    symbols = ['SPOT_WOO_USDT', 'SPOT_BTC_USDT', 'SPOT_ETH_USDT']
    config = {'bbo': True, 'kline': True, 'trades': True, 'orderbook': True}
    # config = {'bbo': False, 'kline': False, 'trades': False, 'orderbook': False, 'market_trades': True}
    interval = '1m'

    try:
        asyncio.run(woox_api.start_subscriptions(symbols, config, interval))
    except KeyboardInterrupt:
        print("Shutting down gracefully...")
    finally:
        asyncio.run(woox_api.close_connection())