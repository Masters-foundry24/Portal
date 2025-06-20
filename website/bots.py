import decimal as de
import math

from website.models import Account, Payment, Deposit, Order, Trade, Bot
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

        self.bot = Bot.query.filter_by(user_id = user).first()
        if not self.bot: # The bot doesn't exist so we will create it.
            db.session.add(Bot(user_id = user, v1 = self.set_mid()))
            db.session.commit()
            self.bot = Bot.query.filter_by(user_id = user).first()
            
        self.main()
        
    def set_mid(self):
        # p = (self.upper_limit + self.lower_limit) / 2
        # floor = self.upper_limit - self.offset_1 - self.depth * self.offset_2
        # ceil = self.lower_limit + self.offset_1 + self.depth * self.offset_2
        # mid = (ceil * self.user.EUR * p + floor * self.user.STN) / (self.user.EUR * p + self.user.STN)
        # mid = self.offset_2 * round(mid / self.offset_2)
        # return str(mid)
        return de.Decimal("26.90")

    def establish_banks(self, bids, asks):
        mid = self.bot.v1

        for i in range(self.depth):

            price = mid - self.offset_1 - i * self.offset_2
            if price >= self.lower_limit:
                id = bot_order(self.user, "bid", self.size, price)
                if id != False:
                    bids.append(id)

            price = mid + self.offset_1 + i * self.offset_2
            if price <= self.upper_limit:
                id = bot_order(self.user, "ask", self.size, price)
                if id != False:
                    asks.append(id)
        
        self.bot.bids = str(bids)
        self.bot.asks = str(asks)
        db.session.commit()
    
    def cancel_all(self, orders):
        for o in orders:
            o.active = False
        self.bot.bids = "[]"
        self.bot.asks = "[]"
        db.session.commit()

    def main(self):
        orders = Order.query.filter_by(account_id = self.user.account_id)

        # If the banks are empty then we should fill them. In this section we 
        # have a few checks that the quantities of the last orders are positive
        # this ensures that they were cancelled rather than traded against. If
        # They were traded with then we have a different method for changing the
        # midpoint.

        if len(self.bot.bids) == 2: 
            bids = [] # Empty bank that the split function would handle poorly.
        else:
            bids = [int(i) for i in self.bot.bids[1:-1].split(", ")]
            bid = Order.query.get(bids[-1])
        if len(self.bot.asks) == 2:
            asks = [] # Empty bank that the split function would handle poorly.
        else:
            asks = [int(i) for i in self.bot.asks[1:-1].split(", ")]
            ask = Order.query.get(asks[-1])

        # Are both banks blank requiring a relaunch?
        if (len(bids) == 0 and len(asks) == 0) or (len(bids) == 0 and len(asks) > 0 and not ask.active) or (len(bids) > 0 and not bid.active and len(asks) == 0) or (len(asks) > 0 and not ask.active and len(bids) > 0 and not bid.active):
            self.cancel_all(orders.filter_by(active = True))
            bids, asks = [], []
            self.bot.v1 = self.set_mid()
            self.establish_banks(bids, asks)
            return
                
        # Was our last bid taken?
        if len(bids) > 0 and not bid.active:
            self.cancel_all(orders.filter_by(active = True))
            bids, asks = [], []
            self.bot.v1 = bid.price - self.offset_2
            self.establish_banks(bids, asks)
            return
        
        # Was our last ask taken?
        if len(asks) > 0 and not ask.active:
            self.cancel_all(orders.filter_by(active = True))
            bids, asks = [], []
            self.bot.v1 = ask.price + self.offset_2
            self.establish_banks(bids, asks)
            return
        
        if len(bids) > 0:
            bid = Order.query.get(bids[0])
            while not bid.active:
                # Our first bid has been taken out, we will adjust both banks.
                bids, asks = self.check_bid_bank(bid, bids, asks)
                if len(bids) == 0:
                    break
                else:
                    bid = Order.query.get(bids[0])

        if len(asks) > 0:
            ask = Order.query.get(asks[0])
            while not ask.active:
                # Our first ask has been taken out, we will adjust both banks.
                bids, asks = self.check_ask_bank(ask, bids, asks)
                if len(asks) == 0:
                    break
                else:
                    ask = Order.query.get(asks[0])
        
        return

    def check_bid_bank(self, bid, bids, asks):
        # First, we will put a new bid at the back of the bank.
        last_bid = Order.query.get(bids[-1])
        price = last_bid.price - self.offset_2
        id = False
        if price >= self.lower_limit and price <= self.upper_limit:
            id = bot_order(self.user, "bid", self.size, price)
        if id != False:
            bids = bids[1:] + [id]
        else: 
            # If we didn't try to enter an order, or tried and failed.
            bids = bids[1:]
        self.bot.bids = str(bids)
        db.session.commit()

        # Second, if we have a full bank of asks then cancel the last one.
        if len(asks) == self.depth:
            last_ask = Order.query.get(asks[-1])
            last_ask.active = False
            asks = asks[:-1]
            self.bot.asks = str(asks)
            db.session.commit()

        if len(asks) > 0:
            ask = Order.query.get(asks[0])
            
            # Thirdly, If our top ask is depleted then we will restore it.
            if ask.quantity != ask.quantity_og:
                id = bot_order(self.user, "ask", self.size, ask.price)
                if id != False:
                    ask.active = False
                    asks[0] = id
                    self.bot.asks = str(asks)
                    db.session.commit()

            # Next we will place a new ask at the front of the bank.
            id = bot_order(self.user, "ask", self.size, ask.price - self.offset_2)
            if id != False:
                asks = [id] + asks
                self.bot.asks = str(asks)
                db.session.commit()
                
        else:
            # We will now start the ask bank.
            price = bid.price + 2 * self.offset_1
            if price >= self.lower_limit and price <= self.upper_limit:
                id = bot_order(self.user, "ask", self.size, price)
                if id != False:
                    asks = [id]
                    self.bot.asks = str(asks)
                    db.session.commit()
    
        return bids, asks
    
    def check_ask_bank(self, ask, bids, asks):
        # First, we will put a new ask at the back of the bank.
        last_ask = Order.query.get(asks[-1])
        price = last_ask.price + self.offset_2
        id = False
        if price >= self.lower_limit and price <= self.upper_limit:
            id = bot_order(self.user, "ask", self.size, price)
        if id != False:
            asks = asks[1:] + [id]
        else: 
            # If we didn't try to enter an order, or tried and failed.
            asks = asks[1:]
        self.bot.asks = str(asks)
        db.session.commit()

        # Second, if we have a full bank of bids then cancel the last one.
        if len(bids) == self.depth:
            last_bid = Order.query.get(bids[-1])
            last_bid.active = False
            bids = bids[:-1]
            self.bot.bids = str(bids)
            db.session.commit()

        if len(bids) > 0:
            bid = Order.query.get(bids[0])
            
            # Thirdly, If our top bid is depleted then we will restore it.
            if bid.quantity != bid.quantity_og:
                id = bot_order(self.user, "bid", self.size, bid.price)
                if id != False:
                    bid.active = False
                    bids[0] = id
                    self.bot.bids = str(bids)
                    db.session.commit()

            # Next we will place a new bid at the front of the bank.
            id = bot_order(self.user, "bid", self.size, bid.price + self.offset_2)
            if id != False:
                bids = [id] + bids
                self.bot.bids = str(bids)
                db.session.commit()
                
        else:
            # We will now start the bid bank.
            price = ask.price - 2 * self.offset_1
            if price >= self.lower_limit and price <= self.upper_limit:
                id = bot_order(self.user, "bid", self.size, price)
                if id != False:
                    bids = [id]
                    self.bot.asks = str(bids)
                    db.session.commit()

        return bids, asks

def bot_6000000():
    """
    Runs the fixed interval market bot in the EUR/STN market.
    """
    return Fixed_Interval_Market_Maker(
        upper_limit = de.Decimal("27.5"),
        lower_limit = de.Decimal("25.5"),
        offset_1 = de.Decimal("0.25"),
        offset_2 = de.Decimal("0.05"),
        depth = 5,
        size = de.Decimal("70"),
        user = 6000000
    )