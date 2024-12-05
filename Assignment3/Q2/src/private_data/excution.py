import numpy as np

class ExecutionReport:
    def __init__(self, data):
        self.msg_type = data['msgType']
        self.symbol = data['symbol']
        self.client_order_id = data['clientOrderId']
        self.order_id = data['orderId']
        self.order_type = data['type']
        self.side = data['side']
        self.quantity = data['quantity']
        self.price = data['price']
        self.trade_id = data['tradeId']
        self.executed_price = data['executedPrice']
        self.executed_quantity = data['executedQuantity']
        self.fee = data['fee']
        self.fee_asset = data['feeAsset']
        self.total_executed_quantity = data['totalExecutedQuantity']
        self.avg_price = data['avgPrice']
        self.status = data['status']
        self.reason = data['reason']
        self.order_tag = data['orderTag']
        self.total_fee = data['totalFee']
        self.fee_currency = data['feeCurrency']
        self.total_rebate = data['totalRebate']
        self.rebate_currency = data['rebateCurrency']
        self.visible = data['visible']
        self.timestamp = data['timestamp']
        self.reduce_only = data['reduceOnly']
        self.maker = data['maker']
        self.leverage = data['leverage']
        self.margin_mode = data['marginMode']

        self.returns = []

    def update(self, data):
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)

        if self.status == 'FILLED':
            self.calculate_return()

    def calculate_return(self):
        if self.side == 'BUY':
            self.returns.append(self.executed_price / self.avg_price - 1)
        elif self.side == 'SELL':
            self.returns.append(1 - self.executed_price / self.avg_price)

    def calculate_sharpe_ratio(self, risk_free_rate=0.0):
        if len(self.returns) < 2:
            return None
        returns = np.array(self.returns)
        sharpe_ratio = (returns.mean() - risk_free_rate) / returns.std()
        return sharpe_ratio

    def calculate_total_return(self):
        if len(self.returns) == 0:
            return 0
        total_return = np.prod(1 + np.array(self.returns)) - 1
        return total_return