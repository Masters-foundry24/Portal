import decimal as de
import json
import math
import os

from website.models import Account, Payment, Deposit, Order, Trade
from website.matching_engine import enter_order
from website import db

def bot_order(user, side: str, quantity: de.Decimal, price: de.Decimal):
    """
    The bot order puts enters out order into the market and runs it past the
    matching engine. It differs from the enter_order function in views.py in
    that it; skips some checks that we trust ourselves not to need, removes the
    flash notifications which will confuse the user and impliments slightly
    different logic encase of errors.

    Inputs:
        -> side: str,
        -> quantity: de.Decimal
        -> price: de.Decimal
    """
    # Next, we will check that the user has enough funds to submit this new 
    # order even after considering any orders they already have in this
    # market. Note, once we expand to having more than one market this 
    # function will need to be changed to consider all the user's orders.
    my_orders = Order.query.filter_by(
        account_id = user.account_id, asset_0 = "STN", asset_1 = "EUR", 
        side = side, active = True)

    if side == "bid":
        balance_used = sum([o.quantity * o.price for o in my_orders])
        quantity = math.floor(min(quantity, (user.STN - balance_used) / price))
    else: # side == "ask"
        balance_used = sum([o.quantity for o in my_orders])
        quantity = math.floor(min(quantity, user.EUR - balance_used))

    if quantity == de.Decimal("0"): # We have no funds available for this order.
        return False

    enter_order(user, side, quantity, price, False)

    # Now we will need to figure out what order we just entered.
    order = user.orders[-1]

    return order.order_id

