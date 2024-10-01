import json
import asyncio
import websockets

async def test_server(websocket, path):
    # 建立一個 WebSocket 伺服器，定期向連接的客戶端發送模擬的訂單簿更新消息
    while True:
        # Simulate orderbook update messages (replace with your actual message format)
        message = {
            "type": "orderbook_update",
            "symbol": "BTC-USDT",
            "bids": [[10000, 5], [9950, 2]],
            "asks": [[10050, 3], [10100, 8]]
        }
        await websocket.send(json.dumps(message))
        await asyncio.sleep(2)  # Send updates every 2 seconds

start_server = websockets.serve(test_server, 'localhost', 8765)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()