# server.py
import socket
import threading
import sys
from config import load_config
from bbo_management import BBOManager
from connection_handler import ConnectionHandler

def main():
    try:
        # Load server configuration
        config = load_config("config.json")
        bbo_manager = BBOManager(config['database']['file'])
        connection_handler = ConnectionHandler(bbo_manager)

        # Set up the server socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow reuse of the port
        server_socket.bind((config['server']['ip'], config['server']['port']))
        server_socket.listen(config['server']['max_connections'])
        
        # Display server start status
        print(f"Lobby server started on {config['server']['ip']}:{config['server']['port']}")
        print("The server is ready to receive connection requests.")

        # Accept connections from players
        while True:
            client_socket, client_address = server_socket.accept()
            print(f"Accepted connection from {client_address}")
            threading.Thread(target=connection_handler.handle_client_connection, args=(client_socket,)).start()

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
    main()