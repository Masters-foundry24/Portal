# This page has received basic logging.

import flask as fl
import flask_login as fo
import decimal as de
import datetime as dt
from sqlalchemy.sql import func, or_
from sqlalchemy import or_, text

from website.models import Account, Payment, Flow, Order, Trade
from website.flows import make_flow, get_flow_table
from website.matching_engine import enter_order
from website.bots import bot_6000000
from website.util import format_de, check_IBAN
from website import db, logger

views = fl.Blueprint("views", __name__)

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

def get_trades(asset_0: str, asset_1: str, row_limit: int = 7):
    """
    Formats the recent trades in a market so that they can be displayed on the
    market page.

    Inputs:
        -> asset_0: str, name of the asset being used as a currency, initially
           STN.
        -> asset_1: str, name of the asset being bought and sold, initially EUR.
        -> row_limit: the number of rows to display in the table.
    """
    trade_data = db.session.execute(text(f"""
        SELECT *
        FROM Trade
        WHERE asset_0="{asset_0}" AND asset_1="{asset_1}" AND buyer!=seller
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

def check_order(user, side: str, quantity: de.Decimal, price: de.Decimal):
    """
    Inputs:
        -> side: str,
        -> quantity: de.Decimal
        -> price: de.Decimal
    """
    # We will begin with some basic checks of the order.
    if quantity <= de.Decimal("0"):
        # You can't enter a negative quantity or a quantity of zero.
        fl.flash("Quantidade deve ser positivo", category = "e")
        return
    elif price <= de.Decimal("0"):
        # All prices must be postitive.
        fl.flash("Preço deve ser positivo", category = "e")
        return

    # Next, we will check that the user has enough funds to submit this new 
    # order even after considering any orders they already have in this
    # market. Note, once we expand to having more than one market this 
    # function will need to be changed to consider all the user's orders.
    my_orders = Order.query.filter_by(
        account_id = user.account_id, asset_0 = "STN", asset_1 = "EUR", 
        side = side, active = True)

    if side == "bid": # Bid order
        balance_used = price * quantity # balance used by current order
        for o in my_orders:
            balance_used += o.quantity * o.price
        if balance_used > user.STN:
            fl.flash("Saldo insufficent, não tens STN bastante.", category = "e")
            return
    else: # Ask order
        balance_used = quantity # balance used by current order
        for o in my_orders:
            balance_used += o.quantity
        if balance_used > user.EUR:
            fl.flash("Saldo insufficent, não tens EUR bastante.", category = "e")
            return
    
    enter_order(user, side, quantity, price)
    
@views.route("/market", methods = ["GET", "POST"])
def market():
    """
    This is the function that acts as the backend to the EUR/STN market. Before
    we can simply the .html file we always need to format the current orders
    into a book and if we get a POST request we need to process the new order as
    well.

    Notes:
        -> The book defaults to a maximum of 7 entries per side.
    """
    if fl.request.method == "POST":
        data = fl.request.form
        side = data.get("side")
        quantity = de.Decimal(data.get("quantity"))
        price = de.Decimal(data.get("price"))
        check_order(fo.current_user, side, quantity, price)
        bot_6000000()
        return fl.redirect("/market")

    book = get_book("STN", "EUR")
    trades = get_trades("STN", "EUR")
    return fl.render_template("market.html", user = fo.current_user, book = book, trades = trades)

@views.route("/how_it_works")
def how_it_works():
    return fl.render_template("how_it_works.html", user = fo.current_user)

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
    trade_data = db.session.execute(text(f"""
        SELECT *
        FROM Trade
        WHERE buyer={account_id} OR seller={account_id}
        ORDER BY time DESC"""))
    # This is another way to make the same SQL query:
    # trade_data = Trade.query.filter(or_(
    # Trade.buyer == account_id, Trade.seller == account_id
    # )).order_by(Trade.time.desc())
    
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
    Similar to get_trades, this function collects the transfer history of a user 
    and formats those transfers ready to display in a table. The SQL query is a
    little more complex than normal because transfers are stored across two
    different tables. After this, the result is converted into a list of lists.

    Inputs:
        -> account_id: int, tells us which user's transfers to collect.
        -> row_limit: int, sets a the maximum number of rows to display, 
           defaults to zero which will result in displaying all available data.
        -> long: bool, controls if we add the extra information found on the
           dedicated 'my transfers' page (True) or just the summary information
           displayed at 'my account' (False).
    """
    transfer_data = db.session.execute(text(f"""
        SELECT 
            flow_id as id,
            time,
            CASE WHEN quantity < 0 THEN 1 ELSE 2 END AS type,
            currency,
            ABS(quantity) AS quantity,
            CASE WHEN quantity < 0 THEN {account_id} ELSE NULL END AS paid_from,
            CASE WHEN quantity > 0 THEN {account_id} ELSE NULL END AS paid_to,
            status
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
            status
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
                lables_status[o.status]
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

@fo.login_required
@views.route("/my_account")
def my_account():
    """
    This function prepares a backend for the 'my account' page where the users
    can see a dashboard summary of their assets.
    """   
    trades = get_my_trades(fo.current_user.account_id, 7)
    transfers = get_transfers(fo.current_user.account_id, 7)
    return fl.render_template("my_account/main.html", user = fo.current_user, trades = trades, transfers = transfers)

@fo.login_required
@views.route("/my_trades")
def my_trades():
    trades = get_my_trades(fo.current_user.account_id, 0, True)
    return fl.render_template("my_account/my_trades.html", user = fo.current_user, trades = trades)

@fo.login_required
@views.route("/my_transfers")
def my_transfers():
    transfers = get_transfers(fo.current_user.account_id, 0, True)
    return fl.render_template("my_account/my_transfers.html", user = fo.current_user, transfers = transfers)

@fo.login_required
@views.route("/deposits")
def deposits():
    """
    Eventually, this will be the page where users can make deposits or 
    withdrawals to/from the network however currently it is just some text 
    telling users to contact Lázaro.
    """
    return fl.render_template("deposits/main.html", user = fo.current_user)

def send_funds(data):
    """
    This function deals with a POST request from the send money page,. It first
    checks that the transfer is valid and if it is executes it before 
    redirecting the user to a GET version of the same page.
    """
    currency = data.get("currency")
    quantity = de.Decimal(data.get("quantity"))
    paid_to_id = int(data.get("paid_to_id"))
    paid_from_id = fo.current_user.account_id
    password = data.get("password")

    paid_to = Account.query.filter_by(account_id = paid_to_id).first()
    paid_from = Account.query.filter_by(account_id = paid_from_id).first()

    # Now for a series of checks to confirm that the request is valid.
    if paid_to_id == paid_from_id:
        # Can't send money to yourself
        fl.flash("Não pode enviar dinheiro da sua conta para a mesma conta", category = "e")
    elif quantity <= de.Decimal("0"):
        # Can't take money from other people's accounts
        fl.flash("O valor deve ser positivo", category = "e")
    elif currency == "STN" and quantity > paid_from.STN:
        # The person is trying to send more money than they have
        fl.flash("Saldo de STN insufficent", category = "e")
    elif currency == "EUR" and quantity > paid_from.EUR:
        # The person is trying to send more money than they have
        fl.flash("Saldo de EUR insufficent", category = "e")
    elif not paid_to:
        # The receipiant does not exist
        fl.flash("Não existe uma conta com o número fornecido", category = "e")
    elif password != paid_from.password:
        # Incorrect password
        fl.flash("Senha incorreta", category = "e")
    else:
        # The payment is valid so, now we will process it.
        db.session.add(Payment(
            currency = currency, quantity = quantity, 
            paid_from_id = paid_from_id, paid_to_id = paid_to_id))
        logger.info(f"PC currency = {currency}, quantity = {quantity}, paid_from_id = {paid_from_id}, paid_to_id = {paid_to_id}")
        if currency == "EUR":
            paid_to.EUR = paid_to.EUR + quantity
            paid_from.EUR = paid_from.EUR - quantity
            logger.info(f"AA account_id = {paid_to_id}, EUR = {paid_to.EUR}")
            logger.info(f"AA account_id = {paid_from_id}, EUR = {paid_to.EUR}")
        elif currency == "STN":
            paid_to.STN = paid_to.STN + quantity
            paid_from.STN = paid_from.STN - quantity
            logger.info(f"AA account_id = {paid_to_id}, STN = {paid_to.STN}")
            logger.info(f"AA account_id = {paid_from_id}, STN = {paid_to.STN}")
            
        # This commits the new balances as well logging a the new payment.
        db.session.commit()
        logger.info(f"Database Commit")
        fl.flash("Dinheiro Enviado", category = "s")
    
    return fl.redirect("/send")

@fo.login_required
@views.route("/send", methods = ["GET", "POST"])
def send():
    """
    This is the backend for the send money page. For a GET request we simply 
    display an html file but for a POST request we first need to check that the
    transfer is valid and if it is excute it before returning the user to the 
    original page.
    """
    if fl.request.method == "POST":
        return send_funds(fl.request.form)
    
    return fl.render_template("send.html", user = fo.current_user)

@fo.login_required
@views.route("/admin/submit_flow", methods = ["GET", "POST"])
def submit_flow():
    """
    This is the backend for the submit flow page. It is only to be used by 
    Lázaro and I to edit user's balances.
    """
    if fl.request.method == "POST":
        data = fl.request.form
        currency = data.get("currency")
        quantity = de.Decimal(data.get("quantity"))
        paid_to_id = int(data.get("paid_to_id"))
        password = data.get("password")
        
        if data.get("name") and currency == "EUR":
            fo.current_user.name_EUR = data.get("name")
            logger.info(f"AA account_id = {fo.current_user.account_id}, name_EUR = {fo.current_user.name_EUR}")

        if data.get("iban") and currency == "EUR":
            IBAN = data.get("iban")
            if check_IBAN(IBAN):
                fo.current_user.IBAN_EUR = IBAN
                logger.info(f"AA account_id = {fo.current_user.account_id}, IBAN_EUR = {IBAN}")
                # If the IBAN is incorrect then the account name isn't saved.
                db.session.commit()
                logger.info(f"Database Commit")
            else:
                fl.flash(f"{IBAN} não é um IBAN válido.", category = "e")
                return fl.render_template("/admin/submit_flow.html", user = fo.current_user)
        
        make_flow(True, currency, quantity, paid_to_id, password)

    return fl.render_template("/admin/submit_flow.html", user = fo.current_user)

@fo.login_required
@views.route("/admin/accounts")
def accounts():
    """
        Lists all the accounts on the Portal if the user is logged in as an
        Administrator.
    """
    if fo.current_user.account_id in [1234567, 9875512]:
        accounts = []
        for a in Account.query:
            accounts.append([a.account_id, a.name, a.password, format_de(a.EUR), format_de(a.STN)])
    else: 
        accounts = []

    return fl.render_template("/admin/accounts.html", user = fo.current_user, accounts = accounts)

@fo.login_required
@views.route("/withdrawals")
def withdrawals():
    return fl.render_template("withdrawals/main.html", user = fo.current_user)

@fo.login_required
@views.route("/withdrawals/STN")
def withdrawals_STN():
    return fl.render_template("withdrawals/STN.html", user = fo.current_user)

@fo.login_required
@views.route("/withdrawals/EUR", methods = ["GET", "POST"])
def withdrawals_EUR():
    if fl.request.method == "POST":
        submit_withdrawal = True
        # We will harvest all the information from the form.
        data = fl.request.form
        quantity = - de.Decimal(data.get("quantity"))
        password = data.get("password")

        if data.get("name"):
            fo.current_user.name_EUR = data.get("name")
            logger.info(f"AA account_id = {fo.current_user.account_id}, name_EUR = {fo.current_user.name_EUR}")
            db.session.commit()
            logger.info(f"Database Commit")
        elif not fo.current_user.name_EUR: # no account name on file:
            fl.flash(f"Precisamos de um nome de conta para enviar seu dinheiro.", category = "e")
            submit_withdrawal = False

        if data.get("iban"):
            IBAN = data.get("iban")
            if check_IBAN(IBAN):
                fo.current_user.IBAN_EUR = IBAN
                logger.info(f"AA account_id = {fo.current_user.account_id}, IBAN_EUR = {IBAN}")
                db.session.commit()
                logger.info(f"Database Commit")
            else:
                fl.flash(f"{IBAN} não é um IBAN válido.", category = "e")
                submit_withdrawal = False
        elif not fo.current_user.IBAN_EUR: # no iban on file:
            fl.flash(f"Precisamos de um IBAN para enviar seu dinheiro.", category = "e")
            submit_withdrawal = False

        if submit_withdrawal:
            make_flow(False, "EUR", quantity, fo.current_user.account_id, password)

    return fl.render_template("withdrawals/EUR.html", user = fo.current_user)

@fo.login_required
@views.route("/admin/review_flows")
def flows():
    flow_table = get_flow_table()
    return fl.render_template("admin/review_flows.html", user = fo.current_user, flows = flow_table)

@fo.login_required
@views.route("/admin")
def admin():
    flow_table = get_flow_table()
    return fl.render_template("admin/main.html", user = fo.current_user, flows = flow_table)