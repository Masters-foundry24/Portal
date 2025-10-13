# This page has received basic logging.

import flask as fl
import decimal as de
import datetime as dt

from website.models import Account, Payment, Flow, Order, Trade
from website import db, logger

def enter_order(user, side: str, quantity: de.Decimal, price: de.Decimal, asset_0: str, asset_1: str, messages: bool = False):
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
    quantity_og = de.Decimal(quantity)

    # Okay, we are satisfied that this is a valid order. Now we will check 
    # if it matches with any current orders, or will be entered as a quote.
    if side == "bid": # Bid order
        opp_orders = Order.query.filter_by(
            asset_0 = asset_0, asset_1 = asset_1, side = "ask", active = True
            ).order_by(Order.price)
        for o in opp_orders:
            if o.price > price:
                # There is no more price overlap.
                break
            quantity_traded = min(quantity, o.quantity)
            quantity -= quantity_traded
            o.quantity -= quantity_traded
            logger.info(f"OA order_id = {o.order_id}, quantity = {o.quantity}")
                
            # Now we will record the new trade
            if messages:
                fl.flash("Pedido negociado", category = "s")
            db.session.add(Trade(
                asset_0 = asset_0, asset_1 = asset_1, 
                quantity = quantity_traded, price = o.price, 
                buyer = user.account_id, seller = o.account_id
                ))
            logger.info(f"TC asset_0 = {asset_0}, asset_1 = {asset_1}, quantity = {quantity_traded}, price = {o.price}, buyer = {user.account_id}, seller = {o.account_id}")

            # Now we update the balances of both traders.
            buyer = Account.query.filter_by(account_id = user.account_id).first()
            seller = Account.query.filter_by(account_id = o.account_id).first()

            if asset_0 == "STN":
                buyer.STN -= quantity_traded * o.price
                seller.STN += quantity_traded * o.price
                logger.info(f"AA account_id = {buyer.account_id}, STN = {buyer.STN}")
                logger.info(f"AA account_id = {seller.account_id}, STN = {seller.STN}")
            elif asset_0 == "EUR":
                buyer.EUR -= quantity_traded * o.price
                seller.EUR += quantity_traded * o.price
                logger.info(f"AA account_id = {buyer.account_id}, EUR = {buyer.EUR}")
                logger.info(f"AA account_id = {seller.account_id}, EUR = {seller.EUR}")
            if asset_0 == "USD":
                buyer.USD -= quantity_traded * o.price
                seller.USD += quantity_traded * o.price
                logger.info(f"AA account_id = {buyer.account_id}, USD = {buyer.USD}")
                logger.info(f"AA account_id = {seller.account_id}, USD = {seller.USD}")
            
            if asset_1 == "STN":
                buyer.STN += quantity_traded
                seller.STN -= quantity_traded
                logger.info(f"AA account_id = {buyer.account_id}, STN = {buyer.STN}")
                logger.info(f"AA account_id = {seller.account_id}, STN = {seller.STN}")
            elif asset_1 == "EUR":
                buyer.EUR += quantity_traded
                seller.EUR -= quantity_traded
                logger.info(f"AA account_id = {buyer.account_id}, EUR = {buyer.EUR}")
                logger.info(f"AA account_id = {seller.account_id}, EUR = {seller.EUR}")
            if asset_1 == "USD":
                buyer.USD += quantity_traded
                seller.USD -= quantity_traded
                logger.info(f"AA account_id = {buyer.account_id}, USD = {buyer.USD}")
                logger.info(f"AA account_id = {seller.account_id}, USD = {seller.USD}")

            if o.quantity == de.Decimal("0"):
                o.active = False
                o.time_traded = dt.datetime.now()
                logger.info(f"OA order_id = {o.order_id}, active = False, time_traded = {o.time_traded}")

            if quantity == de.Decimal("0"):
                # The new order has fully matched with existing orders so we
                # will stop looping and record the order.
                break

    else: # Ask order
        opp_orders = Order.query.filter_by(
            asset_0 = asset_0, asset_1 = asset_1, side = "bid", active = True
            ).order_by(Order.price.desc())
        for o in opp_orders:
            if o.price < price:
                # There is no more price overlap.
                break
            quantity_traded = min(quantity, o.quantity)
            quantity -= quantity_traded
            o.quantity -= quantity_traded
            logger.info(f"OA order_id = {o.order_id}, quantity = {o.quantity}")

            # Now we will record the new trade
            if messages:
                fl.flash("Pedido negociado", category = "s")
            db.session.add(Trade(
                asset_0 = asset_0, asset_1 = asset_1, 
                quantity = quantity_traded, price = o.price, 
                buyer = o.account_id, seller = user.account_id
                ))
            logger.info(f"TC asset_0 = {asset_0}, asset_1 = {asset_1}, quantity = {quantity_traded}, price = {o.price}, buyer = {user.account_id}, seller = {o.account_id}")

            # Now we update the balances of both traders.
            seller = Account.query.filter_by(account_id = user.account_id).first()
            buyer = Account.query.filter_by(account_id = o.account_id).first()

            if asset_0 == "STN":
                buyer.STN -= quantity_traded * o.price
                seller.STN += quantity_traded * o.price
                logger.info(f"AA account_id = {buyer.account_id}, STN = {buyer.STN}")
                logger.info(f"AA account_id = {seller.account_id}, STN = {seller.STN}")
            elif asset_0 == "EUR":
                buyer.EUR -= quantity_traded * o.price
                seller.EUR += quantity_traded * o.price
                logger.info(f"AA account_id = {buyer.account_id}, EUR = {buyer.EUR}")
                logger.info(f"AA account_id = {seller.account_id}, EUR = {seller.EUR}")
            if asset_0 == "USD":
                buyer.USD -= quantity_traded * o.price
                seller.USD += quantity_traded * o.price
                logger.info(f"AA account_id = {buyer.account_id}, USD = {buyer.USD}")
                logger.info(f"AA account_id = {seller.account_id}, USD = {seller.USD}")
            
            if asset_1 == "STN":
                buyer.STN += quantity_traded
                seller.STN -= quantity_traded
                logger.info(f"AA account_id = {buyer.account_id}, STN = {buyer.STN}")
                logger.info(f"AA account_id = {seller.account_id}, STN = {seller.STN}")
            elif asset_1 == "EUR":
                buyer.EUR += quantity_traded
                seller.EUR -= quantity_traded
                logger.info(f"AA account_id = {buyer.account_id}, EUR = {buyer.EUR}")
                logger.info(f"AA account_id = {seller.account_id}, EUR = {seller.EUR}")
            if asset_1 == "USD":
                buyer.USD += quantity_traded
                seller.USD -= quantity_traded
                logger.info(f"AA account_id = {buyer.account_id}, USD = {buyer.USD}")
                logger.info(f"AA account_id = {seller.account_id}, USD = {seller.USD}")

            if o.quantity == de.Decimal("0"):
                o.active = False
                o.time_traded = dt.datetime.now()
                logger.info(f"OA order_id = {o.order_id}, active = False, time_traded = {o.time_traded}")

            if quantity == de.Decimal("0"):
                # The new order has fully matched with existing orders so we
                # will stop looping and record the order.
                break

    active = (quantity > de.Decimal("0"))        
    db.session.add(Order(
        asset_0 = asset_0, asset_1 = asset_1, side = side, price = price, 
        quantity = quantity, quantity_og = quantity_og, 
        account_id = user.account_id, active = active))
    logger.info(f"TC asset_0 = {asset_0}, asset_1 = {asset_1}, side = {side}, price = {price}, quantity = {quantity}, quantity_og = {quantity_og}, account_id = {user.account_id}, active = {active}")
    db.session.commit()
    logger.info(f"Database Commit")
    if messages:
        fl.flash("Pedido enviado", category = "s")
    return