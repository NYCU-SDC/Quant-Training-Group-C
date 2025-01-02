import asyncio
import json
from redis import asyncio as aioredis
from data_processing.Orderbook import OrderBook
import time
import datetime

class OrderbookSubscriber:
    def __init__(self, symbol: str, redis_host: str = "localhost", redis_port: int = 6379):
        """
        初始化訂閱者
        symbol: 交易對符號
        redis_host: Redis 服務器地址
        redis_port: Redis 服務器端口
        """
        self.symbol = symbol
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis = None
        self.orderbook = OrderBook(symbol)
        self.last_update_time = None
        
    async def connect_to_redis(self):
        """建立與 Redis 服務器的連接"""
        try:
            self.redis = await aioredis.from_url(
                f"redis://{self.redis_host}:{self.redis_port}",
                encoding='utf-8',
                decode_responses=True
            )
            print(f"已連接到 Redis 服務器: {self.redis_host}:{self.redis_port}")
        except Exception as e:
            print(f"Redis 連接失敗: {str(e)}")
            
    def format_timestamp(self, ts):
        """將毫秒時間戳轉換為可讀格式"""
        return datetime.datetime.fromtimestamp(ts/1000).strftime('%Y-%m-%d %H:%M:%S.%f')
    
    async def process_orderbook_message(self, message_data: dict):
        """處理從 Redis 接收到的訂單簿數據"""
        try:
            # 解析時間戳和數據
            ts = message_data.get("ts")
            data = message_data.get("data", {})
            
            # 準備更新數據
            update_data = {
                "symbol": self.symbol,
                "asks": data.get("asks", []),
                "bids": data.get("bids", [])
            }
            
            # 更新訂單簿
            asks_mean, bids_mean = self.orderbook.update(update_data)
            
            # 計算並顯示市場指標
            current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
            orderbook_time = self.format_timestamp(ts)

            print("\n" + "="*50)
            print(f"系統當前時間: {current_time}")
            print(f"訂單簿數據時間: {orderbook_time}")
            
            # 顯示訂單簿狀態，設定max_level
            self.orderbook.dump(max_level=10)
            
            # 計算並顯示訂單簿失衡度
            total_bid_size = sum(bid[1] for bid in self.orderbook.bids)
            total_ask_size = sum(ask[1] for ask in self.orderbook.asks)
            imbalance = (total_bid_size - total_ask_size) / (total_bid_size + total_ask_size)
            
            print("\n=== 市場指標 ===")
            print(f"賣單加權平均價格: {self.orderbook.asks_mean:.2f}")
            print(f"買單加權平均價格: {self.orderbook.bids_mean:.2f}")
            print(f"訂單簿失衡度: {imbalance:.4f}")
            
            print("\n=== 價格波動性 ===")
            print(f"賣單價格波動性: {self.orderbook.asks_sample_variance:.4f}")
            print(f"買單價格波動性: {self.orderbook.bids_sample_variance:.4f}")
            
            print("="*50 + "\n")
            
        except Exception as e:
            print(f"處理訂單簿數據時發生錯誤: {e}")
    
    async def subscribe_to_orderbook(self):
        """訂閱訂單簿數據"""
        if not self.redis:
            await self.connect_to_redis()
        
        channel = f"{self.symbol}-orderbook"
        pubsub = self.redis.pubsub()
        
        try:
            await pubsub.subscribe(channel)
            print(f"已訂閱頻道: {channel}")
            
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message is not None:
                    try:
                        message_data = json.loads(message['data'])
                        await self.process_orderbook_message(message_data)
                    except json.JSONDecodeError:
                        print(f"JSON 解析錯誤: {message['data']}")
                
                await asyncio.sleep(0.1)  # 避免 CPU 使用率過高
                
        except Exception as e:
            print(f"訂閱過程中發生錯誤: {e}")
        finally:
            await pubsub.unsubscribe(channel)
            await self.redis.aclose()

async def main():
    """主函數"""
    # 設置交易對
    symbol = "PERP_BTC_USDT"
    
    # 創建訂閱者實例
    subscriber = OrderbookSubscriber(symbol)
    
    try:
        # 開始訂閱
        await subscriber.subscribe_to_orderbook()
    except KeyboardInterrupt:
        print("\n程序被用戶中斷")
    except Exception as e:
        print(f"程序錯誤: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())