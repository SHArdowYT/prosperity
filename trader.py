from typing import Any, List
import string
import numpy as np
import json
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
            compressed.append([listing.symbol, listing.product, listing.denomination])

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

DEFAULT_LIQUIDATION_THRESHOLD = 0
DEFAULT_LQ_PRICE_EPSILON = 0
DEFAULT_EXPONENT_PARAM = 1
DEFAULT_MM_EPSILON = 1
DEFAULT_MR_EPSILON = 3.5

logger = Logger()

PRODUCT_PARAMS = {
    "RAINFOREST_RESIN": {
        "position_limit": 50,
        "exponential_param": DEFAULT_EXPONENT_PARAM,
        "liquidation_threshold": 50,
        "lq_price_epsilon": DEFAULT_LQ_PRICE_EPSILON,
        "mm_epsilon": 0,
        "makemm_epsilon": 2
    },

    "KELP": {
        "position_limit": 50,
        "exponential_param": 1,
        "liquidation_threshold": 50,
        "lq_price_epsilon": DEFAULT_LQ_PRICE_EPSILON,
        "mm_epsilon": 0,
        "makemm_epsilon": 1
    },

    "SQUID_INK": {
        "position_limit": 50,
        "exponential_param": 0.01,
        "liquidation_threshold": DEFAULT_LIQUIDATION_THRESHOLD,
        "lq_price_epsilon": 3,
        "mm_epsilon": 3,
        "mr_epsilon": DEFAULT_MR_EPSILON,
    },
    
    "CROISSANTS": {
        "position_limit": 250,
        "exponential_param": DEFAULT_EXPONENT_PARAM,
        "liquidation_threshold": DEFAULT_LIQUIDATION_THRESHOLD,
        "mm_epsilon": 1,
        "mr_epsilon": DEFAULT_MR_EPSILON,
    },
    
    "JAMS": {
        "position_limit": 350,
        "exponential_param": DEFAULT_EXPONENT_PARAM,
        "liquidation_threshold": DEFAULT_LIQUIDATION_THRESHOLD,
        "mm_epsilon": 1,
        "mr_epsilon": DEFAULT_MR_EPSILON,
    },
    
    "DJEMBES": {
        "position_limit": 60,
        "exponential_param": DEFAULT_EXPONENT_PARAM,
        "liquidation_threshold": DEFAULT_LIQUIDATION_THRESHOLD,
        "mm_epsilon": 1,
        "mr_epsilon": DEFAULT_MR_EPSILON,
    },
    
    "PICNIC_BASKET1": {
        "position_limit": 60,
        "exponential_param": DEFAULT_EXPONENT_PARAM,
        "liquidation_threshold": DEFAULT_LIQUIDATION_THRESHOLD,
        "mm_epsilon": DEFAULT_MM_EPSILON,
        "mr_epsilon": DEFAULT_MR_EPSILON,
    },
        
    "PICNIC_BASKET2": {
        "position_limit": 60,
        "exponential_param": DEFAULT_EXPONENT_PARAM,
        "liquidation_threshold": DEFAULT_LIQUIDATION_THRESHOLD,
        "mm_epsilon": DEFAULT_MM_EPSILON,
        "mr_epsilon": DEFAULT_MR_EPSILON,
    },
}

class Product:

    def __init__(self, name: str):
        self.name = name
        self.params = PRODUCT_PARAMS[self.name]

        self.popular_average: float
        self.exponential_moving_average: float

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name


    # update historical data, sort and return sell/buy orders, print info
    def product_header(self, state: TradingState) -> tuple[dict, OrderDepth]:
        # current orders in market
        order_depth = state.order_depths[self.name]

        # add to historical data
        self.calculate_average(order_depth)
        self.calculate_exp_moving_average()

        # sorting items
        # low to high
        sorted_sell_orders = dict(sorted(order_depth.sell_orders.items()))
        # high to low
        sorted_buy_orders = dict(reversed(sorted(order_depth.buy_orders.items())))

        if self.name in state.position:
            position = state.position[self.name]
        else:
            position = 0

        return (sorted_sell_orders, sorted_buy_orders, position)

    # helper func
    def find_popular_sum_length(self, orders, ask_mode: bool):
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
    def calculate_average(self, order_depth: OrderDepth) -> float:
        ask_price_sum, ask_prices_length = self.find_popular_sum_length(order_depth.sell_orders.items(), ask_mode=True)
        bid_sum, bid_prices_length = self.find_popular_sum_length(order_depth.buy_orders.items(), ask_mode=False)

        if (bid_prices_length != 0 and ask_prices_length != 0):
            ask_average = ask_price_sum / ask_prices_length
            bid_average = bid_sum / bid_prices_length
            self.popular_average = (ask_average + bid_average) / 2
        
        return self.popular_average

    # calculate exp regression line
    def calculate_exp_moving_average(self):
        if hasattr(self, 'exponential_moving_average'):
            self.exponential_moving_average = self.params["exponential_param"] * self.popular_average + (1 - self.params["exponential_param"]) * self.exponential_moving_average
        else:
            self.exponential_moving_average = self.popular_average
        return self.exponential_moving_average


