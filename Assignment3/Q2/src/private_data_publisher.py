import json
import asyncio
import websockets
import time
import datetime
import hmac
import hashlib


class WooXStagingAPIPrivateMessage:
    def __init__(self, app_id: str, api_key, api_secret):
        self.app_id = app_id
        self.market_data_uri = f"wss://wss.staging.woox.io/ws/stream/{self.app_id}"
        self.private_uri = f"wss://wss.staging.woox.io/v2/ws/private/stream/{self.app_id}"
        self.api_key = api_key
        self.api_secret = api_secret
        self.private_connection = None
        self.private_connection = None
        self.orderbooks = {}
        self.bbo_data = {}

    def generate_signature(self, body):
        key_bytes = bytes(self.api_secret, 'utf-8')
        body_bytes = bytes(body, 'utf-8')
        return hmac.new(key_bytes, body_bytes, hashlib.sha256).hexdigest()

    async def connect_private(self):
        """Establish the WebSocket connection."""
        if self.private_connection is None:
            self.private_connection = await websockets.connect(self.private_uri)
            print(f"Connected to {self.private_uri}")
        return self.private_connection

    async def authenticate(self):
        """Send the authentication message."""
        connection = await self.connect_private()
        timestamp = int(time.time() * 1000)  # Current timestamp in milliseconds
        data = f"|{timestamp}"
        # Generate the signature
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
            print("Authentication successful.")
        else:
            print(f"Authentication failed: {response.get('errorMsg')}")

    async def subscribe(self, websocket, config):
        """Subscribe to executionreport, position."""
        if config.get("executionreport"):
            subscribe_message = {
                "event": "subscribe",
                "topic": "executionreport",
            }
            await websocket.send(json.dumps(subscribe_message))
            print(f"Subscribed to executionreport")
        
        if config.get("position"):
            subscribe_message = {
                "event": "subscribe",
                "topic": "position",
            }
            await websocket.send(json.dumps(subscribe_message))
            print(f"Subscribed to position")

        if config.get("balance"):
            subscribe_message = {
                "event": "subscribe",
                "topic": "balance",
            }
            await websocket.send(json.dumps(subscribe_message))
            print(f"Subscribed to balance")

    async def respond_pong(self, websocket):
        """Responds to server PINGs with a PONG."""
        pong_message = {
            "event": "pong",
            "ts": int(asyncio.get_event_loop().time() * 1000)
        }
        await websocket.send(json.dumps(pong_message))

    async def process_market_data(self, message):
        """Process market data and publish it to Redis."""
        data = json.loads(message)
        topic = data.get("topic", "")
        
        if topic == 'position' :
            print(data['positions'])

        if topic == 'executionreport' :
            print(data['executionreport'])
        
        if topic == 'balance' :
            print(data['blances'])

    async def listen_for_data(self, websocket, config):
        """Listen for incoming market data and publish to Redis."""
        async for message in websocket:
            print(f"Received message: {message}")
            await self.process_market_data(message)

    async def close_connection(self):
        """Gracefully closes the WebSocket connection."""
        if self.private_connection is not None:
            await self.private_connection.close()
            self.private_connection = None
            print("Market WebSocket connection closed")

    async def start(self, config):
        """Start the WebSocket connection and market data subscription."""
        auth_connection = await self.authenticate()
        websocket = await self.connect_private()
        await self.subscribe(websocket, config)
        await self.listen_for_data(websocket, config)

# Example usage
async def main():
    app_id = "460c97db-f51d-451c-a23e-3cce56d4c932"
    api_key = 'sdFgbf5mnyDD/wahfC58Kw=='
    api_secret = 'FWQGXZCW4P3V4D4EN4EIBL6KLTDA'
    api = WooXStagingAPIPrivateMessage(app_id=app_id, api_key=api_key, api_secret=api_secret, redis_host="localhost")
    await api.start(config={"executionreport": True, "position": True, "balance": True})

if __name__ == "__main__":
    asyncio.run(main())