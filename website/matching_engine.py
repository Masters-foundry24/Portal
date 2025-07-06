import flask as fl
import decimal as de
import datetime as dt

from website.models import Account, Payment, Flow, Order, Trade
from website import db

def enter_order(user, side: str, quantity: de.Decimal, price: de.Decimal, messages: bool = False):
    """
    An order comes here once it has already passed all its validation checks.
    This function inserts it into the matching engine to check if it matches
    with other products.

    Inputs:
        -> user,
        -> side: str, either "bid" or "ask"
        -> quantity: de.Decimal, 
        -> price: de.Decimal, 
        -> messages: bool, controls if we will display flash messages if the
           order matches, generally, manual orders should have messages while 
           bot orders should not.
    """
    quantity_og = quantity

    # Okay, we are satisfied that this is a valid order. Now we will check 
    # if it matches with any current orders, or will be entered as a quote.
    if side == "bid": # Bid order
        opp_orders = Order.query.filter_by(
            asset_0 = "STN", asset_1 = "EUR", side = "ask", active = True
            ).order_by(Order.price)
        for o in opp_orders:
            if o.price > price:
                # There is no more price overlap.
                break
            quantity_traded = min(quantity, o.quantity)
            quantity -= quantity_traded
            o.quantity -= quantity_traded
                
            # Now we will record the new trade
            if messages:
                fl.flash("Pedido negociado", category = "s")
            db.session.add(Trade(
                asset_0 = "STN", asset_1 = "EUR", 
                quantity = quantity_traded, price = o.price, 
                buyer = user.account_id, seller = o.account_id
                ))

            # Now we update the balances of both traders.
            buyer = Account.query.filter_by(account_id = user.account_id).first()
            seller = Account.query.filter_by(account_id = o.account_id).first()

            buyer.EUR += quantity_traded
            buyer.STN -= quantity_traded * o.price
            seller.EUR -= quantity_traded
            seller.STN += quantity_traded * o.price

            if o.quantity == de.Decimal("0"):
                o.active = False
                o.time_traded = dt.datetime.now()

            if quantity == de.Decimal("0"):
                # The new order has fully matched with existing orders so we
                # will record the order and stop looping.
                db.session.add(Order(
                    asset_0 = "STN", asset_1 = "EUR", side = side, 
                    price = price, quantity = de.Decimal("0"), 
                    quantity_og = de.Decimal(quantity_og), 
                    account_id = user.account_id, active = False
                    ))
                break

        if quantity > de.Decimal("0"):
            # The order has not fully matched with existing orders so we 
            # will post it as a quote.
            db.session.add(Order(
                asset_0 = "STN", asset_1 = "EUR", side = side, 
                price = price, quantity = quantity, 
                quantity_og = de.Decimal(quantity_og), 
                account_id = user.account_id
                ))

    else: # Ask order
        opp_orders = Order.query.filter_by(
            asset_0 = "STN", asset_1 = "EUR", side = "bid", active = True
            ).order_by(Order.price.desc())
        for o in opp_orders:
            if o.price < price:
                # There is no more price overlap.
                break
            quantity_traded = min(quantity, o.quantity)
            quantity -= quantity_traded
            o.quantity -= quantity_traded

            # Now we will record the new trade
            if messages:
                fl.flash("Pedido negociado", category = "s")
            db.session.add(Trade(
                asset_0 = "STN", asset_1 = "EUR", 
                quantity = quantity_traded, price = o.price, 
                buyer = o.account_id, seller = user.account_id
                ))

            # Now we update the balances of both traders.
            seller = Account.query.filter_by(account_id = user.account_id).first()
            buyer = Account.query.filter_by(account_id = o.account_id).first()

            buyer.EUR += quantity_traded
            buyer.STN -= quantity_traded * o.price
            seller.EUR -= quantity_traded
            seller.STN += quantity_traded * o.price

            if o.quantity == de.Decimal("0"):
                o.active = False
                o.time_traded = dt.datetime.now()

            if quantity == de.Decimal("0"):
                # The new order has fully matched with existing orders so we
                # will record the order and stop looping.
                db.session.add(Order(
                    asset_0 = "STN", asset_1 = "EUR", side = side, 
                    price = price, quantity = de.Decimal("0"), 
                    quantity_og = de.Decimal(quantity_og), 
                    account_id = user.account_id, active = False
                    ))
                break

        if quantity > de.Decimal("0"):
            # The order has not fully matched with existing orders so we 
            # will post it as a quote.
            db.session.add(Order(
                asset_0 = "STN", asset_1 = "EUR", side = side, 
                price = price, quantity = quantity, 
                quantity_og = de.Decimal(quantity_og), 
                account_id = user.account_id
                ))

    db.session.commit()
    if messages:
        fl.flash("Pedido enviado", category = "s")
    return