class Trader:

    def __init__(self):
        self.products = [Product(product_name) for product_name in PRODUCT_PARAMS.keys()]

    # handle ask tradings, we buy, looking for sell orders, ask
    def buy_mm(self, product: Product, positions: list, return_orders: List, sorted_sell_orders: dict, price: int) -> List[Order]:
        worst_price = round(price)
        # absolute value volume
        volume = 0
        for ask_price, ask_volume in sorted_sell_orders.items():
            if ask_price < price:
                positions[1] -= abs(ask_volume)
                if positions[1] <= 0:
                    positions[1] += abs(ask_volume)
                    return_orders.append(Order(product.name, worst_price, volume))
                    return
                volume += abs(ask_volume)
                worst_price = ask_price
        return_orders.append(Order(product.name, worst_price, volume))
        positions[1] -= volume

    # handle bid tradings, we sell, ask_volume is positive
    def sell_mm(self, product: Product, positions: list, return_orders: List, sorted_buy_orders: dict, price: int) -> List[Order]:
        worst_price = round(price)
        volume = 0
        for bid_price, bid_volume in sorted_buy_orders.items():
            if bid_price > price:
                positions[2] -= abs(bid_volume)
                if positions[2] <= 0:
                    positions[2] += abs(bid_volume)
                    return_orders.append(Order(product.name, worst_price, -volume))
                    return
                volume += abs(bid_volume)
                worst_price = bid_price
        return_orders.append(Order(product.name, worst_price, -volume))
        positions[2] -= volume
                
    # reliquidates us to be happy and to make more profit YAY
    def handle_liquidation(self, product: Product, positions: list, return_orders: List[Order], sorted_buy_orders: dict, sorted_sell_orders: dict, fair_price: int) -> List[Order]:
        updated_position = positions[0] + (product.params['position_limit'] - positions[0] - positions[1]) - (product.params['position_limit'] + positions[0] - positions[2])
        fair_price = round(fair_price)
        # buying
        if updated_position < -product.params["liquidation_threshold"]:
            for ask_price, ask_volume in sorted_sell_orders.items():
                if ask_price <= fair_price:
                    return_orders.append(Order(product.name, fair_price, min(abs(ask_volume), abs(updated_position) - product.params["liquidation_threshold"], positions[1], 0)))
                    positions[1] -= min(-ask_volume, -updated_position - product.params["liquidation_threshold"], positions[1])

            # return_orders.append(Order(product.name, fair_price, min(-updated_position - product.params["liquidation_threshold"], positions[1])))
            # positions[1] -= min(-updated_position - product.params["liquidation_threshold"], positions[1])
        # selling
        if updated_position > product.params["liquidation_threshold"]:
            for bid_price, bid_volume in sorted_sell_orders.items():
                if bid_price >= fair_price:
                    return_orders.append(Order(product.name, fair_price, -min(abs(bid_volume), abs(updated_position) - product.params["liquidation_threshold"], positions[2], 0)))
                    positions[2] -= min(bid_volume, updated_position - product.params["liquidation_threshold"], positions[2])

            # return_orders.append(Order(product.name, fair_price, -min(updated_position - product.params["liquidation_threshold"], positions[2])))
            # positions[2] -= min(updated_position - product.params["liquidation_threshold"], positions[2])





    def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:

        result: dict[str, list[Order]] = {}
        conversions = 0
        trader_data = ""

        for product in self.products:
            if product.name not in state.order_depths.keys():
                logger.print(product.name, "broken")
                continue

            # update data, give sell and buy orders
            sell_orders, buy_orders, position = product.product_header(state)

            long_position_avaliable = product.params['position_limit'] - position
            short_position_avaliable = product.params['position_limit'] + position
            positions = [position, long_position_avaliable, short_position_avaliable]

            popular_price = product.popular_average
            orders: List[Order] = []
            logger.print(product.name, "positions:", positions)

            # ========================================================================
            # UNIVERSAL
            # ========================================================================

            mm_price = int(popular_price)
            lq_price = int(popular_price)

            # ========================================================================
            # HELP
            # ========================================================================
            if product.name == "KELP":
                logger.print(product.name, "ema:", product.exponential_moving_average)
                logger.print(product.name, "pa:", product.popular_average)
                mm_price = int(product.popular_average)
                lq_price = mm_price

                self.buy_mm(product, positions, orders, sell_orders, mm_price - product.params["mm_epsilon"])
                self.sell_mm(product, positions, orders, buy_orders, mm_price + product.params["mm_epsilon"])

                self.handle_liquidation(product, positions, orders, buy_orders, sell_orders, lq_price)

                # buy
                orders.append(Order(product.name, round(mm_price - product.params["makemm_epsilon"]), positions[1]))
                orders.append(Order(product.name, round(mm_price + product.params["makemm_epsilon"]), -positions[2]))

                # self.handle_liquidation(product.name, positions, orders, lq_price)

            # ========================================================================
            # IN REFOREST RAINS
            # ========================================================================
            elif product.name == "RAINFOREST_RESIN":
                mm_price = 10000
                lq_price = 10000
                
                self.buy_mm(product, positions, orders, sell_orders, mm_price - product.params["mm_epsilon"])
                self.sell_mm(product, positions, orders, buy_orders, mm_price + product.params["mm_epsilon"])

                logger.print("resin:", positions)

                self.handle_liquidation(product, positions, orders, buy_orders, sell_orders, lq_price)
                logger.print("post lq resin:", positions)

                # make these position dynamic
                orders.append(Order(product.name, round(mm_price - product.params["makemm_epsilon"]), positions[1]))
                orders.append(Order(product.name, round(mm_price + product.params["makemm_epsilon"]), -positions[2]))

            # ========================================================================
            # SQUID INK
            # ========================================================================
            elif product.name == "SQUID_INK":
                logger.print(product.name, "ema:", product.exponential_moving_average)
                logger.print(product.name, "pa:", product.popular_average)

                if product.popular_average < product.exponential_moving_average - product.params["mr_epsilon"]:
                    self.buy_mm(product, positions, orders, sell_orders, product.exponential_moving_average - 2 * product.params["mr_epsilon"])

                elif product.popular_average > product.exponential_moving_average + product.params["mr_epsilon"]:
                    self.sell_mm(product, positions, orders, buy_orders, product.exponential_moving_average + 2 * product.params["mr_epsilon"])

                else:
                    self.handle_liquidation(product, positions, orders, buy_orders, sell_orders, lq_price)

                # buy
                # orders.append(Order(product.name, mm_price - mm_epsilon, positions[1]))
                # orders.append(Order(product.name, mm_price + mm_epsilon, -positions[2]))

                # self.handle_liquidation(product.name, positions, orders, lq_price)

            # ========================================================================
            # ELSE
            # ========================================================================
            else:
                logger.print(product, "ema:", product.exponential_moving_average)
                logger.print(product, "pa:", product.popular_average)
                mm_price = product.exponential_moving_average
                lq_price = mm_price

                self.buy_mm(product, positions, orders, sell_orders, mm_price - product.params["mm_epsilon"])
                self.sell_mm(product, positions, orders, buy_orders, mm_price + product.params["mm_epsilon"])

            # ========================================================================
            # UNIVERSAL
            # ========================================================================
            
            # simplify and update our orders
            return_orders = {}
            for order in orders:
                return_orders[order.price] = 0
            for order in orders:
                return_orders[order.price] += order.quantity
            orders = []
            for price, amount in return_orders.items():
                if amount != 0:
                    orders.append(Order(product.name, price, amount))
            result[product.name] = orders

        # ========================================================================
        # ENDING
        # ========================================================================

        logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data


