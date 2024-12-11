# connection_handler.py
import json
from utils import send_message, receive_message, log_event
from bbo_management import BBOManager
from datetime import datetime


class ConnectionHandler:
    def __init__(self, bbo_manager):
        self.bbo_manager = bbo_manager

    def handle_client_connection(self, client_socket):
        try:
            while True:
                message = receive_message(client_socket)
                if not message:
                    break

                request = json.loads(message)
                action = request.get("action")

                # Simulated_WooX_REST_API_Client
                if action == 'get_bbo':
                    self.handle_get_bbo(client_socket, request)
                elif action == 'get_kline':
                    self.handle_get_kline(client_socket, request)
                elif action == 'get_market_trades':
                    self.handle_get_market_trades(client_socket, request)
                elif action == 'get_orderbook':
                    self.handle_get_orderbook(client_socket, request)
                else:
                    send_message(client_socket, "invalid_action")

        except json.JSONDecodeError:
            send_message(client_socket, "invalid_message_format")


    def handle_get_bbo(self, client_socket, request):
        print(f"\nrequest: {request}\n")
        # handle request invalide
        bbo_response = self.bbo_manager.get_bbo(request)
        print(f"\nget_bbo: {bbo_response}\n")
        send_message(client_socket, json.dumps(bbo_response))


    def handle_get_kline(self, client_socket, request):
        print(f"\nrequest: {request}\n")
        # handle request invalide
        kline_response = self.bbo_manager.get_kline(request)
        print(f"\get_kline: {kline_response}\n")
        send_message(client_socket, json.dumps(kline_response))


    def handle_get_market_trades(self, client_socket, request):
        print(f"\nrequest: {request}\n")
        # handle request invalide
        market_trades_response = self.bbo_manager.get_market_trades(request)
        print(f"\get_market_trades: {market_trades_response}\n")
        send_message(client_socket, json.dumps(market_trades_response))

    def handle_get_orderbook(self, client_socket, request):
        print(f"\nrequest: {request}\n")
        # handle request invalide
        market_trades_response = self.bbo_manager.get_orderbook(request)
        print(f"\get_orderbook: {market_trades_response}\n")
        send_message(client_socket, json.dumps(market_trades_response))

    