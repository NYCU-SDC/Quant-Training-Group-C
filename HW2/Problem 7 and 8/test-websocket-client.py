import asyncio
import websockets
import json

async def client():
    uri = "ws://localhost:8765"
    # 實現一個持續運行的連線，WebSocket 可以保持長時間的連接，與 HTTP 不同
    async with websockets.connect(uri) as websocket:
        while True:
            # 當伺服器有數據變更時，立即將這些更新推送給客戶端
            message = await websocket.recv()
            data = json.loads(message)
            print(f"Received orderbook update: {data}")
            # Process the orderbook update data as needed

asyncio.get_event_loop().run_until_complete(client())