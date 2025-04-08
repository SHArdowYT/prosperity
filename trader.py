from typing import Any, List
import string
import numpy as np
from logger import Logger
import json
# import warnings


from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState

KELP_MOVING_AVERAGE = 5
SPACING_POSITION = 32
MM_EPSILON = 1
REGRESSION_DATA_LENGTH = 100
LINEAR_DATA_LENGTH = 1000
WEIGHT_MULTIPLIER = 5
POP_AVE_LENGTH = 100
MM_MULTIPLIER = 3
LIQUIDATION_THRESHOLD = 10
LQ_MULTIPLER = 0.1
REG_EPSILON = 4e-13
REG_OFFSET = 0

logger = Logger()
# warnings.simplefilter('ignore', np.RankWarning)

class Product:

    def __init__(self, name: str):
        self.name = name
        self.past_ave = []

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name


    # update historical data, sort and return sell/buy orders, print info
    def product_header(self, state: TradingState, historical_data: dict[str: list]) -> tuple[dict, OrderDepth]:
        # current orders in market
        order_depth = state.order_depths[self.name]

        # add to historical data
        historical_data[self.name].append(self.find_popular_average(order_depth))

        # sorting items
        # low to high
        sorted_sell_orders = dict(sorted(order_depth.sell_orders.items()))
        # high to low
        sorted_buy_orders = dict(reversed(sorted(order_depth.buy_orders.items())))

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

    # find averages based from volume for one instance
    def find_popular_average(self, order_depth: OrderDepth) -> float:
        ask_price_sum, ask_prices_length = self.process_popular_average(order_depth.sell_orders.items(), ask_mode=True)
        bid_sum, bid_prices_length = self.process_popular_average(order_depth.buy_orders.items(), ask_mode=False)

        if (bid_prices_length != 0 and ask_prices_length != 0):
            ask_average = ask_price_sum / ask_prices_length
            bid_average = bid_sum / bid_prices_length
            pop_ave = (ask_average + bid_average) / 2
        else:
            pop_ave = self.past_ave[-1]
        
        self.past_ave.append(pop_ave)

        return pop_ave

    # moving averages with given length
    def find_moving_average(self, averages: List, length: int):
        return sum(averages[-length:]) / len(averages[-length:]) # if (len(averages) != 0) else -1

    # calculate regression line
    def regression(self, somedata: list[int]) -> tuple[list]:
        somedata = somedata[-REGRESSION_DATA_LENGTH:]
        if len(somedata) == 0:
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
    
    def linear_regression(self, somedata: list[int]) -> tuple[list]:
        somedata = somedata[-LINEAR_DATA_LENGTH:]
        if len(somedata) == 0:
            logger.print("sobbbbb where did my data go")
            logger.print("tinpat" + ("t" * 10))
            return (0, 0)
        elif len(somedata) <= 1:
            return (0, somedata[0])

        m, c = np.polyfit(np.array([i for i in range(len(somedata))]), np.array([data for data in somedata]), deg=1)

        return tuple(float(i) for i in (m, c))

    # TODO for linear regres. not in progress rn
    def find_derivative(self, averages: List):
        pass



