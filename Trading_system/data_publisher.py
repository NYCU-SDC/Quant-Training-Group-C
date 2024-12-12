import json
import asyncio
import websockets
import time
import datetime
import hmac
import hashlib
from redis import asyncio as aioredis

# Import your existing classes
from data_processing.Orderbook import OrderBook
from data_processing.BBO import BBO

class WooXStagingAPI:
    def __init__(self, app_id: str, api_key: str, api_secret: str, redis_host: str, redis_port: int = 6379):
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        
        self.market_data_url = f"wss://wss.staging.woox.io/ws/stream/{self.app_id}"
        self.private_data_url = f"wss://wss.staging.woox.io/v2/ws/private/stream/{self.app_id}"
        
        self.redis_host = redis_host
        self.redis_port = redis_port
        
        self.market_connection = None
        self.private_connection = None
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
            # If data is already string, using it directly
            if isinstance(data, str):
                await self.redis_client.publish(channel, data)
            else:
                # If data is dict, 序列化一次
                await self.redis_client.publish(channel, json.dumps(data))

    async def market_connect(self):
        """Handles WebSocket connection to market data."""
        if self.market_connection is None:
            self.market_connection = await websockets.connect(self.market_data_url)
            print(f"[Market Data Publisher] Connected to {self.market_data_url}")
        return self.market_connection
    
    async def private_connect(self):
        """Handles WebSocket connection to private data."""
        if self.private_connection is None:
            self.private_connection = await websockets.connect(self.private_data_url)
            print(f"[Private Data Publisher] Connected to {self.private_data_url}")
        return self.private_connection
    
    async def close_connections(self):
        """Close all connections"""
        if self.market_connection:
            await self.market_connection.close()
            self.market_connection = None
            print("[Market Data Publisher] Market WebSocket connection closed")
            
        if self.private_connection:
            await self.private_connection.close()
            self.private_connection = None
            print("[Private Data Publisher] Private WebSocket connection closed")
            
        if self.redis_client:
            await self.redis_client.aclose()
            self.redis_client = None
            print("[Data Publisher] Redis connection closed")
    
    def generate_signature(self, body):
        """Generate signature for authentication"""
        key_bytes = bytes(self.api_secret, 'utf-8')
        body_bytes = bytes(body, 'utf-8')
        return hmac.new(key_bytes, body_bytes, hashlib.sha256).hexdigest()
    
    async def authenticate(self):
        """Authenticate private connection"""
        connection = await self.private_connect()
        timestamp = int(time.time() * 1000)
        data = f"|{timestamp}"
        signature = self.generate_signature(data)
        
        auth_message = {
            "event": "auth",
            "params": {
                "apikey": self.api_key,
                "sign": signature,
                "timestamp": timestamp
            }
        }
        await connection.send(json.dumps(auth_message))
        response = json.loads(await connection.recv())
        
        if response.get("success"):
            print("[Private Data Publisher] Authentication successful")
        else:
            print(f"[Private Data Publisher] Authentication failed: {response.get('errorMsg')}")
    
    async def respond_pong(self, connection, publisher_type="Market"):
        """Responds to server PINGs with a PONG."""
        if connection and not connection.closed:
            pong_message = {
                "event": "pong",
                "ts": int(time.time() * 1000)
            }
            await connection.send(json.dumps(pong_message))
            print(f"[{publisher_type} Data Publisher] Sent PONG response")
    
    async def handle_ping_pong(self, message, connection, publisher_type="Market"):
        """Handle ping-pong mechanism"""
        data = json.loads(message)
        if data.get("event") == "ping":
            print(f"[{publisher_type} Data Publisher] Received PING from server")
            await self.respond_pong(connection, publisher_type)
    
    async def subscribe_market(self, symbol, config, interval: str):
        """Subscribe to market data streams"""
        if self.market_connection is None or self.market_connection.closed:
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
                    "symbol": symbol
                }
                if "type" in params:
                    subscription["type"] = params["type"]
                
                await self.market_connection.send(json.dumps(subscription))
                print(f"[Market Data Publisher] Subscribed to {sub_type} for {symbol}")
    
    async def subscribe_private(self, config):
        """Subscribe to private data streams"""
        if self.private_connection is None or self.private_connection.closed:
            print("[Private Data Publisher] No active connection. Attempting to reconnect...")
            await self.private_connect()
        
        subscription_types = {
            "executionreport": {"topic": "executionreport"},
            "position": {"topic": "position"},
            "balance": {"topic": "balance"}
        }
        
        for sub_type, params in subscription_types.items():
            if config.get(sub_type):
                subscription = {
                    "event": "subscribe",
                    "topic": params["topic"]
                }
                await self.private_connection.send(json.dumps(subscription))
                print(f"[Private Data Publisher] Subscribed to {sub_type}")

    async def process_market_data(self, symbol, interval, message):
        """Process market data and publish to Redis"""
        try:
            data = json.loads(message)
            if data.get("event") == "ping":
                await self.handle_ping_pong(message, self.market_connection)
                return
            
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
                # Subscribed Message "ts" and "data", create the original structure
                publish_data = {
                    "ts": data.get("ts"), # the timestamp of this message
                    "data": data['data']
                }
                await self.publish_to_redis(redis_channel, json.dumps(publish_data))
                print(f"[Market Data Publisher] Published {redis_channel} data to Redis")
        
        except json.JSONDecodeError as e:
            print(f"[Market Data Publisher] JSON decode error: {e}")
        except Exception as e:
            print(f"[Market Data Publisher] Processing error: {e}")
    
    async def process_private_data(self, message):
        """Process private data and publish to Redis"""
        try:
            data = json.loads(message)
            if data.get("event") == "ping":
                await self.handle_ping_pong(message, self.private_connection, "Private")
                return
            
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
    
    async def start(self, symbol: str, market_config: dict, private_config: dict, interval: str = '1m'):
        """Start both market and private data streams"""
        # Connect to Redis
        await self.connect_to_redis()
        
        # Connect and authenticate private stream
        await self.authenticate()
        await self.subscribe_private(private_config)
        
        # Connect and subscribe market stream
        await self.subscribe_market(symbol, market_config, interval)
        
        try:
            while True:
                market_task = None
                private_task = None
                
                if any(market_config.values()):
                    market_task = asyncio.create_task(self.market_connection.recv())
                if any(private_config.values()):
                    private_task = asyncio.create_task(self.private_connection.recv())
                
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
    symbol = "PERP_BTC_USDT"
    interval = "1m"
    market_config = {
        "orderbook": True,
        "bbo": False,
        "trade": False,
        "kline": False
    }
    
    # Private data configuration
    private_config = {
        "executionreport": True,
        "position": True,
        "balance": True
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