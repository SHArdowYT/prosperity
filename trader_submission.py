from typing import Any, List
import string
import numpy as np
import json
# import warnings


from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState

KELP_MOVING_AVERAGE = 5
SPACING_POSITION = 32
REGRESSION_DATA_LENGTH = 100
LINEAR_DATA_LENGTH = 100    
WEIGHT_MULTIPLIER = 5
POP_AVE_LENGTH = 100
MM_MULTIPLIER = 1
LIQUIDATION_THRESHOLD = 40
LQ_MULTIPLER = 0.1
REG_M_EPSILON = 0.05
REG_P_EPSILON = 100
REG_OFFSET = 0

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
    def product_header(self, state: TradingState) -> tuple[dict, OrderDepth]:
        # current orders in market
        order_depth = state.order_depths[self.name]

        # add to historical data
        self.past_ave.append(self.find_popular_average(order_depth))

        # sorting items
        # low to high
        sorted_sell_orders = dict(sorted(order_depth.sell_orders.items()))
        # high to low
        sorted_buy_orders = dict(reversed(sorted(order_depth.buy_orders.items())))

        if self.name in state.position:
            position = state.position[self.name]
        else:
            position = 0

        return (sorted_sell_orders, sorted_buy_orders, order_depth, position)

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
        self.products = [Product("RAINFOREST_RESIN"), Product("KELP"), Product("SQUID_INK")]
        # indicators
        self.acceptable_prices_dict = {"RAINFOREST_RESIN": 10000, "KELP": 2018, "SQUID_INK": 2005}

    # handle ask tradings, we buy, looking for sell orders, bid_volume is negative
    def buy_mm(self, product: string, long_position: int, return_orders: List, sorted_sell_orders: dict, price: int) -> List[Order]:
        for bid_price, bid_volume in sorted_sell_orders.items():
            if bid_price < price:
                return_orders.append(Order(product, bid_price, -bid_volume * MM_MULTIPLIER))
                long_position += -bid_volume


    # handle bid tradings, we sell, ask_volume is positive
    def sell_mm(self, product: string, short_position: int, return_orders: List, sorted_buy_orders: dict, price: int) -> List[Order]:
        for ask_price, ask_volume in sorted_buy_orders.items():
            if ask_price > price:
                return_orders.append(Order(product, ask_price, -ask_volume * MM_MULTIPLIER))
                short_position += -ask_volume


    # reliquidates us to be happy and to make more profit YAY
    def handle_liquidation(self, product: string, positions: list, return_orders: List[Order], fair_price: int) -> List[Order]:
        position, long_position, short_position = positions
        if position > LIQUIDATION_THRESHOLD:
            # selling
            return_orders.append(Order(product, int(fair_price), int((-position + LIQUIDATION_THRESHOLD) * LQ_MULTIPLER)))
        elif position < -LIQUIDATION_THRESHOLD:
            # buying
            return_orders.append(Order(product, int(fair_price), int((-position - LIQUIDATION_THRESHOLD) * LQ_MULTIPLER)))

    
    def trade_regression(self, product: str, position: int, return_orders: List, sorted_buy_orders: dict, sorted_sell_orders: dict, price: int) -> List[Order]:
        # buy
        for best_ask, best_ask_amount in sorted_sell_orders.items():
            if best_ask <= price: 
                return_orders.append(Order(product, best_ask, -best_ask_amount))
        # sell
        for best_bid, best_bid_amount in sorted_buy_orders.items():
            if best_bid >= price: 
                return_orders.append(Order(product, best_bid, -best_bid_amount))

    
    def g_trade_regression(self, product: str, position: int, return_orders: List, sorted_buy_orders: dict, sorted_sell_orders: dict, price: int, m: float) -> List[Order]:
        if m > 0 + REG_M_EPSILON:
            # buy
            for best_ask, best_ask_amount in sorted_sell_orders.items():
                if best_ask <= price + REG_P_EPSILON: 
                    return_orders.append(Order(product, best_ask, int(-best_ask_amount/10)))
        elif m < 0 - REG_M_EPSILON:
            # sell
            for best_bid, best_bid_amount in sorted_buy_orders.items():
                if best_bid >= price - REG_P_EPSILON: 
                    return_orders.append(Order(product, best_bid, int(-best_bid_amount/10)))
        # else:
        #     if product in state.position.keys():
        #         lq_thres = 0
        #         lq_multi = 1
        #         if state.position[product] > lq_thres:
        #             orders.append(Order(product, int(price), int((-state.position[product] + lq_thres) * lq_multi)))
        #         elif state.position[product] < -lq_thres:
        #             orders.append(Order(product, int(price), int((-state.position[product] - lq_thres) * lq_multi)))

    def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:

        result: dict[str, list[Order]] = {}
        conversions = 0
        trader_data = ""

        for product in self.products:

            # update data, give sell and buy orders
            sell_orders, buy_orders, order_depth, position = product.product_header(state)
            popular_price = product.past_ave[-1]
            orders: List[Order] = []
            long_position, short_position = 0, 0
            positions = [position, long_position, short_position]

            # ========================================================================
            # UNIVERSAL
            # ========================================================================
            # Order resetting
            # if product.name in state.own_trades.keys():
            #     for trade in state.own_trades[product.name]:
            #         if trade.buyer == "SUBMISSION":
            #             logger.print(f"buying quantity: {trade.quantity}")
            #             orders.append(Order(product.name, trade.price, -trade.quantity))
            #         elif trade.seller == "SUBMISSION":
            #             logger.print(f"selling quantity: {trade.quantity}")
            #             orders.append(Order(product.name, trade.price, trade.quantity))

            # self.handle_liquidation(state, orders, str(product), popular_price)

            mm_price = int(popular_price)
            lq_price = int(popular_price)
            multipler = 1

            # ========================================================================
            # HELP
            # ========================================================================
            if product.name == "KELP":
                mm_epsilon = 1

                # extra product specific
                # choose acceptable price
                # m, c = product.regression(self.historical_data[product.name][-100:])
                # regression_price = m * (state.timestamp/100 + 1) + c
                # self.trade_regression(orders, buy_orders, sell_orders, product.name, regression_price)

                # self.handle_liquidation(state, orders, str(product), popular_price)

                # mm_price = 2018

                # temp
                self.handle_liquidation(product.name, positions, orders, lq_price)
                # make these position dynamic
                if position <= 40:
                    orders.append(Order(product.name, lq_price - mm_epsilon, 10))
                if position >= -40:
                    orders.append(Order(product.name, lq_price + mm_epsilon, -10))

            # ========================================================================
            # IN REFOREST RAINS
            # ========================================================================
            elif product.name == "RAINFOREST_RESIN":
                # choose acceptable price
                # acceptable_price = popular_price
                self.handle_liquidation(product.name, positions, orders, lq_price)

                mm_epsilon = 2
                
                multipler = MM_MULTIPLIER

                # make these position dynamic
                if position <= 40:
                    orders.append(Order(product.name, lq_price - mm_epsilon, 10))
                if position >= -40:
                    orders.append(Order(product.name, lq_price + mm_epsilon, -10))
    

            # ========================================================================
            # SQUID INK
            # ========================================================================
            elif product.name == "SQUID_INK":
                # choose acceptable price
                # acceptable_price = popular_price
                # self.handle_liquidation(state, orders, str(product), lq_price)

                lm, lc = product.linear_regression(product.past_ave)
                
                m, c = product.regression(product.past_ave)
                reg_price = m * (state.timestamp/100 + 1) + c

                # self.handle_liquidation(state, orders, str(product), lq_price)
                self.g_trade_regression(product.name, position, orders, buy_orders, sell_orders, reg_price, lm)

                mm_price = reg_price
                lq_price = reg_price
                

            # ========================================================================
            # UNIVERSAL
            # ========================================================================
            
            # safe market making
            if product.name != "SQUID_INK":
                self.buy_mm(product.name, position, orders, sell_orders, mm_price)
                self.sell_mm(product.name, position, orders, buy_orders, mm_price)

            # simplify and update our orders
            return_orders = {}
            for order in orders:
                return_orders[order.price] = 0
            for order in orders:
                return_orders[order.price] += order.quantity
            orders = []
            for price, amount in return_orders.items():
                orders.append(Order(product.name, price, amount))
            result[product.name] = orders

        # ========================================================================
        # ENDING
        # ========================================================================

        return result, conversions, trader_data


