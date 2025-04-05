from typing import Any, List
import string
import numpy as np
from logger import Logger
import json

from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState

KELP_MOVING_AVERAGE = 5
SPACING_POSITION = 32
MM_EPSILON = 1
REGRESSION_DATA_LENGTH = 20
WEIGHT_MULTIPLIER = 5

logger = Logger()

class Product:

    def __init__(self, name: str):
        self.name = name
        self.past_ave = {}

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name


    # update historical data, sort and return sell/buy orders, print info
    def product_header(self, state: TradingState, historical_data) -> tuple[dict, OrderDepth]:
        # current orders in market
        order_depth = state.order_depths[self.name]

        # add to historical data
        historical_data[self.name].append(self.find_popular_average(order_depth))

        # sorting items
        # low to high
        sorted_sell_orders = dict(sorted(order_depth.sell_orders.items()))
        # high to low
        sorted_buy_orders = dict(reversed(sorted(order_depth.buy_orders.items())))

        logger.print(f"{'sell orders: '.ljust(SPACING_POSITION)}{sorted_sell_orders}\n"
                     f"{'buy orders: '.ljust(SPACING_POSITION)}{sorted_buy_orders}")

        logger.print(#f"{self.name}'s average price is: {self.find_best_average(order_depth)}\n"
                     f"{self.name}{'\'s moving average price is:'.ljust(SPACING_POSITION - len(self.name))}{self.find_moving_average(historical_data[self.name], 20)}\n"
                     f"{self.name}{'\'s popular average price is:'.ljust(SPACING_POSITION - len(self.name))}{self.find_popular_average(order_depth)}\n")

        logger.print(f"{'the equ is: '.ljust(SPACING_POSITION)}{self.regression(historical_data[self.name][-REGRESSION_DATA_LENGTH:])}\n"
                     f"{'the derivative is: '.ljust(SPACING_POSITION)}{self.find_derivative(historical_data[self.name])}")

        # logger.print(f"{'the data are: '.ljust(SPACING_POSITION)}{(historical_data[self.name])}\n")


        return (sorted_sell_orders, sorted_buy_orders, order_depth)

    def process_popular_average(self, orders, ask_mode: bool):
        prices = []
        ask_volume = 0
        for price, volume in list(orders):
            if ((volume < ask_volume) and ask_mode) or ((volume > ask_volume) and not ask_mode):
                prices = [price]
            elif volume == ask_volume:
                prices.append(price)

        # prices_sum = sum(prices)
        # prices_length = len(prices)
        return sum(prices), len(prices)

    # find averages based from volume
    def find_popular_average(self, order_depth: OrderDepth) -> float:
        ask_price_sum, ask_prices_length = self.process_popular_average(order_depth.sell_orders.items(), ask_mode=True)
        bid_sum, bid_prices_length = self.process_popular_average(order_depth.buy_orders.items(), ask_mode=False)

        # logger.print(f"bidlen: {bid_prices_length} asklen: {ask_prices_length}")
        if (bid_prices_length != 0 and ask_prices_length != 0):
            ask_average = ask_price_sum / ask_prices_length
            bid_average = bid_sum / bid_prices_length
            self.past_ave = (ask_average + bid_average) / 2

        return self.past_ave

    # moving averages with given length
    def find_moving_average(self, averages: List, length: int):
        return sum(averages[-length:]) / len(averages[-length:]) # if (len(averages) != 0) else -1

    # calculate regression line
    def regression(self, somedata: list[int]) -> tuple[list]:
        if len(somedata) == 0:
            logger.print("sobbbbb where did my data go")
            logger.print("tinpat" + ("t" * 10))
            return (0, 0)
        elif len(somedata) <= 1:
            return (0, somedata[0])


        # somedata = somedata[-REGRESSION_DATA_LENGTH:]
        weight = lambda pos : pos * WEIGHT_MULTIPLIER
        # weight = lambda pos, length : round(pos / length * WEIGHT_MULTIPLIER)

        weighting_array = [weight(i) for i in range(len(somedata))]
        # weighting_array = [1 for i in range(len(somedata))]

        m, c = np.polyfit(np.array([i for i in range(len(somedata))]), np.array([data for data in somedata]), w=np.exp(weighting_array), deg=1)

        return tuple(float(i) for i in (m, c))

    # TODO for linear regres. not in progress rn
    def find_derivative(self, averages: List):
        pass