class Fixed_Interval_Market_Maker():
    """
    The fixed interval market maker is a market making algorithm that we use
    when a price can move between two points. Such as in the EUR/STN market 
    where traditional money changes will trade with a wide spread that we 
    operate within.

    The market maker will start with a midpoint price and place the first quotes
    at an offset from that price and then further quotes at smaller offsets from 
    the quotes ahead.

    If a quote is partially taken, then no action is required.

    If a quote is taken completely, say an ask quote, then a new quote should be
    inserted behind the last ask, the last bid should be cancelled and a new bid
    quote should be placed in front of the line. If the first bid is partially
    depleted then it should be increased back to full size.

    If a whole bank of quotes is taken then the banks will be reestablished with
    a new midpoint one place behind where the last quote used to stand.
    """
    def __init__(
        self,
        upper_limit: de.Decimal,
        lower_limit: de.Decimal,
        offset_1: de.Decimal,
        offset_2: de.Decimal,
        depth: int,
        size: de.Decimal,
        user: int
    ):
        self.upper_limit = upper_limit
        self.lower_limit = lower_limit
        self.offset_1 = offset_1
        self.offset_2 = offset_2
        self.depth = depth
        self.size = size
        self.user = Account.query.filter_by(account_id = user).first()

        if os.path.exists(f"bots/{self.user.account_id}.json"):
            with open(f"bots/{self.user.account_id}.json") as f:
                self.data = json.load(f)
        else:
            self.data = {
                "mid": "",
                "bid": [],
                "ask": []
            }
            
        self.main()
        with open(f"bots/{self.user.account_id}.json", "w") as f:
            json.dump(self.data, f)
        
    def set_mid(self):
        # p = (self.upper_limit + self.lower_limit) / 2
        # floor = self.upper_limit - self.offset_1 - self.depth * self.offset_2
        # ceil = self.lower_limit + self.offset_1 + self.depth * self.offset_2
        # mid = (ceil * self.user.EUR * p + floor * self.user.STN) / (self.user.EUR * p + self.user.STN)
        # mid = self.offset_2 * round(mid / self.offset_2)
        # return str(mid)
        return "26.90"

    def establish_banks(self):
        self.data["bid"] = []
        self.data["ask"] = []
        mid = de.Decimal(self.data["mid"])

        for i in range(self.depth):

            price = mid - self.offset_1 - i * self.offset_2
            if price >= self.lower_limit:
                id = bot_order(self.user, "bid", self.size, price)
                if id != False:
                    self.data["bid"].append(id)

            price = mid + self.offset_1 + i * self.offset_2
            if price <= self.upper_limit:
                id = bot_order(self.user, "ask", self.size, price)
                if id != False:
                    self.data["ask"].append(id)
    
    def cancel_all(self, orders):
        for o in orders:
            o.active = False
        db.session.commit()

    def main(self):
        orders = Order.query.filter_by(account_id = self.user.account_id)

        # If the banks are empty then we should fill them. In this section we 
        # have a few checks that the quantities of the last orders are positive
        # this ensures that they were cancelled rather than traded against. If
        # They were traded with then we have a different method for changing the
        # midpoint.

        if len(self.data["bid"]) == 0 and len(self.data["ask"]) == 0:
            self.cancel_all(orders.filter_by(active = True))
            self.data["mid"] = self.set_mid()
            self.establish_banks()
            return
        
        elif len(self.data["bid"]) == 0:
            ask = Order.query.get(self.data["ask"][-1])
            if ask.active == False and ask.quantity > de.Decimal("0"):
                self.cancel_all(orders.filter_by(active = True))
                self.data["mid"] = self.set_mid()
                self.establish_banks()
                return
        
        elif len(self.data["ask"]) == 0:
            bid = Order.query.get(self.data["bid"][-1])
            if bid.active == False and bid.quantity > de.Decimal("0"):
                self.cancel_all(orders.filter_by(active = True))
                self.data["mid"] = self.set_mid()
                self.establish_banks()
                return
        
        else:
            bid = Order.query.get(self.data["bid"][-1])
            ask = Order.query.get(self.data["ask"][-1])
            if ask.active == False and bid.active == False and ask.quantity > de.Decimal("0") and bid.quantity > de.Decimal("0"):
                self.cancel_all(orders.filter_by(active = True))
                self.data["mid"] = self.set_mid()
                self.establish_banks()
                return
                
        if len(self.data["bid"]) > 1:
            # Was our last bid taken?
            if bid.active == False:
                self.cancel_all(orders.filter_by(active = True))

                self.data["mid"] = str(bid.price - self.offset_2)
                self.establish_banks()
                return
        
        if len(self.data["ask"]) > 1:
            # Was our last asks taken?
            if ask.active == False:
                self.cancel_all(orders.filter_by(active = True))

                self.data["mid"] = str(ask.price + self.offset_2)
                self.establish_banks()
                return
        
        self.check_bank("bid", "ask", 1)
        self.check_bank("ask", "bid", - 1)
        return

    def check_bank(self, side: str, nide: str, d: int):
        """
            The check bank function will move through either the bank of bid or
            ask orders starting with the most competitive one. For the sake of
            the reader's sanity, all comments are written as though we are 
            checking the bid bank.

            Inputs:
                -> side: str, the bank to be examined, either "bid" or "ask".
                -> nide: str, the not side, if side is "bid" then nide should be 
                   "ask" and vice versa.
                -> d: int, helps put our orders in the right direction if side
                   is "bid" then d should be 1 and if side is "ask" then d 
                   should be -1.
        """
        # Next we will check out bids from the front.
        while True:
            order = Order.query.get(self.data[side][0])
            if order.active:
                return
            else:
                # Our first bid got taken out, so we will put a new bid at the
                # back of the bank.
                last_order = Order.query.get(self.data[side][-1])
                price = last_order.price - d * self.offset_2
                id = False
                if price >= self.lower_limit and price <= self.upper_limit:
                    id = bot_order(self.user, side, self.size, price)
                if id != False:
                    self.data[side] = self.data[side][1:] + [id]
                else: 
                    # If we didn't try to enter an order, or tried to enter one 
                    # and failed.
                    self.data[side] = self.data[side][1:]

                # If we have a full bank of asks then cancel the last one.
                if len(self.data[nide]) == self.depth:
                    last_nrder = Order.query.get(self.data[nide][-1])
                    last_nrder.active = False
                    db.session.commit()
                    self.data[nide] = self.data[nide][:-1]

                
                if len(self.data[nide]) > 0:
                    nrder = Order.query.get(self.data[nide][0])
                    
                    # If our top ask is depleted then we will restore it.
                    nrder.active = False
                    db.session.commit()
                    id = bot_order(self.user, nide, self.size, nrder.price)
                    if id != False:
                        self.data[nide][0] = id

                    # Next we will place a new ask at the front of the bank.
                    id = bot_order(self.user, nide, self.size, nrder.price - d * self.offset_2)
                    if id != False:
                        self.data[nide] = [id] + self.data[nide]
                
                else:
                    # We will now start the ask bank.
                    if price >= self.lower_limit and price <= self.upper_limit:
                        id = bot_order(self.user, nide, self.size, order.price + 2 * d * self.offset_2)
                        if id != False:
                            self.data[nide] = [id]

def bot_6000000():
    """
    Runs the fixed interval market bot in the EUR/STN market.
    """
    return Fixed_Interval_Market_Maker(
        upper_limit = de.Decimal(27.5),
        lower_limit = de.Decimal(25.5),
        offset_1 = de.Decimal(0.25),
        offset_2 = de.Decimal(0.05),
        depth = 5,
        size = de.Decimal(70),
        user = 6000000
    )