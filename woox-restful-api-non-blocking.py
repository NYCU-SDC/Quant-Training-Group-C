import aiohttp
import asyncio
import random

class WooXStagingAPI:
    def __init__(self, base_url='https://api.staging.woox.io'):
        self.base_url = base_url

    async def make_request(self, session, endpoint, params={}):
        async with session.get(self.base_url + endpoint, params=params) as response:
            response.raise_for_status()
            return await response.json()

    async def get_orderbook(self, session, symbol, max_level=100):
        endpoint = f'/v1/public/orderbook/{symbol}'
        params = {"max_level": max_level}
        return await self.make_request(session, endpoint, params)

    async def get_trades(self, session, symbol, limit=100):
        endpoint = f'/v1/public/market_trades'
        params = {"symbol": symbol, "limit": limit}
        return await self.make_request(session, endpoint, params)

    async def get_kline(self, session, symbol, interval="1m", limit=100):
        endpoint = f'/v1/public/kline'
        params = {"symbol": symbol, "type": interval, 'limit': limit}
        return await self.make_request(session, endpoint, params)

async def background_processing_task():
    for i in range(5):
        print(f"[Background Task] Processing data... {i + 1}/5")
        await asyncio.sleep(random.uniform(0.01, 2))
    print("[Background Task] Completed background processing.")

async def busy_loop(api, session, symbol):
    tasks = [
        asyncio.create_task(api.get_orderbook(session, symbol)),
        asyncio.create_task(api.get_trades(session, symbol)),
        asyncio.create_task(api.get_kline(session, symbol))
    ]

    task_names = ["Orderbook", "Trades", "Kline"]

    while True:
        print(f"\nPolling for {symbol} data...\n")
        for i, task in enumerate(tasks):
            if task.done():
                try:
                    result = await task
                    print(f"[{task_names[i]}] done.")
                    print(f"[{task_names[i]}] result={result}")
                    if task_names[i] == "Orderbook":
                        tasks[i] = asyncio.create_task(api.get_orderbook(session, symbol))
                    elif task_names[i] == "Trades":
                        tasks[i] = asyncio.create_task(api.get_trades(session, symbol))
                    elif task_names[i] == "Kline":
                        tasks[i] = asyncio.create_task(api.get_kline(session, symbol))

                except Exception as e:
                    print(f"[{task_names[i]} Error] {e}")

        await background_processing_task()

        await asyncio.sleep(0.1)

async def main():
    api = WooXStagingAPI()
    symbol = 'SPOT_BTC_USDT'

    async with aiohttp.ClientSession() as session:
        await busy_loop(api, session, symbol)

asyncio.run(main())