class Trader:

    def __init__(self):
        # past data
        self.historical_data = {"RAINFOREST_RESIN": [], "KELP": []}
        self.past_ave = {"RAINFOREST_RESIN": -1, "KELP": -2}
        # indicators
        self.acceptable_prices_dict = {"RAINFOREST_RESIN": 10000, "KELP": 2018}

    # handle ask tradings, we buy, looking for sell
    def buy_mm(self, orders: List, sorted_sell_orders: dict, product: string, acceptable_price: int) -> List[Order]:
        for best_ask, best_ask_amount in sorted_sell_orders.items():
            if best_ask <= acceptable_price - MM_EPSILON: 
                orders.append(Order(product, best_ask, -best_ask_amount))
            # break

    # handle sell tradings
    def sell_mm(self, orders: List, sorted_buy_orders: dict, product: string, acceptable_price: int) -> List[Order]:
        for best_bid, best_bid_amount in sorted_buy_orders.items():
            if best_bid >= acceptable_price + MM_EPSILON: 
                orders.append(Order(product, best_bid, -best_bid_amount))
            # break

    # reliquidates us to be happy and to make more profit YAY
    def handle_liquidation(self, state: TradingState, orders: List, product: string, fair_price: int) -> List[Order]:
        if product in state.position.keys():
            orders.append(Order(product, fair_price, -state.position[product]))

    # retire
    def trade_regression(self, orders: List, sorted_buy_orders: dict, sorted_sell_orders: dict, product: string, price: int) -> List[Order]:
        for best_bid, best_bid_amount in sorted_buy_orders.items():
            if best_bid >= price: 
                orders.append(Order(product, best_bid, -best_bid_amount))
            # break

        for best_ask, best_ask_amount in sorted_sell_orders.items():
            if best_ask <= price: 
                orders.append(Order(product, best_ask, -best_ask_amount))
            # break

    

    def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:
        logger.print(f"chat, the time is {state.timestamp}")

        result = {}
        conversions = 0
        trader_data = ""

        availible_products = ["KELP", "RAINFOREST_RESIN"]


        for availible_product in availible_products:
            product = Product(availible_product)

            # update data, give sell and buy orders
            sell_orders, buy_orders, order_depth = product.product_header(state, self.historical_data)
            popular_price = product.find_popular_average(order_depth)
            orders: List[Order] = []

            # ========================================================================
            # UNIVERSAL
            # ========================================================================
            self.handle_liquidation(state, orders, str(product), popular_price)

            # ========================================================================
            # HELP
            # ========================================================================
            if product.name == "KELP":

                # extra product specific
                # choose acceptable price
                m, c = product.regression(self.historical_data[product.name][-100:])
                regression_price = m * (state.timestamp/100 + 1) + c
                # self.trade_regression(orders, buy_orders, sell_orders, product.name, regression_price)

            # ========================================================================
            # IN REFOREST RAINS
            # ========================================================================
            elif str(product) == "RAINFOREST_RESIN":
                # choose acceptable price
                # acceptable_price = popular_price
                pass
    

            # ========================================================================
            # UNIVERSAL
            # ========================================================================
            
            # market making
            mm_price = popular_price
            self.buy_mm(orders, sell_orders, str(product), mm_price)
            self.sell_mm(orders, buy_orders, str(product), mm_price)

            # update our orders
            result[str(product)] = orders



        # ========================================================================
        # ENDING
        # ========================================================================

        logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data


