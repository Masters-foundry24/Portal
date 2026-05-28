# This file is for functions that query the database and create the lists of 
# lists which populate the website's tables.

# import os
# import flask as fl
# import flask_login as fo
# import hashlib as hl
import decimal as de
import datetime as dt
from sqlalchemy.sql import func, or_
from sqlalchemy import or_, text

from website.models import Account, Payment, Flow, Order, Trade, Instrument
# from website.flows import make_flow, get_flow_table, cancel_orders
# from website.matching_engine import enter_order
# from website.bots import bot_6000000, bot_6010000
from website.util import format_de, check_IBAN, sanitise
# from website.tables import get_book
from website import db, logger


def get_book(asset_0: str, asset_1: str, row_count: int = 7):
    """
    Formats the current orders into a book so that they can be displayed on the
    market page.

    Inputs:
        -> asset_0: str, name of the asset being used as a currency, initially
           STN.
        -> asset_1: str, name of the asset being bought and sold, initially EUR.
        -> row_count: the number of rows to display in the table.

    Returns:
        -> book: list, of lists where each sub list has 4 entries corresponding
           to the 4 columns of the book.
    """
    book_data = db.session.query(
        Order.price, 
        func.sum(Order.quantity).label("quantity")
        ).filter_by(asset_0 = asset_0, asset_1 = asset_1, active = True)
    book_bid = book_data.filter_by(side = "bid").group_by(Order.price).order_by(
        Order.price.desc())
    book_ask = book_data.filter_by(side = "ask").group_by(Order.price).order_by(
        Order.price)

    book = [["-", "-", "-", "-"] for _ in range(row_count)]

    i = 0
    for o in book_bid:
        book[i][0] = o.quantity
        book[i][1] = o.price
        i += 1
        if i == row_count:
            break

    i = 0
    for o in book_ask:
        book[i][3] = o.quantity
        book[i][2] = o.price
        i += 1
        if i == row_count:
            break

    return book

def get_market_trades(asset_0: str, asset_1: str, row_limit: int = 7, filterwashing: bool = True, status: int = 1):
    """
    Formats the recent trades in a market so that they can be displayed on the
    market page.

    Inputs:
        -> asset_0: str, name of the asset being used as a currency, initially
           STN.
        -> asset_1: str, name of the asset being bought and sold, initially EUR.
        -> row_limit: the number of rows to display in the table.
    """
    if not (sanitise(asset_0, str) and sanitise(asset_1, str) and sanitise(filterwashing, bool) and sanitise(status, int)):
        return []
    trade_data = db.session.execute(text(f"""
        SELECT *
        FROM Trade
        WHERE asset_0="{asset_0}" AND asset_1="{asset_1}" {"AND buyer!=seller" if filterwashing else ""} AND status={status}
        ORDER BY time DESC"""))
    
    trades, i = [], 0
    for o in trade_data:
        time = dt.datetime.strptime(o.time, "%Y-%m-%d %H:%M:%S")
        # side = "side"
        trades.append([
            time.strftime("%d/%m/%y %H:%M:%S"),
            # side,
            format_de(o.quantity),
            format_de(o.price)
        ])
        i += 1
        if i == row_limit:
            break
    
    return trades

def get_my_trades(account_id: int, row_limit: int = 0, long: bool = False):
    """
    Collects the trade history of a user and formats those trades ready to 
    display in a table. The function begins with an SQL query and then converts
    the result into a list of lists. 

    Inputs:
        -> account_id: int, tells us which user's trades to collect.
        -> row_limit: int, sets a the maximum number of rows to display, 
           defaults to zero which will result in displaying all available data.
        -> long: bool, controls if we add the extra information found on the
           dedicated 'my trades' page (True) or just the summary information
           displayed at 'my account' (False).
    """
    if not sanitise(account_id, int):
        return []
    trade_data = db.session.execute(text(f"""
        SELECT *
        FROM Trade
        WHERE buyer={account_id} OR seller={account_id}
        ORDER BY time DESC"""))
    
    trades, i = [], 0
    for o in trade_data:
        time = dt.datetime.strptime(o.time, "%Y-%m-%d %H:%M:%S")
        if o.buyer == account_id:
            if o.seller == account_id:
                side = "Lavagem"
            else:
                side = "Compra"
        else:
            side = "Vende"
        if long:
            trades.append([
                time.strftime("%d/%m/%y %H:%M:%S"),
                f"{o.asset_0}/{o.asset_1}",
                side,
                format_de(o.quantity),
                format_de(o.price),
                format_de(0), # taxa
                format_de(o.quantity * o.price + 0)
            ])
        else:
            trades.append([
                time.strftime("%d/%m/%y"),
                f"{o.asset_0}/{o.asset_1}",
                side,
                format_de(o.quantity),
                format_de(o.price)
            ])
        i += 1
        if i == row_limit:
            break
    
    return trades

