import asyncio
import json
import datetime
import time
from redis import asyncio as aioredis

class DataSubscriber:
    def __init__(self, redis_host="localhost", redis_port=6379):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis = None
        self.active_channels = {}
        self.kline_last_process_time = {}
    
    async def connect_to_redis(self):
        """Connect to Redis Server"""
        self.redis = await aioredis.from_url(
            f"redis://{self.redis_host}:{self.redis_port}",
            encoding='utf-8',
            decode_responses=True
        )
        print(f"Connected to Redis at {self.redis_host}:{self.redis_port}")
    
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

    def get_interval_seconds(self, interval: str) -> int:
        """Convert interval string to seconds"""
        unit = interval[-1]
        value = int(interval[:-1])
        
        if unit == 'm':
            return value * 60
        elif unit == 'h':
            return value * 3600
        elif unit == 'd':
            return value * 86400
        else:
            raise ValueError(f"Unsupported interval format: {interval}")
    
    def get_current_interval_time(self, interval: str) -> tuple[int, int]:
        """Calculate current interval's start and end time"""
        interval_seconds = self.get_interval_seconds(interval)
        current_time = int(time.time())
        
        # 計算當前時間所在的區間起始時間
        interval_start = (current_time // interval_seconds) * interval_seconds
        interval_end = interval_start + interval_seconds
        
        return interval_start, interval_end

    def should_process_kline(self, symbol: str, interval: str, kline_data: dict) -> bool:
        """
        Check if we should process this kline data based on kline's own time
        """
        try:
            # 從 kline 數據中獲取結束時間
            end_time = int(kline_data.get('endTime', 0))
            
            # 如果是第一次處理該 symbol 的數據
            if symbol not in self.kline_last_process_time:
                self.kline_last_process_time[symbol] = end_time
                return True
            
            # 如果是新的時間區間的數據
            if end_time > self.kline_last_process_time[symbol]:
                self.kline_last_process_time[symbol] = end_time
                return True
                
            return False
            
        except Exception as e:
            print(f"Error in should_process_kline: {e}")
            return False
    
    async def process_orderbook_data(self, data):
        """Process orderbook data"""
        print("\nOrderbook Data:")
        print(f"Asks (first 5): {data.get('asks', [])[:5]}")
        print(f"Bids (first 5): {data.get('bids', [])[:5]}")
    
    async def process_bbo_data(self, data):
        """Process BBO data"""
        print("\nBBO Data:")
        print(f"Best Bid: {data.get('bid', '')}")
        print(f"Best Ask: {data.get('ask', '')}")
    
    async def process_trade_data(self, data):
        """Process trade data"""
        print("\nTrade Data:")
        print(f"Price: {data.get('price', '')}")
        print(f"Size: {data.get('size', '')}")
        print(f"Side: {data.get('side', '')}")
    
    async def process_kline_data(self, data):
        """Process kline data"""
        print("\nKline Data:")
        print(f"startTime: {data.get('startTime', '')}")
        print(f"endTime: {data.get('endTime', '')}")
        print(f"open: {data.get('open', '')}")
        print(f"high: {data.get('high', '')}")
        print(f"low: {data.get('low', '')}")
        print(f"close: {data.get('close', '')}")
        print(f"volume: {data.get('volume', '')}")
        
        # 將處理後的數據存儲到Redis
        await self.redis.set('latest_kline', json.dumps(data))
        # 添加這一行來發布消息
        await self.redis.publish('latest_kline', json.dumps(data))
    
    async def process_execution_report(self, data):
        """Process execution report data"""
        print("\nExecution Report:")
        print(f"Order ID: {data.get('orderId', '')}")
        print(f"Symbol: {data.get('symbol', '')}")
        print(f"Side: {data.get('side', '')}")
        print(f"Price: {data.get('price', '')}")
        print(f"Quantity: {data.get('quantity', '')}")
        print(f"Status: {data.get('status', '')}")
    
    async def process_position_data(self, data):
        """Process position data"""
        print("\nPosition Data:")
        print(f"Symbol: {data.get('symbol', '')}")
        print(f"Size: {data.get('size', '')}")
        print(f"Entry Price: {data.get('entryPrice', '')}")
        print(f"Unrealized PNL: {data.get('unrealizedPnl', '')}")
    
    async def process_balance_data(self, data):
        """Process balance data"""
        print("\nBalance Data:")
        print(f"Asset: {data.get('asset', '')}")
        print(f"Total Balance: {data.get('total', '')}")
        print(f"Available Balance: {data.get('available', '')}")
        print(f"Frozen Balance: {data.get('frozen', '')}")
    
    async def process_message(self, channel: str, data: dict):
        """Process channel message"""
        try:
            # 檢查是否是 kline 數據
            if 'kline' in channel:
                symbol = channel.split('-kline-')[0]
                interval = channel.split('-kline-')[1]
                
                # 根據 kline 數據本身的時間來判斷是否處理
                if not self.should_process_kline(symbol, interval, data):
                    return
            
            # 輸出處理信息
            print(f"\n{'='*50}")
            print(f"Channel: {channel}")
            print(f"Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}")
            
            # 根據不同類型處理數據
            if 'orderbook' in channel:
                await self.process_orderbook_data(data)
            elif 'bbo' in channel:
                await self.process_bbo_data(data)
            elif 'trade' in channel:
                await self.process_trade_data(data)
            elif 'kline' in channel:
                await self.process_kline_data(data)
            elif channel == 'executionreport':
                await self.process_execution_report(data)
            elif channel == 'position':
                await self.process_position_data(data)
            elif channel == 'balance':
                await self.process_balance_data(data)
            
            print(f"{'='*50}\n")
            
        except Exception as e:
            print(f"Error processing message for channel {channel}: {e}")
    
    async def subscribe_to_data(self, symbol: str, market_config: dict, private_config: dict, interval: str = '1m'):
        """Subscribe to both market and private data"""
        if not self.redis:
            await self.connect_to_redis()
        
        pubsub = self.redis.pubsub()
        
        # Get all channel names
        market_channels = self.get_market_channel_names(symbol, market_config, interval)
        private_channels = self.get_private_channel_names(private_config)
        channels = market_channels + private_channels
        
        if not channels:
            print("No channels selected for subscription")
            return
        
        await pubsub.subscribe(*channels)
        print(f"Subscribed to channels: {channels}")
        
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message is not None:
                    channel = message['channel']
                    try:
                        data = json.loads(message['data'])
                        await self.process_message(channel, data)
                    except json.JSONDecodeError:
                        print(f"Failed to decode message data: {message['data']}")
                
                await asyncio.sleep(0.1)
                
        except asyncio.CancelledError:
            print("\nUnsubscribing from channels...")
            await pubsub.unsubscribe()
            await self.redis.aclose()
        except Exception as e:
            print(f"Error in subscription: {e}")

async def main():
    subscriber = DataSubscriber()
    
    symbol = "PERP_BTC_USDT"
    interval = "1m"
    
    # Market data configuration
    market_config = {
        "orderbook": True,
        "bbo": True,
        "trade": True,
        "kline": True
    }
    
    # Private data configuration
    private_config = {
        "executionreport": True,
        "position": True,
        "balance": True
    }
    
    try:
        subscription_task = asyncio.create_task(
            subscriber.subscribe_to_data(symbol, market_config, private_config, interval)
        )
        
        await asyncio.gather(subscription_task)
        
    except KeyboardInterrupt:
        print("\nGracefully shutting down...")
    finally:
        if 'subscription_task' in locals():
            subscription_task.cancel()
            try:
                await subscription_task
            except asyncio.CancelledError:
                pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    except Exception as e:
        print(f"Program error: {str(e)}")