class Trader:

    def __init__(self):
        # past data
        self.historical_data = {"RAINFOREST_RESIN": [], "KELP": [], "SQUID_INK": []}
        self.past_ave = {"RAINFOREST_RESIN": -1, "KELP": -1, "SQUID_INK": -1}
        # indicators
        self.acceptable_prices_dict = {"RAINFOREST_RESIN": 10000, "KELP": 2018, "SQUID_INK": 2005}

    # handle ask tradings, we buy, looking for sell orders
    def buy_mm(self, orders: List, sorted_sell_orders: dict, product: string, acceptable_price: int, state: TradingState, multipler: float) -> List[Order]:
        for best_ask, best_ask_amount in sorted_sell_orders.items():
            logger.print(best_ask, best_ask_amount)
            if best_ask <= acceptable_price - MM_EPSILON: 
                orders.append(Order(product, best_ask, int(-best_ask_amount * multipler)))
                # if product in state.position.keys():
                #     if -best_ask_amount * MM_MULTIPLIER > -state.position[product]:
                #         orders.append(Order(product, best_ask, -best_ask_amount * MM_MULTIPLIER))
                #     else:
                #         # orders.append(Order(product, best_ask, -state.position[product] + 50))
                #         pass
                # else:
                #     if -best_ask_amount * MM_MULTIPLIER > 0:
                #         orders.append(Order(product, best_ask, -best_ask_amount * MM_MULTIPLIER))
                #     else:
                #         # orders.append(Order(product, best_ask, 50))
                #         pass
            # break

    # handle bid tradings, we sell
    def sell_mm(self, orders: List, sorted_buy_orders: dict, product: string, acceptable_price: int, state: TradingState, multipler: float) -> List[Order]:
        for best_bid, best_bid_amount in sorted_buy_orders.items():
            if best_bid >= acceptable_price + MM_EPSILON: 
                orders.append(Order(product, best_bid, int(-best_bid_amount * multipler)))
                # if product in state.position.keys():
                #     if best_bid_amount * MM_MULTIPLIER > -state.position[product]:
                #         orders.append(Order(product, best_bid, -best_bid_amount * MM_MULTIPLIER))
                #     else:
                #         # orders.append(Order(product, best_bid, -state.position[product] - 50))
                #         pass
                # else:
                #     if best_bid_amount * MM_MULTIPLIER > 0:
                #         orders.append(Order(product, best_bid, -best_bid_amount * MM_MULTIPLIER))
                #     else:
                #         # orders.append(Order(product, best_bid, -50))
                #         pass
            # break

    # reliquidates us to be happy and to make more profit YAY
    def handle_liquidation(self, state: TradingState, orders: List, product: string, fair_price: int) -> List[Order]:
        if product in state.position.keys():
            if state.position[product] > LIQUIDATION_THRESHOLD:
                orders.append(Order(product, fair_price, int((-state.position[product] + LIQUIDATION_THRESHOLD) * LQ_MULTIPLER)))
            elif state.position[product] < -LIQUIDATION_THRESHOLD:
                orders.append(Order(product, fair_price, int((-state.position[product] - LIQUIDATION_THRESHOLD) * LQ_MULTIPLER)))

    
    def trade_regression(self, orders: List, sorted_buy_orders: dict, sorted_sell_orders: dict, product: string, price: int) -> List[Order]:
        # buy
        for best_ask, best_ask_amount in sorted_sell_orders.items():
            if best_ask <= price: 
                orders.append(Order(product, best_ask, -best_ask_amount))
        # sell
        for best_bid, best_bid_amount in sorted_buy_orders.items():
            if best_bid >= price: 
                orders.append(Order(product, best_bid, -best_bid_amount))

    
    def g_trade_regression(self, orders: List, sorted_buy_orders: dict, sorted_sell_orders: dict, product: string, price: int, m: float) -> List[Order]:
        if m > 0 + REG_EPSILON:
            # buy
            for best_ask, best_ask_amount in sorted_sell_orders.items():
                # if best_ask <= price: 
                orders.append(Order(product, best_ask, -best_ask_amount))
                logger.print("i am buying!")
        elif m < 0 - REG_EPSILON:
            # sell
            for best_bid, best_bid_amount in sorted_buy_orders.items():
                # if best_bid >= price: 
                orders.append(Order(product, best_bid, -best_bid_amount))
                logger.print("i am selling!")

    
    def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:

        result = {}
        conversions = 0
        trader_data = ""

        availible_products = ["KELP", "RAINFOREST_RESIN", "SQUID_INK"]


        for availible_product in availible_products:
            product = Product(availible_product)

            # update data, give sell and buy orders
            sell_orders, buy_orders, order_depth = product.product_header(state, self.historical_data)
            popular_price = product.find_popular_average(order_depth)
            orders: List[Order] = []

            # ========================================================================
            # UNIVERSAL
            # ========================================================================
            # self.handle_liquidation(state, orders, str(product), popular_price)

            mm_price = int(popular_price)
            lq_price = int(popular_price)
            multipler = 1

            # ========================================================================
            # HELP
            # ========================================================================
            if product.name == "KELP":

                # extra product specific
                # choose acceptable price
                # m, c = product.regression(self.historical_data[product.name][-100:])
                # regression_price = m * (state.timestamp/100 + 1) + c
                # self.trade_regression(orders, buy_orders, sell_orders, product.name, regression_price)

                # self.handle_liquidation(state, orders, str(product), popular_price)

                # mm_price = 2018

                # temp
                # self.handle_liquidation(state, orders, str(product), lq_price)
                pass

            # ========================================================================
            # IN REFOREST RAINS
            # ========================================================================
            elif product.name == "RAINFOREST_RESIN":
                # choose acceptable price
                # acceptable_price = popular_price
                self.handle_liquidation(state, orders, str(product), lq_price)
                
                multipler = MM_MULTIPLIER
    

            # ========================================================================
            # SQUID INK
            # ========================================================================
            elif product.name == "SQUID_INK":
                # choose acceptable price
                # acceptable_price = popular_price
                # self.handle_liquidation(state, orders, str(product), lq_price)

                lm, lc = product.linear_regression(product.past_ave)
                logger.print(f"gradient is {lm}")
                
                m, c = product.regression(product.past_ave)
                reg_price = m * (state.timestamp/100 + 1) + c
                self.g_trade_regression(orders, buy_orders, sell_orders, product.name, reg_price, lm)

                mm_price = reg_price
                

            # ========================================================================
            # UNIVERSAL
            # ========================================================================
            
            # safe market making
            if product.name != "SQUID_INK":
                self.buy_mm(orders, sell_orders, str(product), mm_price, state, multipler)
                self.sell_mm(orders, buy_orders, str(product), mm_price, state, multipler)

            # update our orders
            result[str(product)] = orders



        # ========================================================================
        # ENDING
        # ========================================================================

        logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data


