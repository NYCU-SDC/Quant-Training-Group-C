# don't change
import socket

def log_event(message, level='INFO'):
    with open("lobby_server.log", 'a') as logfile:
        logfile.write(f"[{level}] {message}\n")

def send_message(client_socket, message):
    try:
        client_socket.sendall(message.encode('utf-8'))
    except socket.error as e:
        log_event(f"Failed to send message: {e}", "ERROR")

def receive_message(client_socket):
    try:
        return client_socket.recv(1024).decode('utf-8')
    except socket.error as e:
        log_event(f"Failed to receive message: {e}", "ERROR")
        return None
