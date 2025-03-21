# hi

from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import string
import logger

class Trader:
    
    def run(self, state: TradingState):
        result = {} # dictionary of key -> str: product, value -> list of orders: orders

        # logic
        acceptable_price_dict = {"RAINFOREST_RESIN": 10000, "KELP": 2018}
        
        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product] # order depth for a product
            orders: List[Order] = []
            acceptable_price = acceptable_price_dict[product];  # Participant should calculate this value
            
            # buying
            if len(order_depth.sell_orders) != 0: # if there are sell orders
                best_ask, best_ask_amount = list(order_depth.sell_orders.items())[0] # first pair of price and quantity
                if int(best_ask) < acceptable_price: 
                    orders.append(Order(product, best_ask, -best_ask_amount))


            # selling
            if len(order_depth.buy_orders) != 0: # if there are buy orders
                best_bid, best_bid_amount = list(order_depth.buy_orders.items())[0]
                if int(best_bid) > acceptable_price:
                    orders.append(Order(product, best_bid, -best_bid_amount))
            
            result[product] = orders
    
        traderData = "SAMPLE" # String value holding Trader state data required. It will be delivered as TradingState.traderData on next execution.
        conversions = 1
        return result, conversions, traderData
