# This page has received basic logging.

import yfinance as yf
import decimal as de
import flask as fl
import math
import time

from website.models import Account, Payment, Flow, Order, Trade, Bot
from website.matching_engine import enter_order
from website import db, logger, executor

def bot_order(user, side: str, quantity: de.Decimal, price: de.Decimal, asset_0: str, asset_1: str):
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
        account_id = user.account_id, asset_0 = asset_0, asset_1 = asset_1, 
        side = side, active = True)

    if side == "bid":
        balance_used = sum([o.quantity * o.price for o in my_orders])
        if asset_0 == "STN":
            quantity = math.floor(min(quantity, (user.STN - balance_used) / price))
        elif asset_0 == "EUR":
            quantity = math.floor(min(quantity, (user.EUR - balance_used) / price))
        elif asset_0 == "USD":
            quantity = math.floor(min(quantity, (user.USD - balance_used) / price))
        elif asset_0 == "GBP":
            quantity = math.floor(min(quantity, (user.GBP - balance_used) / price))
        elif asset_0 == "JPY":
            quantity = math.floor(min(quantity, (user.JPY - balance_used) / price))
        elif asset_0 == "CAD":
            quantity = math.floor(min(quantity, (user.CAD - balance_used) / price))
        elif asset_0 == "AUD":
            quantity = math.floor(min(quantity, (user.AUD - balance_used) / price))
        elif asset_0 == "CHF":
            quantity = math.floor(min(quantity, (user.CHF - balance_used) / price))
    else: # side == "ask"
        balance_used = sum([o.quantity for o in my_orders])
        if asset_0 == "STN":
            quantity = math.floor(min(quantity, user.STN - balance_used))
        elif asset_1 == "EUR":
            quantity = math.floor(min(quantity, user.EUR - balance_used))
        elif asset_1 == "USD":
            quantity = math.floor(min(quantity, user.USD - balance_used))
        elif asset_1 == "GBP":
            quantity = math.floor(min(quantity, user.GBP - balance_used))
        elif asset_1 == "JPY":
            quantity = math.floor(min(quantity, user.JPY - balance_used))
        elif asset_1 == "CAD":
            quantity = math.floor(min(quantity, user.CAD - balance_used))
        elif asset_1 == "AUD":
            quantity = math.floor(min(quantity, user.AUD - balance_used))
        elif asset_1 == "CHF":
            quantity = math.floor(min(quantity, user.CHF - balance_used))

    if quantity == de.Decimal("0"): # We have no funds available for this order.
        return False

    enter_order(user, side, quantity, price, asset_0, asset_1, False)

    # Now we will need to figure out what order we just entered.
    order = user.orders[-1]

    return order.order_id

