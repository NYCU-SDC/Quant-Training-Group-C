import asyncio
import socket
import sys
from config import load_config
from management_data import DataManager
from management_subscribe import SubscribeManager
from management_matching import MatchingManager
from async_connection_handler import AsyncConnectionHandler

async def main():
    try:
        # Load server configuration
        config = load_config("config.json")
        simulate_speed = config['simulator']['simulate_speed']
        start_timestamp = config['simulator']['start_timestamp']
        base_timestamp = config['simulator']['base_timestamp']
        
        data_manager = DataManager(simulate_speed, start_timestamp, base_timestamp)
        subscribe_manager = SubscribeManager(simulate_speed, start_timestamp, base_timestamp)
        matching_manager = MatchingManager(simulate_speed, start_timestamp, base_timestamp)
        connection_handler = AsyncConnectionHandler(data_manager, subscribe_manager, matching_manager,
                                                    simulate_speed, start_timestamp, base_timestamp)

        # Set up the server socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow reuse of the port
        server_socket.bind((config['server']['ip'], config['server']['port']))
        server_socket.listen(config['server']['max_connections'])
        server_socket.setblocking(False)  # Set the socket to non-blocking mode

        # Display server start status
        print(f"Lobby server started on {config['server']['ip']}:{config['server']['port']}")
        print("The server is ready to receive connection requests.")

        loop = asyncio.get_event_loop()

        async def accept_connections():
            while True:
                client_socket, client_address = await loop.sock_accept(server_socket)
                print(f"Accepted connection from {client_address}")
                loop.create_task(connection_handler.handle_client_connection(client_socket))

        await accept_connections()

    except socket.error as e:
        # Handle port or configuration errors
        print(f"Failed to start the server: {e}")
        print("Please check if the port is already in use or if the configuration is correct.")
        sys.exit(1)  # Exit the program with an error status

    except Exception as e:
        # Catch any other unexpected errors
        print(f"Unexpected error occurred: {e}")
        sys.exit(1)  # Exit the program with an error status

if __name__ == "__main__":
    asyncio.run(main())
