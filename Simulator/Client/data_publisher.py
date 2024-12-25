import json
import asyncio
import time
from redis import asyncio as aioredis

# Import your existing classes
from data_processing.Orderbook import OrderBook
from data_processing.BBO import BBO

class WooXStagingAPI:
    def __init__(self, app_id: str, api_key: str, api_secret: str, redis_host: str, redis_port: int = 6379):
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        
        self.market_reader = None
        self.market_writer = None
        self.market_connection = False

        self.private_reader = None
        self.private_writer = None
        self.private_connection = False
        
        self.redis_host = redis_host
        self.redis_port = redis_port
        
        self.redis_client = None
        
        self.orderbooks = {}
        self.bbo_data = {}
    
    async def connect_to_redis(self):
        """Connect to Redis Server"""
        try:
            self.redis_client = await aioredis.from_url(
                f"redis://{self.redis_host}:{self.redis_port}",
                encoding='utf-8',
                decode_responses=True
            )
            print(f"[Data Publisher] Connected to Redis server at {self.redis_host}:{self.redis_port}")
        except Exception as e:
            print(f"[Data Publisher] Failed to connect to Redis: {str(e)}")
    
    async def publish_to_redis(self, channel, data):
        """Publish data to Redis Channel"""
        if self.redis_client:
            await self.redis_client.publish(channel, json.dumps(data))
    
    async def market_connect(self):
        """Handles TCP connection to market data."""
        if self.market_connection is False:
            # 使用 TCP 連線 (asyncio.open_connection)
            self.market_reader, self.market_writer = await asyncio.open_connection(
                host='localhost', 
                port=10001, 
                local_addr=('127.0.0.1', 50001) # IPv6 格式
            )
            # 儲存連線物件
            self.market_connection = True
            print(f"[Market Data Publisher] Connected to TCP server at localhost:50001")
        return (self.market_reader, self.market_writer)
    
    async def private_connect(self):
        """Handles TCP connection to private data."""
        if self.private_connection is False:
            # 使用 asyncio.open_connection 建立 TCP 連線
            self.private_reader, self.private_writer = await asyncio.open_connection(
                host='localhost', 
                port=10001, 
                local_addr=('127.0.0.1', 50002) # IPv6 格式
            )
            self.private_connection = True
            print(f"[Private Data Publisher] Connected to TCP server at localhost:50002")
        return (self.private_reader, self.private_writer)
    
    async def close_connections(self):
        """Close all connections"""
        if self.market_writer:
            self.market_writer.close()
            await self.market_writer.wait_closed()
        
        if self.private_writer:
            self.private_writer.close()
            await self.private_writer.wait_closed()
            
        if self.redis_client:
            await self.redis_client.aclose()
            self.redis_client = None
            print("[Data Publisher] Redis connection closed")
    
    async def subscribe_market(self, symbol, config, interval: str):
        """Subscribe to market data streams via TCP connection"""
        # 檢查連線狀態，若無連線則重新連線
        if self.market_connection is False:
            print("[Market Data Publisher] No active connection. Attempting to reconnect...")
            await self.market_connect()
        
        subscription_types = {
            "orderbook": {"topic": f"{symbol}@orderbook", "type": "orderbook"},
            "bbo": {"topic": f"{symbol}@bbo", "type": "bbo"},
            "trade": {"topic": f"{symbol}@trade"},
            "kline": {"topic": f"{symbol}@kline_{interval}" if config.get("kline") else None}
        }
    
        for sub_type, params in subscription_types.items():
            if config.get(sub_type) and params["topic"]:
                subscription = {
                    "event": "subscribe",
                    "topic": params["topic"],
                    "symbol": symbol,
                    # "timestamp": int(time.time() * 1000)
                    "timestamp": 1733982717759
                }
                if "type" in params:
                    subscription["type"] = params["type"]
                
                try:
                    # 發送訂閱請求到 TCP 伺服器
                    self.market_writer.write(json.dumps(subscription).encode('utf-8') + b'\n')
                    await self.market_writer.drain()
                    print(f"[Market Data Publisher] Subscribed to {sub_type} for {symbol}")

                    # 接收伺服器回應 (可選)
                    response = await self.market_reader.read(16384)
                    print(f"[Market Data Publisher] Response: {response.decode('utf-8')}")
                except Exception as e:
                    print(f"[Market Data Publisher] Error subscribing to {sub_type}: {e}")

    async def subscribe_private(self, config):
        """Subscribe to private data streams via TCP connection"""
        # 檢查連線狀態，若無連線則重新連線
        if self.private_connection is False:
            print("[Private Data Publisher] No active connection. Attempting to reconnect...")
            await self.private_connect()
        
        # 設定訂閱主題
        subscription_types = {
            "executionreport": {"topic": "executionreport"},
            "position": {"topic": "position"},
            "balance": {"topic": "balance"}
        }

        for sub_type, params in subscription_types.items():
            if config.get(sub_type):
                subscription = {
                    "event": "subscribe",
                    "topic": params["topic"],
                    # "timestamp": int(time.time() * 1000)
                    "timestamp": 1733983629770
                }
                try:
                    # 發送訂閱請求到 TCP 伺服器
                    self.private_writer.write(json.dumps(subscription).encode('utf-8') + b'\n')
                    await self.private_writer.drain()
                    print(f"[Private Data Publisher] Subscribed to {sub_type}")

                    # 接收伺服器回應 (可選)
                    response = await self.private_reader.read(16384)
                    print(f"[Private Data Publisher] Response: {response.decode('utf-8')}")
                except Exception as e:
                    print(f"[Private Data Publisher] Error subscribing to {sub_type}: {e}")

    async def process_market_data(self, symbol, interval, message):
        """Process market data and publish to Redis"""
        try:
            data = json.loads(message)
            if 'topic' not in data:
                print(f"[Market Data Publisher] Message missing topic: {data}")
                return
            
            topic_mapping = {
                f"{symbol}@orderbook": f"{symbol}-orderbook",
                f"{symbol}@bbo": f"{symbol}-bbo",
                f"{symbol}@trade": f"{symbol}-trade",
                f"{symbol}@kline_{interval}": f"{symbol}-kline-{interval}"
            }
            
            redis_channel = topic_mapping.get(data['topic'])
            if redis_channel and 'data' in data:
                await self.publish_to_redis(redis_channel, data['data'])
                print(f"[Market Data Publisher] Published {redis_channel} data to Redis")
        
        except json.JSONDecodeError as e:
            print(f"[Market Data Publisher] JSON decode error: {e}")
        except Exception as e:
            print(f"[Market Data Publisher] Processing error: {e}")
    
    async def process_private_data(self, message):
        """Process private data and publish to Redis"""
        try:
            data = json.loads(message)
            
            if data.get("event") == "subscribe":
                print(f"[Private Data Publisher] Subscription {data.get('success', False) and 'successful' or 'failed'}")
                return
            
            if 'topic' not in data:
                print(f"[Private Data Publisher] Message missing topic: {data}")
                return
            
            topic_mapping = {
                "executionreport": "executionreport",
                "balance": "balance",
                "position": "position",
            }
            
            redis_channel = topic_mapping.get(data['topic'])
            if redis_channel and 'data' in data:
                await self.publish_to_redis(redis_channel, data['data'])
                print(f"[Private Data Publisher] Published {redis_channel} data to Redis")
        
        except json.JSONDecodeError as e:
            print(f"[Private Data Publisher] JSON decode error: {e}")
        except Exception as e:
            print(f"[Private Data Publisher] Processing error: {e}")

    async def read_from_connection(self, reader):
        """從指定連線讀取資料"""
        try:
            while True:
                # 使用 reader 讀取資料
                data = await reader.readline()
                if not data:
                    print("[Connection Closed] No more data received.")
                    break

                # 解析並處理資料
                message = json.loads(data.decode('utf-8').strip())
                print(f"[Data Received] {message}")
                await self.process_message(message)

        except Exception as e:
            print(f"Error in reading connection: {e}")

    async def start(self, symbol: str, market_config: dict, private_config: dict, interval: str = '1m'):
        """Start both market and private data streams"""
        # Connect to Redis
        await self.connect_to_redis()
        await self.subscribe_private(private_config)
        await self.subscribe_market(symbol, market_config, interval)
        
        try:
            while True:
                market_task = None
                private_task = None
                
                if any(market_config.values()):
                    # market_task = asyncio.create_task(self.market_connection.recv())
                    market_task = asyncio.create_task(self.market_reader.read(16384))

                if any(private_config.values()):
                    # private_task = asyncio.create_task(self.private_connection.recv())
                    private_task = asyncio.create_task(self.private_reader.read(16384))
                
                tasks = [task for task in [market_task, private_task] if task is not None]
                done, pending = await asyncio.wait(
                    tasks,
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                for task in done:
                    if task == market_task:
                        message = await task
                        await self.process_market_data(symbol, interval, message)
                    elif task == private_task:
                        message = await task
                        await self.process_private_data(message)
                
                for task in pending:
                    task.cancel()
                
                await asyncio.sleep(0.1)
        
        except asyncio.CancelledError:
            print("\nShutting down...")
        except Exception as e:
            print(f"Error in main loop: {e}")
        finally:
            await self.close_connections()


async def main():
    # Initialize 
    app_id = "460c97db-f51d-451c-a23e-3cce56d4c932"
    api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
    api_secret = 'FWQGXZCW4P3V4D4EN4EIBL6KLTDA'
    
    # Initialize API
    api = WooXStagingAPI(app_id=app_id, api_key=api_key, api_secret=api_secret, redis_host="localhost")
    
    # Market data configuration
    symbol = "SPOT_BTC_USDT"
    interval = "1m"
    market_config = {
        "bbo": True,
        "orderbook": True,
        "trade": False,
        "kline": False
    }
    
    # Private data configuration
    private_config = {
        "executionreport": False,
        "position": False,
        "balance": False
    }
    
    try:
        await api.start(symbol, market_config, private_config, interval)
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    except Exception as e:
        print(f"Program error: {str(e)}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    except Exception as e:
        print(f"Program error: {str(e)}")