class Deriviative_Market_Maker():
    """
    The derivative market maker is a market makeing algorithm that we use when
    there is already substantical volume for this product outside of the Portal,
    such as the USD/EUR market
    
    The algorithm has an external price which it treats as authoritative and
    which is queries frequently. Then it simply attempts to quote a range around
    that number.

    Every x minutes the bot querys its source and then wants to place two large
    quotes on the closest ticks outside of its offset. If the bot's current 
    quotes are not at the right levels or the right size then it cancels them
    and places new ones.

    When a trade occurs on the market the bot will query its source and adjust
    its quotes if the price is wrong but not the size.

    The trigger to query the source every x minutes is handled outside the bot.
    """
    def __init__(
        self,
        source: str,
        offset: de.Decimal,
        size: de.Decimal,
        user: int
    ):
        self.source = source
        self.offset = offset
        self.size = size
        self.user = Account.query.filter_by(account_id = user).first()

        self.bot = Bot.query.filter_by(user_id = user).first()
        if not self.bot: # The bot doesn't exist so we will create it.
            db.session.add(Bot(user_id = user, v1 = -1, v2 = -1))
            db.session.commit()
            self.bot = Bot.query.filter_by(user_id = user).first()
            
        self.main()

    def query_source(self):
        data = yf.Ticker("EUR=X")
        price = (data.info["bid"] + data.info["ask"]) / 2
        return de.Decimal(price)

    def main(self, source_price = None):
        orders = Order.query.filter_by(account_id = self.user.account_id, active = True)

        # If we did not get given a source price then this check must be caused
        # by a trade, in which case we do not need to check the size of our 
        # orders.
        check_size = True
        if source_price is None:
            check_size = False
            source_price = self.query_source()

        ask_price = (source_price + self.offset).quantize(de.Decimal("0.01"), rounding = de.ROUND_UP)
        bid_price = (source_price - self.offset).quantize(de.Decimal("0.01"), rounding = de.ROUND_DOWN)
        ask_size = de.Decimal(math.floor(min(self.size, self.user.USD)))
        bid_size = de.Decimal(math.floor(min(self.size, self.user.EUR / bid_price)))
        
        if self.bot.v1 in [-1, 0]:
            self.bot.v1 = bot_order(self.user, "ask", ask_size, ask_price, asset_0 = "EUR", asset_1 = "USD")
            db.session.commit()
        else:
            o = Order.query.get(int(self.bot.v1))
            if not o.active or o.price != ask_price or (check_size and ask_size != o.quantity):
                o.active = False
                logger.info(f"OA order_id = {o.order_id}, active = False")
                db.session.commit()
                logger.info(f"Database Commit")
                self.bot.v1 = bot_order(self.user, "ask", ask_size, ask_price, asset_0 = "EUR", asset_1 = "USD")
                db.session.commit()
        
        if self.bot.v2 in [-1, 0]:
            self.bot.v2 = bot_order(self.user, "bid", bid_size, bid_price, asset_0 = "EUR", asset_1 = "USD")
            db.session.commit()
        else:
            o = Order.query.get(int(self.bot.v2))
            if not o.active or o.price != bid_price or (check_size and bid_size != o.quantity):
                o.active = False
                logger.info(f"OA order_id = {o.order_id}, active = False")
                db.session.commit()
                logger.info(f"Database Commit")
                self.bot.v2 = bot_order(self.user, "bid", bid_size, bid_price, asset_0 = "EUR", asset_1 = "USD")
                db.session.commit()
        
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
                id = bot_order(self.user, "bid", self.size, price, asset_0 = "STN", asset_1 = "EUR")
                if id != False:
                    bids.append(id)

            price = mid + self.offset_1 + i * self.offset_2
            if price <= self.upper_limit:
                id = bot_order(self.user, "ask", self.size, price, asset_0 = "STN", asset_1 = "EUR")
                if id != False:
                    asks.append(id)
        
        self.bot.bids = str(bids)
        self.bot.asks = str(asks)
        db.session.commit()
        logger.info(f"Database Commit")
    
    def cancel_all(self, orders):
        for o in orders:
            o.active = False
            logger.info(f"OA order_id = {o.order_id}, active = False")
        self.bot.bids = "[]"
        self.bot.asks = "[]"
        db.session.commit()
        logger.info(f"Database Commit")

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
            id = bot_order(self.user, "bid", self.size, price, asset_0 = "STN", asset_1 = "EUR")
        if id != False:
            bids = bids[1:] + [id]
        else: 
            # If we didn't try to enter an order, or tried and failed.
            bids = bids[1:]
        self.bot.bids = str(bids)
        db.session.commit()
        logger.info(f"Database Commit")

        # Second, if we have a full bank of asks then cancel the last one.
        if len(asks) == self.depth:
            last_ask = Order.query.get(asks[-1])
            last_ask.active = False
            logger.info(f"OA order_id = {last_ask.order_id}, active = False")
            asks = asks[:-1]
            self.bot.asks = str(asks)
            db.session.commit()
            logger.info(f"Database Commit")

        if len(asks) > 0:
            ask = Order.query.get(asks[0])
            
            # Thirdly, If our top ask is depleted then we will restore it.
            if ask.quantity != ask.quantity_og:
                id = bot_order(self.user, "ask", self.size, ask.price, asset_0 = "STN", asset_1 = "EUR")
                if id != False:
                    ask.active = False
                    logger.info(f"OA order_id = {ask.order_id}, active = False")
                    asks[0] = id
                    self.bot.asks = str(asks)
                    db.session.commit()
                    logger.info(f"Database Commit")

            # Next we will place a new ask at the front of the bank.
            id = bot_order(self.user, "ask", self.size, ask.price - self.offset_2, asset_0 = "STN", asset_1 = "EUR")
            if id != False:
                asks = [id] + asks
                self.bot.asks = str(asks)
                db.session.commit()
                logger.info(f"Database Commit")
                
        else:
            # We will now start the ask bank.
            price = bid.price + 2 * self.offset_1
            if price >= self.lower_limit and price <= self.upper_limit:
                id = bot_order(self.user, "ask", self.size, price, asset_0 = "STN", asset_1 = "EUR")
                if id != False:
                    asks = [id]
                    self.bot.asks = str(asks)
                    db.session.commit()
                    logger.info(f"Database Commit")
    
        return bids, asks
    
    def check_ask_bank(self, ask, bids, asks):
        # First, we will put a new ask at the back of the bank.
        last_ask = Order.query.get(asks[-1])
        price = last_ask.price + self.offset_2
        id = False
        if price >= self.lower_limit and price <= self.upper_limit:
            id = bot_order(self.user, "ask", self.size, price, asset_0 = "STN", asset_1 = "EUR")
        if id != False:
            asks = asks[1:] + [id]
        else: 
            # If we didn't try to enter an order, or tried and failed.
            asks = asks[1:]
        self.bot.asks = str(asks)
        db.session.commit()
        logger.info(f"Database Commit")

        # Second, if we have a full bank of bids then cancel the last one.
        if len(bids) == self.depth:
            last_bid = Order.query.get(bids[-1])
            last_bid.active = False
            logger.info(f"OA order_id = {last_bid.order_id}, active = False")
            bids = bids[:-1]
            self.bot.bids = str(bids)
            db.session.commit()
            logger.info(f"Database Commit")

        if len(bids) > 0:
            bid = Order.query.get(bids[0])
            
            # Thirdly, If our top bid is depleted then we will restore it.
            if bid.quantity != bid.quantity_og:
                id = bot_order(self.user, "bid", self.size, bid.price, asset_0 = "STN", asset_1 = "EUR")
                if id != False:
                    bid.active = False
                    logger.info(f"OA order_id = {bid.order_id}, active = False")
                    bids[0] = id
                    self.bot.bids = str(bids)
                    db.session.commit()
                    logger.info(f"Database Commit")

            # Next we will place a new bid at the front of the bank.
            id = bot_order(self.user, "bid", self.size, bid.price + self.offset_2, asset_0 = "STN", asset_1 = "EUR")
            if id != False:
                bids = [id] + bids
                self.bot.bids = str(bids)
                db.session.commit()
                logger.info(f"Database Commit")
                
        else:
            # We will now start the bid bank.
            price = ask.price - 2 * self.offset_1
            if price >= self.lower_limit and price <= self.upper_limit:
                id = bot_order(self.user, "bid", self.size, price, asset_0 = "STN", asset_1 = "EUR")
                if id != False:
                    bids = [id]
                    self.bot.asks = str(bids)
                    db.session.commit()
                    logger.info(f"Database Commit")

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

# @app.route("/start/6010000")
def bot_6010000():
    """
    Runs the derivative market making bot in the USD/EUR market.
    """
    return Deriviative_Market_Maker(
        source = "AAPL",
        offset = de.Decimal("0.001"),
        size = de.Decimal("300"),
        user = 6010000
    )