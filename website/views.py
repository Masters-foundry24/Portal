# This page has received basic logging.

import os
import flask as fl
import flask_login as fo
import hashlib as hl
import decimal as de
import datetime as dt
from sqlalchemy.sql import func, or_
from sqlalchemy import or_, text

from website.models import Account, Payment, Flow, Order, Trade, Instrument
from website.flows import make_flow, get_flow_table, cancel_orders
from website.matching_engine import enter_order
from website.bots import bot_6000000, bot_6010000
from website.util import format_de, check_IBAN, sanitise
from website.tables import get_book, get_market_trades, get_my_trades, get_transfers
from website import db, logger, executor

views = fl.Blueprint("views", __name__)

def check_order(user, side: str, quantity: de.Decimal, price: de.Decimal, asset_0: str, asset_1: str):
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
    # order even after considering any orders that they already have.
    if side == "bid": # Bid order
        balance_available = getattr(user, asset_0)
        
        my_bid_orders = Order.query.filter_by(
            account_id = user.account_id, asset_0 = asset_0, side = "bid", 
            active = True)
        my_ask_orders = Order.query.filter_by(
            account_id = user.account_id, asset_1 = asset_0, side = "ask", 
            active = True)
        
        balance_used = price * quantity # balance used by current order
        for o in my_bid_orders:
            balance_used += o.quantity * o.price
        for o in my_ask_orders:
            balance_used += o.quantity
        
        if balance_used > balance_available:
            fl.flash(f"Saldo insufficent, não tens {asset_0} bastante.", category = "e")
            return
    
    else: # Ask order
        balance_available = getattr(user, asset_1)

        my_bid_orders = Order.query.filter_by(
            account_id = user.account_id, asset_0 = asset_1, side = "bid", 
            active = True)
        my_ask_orders = Order.query.filter_by(
            account_id = user.account_id, asset_1 = asset_1, side = "ask", 
            active = True)
        
        balance_used = quantity # balance used by current order
        for o in my_bid_orders:
            balance_used += o.quantity * o.price
        for o in my_ask_orders:
            balance_used += o.quantity

        if balance_used > balance_available:
            fl.flash(f"Saldo insufficent, não tens {asset_1} bastante.", category = "e")
            return
    
    enter_order(user, side, quantity, price, asset_0, asset_1, True)

# TAB: MERCADOS

def market(asset_1, asset_0):
    """
    This is the function that acts as the backend to the various market pages. 
    Before we can serve the .html file we always need to format the current 
    orders into a book and if we get a POST request we need to process the new 
    order as well.

    Inputs:
        -> asset_1: the asset that is treated as an asset, bought and sold in
           this market.
        -> asset_0: the asset that is treated as a currency.

    Notes:
        -> The book defaults to a maximum of 7 entries per side.
    """
    if fl.request.method == "POST":
        data = fl.request.form
        side = data.get("side")
        quantity = de.Decimal(data.get("quantity"))
        price = de.Decimal(data.get("price"))
        check_order(fo.current_user, side, quantity, price, asset_0, asset_1)

        # Running our bots in response
        if asset_0 == "STN":
            bot_6000000()
        else:
            @fl.copy_current_request_context
            def run_bot():
                bot_6010000()
            print("Starting bot 6010000")
            executor.submit(run_bot)
        return fl.redirect(f"/markets/{asset_1}{asset_0}")

    book = get_book(asset_0, asset_1)
    trades = get_market_trades(asset_0, asset_1)
    orders = Order.query.filter_by(account_id = fo.current_user.account_id, asset_0 = asset_0, asset_1 = asset_1)
    return fl.render_template(f"markets/{asset_1}{asset_0}.html", user = fo.current_user, book = book, trades = trades, orders = orders)

@views.route("/markets/EURSTN", methods = ["GET", "POST"])
def EURSTN():
    return market("EUR", "STN")

@views.route("/markets/USDEUR", methods = ["GET", "POST"])
def USDEUR():
    return market("USD", "EUR")

@views.route("/markets/GBPEUR", methods = ["GET", "POST"])
def GBPEUR():
    return market("GBP", "EUR")

@views.route("/markets/JPYEUR", methods = ["GET", "POST"])
def JPYEUR():
    return market("JPY", "EUR")

@views.route("/markets/CADEUR", methods = ["GET", "POST"])
def CADEUR():
    return market("CAD", "EUR")

