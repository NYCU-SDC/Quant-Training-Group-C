class OrderBook:
    def __init__(self, symbol):
        self.symbol = symbol
        self.asks = []  # Stores the ask side (price, size)
        self.bids = []  # Stores the bid side (price, size)

    def update(self, data):
        """Updates the orderbook with new data."""
        if data["symbol"] != self.symbol:
            raise ValueError("Data symbol does not match orderbook symbol")

        self.asks = data["asks"]
        self.bids = data["bids"]

    def dump(self, max_level=10):
        """Prints the orderbook in a vertical format."""
        max_ask_level = min(max_level, len(self.asks))  # Limit ask levels to max_level
        max_bid_level = min(max_level, len(self.bids))  # Limit bid levels to max_level

        print(f"Orderbook for {self.symbol} (Top {max_level} levels):")
        print(f"{'Ask Price':>15} | {'Ask Size':>15}")
        print("-" * 35)

        # Print Ask orders (sorted from highest to lowest)
        for i in range(max_ask_level):
            ask_price, ask_size = self.asks[i]
            print(f"{ask_price:>15.2f} | {ask_size:>15.6f}")

        print("-" * 35)
        print(f"{'Bid Price':>15} | {'Bid Size':>15}")
        print("-" * 35)

        # Print Bid orders (sorted from highest to lowest)
        for i in range(max_bid_level):
            bid_price, bid_size = self.bids[i]
            print(f"{bid_price:>15.2f} | {bid_size:>15.6f}")

        print("-" * 35)
