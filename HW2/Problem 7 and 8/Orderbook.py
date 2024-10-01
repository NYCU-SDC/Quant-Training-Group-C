import numpy as np

class OrderBook:
    # 資產的代碼
    # 紀錄買方（bids）和賣方（asks）的訂單的訂單
    def __init__(self, symbol):
        self.symbol = symbol

        
        self.asks = []  # Stores the ask side (price, size)
        self.asks_weight = None
        self.asks_mean = None
        self.asks_Sn = None
        self.asks_population_variance = None
        self.asks_sample_variance = None

        self.bids = []  # Stores the bid side (price, size)
        self.bids_weight = None
        self.bids_mean = None
        self.bids_Sn = None
        self.bids_population_variance = None
        self.bids_sample_variance = None

    
    # 從外部接收新的訂單資料，並更新訂單簿的內容
    def update(self, data):
        """Updates the orderbook with new data."""
        # 避免錯誤更新
        if data["symbol"] != self.symbol:
            raise ValueError("Data symbol does not match orderbook symbol")

        self.asks = data["asks"]
        self.bids = data["bids"]

        if self.asks_weight is None:
            # update asks
            money = np.array([ask[0] for ask in self.asks])
            weight = np.array([ask[1] for ask in self.asks])
            self.asks_weight = np.sum(weight)
            self.asks_mean = np.sum(money * weight) / self.asks_weight
            self.asks_Sn = np.sum(weight * (money - self.asks_mean)**2)
            self.asks_population_variance = self.asks_Sn / self.asks_weight
            # refer to "weighted variance": weighted variance is different [Wikipedia]:
            self.asks_sample_variance = self.asks_population_variance * (
                self.asks_weight / (self.asks_weight - np.sum(weight**2) / self.asks_weight)
            )

            # update bids
            money = np.array([bid[0] for bid in self.bids])
            weight = np.array([bid[1] for bid in self.bids])
            self.bids_weight = np.sum(weight)
            self.bids_mean = np.sum(money * weight) / self.bids_weight
            self.bids_Sn = np.sum(weight * (money - self.bids_mean)**2)
            self.bids_population_variance = np.sum(weight * (money - self.bids_mean)**2) / self.bids_weight
            # refer to "weighted variance": weighted variance is different [Wikipedia]:
            self.bids_sample_variance = self.bids_Sn / (self.bids_weight - np.sum(weight**2) / self.bids_weight)
            self.bids_sample_variance = self.bids_population_variance * (
                self.bids_weight / (self.bids_weight - np.sum(weight**2) / self.bids_weight)
            )
        else:
            # https://fanf2.user.srcf.net/hermes/doc/antiforgery/stats.pdf
            for money, weight in self.asks:
                old_mean = self.asks_mean
                self.asks_weight = self.asks_weight + weight
                self.asks_mean = money - (self.asks_weight - weight) / self.asks_weight * (money - self.asks_mean)
                self.asks_Sn = self.asks_Sn + weight * (money - old_mean) * (money - self.asks_mean)
                self.asks_population_variance = self.asks_Sn / self.asks_weight
                self.asks_sample_variance = self.asks_population_variance * (self.asks_weight / (self.asks_weight - np.sum(weight**2) / self.asks_weight))
            for money, weight in self.bids:
                old_mean = self.bids_mean
                self.bids_weight = self.bids_weight + weight
                self.bids_mean = money - (self.bids_weight - weight) / self.bids_weight * (money - self.bids_mean)
                self.bids_Sn = self.bids_Sn + weight * (money - old_mean) * (money - self.bids_mean)
                self.bids_population_variance = self.bids_Sn / self.bids_weight
                self.bids_sample_variance = self.bids_population_variance * (self.bids_weight / (self.bids_weight - np.sum(weight**2) / self.bids_weight))

        

    def dump(self, max_level=10):
        """Prints the orderbook in a vertical format."""
        # 限制掛單深度，只顯示前幾筆掛單，聚焦於最相關的訂單
        max_ask_level = min(max_level, len(self.asks))  # Limit ask levels to max_level
        max_bid_level = min(max_level, len(self.bids))  # Limit bid levels to max_level

        print(f"Orderbook for {self.symbol} (Top {max_level} levels):")
        print(f"{'Ask Price':>15} | {'Ask Size':>15}")
        print("-" * 35)

        # 假設訂單已經排序，打印出價格
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