@views.route("/markets/AUDEUR", methods = ["GET", "POST"])
def AUDEUR():
    return market("AUD", "EUR")

@views.route("/markets/CHFEUR", methods = ["GET", "POST"])
def CHFEUR():
    return market("CHF", "EUR")

# TAB: COMO FUNCIONA

@views.route("/how_it_works")
def how_it_works():
    return fl.render_template("how_it_works.html", user = fo.current_user)

# TAB: MINHA CONTA

@fo.login_required
@views.route("/my_account")
def my_account():
    """
    This function prepares a backend for the 'my account' page where the users
    can see a dashboard summary of their assets.
    """
    trades = get_my_trades(fo.current_user.account_id, 7)
    transfers = get_transfers(fo.current_user.account_id, 7)
    image_path = fl.current_app.root_path + \
        f"/static/images/{fo.current_user.account_id}.{fo.current_user.photo}"
    if os.path.exists(image_path):
        image_name = f"{fo.current_user.account_id}.{fo.current_user.photo}"
    else:
        image_name = "default.png"
    image_path = fl.url_for("static", filename = f"images/{image_name}")
    return fl.render_template("my_account/main.html", user = fo.current_user, trades = trades, transfers = transfers, image_path = image_path)

@fo.login_required
@views.route("/my_account/change_email", methods = ["GET", "POST"])
def change_email():
    """
    This function prepares a backend for the 'change email' page where the users
    can change their email.
    """
    if fl.request.method == "POST":
        data = fl.request.form
        email = data.get("email")
        password = data.get("password")

        if hl.sha256(password.encode()).hexdigest() != fo.current_user.hash:
            # Incorrect password
            fl.flash("Senha incorreta", category = "e")
        else:
            fo.current_user.email = email
            db.session.commit()
            fl.flash("E-mail mudou", category = "s")
            logger.info(f"AA account_id = {fo.current_user.account_id}, email = {email}")
            return fl.redirect(f"/my_account")

    return fl.render_template("my_account/change_email.html", user = fo.current_user)

@fo.login_required
@views.route("/my_account/change_password", methods = ["GET", "POST"])
def change_password():
    """
    This function prepares a backend for the 'change password' page where the 
    users can change their password.
    """
    if fl.request.method == "POST":
        data = fl.request.form
        password_1 = data.get("password_1")
        password_2 = data.get("password_2")
        password = data.get("password")

        if hl.sha256(password.encode()).hexdigest() != fo.current_user.hash:
            # Incorrect password
            fl.flash("Senha incorreta", category = "e")
        elif password_1 != password_2:
            fl.flash("Novas senhas não são iguais", category = "e")
        else:
            fo.current_user.password = password_1
            fo.current_user.hash = hl.sha256(password_1.encode()).hexdigest()
            db.session.commit()
            fl.flash("Senhas mudou", category = "s")
            logger.info(f"AA account_id = {fo.current_user.account_id}, password = CHANGED")
            return fl.redirect(f"/my_account")

    return fl.render_template("my_account/change_password.html", user = fo.current_user)

@fo.login_required
@views.route("/my_account/change_name", methods = ["GET", "POST"])
def change_name():
    """
    This function prepares a backend for the 'change name' page where the users
    can change their name.
    """
    if fl.request.method == "POST":
        data = fl.request.form
        name = data.get("name")
        password = data.get("password")

        if hl.sha256(password.encode()).hexdigest() != fo.current_user.hash:
            # Incorrect password
            fl.flash("Senha incorreta", category = "e")
        else:
            fo.current_user.name = name
            db.session.commit()
            fl.flash("Nome mudou", category = "s")
            logger.info(f"AA account_id = {fo.current_user.account_id}, name = {name}")
            return fl.redirect(f"/my_account")

    return fl.render_template("my_account/change_name.html", user = fo.current_user)

@fo.login_required
@views.route("/my_account/change_phone", methods = ["GET", "POST"])
def change_phone():
    """
    This function prepares a backend for the 'change phone' page where the users
    can change their phone.
    """
    if fl.request.method == "POST":
        data = fl.request.form
        phone = data.get("phone")
        password = data.get("password")

        if hl.sha256(password.encode()).hexdigest() != fo.current_user.hash:
            # Incorrect password
            fl.flash("Senha incorreta", category = "e")
        else:
            fo.current_user.phone = phone
            db.session.commit()
            fl.flash("Telefone mudou", category = "s")
            logger.info(f"AA account_id = {fo.current_user.account_id}, phone = {phone}")
            return fl.redirect(f"/my_account")

    return fl.render_template("my_account/change_phone.html", user = fo.current_user)

