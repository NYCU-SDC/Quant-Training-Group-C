import json
import asyncio
import logging
import time
from typing import List, Dict, Any
from redis import asyncio as aioredis
from redis.exceptions import ConnectionError, TimeoutError
from strategy_logics.cta_strategy import ExampleStrategy

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('StrategyExecutor')

class StrategyExecutor:
    def __init__(self, redis_url="redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client = None
        self.strategies = []
        self.running = False
        self.subscription_channels = set()
        self.pubsub = None

    def add_strategy(self, strategy):
        """Add a strategy to the executor."""
        self.strategies.append(strategy)
        if strategy not in self.strategies:
            self.strategies.append(strategy)
            print("[Strategy Executor] Added strategy:", self.strategies)
        else:
            print(f"[Strategy Executor] {self.strategies} already exists")
    
    def remove_strategy(self, strategy):
        """Remove a strategy to the executor."""
        if strategy in self.strategies:
            self.strategies.remove(strategy)
            print("[Strategy Executor] Removed strategy:", self.strategies)

    async def connect_to_redis(self):
        """Connect to Redis."""
        self.redis_client = await aioredis.from_url(self.redis_url)
        print(f"[Strategy Executor] Connected to Redis at {self.redis_url}")

    def get_market_channel_names(self, symbol: str, config: dict, interval: str = '1m') -> list:
        """Get market data channel names"""
        channels = []
        if config.get("orderbook"):
            channels.append(f"{symbol}-orderbook")
        if config.get("bbo"):
            channels.append(f"{symbol}-bbo")
        if config.get("trade"):
            channels.append(f"{symbol}-trade")
        if config.get("kline"):
            channels.append(f"{symbol}-kline-{interval}")
        return channels
    
    def get_processed_channel_names(self, symbol: str, config: dict) -> list:
        """Get processed data channel names"""
        channels = []
        if config.get("kline"):
            channels.append(f"{symbol}-processed-kline")  # processed-kline channel
        if config.get("orderbook"):
            channels.append(f"{symbol}-processed-orderbook")  # processed-orderbook channel 
        # 如果有其他處理過的數據，也可以加入
        return channels
    
    def get_private_channel_names(self, config: dict) -> list:
        """Get private data channel names"""
        channels = []
        if config.get("executionreport"):
            channels.append("executionreport")
        if config.get("position"):
            channels.append("position")
        if config.get("balance"):
            channels.append("balance")
        return channels

    async def subscribe_to_channels(self, symbol: str, market_config: dict, private_config: dict, interval: str = '1m'):
        """Subscribe to both market and private data channels"""
        if not self.redis_client:
            await self.connect_to_redis()
        
        pubsub = self.redis_client.pubsub()

        # Get all channel names
        market_channels = self.get_market_channel_names(symbol, market_config, interval)
        processed_channels = self.get_processed_channel_names(symbol, market_config)
        private_channels = self.get_private_channel_names(private_config)
        channels = market_channels + processed_channels + private_channels

        if not channels:
            print("No channels selected for subscription")
            return
        
        await pubsub.subscribe(*channels)
        print(f"Subscribed to channels: {channels}")
        return pubsub

    async def dispatch_to_strategies(self, channel: str, data: dict):
        """Dispatch data to strategies with identification of processed data"""
        try:
            # 確保 channel 是字符串格式
            channel = channel.decode('utf-8') if isinstance(channel, bytes) else channel
            print(f"[Strategy Executor] Dispatching data from channel {channel}")
            
            # analyze data
            try:
                if isinstance(data, str):
                    parsed_data = json.loads(data)
                else:
                    parsed_data = data
            except json.JSONDecodeError:
                print(f"[Strategy Executor] Invalid JSON data received on channel {channel}")
                return
            
            # run strategy
            tasks = []
            for strategy in self.strategies:
                task = asyncio.create_task(
                    strategy.execute(channel, parsed_data, self.redis_client)
                )
                tasks.append(task)
            
            await asyncio.gather(*tasks)
            
        except Exception as e:
            print(f"[Strategy Executor] Error dispatching to strategies: {str(e)}")
            

    async def listen_to_market_data(self, pubsub):
        """Listen for market data and dispatch it to strategies."""
        self.running = True
        try:
            async for message in pubsub.listen():
                if not self.running:
                    break
            
                if message["type"] == "message":
                    try:
                        channel = message["channel"]
                        data = json.loads(message["data"])
                        print(f"[Strategy Executor] Received data from channel {channel}")
                        
                        await self.dispatch_to_strategies(channel, data)
                    except json.JSONDecodeError as e:
                        print(f"[Strategy Executor] Failed to decode message data: {str(e)}")
                    except Exception as e:
                        print(f"Error processing message: {str(e)}")
                        
        except asyncio.CancelledError:
            print("Market data listener cancelled")
        except Exception as e:
            print(f"Error in market data listener: {str(e)}")
        finally:
            self.running = False
    
    async def stop(self):
        self.running = False
        if self.pubsub:
            await self.pubsub.unsubscribe()
        if self.redis_client:
            await self.redis_client.aclose()
        logger.info("Strategy executor stopped")
        


async def main():
    redis_url = "redis://localhost:6379"

    # Strategy Executor
    strategy_executor = StrategyExecutor(redis_url)
    
    try:
        await strategy_executor.connect_to_redis()
        print("[Strategy Executor] Connecting to Redis...")

        # add strategy signal
        strategy_executor.add_strategy(ExampleStrategy(signal_channel="order-executor"))

        # Settings
        symbol = 'PERP_BTC_USDT'
        interval = '1m'

        market_config = {
            "orderbook": True,
            "bbo": True,
            "trade": False,
            "kline": False
        }
            
        private_config = {
            "executionreport": True,
            "position": True,
            "balance": True
        }
        # Subscribe the channels
        pubsub = await strategy_executor.subscribe_to_channels(symbol, market_config, private_config, interval)

        # Run both concurrently
        await asyncio.gather(
            strategy_executor.listen_to_market_data(pubsub),
            # order_executor.listen_for_signals(signal_pubsub),
        )
    except KeyboardInterrupt:
        logger.info("Program terminated by user")
    except Exception as e:
        logger.error(f"Program error: {str(e)}")
    finally:
        await strategy_executor.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program terminated by user")
    except Exception as e:
        logger.error(f"Program error: {str(e)}")
