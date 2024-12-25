import asyncio
import json
import logging
from strategy_executor import StrategyExecutor


class MarketMakingStrategy:
    def __init__(self, signal_channel, config):
        self.signal_channel = signal_channel
        self.config = config
        self.symbol = config['symbol']
        self.bid_offset = config['bid_offset']
        self.ask_offset = config['ask_offset']
        self.trade_size = config['trade_size']
        self.refresh_interval = config['refresh_interval']
        self.logger = logging.getLogger("MarketMakingStrategy")
        self.current_bid_order = None
        self.current_ask_order = None

    def start(self):
        self.logger.info("Market Making Strategy started.")

    def stop(self):
        self.logger.info("Market Making Strategy stopped.")

    async def execute(self, channel, data, redis_client):
        try:
            if 'orderbook' in channel:
                if not data['data']['bids'] or not data['data']['asks']:
                    self.logger.warning("Incomplete orderbook data received.")
                    return

                top_bid = float(data['data']['bids'][0][0])
                top_ask = float(data['data']['asks'][0][0])

                new_bid_price = round(top_bid * (1 - self.bid_offset), 2)
                new_ask_price = round(top_ask * (1 + self.ask_offset), 2)

                if self.current_bid_order != new_bid_price or self.current_ask_order != new_ask_price:
                    self.logger.info(f"Refreshing orders: Bid={new_bid_price}, Ask={new_ask_price}")

                    await self.cancel_orders(redis_client)

                    await self.place_order(redis_client, 'LONG', 'LIMIT', self.trade_size, new_bid_price)
                    await self.place_order(redis_client, 'SHORT', 'LIMIT', self.trade_size, new_ask_price)

                    self.current_bid_order = new_bid_price
                    self.current_ask_order = new_ask_price

        except Exception as e:
            self.logger.error(f"Error executing market making strategy: {e}")

    async def place_order(self, redis_client, position_side, order_type, quantity, price):
        signal = {
            'symbol': self.symbol,
            'position_side': position_side,
            'order_type': order_type,
            'quantity': quantity,
            'price': price,
            'reduce_only': False
        }
        await redis_client.publish(self.signal_channel, json.dumps(signal))
        self.logger.info(f"Placed {position_side} order: {signal}")

    async def cancel_orders(self, redis_client):
        self.logger.info("Cancelling all outstanding orders.")

async def main():

    logging.basicConfig(level=logging.INFO)

    config = {
        'symbol': 'SPOT_BTC_USDT',
        'bid_offset': 0.001,
        'ask_offset': 0.001,
        'trade_size': 0.01,
        'refresh_interval': 5,
        'signal_channel': 'trading_signals'
    }

    executor = StrategyExecutor(redis_url="redis://localhost:6379", config={})
    await executor.add_strategy(MarketMakingStrategy, config)

    market_channels = ['[MD]SPOT_BTC_USDT-orderbook']
    private_channels = []

    await executor.start(market_channels, private_channels)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStrategy terminated by user.")
