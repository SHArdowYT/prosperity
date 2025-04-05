import json
from typing import Any, List
import string
import logger
import numpy as np

# this is a change

from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState

class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(
            self.to_json(
                [
                    self.compress_state(state, ""),
                    self.compress_orders(orders),
                    conversions,
                    "",
                    "",
                ]
            )
        )

        # We truncate state.traderData, trader_data, and self.logs to the same max. length to fit the log limit
        max_item_length = (self.max_log_length - base_length) // 3

        print(
            self.to_json(
                [
                    self.compress_state(state, self.truncate(state.traderData, max_item_length)),
                    self.compress_orders(orders),
                    conversions,
                    self.truncate(trader_data, max_item_length),
                    self.truncate(self.logs, max_item_length),
                ]
            )
        )

        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp,
            trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        compressed = []
        for listing in listings.values():
            compressed.append([listing["symbol"], listing["product"], listing["denomination"]])

        return compressed

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        compressed = {}
        for symbol, order_depth in order_depths.items():
            compressed[symbol] = [order_depth.buy_orders, order_depth.sell_orders]

        return compressed

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        compressed = []
        for arr in trades.values():
            for trade in arr:
                compressed.append(
                    [
                        trade.symbol,
                        trade.price,
                        trade.quantity,
                        trade.buyer,
                        trade.seller,
                        trade.timestamp,
                    ]
                )

        return compressed

    def compress_observations(self, observations: Observation) -> list[Any]:
        conversion_observations = {}
        for product, observation in observations.conversionObservations.items():
            conversion_observations[product] = [
                observation.bidPrice,
                observation.askPrice,
                observation.transportFees,
                observation.exportTariff,
                observation.importTariff,
                observation.sugarPrice,
                observation.sunlightIndex,
            ]

        return [observations.plainValueObservations, conversion_observations]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        compressed = []
        for arr in orders.values():
            for order in arr:
                compressed.append([order.symbol, order.price, order.quantity])

        return compressed

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        if len(value) <= max_length:
            return value

        return value[: max_length - 3] + "..."

logger = Logger()

