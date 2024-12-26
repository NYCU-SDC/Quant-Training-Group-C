# utils.py
import socket
import asyncio


def log_event(message, level='INFO'):
    with open("lobby_server.log", 'a') as logfile:
        logfile.write(f"[{level}] {message}\n")

async def receive_message(client_socket):
    loop = asyncio.get_event_loop()
    try:
        data = await loop.sock_recv(client_socket, 4096)  # 非阻塞接收
        return data.decode('utf-8') if data else None
    except Exception as e:
        print(f"Error receiving message: {e}")
        return None

async def send_message(client_socket, message):
    loop = asyncio.get_event_loop()
    try:
        await loop.sock_sendall(client_socket, message.encode('utf-8'))  # 非阻塞發送
    except Exception as e:
        print(f"Error sending message: {e}")