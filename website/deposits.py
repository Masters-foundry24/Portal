# This file handels all our logic for deposits and withdrawals. The functions
# that render pages should call these functions as soon as possible.

import flask as fl
import flask_login as fo
import decimal as de

from website.models import Account, Payment, Deposit, Order, Trade
from website import db

def admin_checks(account, password):
    """
    This function preforms some sanity checks on deposits/withdrawals entered by
    the administator.
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
    This function preforms some sanity checks on deposits/withdrawals entered by
    the account holder.
    """
    if currency == "EUR" and account.EUR + quantity < de.Decimal("0"):
        # The person is trying to withdraw more money than they have
        fl.flash("Saldo de EUR insufficent", category = "e")
        return False
    elif currency == "STN" and account.STN + quantity < de.Decimal("0"):
        # The person is trying to withdraw more money than they have
        fl.flash("Saldo de STN insufficent", category = "e")
        return False
    elif False:
        # Verify that the IBAN passes a checksum
        return False
    elif quantity < de.Decimal and password != account.password:
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
    else:
        balance_available = account.EUR + quantity
    
    # Bid, orders that are using the currency to purchase something else.
    my_orders = Order.query.filter_by(
        account_id = account.account_id, asset_0 = "STN", side = "bid", 
        active = True)
    for o in my_orders:
        if o.quantity * o.price + balance_used > balance_available:
            # Cancelling the order because the user no longer has funds for it.
            fl.flash(f"Pedido {o.order_id} cancelado, fundos retirados", category = "s")
            o.active = False
        else:
            balance_used += o.quantity * o.price
    
    # Ask orders that are selling the currency as an asset.
    my_orders = Order.query.filter_by(
        account_id = account.account_id, asset_1 = "EUR", side = "ask", 
        active = True)
    for o in my_orders:
        if o.quantity + balance_used > balance_available:
            # Cancelling the order because the user no longer has funds for it.
            fl.flash(f"Pedido {o.order_id} cancelado, fundos retirados", category = "s")
            o.active = False
        else:
            balance_used += o.quantity
    
    # We will not commit these changes yet, only once we have also made the 
    # withdrawal that requires cancelling these orders


def make_deposit(admin: bool, currency: str, quantity: de.Decimal, account_id: int, password: str = None):
    """
    This function adds a new pending deposit (or withdrawal) to the database.

    Inputs:
        -> admin: bool, a withdrawal can can entered into the system by the 
           administrator or the user, a value of True here indicates that the 
           administrator entered the deposit while False indicates that the
           account holder did it. This will affect what checks we preform before
           accepting the deposit.
        -> currency: str, the currency being deposited (either EUR or STN).
        -> quantity: de.Decimal, the amount to be deposited, a negative value
           indicates a withdrawal.
        -> account_id: 
        -> password: entered with the withdrawal or deposit to authorise it. Not
           needed for a user iniciated deposit, but is needed for a user 
           iniciated withdrawal.
    """
    # First we will get the account we are paying into, this variable will be
    # useful later.
    if admin:
        account = Account.query.filter_by(account_id = account_id).first()
    else:
        account = fo.current_user
    
    # Next we will preform some basic checks on the withdrawal, these will be
    # different based on whether or not this is an admin deposit.
    if admin and not admin_checks(account, password):
        return # checks failed
    elif not admin and not user_checks(currency, quantity, password, account):
        return # checks failed
    
    # The order is valid, however, completing a withdrawal may require us to 
    # cancel some orders that were selling assets that are now being withdrawn.
    if quantity < de.Decimal("0"):
        cancel_orders(account, currency, quantity)

    # Now that we're satified that the change is valid, let's record it.
    db.session.add(Deposit(
        currency = currency, quantity = quantity, paid_to_id = account_id)) # , 
        # status = "Pending"))
    
    # For withdrawals we will take the funds away now, for deposits we will wait
    # until the deposit is status: "Done"
    if quantity > de.Decimal("0"): # deposit
        if admin:
            if currency == "EUR":
                account.EUR = account.EUR + quantity
            elif currency == "STN":
                account.STN = account.STN + quantity
            fl.flash(f"Depósito de {currency} {quantity} criado oa conta {account_id}", category = "s")
        else:
            fl.flash(f"Depósito de {currency} {quantity} criado oa sua conta", category = "s")
    else: # withdrawals
        if currency == "EUR":
            account.EUR = account.EUR + quantity
        elif currency == "STN":
            account.STN = account.STN + quantity
        if admin:
            fl.flash(f"{currency} {quantity} tirou de conta {account_id}", category = "s")
        else:
            fl.flash(f"{currency} {quantity} retirou da sua conta", category = "s")
    
    db.session.commit()
    return fl.redirect("/deposits" if admin else "/my_account")