@fo.login_required
@views.route("/my_account/change_photo", methods = ["GET", "POST"])
def change_photo():
    """
    This function prepares a backend for the 'change photo' page where the users
    can change their profile photo.
    """
    if fl.request.method == "POST":
        # data = fl.request.form
        file = fl.request.files["photo"]
        if file:
            filetype = file.filename.split(".")[-1].lower()
            if filetype in ["png", "jpeg", "jpg"]:
                image_path = fl.current_app.root_path + f"/static/images/{fo.current_user.account_id}.{filetype}"
                file.save(image_path)
                fo.current_user.photo = filetype
                db.session.commit()
                fl.flash("Foto mudou", category = "s")
                logger.info(f"AA account_id = {fo.current_user.account_id}, photo = {filetype}")
                return fl.redirect(f"/my_account")
            else:
                fl.flash("A foto deve ser '.png', '.jpeg' ou '.jpg'", category = "e")
        else:
            fl.flash("Escolhe uma foto", category = "e")

    return fl.render_template("my_account/change_photo.html", user = fo.current_user)

@fo.login_required
@views.route("/my_account/bank_details")
def bank_details():
    """
    This function prepares a backend for the 'bank details' page where the users
    can see the bank accounts which we have on file for them.
    """
    return fl.render_template("my_account/bank_details.html", user = fo.current_user)

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

# TAB: DEPÓSITOS

@fo.login_required
@views.route("/deposits")
def deposits():
    """
    Eventually, this will be the page where users can make deposits or 
    withdrawals to/from the network however currently it is just some text 
    telling users to contact Lázaro.
    """
    return fl.render_template("deposits/main.html", user = fo.current_user)

# TAB: RETIRADA

@fo.login_required
@views.route("/withdrawals")
def withdrawals():
    return fl.render_template("withdrawals/main.html", user = fo.current_user)

@fo.login_required
@views.route("/withdrawals/<currency>", methods = ["GET", "POST"])
def withdrawal(currency):
    """
    Allows the client to submit a withdrawal flow which then needs to be 
    approved and preformed by an admin.

    Notes:
        -> Since STN is not connected to bank accounts the STN withdrawals page
           does not redirect here.
    """
    currency = currency.upper()
    
    if currency == "STN":
        return fl.render_template("withdrawals/STN.html", user = fo.current_user)
    
    elif currency in ["EUR", "USD", "GBP", "JPY", "CAD", "AUD", "CHF"]:
        if fl.request.method == "POST":
            submit_withdrawal = True
            data = fl.request.form
            quantity = - de.Decimal(data.get("quantity"))
            password = data.get("password")
            message = data.get("message")

            if data.get("name"):
                name = data.get("name")
                setattr(fo.current_user, f"name_{currency}", name)
                logger.info(f"AA account_id = {fo.current_user.account_id}, name_{currency} = {name}")
                db.session.commit()
                logger.info(f"Database Commit")
            elif not getattr(fo.current_user, f"name_{currency}"): # no account name on file:
                fl.flash(f"Precisamos de um nome de conta para enviar seu dinheiro.", category = "e")
                submit_withdrawal = False

            if data.get("iban"):
                IBAN = data.get("iban")
                if check_IBAN(IBAN):
                    setattr(fo.current_user, f"IBAN_{currency}", IBAN)
                    logger.info(f"AA account_id = {fo.current_user.account_id}, IBAN_{currency} = {IBAN}")
                    db.session.commit()
                    logger.info(f"Database Commit")
                else:
                    fl.flash(f"{IBAN} não é um IBAN válido.", category = "e")
                    submit_withdrawal = False
            elif not getattr(fo.current_user, f"IBAN_{currency}"): # no iban on file:
                fl.flash(f"Precisamos de um IBAN para enviar seu dinheiro.", category = "e")
                submit_withdrawal = False

            if submit_withdrawal:
                make_flow(False, currency, quantity, fo.current_user.account_id, password, message)

        return fl.render_template(f"withdrawals/{currency}.html", user = fo.current_user)
    
    else: # If the user inserts a currency like "COW"
        fl.abort(404)