class Trader:

    def __init__(self):
        # past data
        self.historical_data = {"RAINFOREST_RESIN": [], "KELP": []}
        self.past_ave = {"RAINFOREST_RESIN": -1, "KELP": -2}
       
        # indicators
        self.acceptable_prices_dict = {"RAINFOREST_RESIN": 10000, "KELP": 2018}

    # find average from worst values
    def find_worst_average(self, order_depth: OrderDepth):
        worst_ask = list(order_depth.sell_orders.items())[-1][0]
        worst_bid = list(order_depth.buy_orders.items())[-1][0]
        average = np.mean([worst_ask, worst_bid])
        return average

    # find average from best values
    def find_best_average(self, order_depth: OrderDepth):
        best_ask = list(order_depth.sell_orders.items())[0][0]
        best_bid = list(order_depth.buy_orders.items())[0][0]
        average = np.mean([best_ask, best_bid])
        return average

    # find averages based from volume
    def find_popular_average(self, order_depth: OrderDepth, product: string):
        ask_items = []
        ask_volume = 0
        for ask_item in list(order_depth.sell_orders.items()):
            if ask_item[1] < ask_volume:
                ask_items = [ask_item]
            elif ask_item[1] == ask_volume:
                ask_items.append(ask_item)

        ask_sum = sum(item[0] for item in ask_items)
        ask_items_length = len(ask_items)

        bid_items = []
        bid_volume = 0
        for bid_item in list(order_depth.buy_orders.items()):
            if bid_item[1] > bid_volume:
                bid_items = [bid_item]
            elif bid_item[1] == bid_volume:
                bid_items.append(bid_item)

        bid_sum = sum(item[0] for item in bid_items)
        bid_items_length = len(bid_items)

        if (bid_items_length != 0 and ask_items_length != 0):
            ask_average = ask_sum / ask_items_length
            bid_average = bid_sum / bid_items_length
            self.past_ave[product] = (ask_average + bid_average) / 2

        return self.past_ave[product]

 
    # moving averages with given length
    def find_moving_average(self, averages: List, length: int):
        return sum(averages[-length:]) / len(averages[-length:]) # if (len(averages) != 0) else -1

    def regression(self, somedata: list[int]) -> tuple[list]:
        weight = lambda pos, length : round(pos / length * 5)
        datapoints = []
        counter = 0
        for i in somedata:
            for j in range(weight(i, len(somedata))):
                datapoints.append([counter, i])
            counter += 1

        m, c = np.polyfit(np.array([datapoint[0] for datapoint in datapoints]), np.array([datapoint[1] for datapoint in datapoints]), deg=1)
        return (m, c)

    # TODO for linear regres. not in progress rn
    def find_derivative(self, averages: List):
        pass

    def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:
        logger.print(f"chat, the time is {state.timestamp}")

        result = {}
        conversions = 0
        trader_data = ""

        # # order depth for each product. Contains sell orders and buy orders (dict of price:quantity)
        # for product, order_depth in (state.order_depths).items():
        #     # initalise
        #     # add to historical data
        #     self.historical_data[product].append(self.find_best_average(order_depth))
        #     # orders to push in this timeframe
        #     orders: List[Order] = []

        #     # low to high
        #     sorted_sell_orders = dict(sorted(order_depth.sell_orders.items()))
        #     # high to low
        #     sorted_buy_orders = dict(reversed(sorted(order_depth.buy_orders.items())))
        #     logger.print(f"sell orders: {sorted_sell_orders}\n"
        #                  f"buy orders: {sorted_buy_orders}")
        #     # if state.timestamp >= 34000:
        #     #     self.acceptable_prices_dict = {"RAINFOREST_RESIN": 10000, "KELP": 2018}

        #     acceptable_price = self.acceptable_prices_dict[product]
        #     acceptable_price = self.find_moving_average(self.historical_data[product], 1000)

        #     if True:
        #         # we buying, looking for sell orders
        #         for best_ask, best_ask_amount in sorted_sell_orders.items():
        #             if best_ask < acceptable_price - 1: 
        #                 orders.append(Order(product, best_ask, -best_ask_amount))
        #             break

        #         # we selling
        #         for best_bid, best_bid_amount in sorted_buy_orders.items():
        #             if best_bid > acceptable_price + 1: 
        #                 orders.append(Order(product, best_bid, -best_bid_amount))
        #             break
            
        #     # ending
        #     logger.print(f"{product}'s average price is: {self.find_best_average(order_depth)}\n"
        #                  f"{product}'s moving average price is : {self.find_moving_average(self.historical_data[product], 20)}")
        #     result[product] = orders

        # ========================================================================
        # KELP
        # ========================================================================
        product = "KELP"
        order_depth = state.order_depths[product]
        # initalise
        # add to historical data
        self.historical_data[product].append(self.find_popular_average(order_depth, product))
        # orders to push in this timeframe
        orders: List[Order] = []

        # sorting items
        # low to high
        sorted_sell_orders = dict(sorted(order_depth.sell_orders.items()))
        # high to low
        sorted_buy_orders = dict(reversed(sorted(order_depth.buy_orders.items())))


        logger.print(f"sell orders: {sorted_sell_orders}\n"
                     f"buy orders: {sorted_buy_orders}")
        # if state.timestamp >= 34000:
        #     self.acceptable_prices_dict = {"RAINFOREST_RESIN": 10000, "KELP": 2018}

        # acceptable_price = self.acceptable_prices_dict[product]
        acceptable_price = self.find_moving_average(self.historical_data[product], 20)

        if True:
            # we buying, looking for sell orders
            for best_ask, best_ask_amount in sorted_sell_orders.items():
                if best_ask < acceptable_price - 1: 
                    orders.append(Order(product, best_ask, -best_ask_amount))
                break

            # we selling
            for best_bid, best_bid_amount in sorted_buy_orders.items():
                if best_bid > acceptable_price + 1: 
                    orders.append(Order(product, best_bid, -best_bid_amount))
                break
        
        # ending
        # logger.print(f"{product}'s average price is: {self.find_best_average(order_depth)}\n"
        logger.print(f"{product}'s moving average price is : {self.find_moving_average(self.historical_data[product], 20)}\n"
                     f"{product}'s popular average price is : {self.find_popular_average(order_depth, product)}\n")
        result[product] = orders

        # ========================================================================
        # RAINFOREST RESIN
        # ========================================================================
        product = "RAINFOREST_RESIN"
        order_depth = state.order_depths[product]
        # initalise
        # add to historical data
        self.historical_data[product].append(self.find_popular_average(order_depth, product))
        # orders to push in this timeframe
        orders: List[Order] = []

        # low to high
        sorted_sell_orders = dict(sorted(order_depth.sell_orders.items()))
        # high to low
        sorted_buy_orders = dict(reversed(sorted(order_depth.buy_orders.items())))
        logger.print(f"sell orders: {sorted_sell_orders}\n"
                        f"buy orders: {sorted_buy_orders}")
        # if state.timestamp >= 34000:
        #     self.acceptable_prices_dict = {"RAINFOREST_RESIN": 10000, "KELP": 2018}

        acceptable_price = self.acceptable_prices_dict[product]
        acceptable_price = self.find_moving_average(self.historical_data[product], 100)

        if True:
            # we buying, looking for sell orders
            for best_ask, best_ask_amount in sorted_sell_orders.items():
                if best_ask < acceptable_price - 1: 
                    orders.append(Order(product, best_ask, -best_ask_amount))
                break

            # we selling
            for best_bid, best_bid_amount in sorted_buy_orders.items():
                if best_bid > acceptable_price + 1: 
                    orders.append(Order(product, best_bid, -best_bid_amount))
                break
        
        # ending
        # logger.print(f"{product}'s average price is: {self.find_best_average(order_depth)}\n"
        logger.print(f"{product}'s moving average price is : {self.find_moving_average(self.historical_data[product], 20)}\n"
                     f"{product}'s popular average price is : {self.find_popular_average(order_depth, product)}\n")
        result[product] = orders

        logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data
