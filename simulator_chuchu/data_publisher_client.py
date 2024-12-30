import asyncio
import websockets
import json
from redis import asyncio as aioredis

class ExchangeSimulatorClient:
    def __init__(self, app_id, redis_host, redis_port=6379):
        self.app_id = app_id
        self.redis_host = redis_host
        self.redis_port = redis_port
        
        self.market_url = f"ws://localhost:8765/ws/stream/{self.app_id}"
        self.private_url = f"ws://localhost:8765/v2/ws/private/stream/{self.app_id}"
        
        self.market_connection = None
        self.private_connection = None
        self.redis_client = None

    async def connect_to_redis(self):
        """Connect to Redis server"""
        self.redis_client = await aioredis.from_url(
            f"redis://{self.redis_host}:{self.redis_port}",
            encoding="utf-8",
            decode_responses=True,
        )
        print(f"Connected to Redis at {self.redis_host}:{self.redis_port}")

    async def market_connect(self):
        """Connect to market data WebSocket"""
        self.market_connection = await websockets.connect(self.market_url)
        print(f"Connected to Exchange Simulator market data at {self.market_url}")

    async def private_connect(self):
        """Connect to private data WebSocket"""
        self.private_connection = await websockets.connect(self.private_url)
        print(f"Connected to Exchange Simulator private data at {self.private_url}")

    async def close_connections(self):
        """Close all connections"""
        if self.market_connection:
            await self.market_connection.close()
            print("Disconnected from Exchange Simulator market data")
        if self.private_connection:
            await self.private_connection.close()
            print("Disconnected from Exchange Simulator private data")
        if self.redis_client:
            await self.redis_client.close()
            print("Disconnected from Redis")

    async def subscribe_market(self, symbol, config, interval):
        """Subscribe to market data"""
        subscriptions = {
            "orderbook": {"topic": f"{symbol}@orderbook", "type": "orderbook"},
            "bbo": {"topic": f"{symbol}@bbo", "type": "bbo"},
            "trade": {"topic": f"{symbol}@trades"},
            "kline": {"topic": f"{symbol}@kline_{interval}"},
        }

        for sub_type, params in subscriptions.items():
            if config.get(sub_type):
                request = {
                        "event": "subscribe",
                        "topic": params["topic"],
                        "symbol": symbol
                    }
                if "type" in params:
                    request["type"] = params["type"]
                
                await self.market_connection.send(json.dumps(request))
                print(f"Subscribed to {sub_type} for {symbol}")

    async def subscribe_private(self, config, private_data_id):
        """Subscribe to private data"""
        subscriptions = {
            "executionreport": {"topic": "executionreport"},
            "position": {"topic": "position"},
            "balance": {"topic": "balance"},
        }

        for sub_type, params in subscriptions.items():
            if config.get(sub_type):
                request = {
                    "id":private_data_id,
                    "event": "subscribe",
                    "topic": params["topic"],
                }
                await self.private_connection.send(json.dumps(request))
                print(f"Subscribed to {sub_type}")

    async def handle_market_data(self):
        """Handle market data"""
        async for message in self.market_connection:
            try:
                data = json.loads(message)
                topic = data.get("topic")
                if topic:
                    redis_channel = f"{topic}"
                    if "symbol" in data:
                        redis_channel += f":{data['symbol']}"
                    await self.redis_client.publish(redis_channel, json.dumps(data))
                    print(f"Published market data to {redis_channel}")
            except Exception as e:
                print(f"Error handling market data: {e}")

    async def handle_private_data(self):
        """Handle private data"""
        async for message in self.private_connection:
            try:
                data = json.loads(message)
                topic = data.get("topic")
                if topic:
                    await self.redis_client.publish(topic, json.dumps(data))
                    print(f"Published private data to {topic}")
            except Exception as e:
                print(f"Error handling private data: {e}")

    async def start(self, symbol, market_config, private_config, interval, private_data_id):
        """Start the client"""
        try:
            await self.connect_to_redis()
            await self.market_connect()
            await self.private_connect()
            await self.subscribe_market(symbol, market_config, interval)
            await self.subscribe_private(private_config, private_data_id)

            market_task = asyncio.create_task(self.handle_market_data())
            private_task = asyncio.create_task(self.handle_private_data())

            await asyncio.gather(market_task, private_task)

        except Exception as e:
            print(f"Error in start: {e}")

        finally:
            await self.close_connections()

async def main():
    app_id = "data_publisher"

    client = ExchangeSimulatorClient(app_id, redis_host="localhost")

    symbol = "PERP_BTC_USDT"
    interval = "1m"
    market_config = {
        "orderbook": True,
        "bbo": False,
        "trade": True,
        "kline": False
    }

    private_data_id = 0
    private_config = {
        "executionreport": True,
        "position": True,
        "balance": True
    }

    await client.start(symbol, market_config, private_config, interval, private_data_id)

if __name__ == "__main__":
    asyncio.run(main())