# TAB: ENVIAR DINHEIRO

def send_funds(data):
    # For some reason when variables come back from a form for a 2nd time that
    # have a slash at the end. For now I will just remove those slashes.
    currency = data.get("currency").replace("/", "")
    quantity = de.Decimal(data.get("quantity").replace("/", ""))
    paid_to_id = int(data.get("paid_to_id").replace("/", ""))
    paid_from_id = fo.current_user.account_id
    password = data.get("password")

    paid_to = Account.query.filter_by(account_id = paid_to_id).first()
    paid_from = fo.current_user

    # Now we will preform all the checks on the payment which the user might 
    # want to avoid.
    if quantity <= de.Decimal("0"):
        # Can't take money from other people's accounts
        fl.flash("O valor deve ser positivo", category = "e")
    elif quantity > getattr(paid_from, currency):
        # The person is trying to send more money than they have
        fl.flash(f"Saldo de {currency} insufficent", category = "e")
    elif not paid_to:
        # The receipiant does not exist
        fl.flash("Não existe uma conta com o número fornecido", category = "e")
    elif hl.sha256(password.encode()).hexdigest() != paid_from.hash:
        # Incorrect password
        fl.flash("Senha incorreta", category = "e")

    else:
        # The payment is valid so, now we will process it. To begin with we will
        # cancel any orders that use the same money that we will be paying out.
        cancel_orders(paid_from, currency, - quantity)
        db.session.add(Payment(
            currency = currency, quantity = quantity, 
            paid_from_id = paid_from_id, paid_to_id = paid_to_id))
        logger.info(f"PC currency = {currency}, quantity = {quantity}, paid_from_id = {paid_from_id}, paid_to_id = {paid_to_id}")
        # Add money to the reciever
        setattr(paid_to, currency, getattr(paid_to, currency) + quantity)
        logger.info(f"AA account_id = {paid_to_id}, {currency} = {getattr(paid_to, currency)}")
        # Subtract money from the payer
        setattr(paid_from, currency, getattr(paid_from, currency) - quantity)
        logger.info(f"AA account_id = {paid_from_id}, {currency} = {getattr(paid_from, currency)}")

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
    transfer is valid and if it is proceed to the confirmation page.
    """
    if fl.request.method == "POST":
        data = fl.request.form
        currency = data.get("currency")
        quantity = de.Decimal(data.get("quantity"))
        paid_to_id = int(data.get("paid_to_id"))
        paid_from_id = fo.current_user.account_id

        paid_to = Account.query.filter_by(account_id = paid_to_id).first()

        if paid_to_id == paid_from_id:
            # Can't send money to yourself. Since the user can hack straight to the
            # confirmation page all of our other checks have to be moved there.
            fl.flash("Não pode enviar dinheiro da sua conta para a mesma conta", category = "e")
            return fl.redirect(f"send")
        else:
            return fl.redirect(f"send/confirm?currency={currency}&quantity={str(quantity)}&name={paid_to.name.replace(" ", "%20")}&paid_to_id={paid_to_id}")
    
    return fl.render_template("send/main.html", user = fo.current_user)

@fo.login_required
@views.route("/send/confirm", methods = ["GET", "POST"])
def confirm_send():
    """
    This is the backend for the confirm send money page. Once we get here the
    transfer has already been checked so if it is a POST request we simply 
    excute it before returnin the user to the original page.
    """
    if fl.request.method == "POST":
        return send_funds(fl.request.form)
    
    currency = fl.request.args.get("currency")
    quantity = fl.request.args.get("quantity")
    name = fl.request.args.get("name")
    paid_to_id = fl.request.args.get("paid_to_id")
    return fl.render_template("send/confirm.html", user = fo.current_user, currency = currency, quantity = quantity, paid_to_id = paid_to_id, name = name)

# TAB: POUPANÇA

@fo.login_required
@views.route("/saving", methods = ["GET", "POST"])
def saving():
    if fl.request.method == "POST":
        data = fl.request.form
        quantity = de.Decimal(data.get("quantity"))
        side = data.get("side")
        currency = "EUR"

        if currency == "EUR":
            if quantity < 0:
                fl.flash(f"Não pode ser negativo.", category = "e")
            if side == "add" and quantity > fo.current_user.EUR:
                fl.flash(f"Não tem saldo bastante.", category = "e")
            elif side == "subtract" and quantity > fo.current_user.SAVE_EUR - fo.current_user.RAVE_EUR:
                fl.flash(f"Não podes tirar mais dinheiro que está na propança.", category = "e")
            else:
                if side == "add":
                    fo.current_user.SAVE_EUR += quantity
                    fo.current_user.EUR -= quantity
                    db.session.add(Trade(
                        asset_0 = "EUR", asset_1 = "SAVE_EUR", 
                        quantity = quantity, price = de.Decimal("1"), 
                        buyer = fo.current_user.account_id, seller = 1234567, 
                        status = 1
                    ))
                    logger.info(f"TC asset_0 = EUR, asset_1 = SAVE_EUR, quantity = {quantity}, price = 1.0, buyer = {fo.current_user.account_id}, seller = 1234567")
                    db.session.commit()
                    logger.info(f"Database Commit")
                    fl.flash(f"Dinheiro colocado na caixa.", category = "s")
                else:
                    fo.current_user.RAVE_EUR += quantity
                    db.session.add(Trade(
                        asset_0 = "EUR", asset_1 = "SAVE_EUR", 
                        quantity = quantity, price = de.Decimal("1"), 
                        buyer = 1234567, 
                        seller = fo.current_user.account_id, status = 0
                    ))
                    logger.info(f"TC asset_0 = EUR, asset_1 = SAVE_EUR, quantity = {- quantity}, price = 1.0, buyer = 1234567, seller = {fo.current_user.account_id}")
                    db.session.commit()
                    logger.info(f"Database Commit")
                    fl.flash(f"Dinheiro tirado na caixa.", category = "s")

    EUR_saving = Instrument.query.filter_by(name = "EUR_saving").first()
    EUR_i = format_de(100 * EUR_saving.interest) + "%"
    if EUR_saving.interest_next == None:
        EUR_i_next = "Ainda não foi anunciado"
    else:
        EUR_i_next = format_de(100 * EUR_saving.interest_next) + "%"
    return fl.render_template("saving.html", user = fo.current_user, EUR_i = EUR_i, EUR_i_next = EUR_i_next)

# TAB: ADMIN

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
        if data.get("direction") == "deposit":
            quantity = de.Decimal(data.get("quantity"))
        elif data.get("direction") == "withdrawal":
            quantity = - de.Decimal(data.get("quantity"))
        else:
            fl.flash(f"Escolhe se o fluxo é um deposito ou retirada.", category = "e")
        paid_to_id = int(data.get("paid_to_id"))
        password = data.get("password")
        message = data.get("message")

        # This will be equal to the current user unless and administrator 
        # submitted the flow.
        paid_to = Account.query.filter_by(account_id = paid_to_id).first()
        
        # Saving the user's name for next time.
        if data.get("name"):
            name = data.get("name")
            setattr(paid_to, f"name_{currency}", name)
            logger.info(f"AA account_id = {paid_to.account_id}, name_{currency} = {name}")

        # Saving the user's IBAN for next time.
        if data.get("iban"):
            IBAN = data.get("iban")
            if check_IBAN(IBAN):
                setattr(paid_to, f"IBAN_{currency}", IBAN)
                logger.info(f"AA account_id = {paid_to.account_id}, IBAN_{currency} = {IBAN}")
                # If the IBAN is incorrect then the account name isn't saved.
                db.session.commit()
                logger.info(f"Database Commit")
            else:
                fl.flash(f"{IBAN} não é um IBAN válido.", category = "e")
                return fl.render_template("/admin/submit_flow.html", user = fo.current_user)
        
        make_flow(True, currency, quantity, paid_to_id, password, message)

    return fl.render_template("/admin/submit_flow.html", user = fo.current_user)

@fo.login_required
@views.route("/admin/accounts")
def accounts():
    """
        Lists all the accounts on the Portal if the user is logged in as an
        Administrator.
    """
    if fo.current_user.account_id in [1234567, 9875512]:
        totals = [
            de.Decimal(0), de.Decimal(0), de.Decimal(0), de.Decimal(0), 
            de.Decimal(0), de.Decimal(0), de.Decimal(0), de.Decimal(0)]
        accounts = [[]] # the second brakets will be filled by the totals.
        for a in Account.query:
            accounts.append([
                a.account_id, a.name, a.password, a.hash, format_de(a.EUR), 
                format_de(a.STN), format_de(a.USD), format_de(a.GBP), 
                format_de(a.JPY), format_de(a.CAD), format_de(a.AUD),
                format_de(a.CHF)])
            totals[0] += a.EUR
            totals[1] += a.STN
            totals[2] += a.USD
            totals[3] += a.GBP
            totals[4] += a.JPY
            totals[5] += a.CAD
            totals[6] += a.AUD
            totals[7] += a.CHF
        accounts[0] = ["", "Total", "", "", format_de(totals[0]), 
            format_de(totals[1]), format_de(totals[2]), format_de(totals[3]), 
            format_de(totals[4]), format_de(totals[5]), format_de(totals[6]), 
            format_de(totals[7])]
    else: 
        accounts = []

    return fl.render_template("/admin/accounts.html", user = fo.current_user, accounts = accounts)

@fo.login_required
@views.route("/admin/view_flows")
def view_flows():
    """
        Lists all the flows on the Portal database if the user is logged in as 
        an Administrator.
    """
    if fo.current_user.account_id in [1234567, 9875512]:
        transfers = get_transfers(-1, 0, True)
    else: 
        transfers = []

    return fl.render_template("admin/view_flows.html", user = fo.current_user, transfers = transfers)

@fo.login_required
@views.route("/admin/review_flows")
def flows():
    if fo.current_user.account_id in [1234567, 9875512]:
        flow_table = get_flow_table()
    else: 
        flow_table = []
    return fl.render_template("admin/review_flows.html", user = fo.current_user, flows = flow_table)

@fo.login_required
@views.route("/admin/edit_interest", methods = ["GET", "POST"])
def edit_interest():
    if fl.request.method == "POST":
        data = fl.request.form
        password = data.get("password")
        if data.get("EUR_interest") == "":
            EUR_interest = None
        else:
            EUR_interest = de.Decimal(data.get("EUR_interest"))

        if hl.sha256(password.encode()).hexdigest() != "c9cab0238debc6e55498e2c0963a1d8e25bd29c95ddd53a3fff841ee636b6bc5":
            # Incorrect password
            fl.flash("Senha incorreta", category = "e")
            return fl.render_template("admin/edit_interest.html", user = fo.current_user, EUR_i = EUR_i, EUR_i_next = EUR_i_next)

        if EUR_interest is None or EUR_interest == de.Decimal("0"):
            Instrument.query.filter_by(name = "EUR_saving").first().interest_next = None
            pass
        else:
            Instrument.query.filter_by(name = "EUR_saving").first().interest_next = EUR_interest
        db.session.commit()

    EUR_saving = Instrument.query.filter_by(name = "EUR_saving").first()
    EUR_i = EUR_saving.interest
    if EUR_saving.interest_next == None:
        EUR_i_next = "Não foi anunciado"
    else:
        EUR_i_next = EUR_saving.interest_next
    return fl.render_template("admin/edit_interest.html", user = fo.current_user, EUR_i = EUR_i, EUR_i_next = EUR_i_next)

@fo.login_required
@views.route("/admin/review_interest")
def review_interest():
    if fo.current_user.account_id in [1234567, 9875512]:
        trade_data = db.session.execute(text(f"""
            SELECT *
            FROM Trade
            WHERE status=0
            ORDER BY time DESC"""))
    
        table = []
        for o in trade_data:
            time = dt.datetime.strptime(o.time, "%Y-%m-%d %H:%M:%S")
            table.append([
                o.trade_id, time.strftime("%d/%m/%y %H:%M:%S"), o.buyer,
                o.asset_0, o.asset_1, format_de(o.quantity),
                # format_de(o.price),
            ])
    else: 
        table = []
    return fl.render_template("admin/review_interest.html", user = fo.current_user, table = table)

@fo.login_required
@views.route("/admin")
def admin():
    flow_table = get_flow_table()
    return fl.render_template("admin/main.html", user = fo.current_user, flows = flow_table)

@views.route("/offline")
def offline():
    return fl.render_template("offline.html", user = fo.current_user)

@views.route("/ping")
def ping():
    return fl.Response("ping", status = 200, mimetype = "text/plain")

# 1470