def get_transfers(account_id: int, row_limit: int = 0, long: bool = False):
    """
    Similar to get_my_trades, this function collects the transfer history of a 
    user and formats those transfers ready to display in a table. The SQL query 
    is a little more complex than normal because transfers are stored across two
    different tables. After this, the result is converted into a list of lists.

    Inputs:
        -> account_id: int, tells us which user's transfers to collect. -1 
           indicates that admin is making the request asking for all accounts.
        -> row_limit: int, sets a the maximum number of rows to display, 
           defaults to zero which will result in displaying all available data.
        -> long: bool, controls if we add the extra information found on the
           dedicated 'my transfers' page (True) or just the summary information
           displayed at 'my account' (False).
    """
    if not sanitise(account_id, int):
        return []
    if account_id == -1: # This is true when creating the administrator's table.
        transfer_data = db.session.execute(text(f"""
            SELECT 
                flow_id as id,
                time,
                CASE WHEN quantity < 0 THEN 1 ELSE 2 END AS type,
                currency,
                ABS(quantity) AS quantity,
                CASE WHEN quantity < 0 THEN paid_to_id ELSE NULL END AS paid_from,
                CASE WHEN quantity > 0 THEN paid_to_id ELSE NULL END AS paid_to,
                status,
                message
            FROM Flow 
            UNION
            SELECT 
                payment_id as id,
                time, 
                0 AS type, 
                currency, 
                quantity, 
                paid_from_id AS paid_from, 
                paid_to_id AS paid_to,
                status,
                message
            FROM Payment
            ORDER BY time DESC"""))
    else:
        transfer_data = db.session.execute(text(f"""
            SELECT 
                flow_id as id,
                time,
                CASE WHEN quantity < 0 THEN 1 ELSE 2 END AS type,
                currency,
                ABS(quantity) AS quantity,
                CASE WHEN quantity < 0 THEN {account_id} ELSE NULL END AS paid_from,
                CASE WHEN quantity > 0 THEN {account_id} ELSE NULL END AS paid_to,
                status,
                message
            FROM Flow 
            WHERE paid_to_id={account_id}
            UNION
            SELECT 
                payment_id as id,
                time, 
                0 AS type, 
                currency, 
                quantity, 
                paid_from_id AS paid_from, 
                paid_to_id AS paid_to,
                status,
                message
            FROM Payment
            WHERE paid_from_id={account_id} OR paid_to_id={account_id}
            ORDER BY time DESC"""))
    
    lables_long = ["Pagamento", "Retirada", "Depósito"]
    lables_short = ["P", "R", "D"]
    lables_status = ["Pendente", "Aprovado", "Cancelado"]
    transfers, i = [], 0
    for o in transfer_data:
        time = dt.datetime.strptime(o.time, "%Y-%m-%d %H:%M:%S")
        if long:
            transfers.append([
                o.id,
                time.strftime("%d/%m/%y %H:%M:%S"), 
                lables_long[o.type],
                f"{o.currency} {format_de(o.quantity)}", 
                "-" if o.paid_from is None else o.paid_from,
                "-" if o.paid_to is None else o.paid_to,
                lables_status[o.status],
                o.message
            ])
        else:
            transfers.append([
                time.strftime("%d/%m/%y"), 
                lables_short[o.type],
                f"{o.currency} {format_de(o.quantity)}", 
                "-" if o.paid_from is None else o.paid_from,
                "-" if o.paid_to is None else o.paid_to
                ])
        i += 1
        if i == row_limit:
            break
        
    return transfers
