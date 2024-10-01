import json
import asyncio
import websockets

class WooXStagingAPI:
    def __init__(self, app_id: str):
        self.app_id = app_id
        self.uri = f"wss://wss.staging.woox.io/ws/stream/{self.app_id}"
        self.connection = None
        #  利用 Ping-Pong 機制來保持連接活躍
        self.keep_alive_interval = 10  # Ping interval (seconds)

    #  建立與 WooX WebSocket 伺服器的持久連接
    async def connect(self):
        """Handles WebSocket connection"""
        if self.connection is None:
            self.connection = await websockets.connect(self.uri)
            print(f"Connected to {self.uri}")
        return self.connection

    async def respond_pong(self, websocket):
        """Responds to server PINGs with a PONG"""
        pong_message = {
            "event": "pong",
            "ts": int(asyncio.get_event_loop().time() * 1000)  # Current timestamp in milliseconds
        }
        await websocket.send(json.dumps(pong_message))
        print(f"Sent PONG: {pong_message}")

    # # 定期送出 pong
    # async def send_ping(self, websocket):
    #     """Sends a periodic PING message to the server"""
    #     ping_message = {
    #         "event": "ping",
    #         "ts": int(asyncio.get_event_loop().time() * 1000)  # Current timestamp in milliseconds
    #     }
    #     await websocket.send(json.dumps(ping_message))
    #     print(f"Sent PING: {ping_message}")
    
    async def handle_ping_pong_test(self):
        """Handles the ping-pong mechanism"""
        websocket = await self.connect()

        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                print(data)

                if data.get("event") == "ping":
                    await self.respond_pong(websocket)
                
                # # 定期送出 pong
                # await asyncio.sleep(self.keep_alive_interval)
                # print(f"Waiting {self.keep_alive_interval} seconds before sending next PING")
                # await self.send_ping(websocket)

            except websockets.ConnectionClosed as e:
                # 處理 websockets.ConnectionClosed 異常
                print(f"Connection closed: {e}")
                break
            except Exception as e:
                # 處理任何非 websockets.ConnectionClosed 的錯誤
                # e.g. 收到的 message 不是有效的 JSON 格式
                print(f"Error receiving data: {e}")
                break

    async def close_connection(self):
        """Gracefully closes the WebSocket connection"""
        if self.connection is not None:
            await self.connection.close()
            self.connection = None
            print("WebSocket connection closed")

    async def start_ping_pong_test(self):
        """Start the ping-pong test subscription"""
        await self.handle_ping_pong_test()

if __name__ == "__main__":
    app_id = ""
    woox_api = WooXStagingAPI(app_id)

    try:
        asyncio.run(woox_api.start_ping_pong_test())
    except KeyboardInterrupt:
        # 例外處理
        print("Shutting down gracefully...")
    finally:
        # 斷開連接
        asyncio.run(woox_api.close_connection())