import asyncio
import json
import logging
from strategy_executor import StrategyExecutor

class AlphaSpreadStrategy:
    def __init__(self, signal_channel, config):
        self.signal_channel = signal_channel
        self.config = config
        self.spread_threshold = config['spread_threshold']
        self.trade_size = config['trade_size']
        self.logger = logging.getLogger("AlphaSpreadStrategy")

    def start(self):
        self.logger.info("Alpha Spread Strategy started.")

    def stop(self):
        self.logger.info("Alpha Spread Strategy stopped.")

    async def execute(self, channel, data, redis_client):
        try:
            if 'orderbook' in channel:
                if not data['data']['bids'] or not data['data']['asks']:
                    self.logger.warning("Incomplete order book data received.")
                    return
                
                bid = float(data['data']['bids'][0][0])
                ask = float(data['data']['asks'][0][0])
                spread = (ask - bid) / bid

                self.logger.info(f"Bid: {bid}, Ask: {ask}, Spread: {spread:.4%}")

                if spread > self.spread_threshold:
                    long_signal = {
                        'symbol': self.config['symbol'],
                        'position_side': 'LONG',
                        'order_type': 'LIMIT',
                        'quantity': self.trade_size,
                        'price': bid,
                        'reduce_only': False
                    }
                    await redis_client.publish(self.signal_channel, json.dumps(long_signal))
                    self.logger.info(f"Published LONG signal: {long_signal}")

                    short_signal = {
                        'symbol': self.config['symbol'],
                        'position_side': 'SHORT',
                        'order_type': 'LIMIT',
                        'quantity': self.trade_size,
                        'price': ask,
                        'reduce_only': False
                    }
                    await redis_client.publish(self.signal_channel, json.dumps(short_signal))
                    self.logger.info(f"Published SHORT signal: {short_signal}")

        except Exception as e:
            self.logger.error(f"Error executing strategy: {e}")

async def main():
    logging.basicConfig(level=logging.INFO)

    config = {
        'symbol': 'SPOT_BTC_USDT',
        'spread_threshold': 0.0088,
        'trade_size': 0.01,        
        'signal_channel': 'trading_signals'
    }

    executor = StrategyExecutor(redis_url="redis://localhost:6379", config={})
    await executor.add_strategy(AlphaSpreadStrategy, config)

    market_channels = ['[MD]PERP_BTC_USDT-orderbook']
    private_channels = []

    await executor.start(market_channels, private_channels)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStrategy terminated by user.")