# def deposit_funds(currency: str, quantity: de.Decimal, paid_to_id: int, password: str):
#     """
#     This function deals with POST requests from the secrete deposits money page.
#     """
#     paid_to = Account.query.filter_by(account_id = paid_to_id).first()
# 
#     if not paid_to:
#         # The receipiant does not exist
#         fl.flash("Não existe uma conta com o número fornecido", category = "e")
#     elif password != "Austria":
#         # Incorrect password
#         fl.flash("Senha incorreta", category = "e")
#     else:
#         # The order is valid, however, completing a withdrawal may require us to 
#         # cancel some orders that were selling assets that are now being 
#         # withdrawn.
#         if currency == "STN" and quantity < de.Decimal("0"):
#             balance_available = fo.current_user.STN + quantity
#             balance_used = de.Decimal("0")
#             my_orders = Order.query.filter_by(
#                 account_id = fo.current_user.account_id, asset_0 = "STN", 
#                 asset_1 = "EUR", side = "bid", active = True)
#             for o in my_orders:
#                 if o.quantity * o.price + balance_used > balance_available:
#                     # Cancelling an order because the user no longer has the 
#                     # funds for it.
#                     fl.flash(f"Pedido {o.order_id} cancelado, fundos retirados", category = "s")
#                     o.active = False
#                 else:
#                     balance_used += o.quantity * o.price
# 
#         elif currency == "EUR" and quantity < de.Decimal("0"):
#             balance_available = fo.current_user.EUR + quantity
#             balance_used = de.Decimal("0")
#             my_orders = Order.query.filter_by(
#                 account_id = fo.current_user.account_id, asset_0 = "STN", 
#                 asset_1 = "EUR", side = "ask", active = True)
#             for o in my_orders:
#                 if o.quantity + balance_used > balance_available:
#                     # Cancelling an order because the user no longer has the 
#                     # funds for it.
#                     fl.flash(f"Pedido {o.order_id} cancelado, fundos retirados", category = "s")
#                     o.active = False
#                 else:
#                     balance_used += o.quantity
#         
#         # Now that we're satified that the change is valid, let's record it.
#         db.session.add(Deposit(
#             currency = currency, quantity = quantity, 
#             paid_to_id = paid_to_id, status = "Pending"
#             ))
#         if currency == "EUR":
#             paid_to.EUR = paid_to.EUR + quantity
#         elif currency == "STN":
#             paid_to.STN = paid_to.STN + quantity
#             
#         # This commits the new balance as well logging a new deposit.
#         db.session.commit()
#         if quantity > de.Decimal("0"):
#             fl.flash(f"{currency} {quantity} colocou em conta {paid_to_id}", category = "s")
#         else:
#             fl.flash(f"{currency} {quantity} tirou de conta {paid_to_id}", category = "s")
#     
#     return fl.redirect("/deposits")
# 
# def withdraw_EUR(quantity: de.Decimal, name: str, iban: str, password: str):
#     # Next we will preform some checks that the withdrawal is valid.
#     if quantity <= de.Decimal("0"):
#         # Can't use this as a form of depoit
#         fl.flash("O valor deve ser positivo", category = "e")
#     elif quantity > fo.current_user.EUR:
#         # The person is trying to send more money than they have
#         fl.flash("Saldo de EUR insufficent", category = "e")
#     elif False:
#         # Verify that the IBAN passes a checksum
#         pass
#     elif password != fo.current_user.password:
#         # Incorrect password
#         fl.flash("Senha incorreta", category = "e")
#     else:
#         # The payment is valid so, now we will process it.
#         db.session.add(Deposit(
#             currency = "EUR", quantity = - quantity, 
#             paid_to_id = fo.current_user.account_id, status = "Pending"
#         ))
#         fo.current_user.EUR -= quantity
#         
#         # This commits the new balance as well logging a new deposit.
#         db.session.commit()
#         fl.flash(f"EUR {quantity} retirou da sua conta", category = "s")