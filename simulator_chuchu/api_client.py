import asyncio
import json
import websockets

class ExchangeSimulatorAPIClient:
    def __init__(self, base_url='ws://localhost:8765/api'):
        self.base_url = base_url

    async def make_request(self, method, params=None):
        async with websockets.connect(self.base_url) as websocket:
            request = {"method": method, "params": params}
            await websocket.send(json.dumps(request))
            response = await websocket.recv()
            return json.loads(response)

    async def send_order(self, params):
        return await self.make_request("send_order", params)

    async def send_algo_order(self, params):
        return await self.make_request("send_algo_order", params)

    async def edit_order_by_client_order_id(self, params):
        return await self.make_request("edit_order_by_client_order_id", params)

    async def cancel_order_by_client_order_id(self, params):
        return await self.make_request("cancel_order_by_client_order_id", params)
    
    async def cancel_order(self, params):
        return await self.make_request("cancel_order", params)
    
    async def cancel_orders(self, params):
        return await self.make_request("cancel_orders", params)

    async def cancel_all_pending_orders(self, params=None):
        return await self.make_request("cancel_all_pending_orders", params)

    async def get_open_orders(self, params=None):
        return await self.make_request("get_open_orders", params)

    async def get_order_info(self, params):
        return await self.make_request("get_order_info", params)

    async def get_positions(self, params=None):
        return await self.make_request("get_positions", params)

    async def get_account_info(self, params=None):
        return await self.make_request("get_account_info", params)

    async def get_balance(self, params=None):
        return await self.make_request("get_balance", params)

    async def transfer(self, params):
        return await self.make_request("transfer", params)