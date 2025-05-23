import flask as fl
import flask_login as fo
import decimal as de
import datetime as dt
from sqlalchemy.sql import func, or_
from sqlalchemy import or_, text

from .models import Account, Payment, Deposit, Order, Trade
from . import db

views = fl.Blueprint("views", __name__)

def format_de(number):
    """
    In this function we format decimals so that they can be displayed properly
    in tables.

    Todo:
        -> Add full stops at each three digits for very large numbers.
        -> Round numbers with more decimals rather than truncate them.
    """
    number = str(number)
    number = number.replace(".", ",")
    if "," in number:
        pos = len(number) - number.index(",")
        if pos == 2: # One digit behind the decimal point.
            number = number + "0"
        elif pos == 3: # Two digits behind the decimal point.
            pass
        else: # cut off excess digits (rather than round them).
            number = number[:len(number) - (pos - 3)]
    else:
        number = number + ",00"
    return number

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

        # We will begin with some basic checks of the order.
        if quantity <= de.Decimal("0"):
            # You can't enter a negative quantity or a quantity of zero.
            fl.flash("Quantidade deve ser positivo", category = "e")
            book = get_book("STN", "EUR")
            return fl.render_template("market.html", user = fo.current_user, book = book)
        elif price <= de.Decimal("0"):
            # All prices must be postitive.
            fl.flash("Preço deve ser positivo", category = "e")
            book = get_book("STN", "EUR")
            return fl.render_template("market.html", user = fo.current_user, book = book)

        # Next, we will check that the user has enough funds to submit this new 
        # order even after considering any orders they already have in this
        # market. Note, once we expand to having more than one market this 
        # function will need to be changed to consider all the user's orders.
        my_orders = Order.query.filter_by(
            account_id = fo.current_user.account_id, asset_0 = "STN", 
            asset_1 = "EUR", side = side, active = True)

        if side == "bid": # Bid order
            balance_used = price * quantity # balance used by current order
            for o in my_orders:
                balance_used += o.quantity * o.price
            if balance_used > fo.current_user.STN:
                fl.flash("Saldo insufficent, não tens STN bastante.", category = "e")
                book = get_book("STN", "EUR")
                return fl.render_template("market.html", user = fo.current_user, book = book)
        else: # Ask order
            balance_used = quantity # balance used by current order
            for o in my_orders:
                balance_used += o.quantity
            if balance_used > fo.current_user.EUR:
                fl.flash("Saldo insufficent, não tens EUR bastante.", category = "e")
                book = get_book("STN", "EUR")
                return fl.render_template("market.html", user = fo.current_user, book = book)

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
                fl.flash("Pedido negociado", category = "s")
                db.session.add(Trade(
                    asset_0 = "STN", asset_1 = "EUR", 
                    quantity = quantity_traded, price = o.price, 
                    buyer = fo.current_user.account_id, seller = o.account_id
                    ))

                # Now we update the balances of both traders.
                buyer = Account.query.filter_by(account_id = fo.current_user.account_id).first()
                seller = Account.query.filter_by(account_id = o.account_id).first()

                buyer.EUR += quantity_traded
                buyer.STN -= quantity_traded * o.price
                seller.EUR -= quantity_traded
                seller.STN += quantity_traded * o.price

                if o.quantity == de.Decimal("0"):
                    o.active = False

                if quantity == de.Decimal("0"):
                    # The new order has fully matched with existing orders so we
                    # will record the order and stop looping.
                    db.session.add(Order(
                        asset_0 = "STN", asset_1 = "EUR", side = side, 
                        price = price, quantity = de.Decimal("0"), 
                        quantity_og = de.Decimal(data.get("quantity")), 
                        account_id = fo.current_user.account_id, active = False
                        ))
                    break

            if quantity > de.Decimal("0"):
                # The order has not fully matched with existing orders so we 
                # will post it as a quote.
                db.session.add(Order(
                    asset_0 = "STN", asset_1 = "EUR", side = side, 
                    price = price, quantity = de.Decimal("0"), 
                    quantity_og = de.Decimal(data.get("quantity")), 
                    account_id = fo.current_user.account_id
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
                fl.flash("Pedido negociado", category = "s")
                db.session.add(Trade(
                    asset_0 = "STN", asset_1 = "EUR", 
                    quantity = quantity_traded, price = o.price, 
                    buyer = o.account_id, seller = fo.current_user.account_id
                    ))

                # Now we update the balances of both traders.
                seller = Account.query.filter_by(account_id = fo.current_user.account_id).first()
                buyer = Account.query.filter_by(account_id = o.account_id).first()

                buyer.EUR += quantity_traded
                buyer.STN -= quantity_traded * o.price
                seller.EUR -= quantity_traded
                seller.STN += quantity_traded * o.price

                if o.quantity == de.Decimal("0"):
                    o.active = False

                if quantity == de.Decimal("0"):
                    # The new order has fully matched with existing orders so we
                    # will record the order and stop looping.
                    db.session.add(Order(
                        asset_0 = "STN", asset_1 = "EUR", side = side, 
                        price = price, quantity = de.Decimal("0"), 
                        quantity_og = de.Decimal(data.get("quantity")), 
                        account_id = fo.current_user.account_id, active = False
                        ))
                    break

            if quantity > de.Decimal("0"):
                # The order has not fully matched with existing orders so we 
                # will post it as a quote.
                db.session.add(Order(
                    asset_0 = "STN", asset_1 = "EUR", side = side, 
                    price = price, quantity = quantity, 
                    quantity_og = de.Decimal(data.get("quantity")), 
                    account_id = fo.current_user.account_id
                    ))

        db.session.commit()
        fl.flash("Pedido enviado", category = "s")

    book = get_book("STN", "EUR")
    return fl.render_template("market.html", user = fo.current_user, book = book)

@views.route("/how_it_works")
def how_it_works():
    return fl.render_template("how_it_works.html", user = fo.current_user)

def get_trades(account_id: int, row_limit: int = 0, long: bool = False):
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
            time,
            CASE WHEN quantity < 0 THEN 1 ELSE 2 END AS type,
            currency,
            ABS(quantity) AS quantity,
            CASE WHEN quantity < 0 THEN {account_id} ELSE NULL END AS paid_from,
            CASE WHEN quantity > 0 THEN {account_id} ELSE NULL END AS paid_to
        FROM Deposit 
        WHERE paid_to_id={account_id}
        UNION
        SELECT 
            time, 
            0 AS type, 
            currency, 
            quantity, 
            paid_from_id AS paid_from, 
            paid_to_id AS paid_to
        FROM Payment
        WHERE paid_from_id={account_id} OR paid_to_id={account_id}
        ORDER BY time DESC"""))
    
    lables_long = ["Pagamento", "Retirada", "Depósito"]
    lables_short = ["P", "R", "D"]
    transfers, i = [], 0
    for o in transfer_data:
        time = dt.datetime.strptime(o.time, "%Y-%m-%d %H:%M:%S")
        if long:
            transfers.append([
                time.strftime("%d/%m/%y %H:%M:%S"), 
                lables_long[o.type],
                f"{o.currency} {format_de(o.quantity)}", 
                "-" if o.paid_from is None else o.paid_from,
                "-" if o.paid_to is None else o.paid_to
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
    trades = get_trades(fo.current_user.account_id, 7)
    transfers = get_transfers(fo.current_user.account_id, 7)
    return fl.render_template("my_account.html", user = fo.current_user, trades = trades, transfers = transfers)

@fo.login_required
@views.route("/my_trades")
def my_trades():
    trades = get_trades(fo.current_user.account_id, 0, True)
    return fl.render_template("my_trades.html", user = fo.current_user, trades = trades)

@fo.login_required
@views.route("/my_transfers")
def my_transfers():
    transfers = get_transfers(fo.current_user.account_id, 0, True)
    return fl.render_template("my_transfers.html", user = fo.current_user, transfers = transfers)

@fo.login_required
@views.route("/transfers")
def transfers():
    """
    Eventually, this will be the page where users can make deposits or 
    withdrawals to/from the network however currently it is just some text 
    telling users to contact Lázaro.
    """
    return fl.render_template("transfers.html", user = fo.current_user)

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
        data = fl.request.form
        currency = data.get("currency")
        quantity = de.Decimal(data.get("quantity"))
        paid_to_id = int(data.get("paid_to_id"))
        password = data.get("password")

        paid_to = Account.query.filter_by(account_id = paid_to_id).first()
        paid_from = Account.query.filter_by(account_id = fo.current_user.account_id).first()

        # Now for a series of checks to confirm that the request is valid.
        if paid_to_id == fo.current_user.account_id:
            # Can't send money to yourself
            fl.flash("Não pode enviar dinheiro da sua conta para a mesma conta", category = "e")
        elif quantity <= de.Decimal("0"):
            # Can't take money from other people's accounts
            fl.flash("O valor deve ser positivo", category = "e")
        elif currency == "STN" and quantity > fo.current_user.STN:
            # The person is trying to send more money than they have
            fl.flash("Saldo de STN insufficent", category = "e")
        elif currency == "EUR" and quantity > fo.current_user.EUR:
            # The person is trying to send more money than they have
            fl.flash("Saldo de EUR insufficent", category = "e")
        elif not paid_to:
            # The receipiant does not exist
            fl.flash("Não existe uma conta com o número fornecido", category = "e")
        elif password != fo.current_user.password:
            # Incorrect password
            fl.flash("Senha incorreta", category = "e")
        else:
            # The payment is valid so, now we will process it.
            db.session.add(Payment(
                currency = currency, quantity = quantity, 
                paid_from_id = fo.current_user.account_id, 
                paid_to_id = paid_to_id
                ))
            if currency == "EUR":
                paid_to.EUR = paid_to.EUR + quantity
                paid_from.EUR = paid_from.EUR - quantity
            elif currency == "STN":
                paid_to.STN = paid_to.STN + quantity
                paid_from.STN = paid_from.STN - quantity
            
            # This commits the new balances as well logging a the new payment.
            db.session.commit()
            fl.flash("Dinheiro Enviou", category = "s")
    
    return fl.render_template("send.html", user = fo.current_user)

@views.route("/deposits", methods = ["GET", "POST"])
def deposits():
    """
    This is the backend for the deposit page. It is only to be used by Lázaro
    and I to edit user's balances.
    """
    if fl.request.method == "POST":
        data = fl.request.form
        currency = data.get("currency")
        quantity = de.Decimal(data.get("quantity"))
        paid_to_id = int(data.get("paid_to_id"))
        password = data.get("password")

        paid_to = Account.query.filter_by(account_id = paid_to_id).first()

        if not paid_to:
            # The receipiant does not exist
            fl.flash("Não existe uma conta com o número fornecido", category = "e")
        elif password != "Austria":
            # Incorrect password
            fl.flash("Senha incorreta", category = "e")
        else:
            # Now that we're satified that the change is valid, let's record it.
            db.session.add(Deposit(
                currency = currency, quantity = quantity, 
                paid_to_id = paid_to_id
                ))
            if currency == "EUR":
                paid_to.EUR = paid_to.EUR + quantity
            elif currency == "STN":
                paid_to.STN = paid_to.STN + quantity
            
            # This commits the new balance as well logging a new deposit.
            db.session.commit()
            if quantity > de.Decimal("0"):
                fl.flash(f"{currency} {quantity} tirou de conta {paid_to_id}", category = "s")
            else:
                fl.flash(f"{currency} {quantity} colocou em conta {paid_to_id}", category = "s")

    return fl.render_template("deposits.html", user = fo.current_user)

# @views.route("/delete/<int:id>")
# def delete(id):
#     pass
#     # order_to_delete = Order.query.get_or_404(id)
# 
#     # db.session.delete(order_to_delete)
#     # db.session.commit()
#     # fl.flash("Order cancelled")