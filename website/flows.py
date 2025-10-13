# This file handels all our logic for deposits and withdrawals. The functions
# that render pages should call these functions as soon as possible.

# This page has received basic logging.

import flask as fl
import flask_login as fo
import decimal as de
import datetime as dt

from website.models import Account, Payment, Flow, Order, Trade
from website.util import format_de
from website import db, logger

def admin_checks(account, password):
    """
    Preforms some sanity checks on flows entered by the administator.
    """
    if not account:
        # The receipiant does not exist
        fl.flash("Não existe uma conta com o número fornecido", category = "e")
        return False
    elif password != "Austria":
        # Incorrect password
        fl.flash("Senha incorreta", category = "e")
        return False
    else:
        # Order is valid
        return True

def user_checks(currency, quantity, password, account):
    """
    Preforms some sanity checks on flows entered by the account holder.
    """
    if currency == "EUR" and account.EUR + quantity < de.Decimal("0"):
        # The person is trying to withdraw more money than they have
        fl.flash("Saldo de EUR insufficent", category = "e")
        return False
    elif currency == "STN" and account.STN + quantity < de.Decimal("0"):
        # The person is trying to withdraw more money than they have
        fl.flash("Saldo de STN insufficent", category = "e")
        return False
    elif currency == "USD" and account.USD + quantity < de.Decimal("0"):
        # The person is trying to withdraw more money than they have
        fl.flash("Saldo de USD insufficent", category = "e")
        return False
    elif False:
        # Verify that the IBAN passes a checksum
        return False
    elif quantity < de.Decimal("0") and password != account.password:
        # Incorrect password during withdrawal
        fl.flash("Senha incorreta", category = "e")
        return False
    else:
        return True

def cancel_orders(account, currency, quantity):
    """
    When we withdraw funds we may need to cancel orders that were using those
    funds. This function finds those orders and cancels them.
    """
    balance_used = de.Decimal("0")
    if currency == "STN":
        balance_available = account.STN + quantity
    elif currency == "EUR":
        balance_available = account.EUR + quantity
    elif currency == "USD":
        balance_available = account.USD + quantity
    
    # Bid, orders that are using the currency to purchase something else.
    my_orders = Order.query.filter_by(
        account_id = account.account_id, asset_0 = currency, side = "bid", 
        active = True)
    for o in my_orders:
        if o.quantity * o.price + balance_used > balance_available:
            # Cancelling the order because the user no longer has funds for it.
            fl.flash(f"Pedido {o.order_id} cancelado, fundos retirados", category = "s")
            o.active = False
            logger.info(f"OA order_id = {o.order_id}, active = False")
        else:
            balance_used += o.quantity * o.price
    
    # Ask orders that are selling the currency as an asset.
    my_orders = Order.query.filter_by(
        account_id = account.account_id, asset_1 = currency, side = "ask", 
        active = True)
    for o in my_orders:
        if o.quantity + balance_used > balance_available:
            # Cancelling the order because the user no longer has funds for it.
            fl.flash(f"Pedido {o.order_id} cancelado, fundos retirados", category = "s")
            o.active = False
            logger.info(f"OA order_id = {o.order_id}, active = False")
        else:
            balance_used += o.quantity
    
    # We will not commit these changes yet, only once we have also made the 
    # withdrawal that requires cancelling these orders


def make_flow(admin: bool, currency: str, quantity: de.Decimal, account_id: int, password: str = None):
    """
    This function adds a new pending flow to the database.

    Inputs:
        -> admin: bool, a withdrawal can can entered into the system by the 
           administrator or the user, a value of True here indicates that the 
           administrator entered the flow while False indicates that the account 
           holder did it. This will affect what checks we preform before
           accepting the flow.
        -> currency: str, the currency being deposited (either EUR or STN).
        -> quantity: de.Decimal, the amount to be deposited, a negative value
           indicates a withdrawal.
        -> account_id: 
        -> password: entered with the flow to authorise it. Needed for a user 
           iniciated withdrawal, but not for a user indicated deposit.
    """
    # First we will get the account we are paying into, this variable will be
    # useful later.
    if admin:
        account = Account.query.filter_by(account_id = account_id).first()
    else:
        account = fo.current_user
    
    # Next we will preform some basic checks on the withdrawal, these will be
    # different based on whether or not this is an admin flow.
    if admin and not admin_checks(account, password):
        return # checks failed
    elif not admin and not user_checks(currency, quantity, password, account):
        return # checks failed
    
    # The order is valid, however, completing a withdrawal may require us to 
    # cancel some orders that were selling assets that are now being withdrawn.
    if quantity < de.Decimal("0"):
        cancel_orders(account, currency, quantity)

    # Now that we're satified that the change is valid, let's record it.
    db.session.add(Flow(
        currency = currency, quantity = quantity, paid_to_id = account_id))
    logger.info(f"FC account_id = {account_id}, currency = {currency}, quantity = {quantity}")
    
    # For withdrawals we will take the funds away now, for deposits we will wait
    # until the flow is status: "Approved"
    if quantity > de.Decimal("0"): # deposit
        if admin:
            fl.flash(f"Depósito de {currency} {quantity} criado oa conta {account_id}", category = "s")
        else:
            fl.flash(f"Depósito de {currency} {quantity} criado oa sua conta", category = "s")
    else: # withdrawals
        if currency == "EUR":
            account.EUR = account.EUR + quantity
            logger.info(f"AA account_id = {account_id}, EUR = {account.EUR}")
        elif currency == "STN":
            account.STN = account.STN + quantity
            logger.info(f"AA account_id = {account_id}, STN = {account.STN}")
        elif currency == "USD":
            account.USD = account.USD + quantity
            logger.info(f"AA account_id = {account_id}, USD = {account.USD}")
        if admin:
            fl.flash(f"{currency} {abs(quantity)} tirou de conta {account_id}", category = "s")
        else:
            fl.flash(f"{currency} {abs(quantity)} retirou da sua conta", category = "s")
    
    db.session.commit()
    logger.info(f"Database Commit")
    return fl.redirect("/admin/review_flows" if admin else "/my_account")

def get_flow_table():
    flows = Flow.query.filter_by(status = 0)
    table = []
    for f in flows:
        if f.currency == "EUR": # Withdrawal
            a = Account.query.filter_by(account_id = f.paid_to_id).first()
            IBAN = a.IBAN_EUR
            name = a.name_EUR
        elif f.currency == "USD": # Withdrawal
            a = Account.query.filter_by(account_id = f.paid_to_id).first()
            IBAN = a.IBAN_USD
            name = a.name_USD
        else:
            IBAN, name = "", ""
        table.append([
            f.flow_id,
            f.time.strftime("%d/%m/%y %H:%M:%S"),
            f.paid_to_id,
            f.currency,
            format_de(f.quantity),
            name,
            IBAN
        ])
    return table