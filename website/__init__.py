# A file with the specific __init__.py name turns our website into a python package.

import flask as fl
import flask_sqlalchemy as fs
import datetime as dt
import os
import flask_login as fo
import decimal as de
import logging
import time

from concurrent.futures import ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers = 5)

db = fs.SQLAlchemy()
db_name = "database.db"

logging.basicConfig(
    filename = "database.log",
    format = '%(asctime)s: %(name)s - %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__) # __name__
logging.getLogger('werkzeug').setLevel(logging.CRITICAL + 1)
# logging.getLogger('werkzeug').setLevel(logging.DEBUG)
logging.getLogger('website').setLevel(logging.DEBUG)

logger.info("Initial message to test our logger")

def create_app():
    """
    This function initialises our app to run a website, it was mostly copied
    from this tutorial: https://www.youtube.com/watch?v=dam0GPOAvVI&t=4228s
    """
    app = fl.Flask(__name__)
    app.config["SECRET_KEY"] = "keyyy"

    # This tells flask the location where the database is stored 
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_name}"
    db.init_app(app)

    from website.views import views
    from website.auth import auth

    app.register_blueprint(views, url_prefix = "/")
    app.register_blueprint(auth, url_prefix = "/")

    from website.models import Order, Account, Payment, Flow, Bot
    from website.bots import bot_6000000, bot_6010000

    create_database(app)

    login_manager = fo.LoginManager()
    # login_view tells the manager where to send people who try to access a page 
    # that requires a login auth is the file and login is the function name.
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    # def bot_manager():
    #     while True:
    #         def run_bot():
    #             with app.app_context():
    #                 bot_6010000()
    # 
    #         print("About to run bot 6010000")
    #         run_bot()
    #         time.sleep(300)
    # 
    # executor.submit(bot_manager)

    @login_manager.user_loader
    def load_user(id):
        return Account.query.get(int(id))
    
    @app.route("/cancel/<int:id>")
    def cancel_order(id, return_path = None):
        """
        This function is triggered when the user cancels an order of theirs. It
        simply marks that order inactive in the database.

        Inputs:
            -> id: int, the id of the order to be cancelled.
            -> return_path: str, the path where the user is returned after the 
               their order is cancelled (usually, the same page that the order
               cancelled from).
        """
        o = Order.query.get_or_404(id) # order to cancel

        o.active = False
        o.time_cancelled = dt.datetime.now()
        logger.info(f"OA order_id = {o.order_id}, active = False, time_cancelled = {o.time_cancelled}")

        # db.session.delete(o)
        db.session.commit()
        logger.info(f"Database Commit")
        fl.flash("Pedido cancelado")

        if o.asset_0 == "STN" and o.asset_1 == "EUR" and fo.current_user.account_id != 6000000:
            bot_6000000()
        if return_path is None:
            return fl.redirect(f"/markets/{o.asset_1}{o.asset_0}")
        else:
            return fl.redirect(return_path)
    
    @app.route("/cancel_from_account/<int:id>")
    def cancel_order_from_account(id):
        """
        This function only exists as a wrapper to ensure that we are returned to
        the correct page after cancelling an order.
        """
        return cancel_order(id, "/my_account")
    
    @app.route("/admin/cancel_flow/<int:id>")
    def cancel_flow(id, return_path = "/admin/review_flows"):
        """
        This function is triggered when the administrator cancels a deposit or
        withdrawal.

        Inputs:
            -> id: int, the id of the flow to be cancelled.
            -> return_path: str, the path where the user is returned after the 
               their order is cancelled (usually, the same page that the 
               cancelled from).
        """
        f = Flow.query.get_or_404(id) # flow to cancel

        f.status = 2
        f.time_cancelled = dt.datetime.now()
        logger.info(f"FA flow_id = {f.flow_id}, status = 2, time_cancelled = {f.time_cancelled}")

        # If this is a withdrawal then we need to put the funds back in the 
        # user's account.
        if f.quantity < de.Decimal("0"):
            account_id = f.paid_to_id
            account = Account.query.filter_by(account_id = account_id).first()
            if f.currency == "EUR":
                account.EUR = account.EUR - f.quantity
                logger.info(f"AA account_id = {account.account_id}, EUR = {account.EUR}")
            elif f.currency == "STN":
                account.STN = account.STN - f.quantity
                logger.info(f"AA account_id = {account.account_id}, STN = {account.STN}")
            elif f.currency == "USD":
                account.USD = account.USD - f.quantity
                logger.info(f"AA account_id = {account.account_id}, USD = {account.USD}")
            elif f.currency == "GBP":
                account.GBP = account.GBP - f.quantity
                logger.info(f"AA account_id = {account.account_id}, GBP = {account.GBP}")
            elif f.currency == "JPY":
                account.JPY = account.JPY - f.quantity
                logger.info(f"AA account_id = {account.account_id}, JPY = {account.JPY}")
            elif f.currency == "CAD":
                account.CAD = account.CAD - f.quantity
                logger.info(f"AA account_id = {account.account_id}, CAD = {account.CAD}")
            elif f.currency == "AUD":
                account.AUD = account.AUD - f.quantity
                logger.info(f"AA account_id = {account.account_id}, AUD = {account.AUD}")
            elif f.currency == "CHF":
                account.CHF = account.CHF - f.quantity
                logger.info(f"AA account_id = {account.account_id}, CHF = {account.CHF}")

        # db.session.delete(order_to_cancel)
        db.session.commit()
        logger.info(f"Database Commit")
        fl.flash("Deposito cancelado")

        return fl.redirect(return_path)
    
    @app.route("/cancel_flow_from_account/<int:id>")
    def cancel_flow_from_account(id):
        """
        This function only exists as a wrapper to ensure that we are returned to
        the correct page after cancelling a flow.
        """
        return cancel_flow(id, "/my_transfers")
    
    @app.route("/admin/approve_flow/<int:id>")
    def approve_flow(id, return_path = "/admin/review_flows"):
        """
        This function is triggered when the administrator executes on a deposit 
        or withdrawal.

        Inputs:
            -> id: int, the id of the flow to be excuted.
            -> return_path: str, the path where the user is returned after the 
               their flow is excuted.
        """
        f = Flow.query.get_or_404(id) # flow to approve

        f.status = 1
        f.time_executed = dt.datetime.now()
        logger.info(f"FA flow_id = {f.flow_id}, status = 1, time_cancelled = {f.time_executed}")

        # If this is a deposit we now need to put the funds in the user's 
        # account.
        if f.quantity > de.Decimal("0"):
            account_id = f.paid_to_id
            account = Account.query.filter_by(account_id = account_id).first()
            if f.currency == "EUR":
                account.EUR = account.EUR + f.quantity
                logger.info(f"AA account_id = {account.account_id}, EUR = {account.EUR}")
            elif f.currency == "STN":
                account.STN = account.STN + f.quantity
                logger.info(f"AA account_id = {account.account_id}, STN = {account.STN}")
            elif f.currency == "USD":
                account.USD = account.USD + f.quantity
                logger.info(f"AA account_id = {account.account_id}, USD = {account.USD}")
            elif f.currency == "GBP":
                account.GBP = account.GBP + f.quantity
                logger.info(f"AA account_id = {account.account_id}, GBP = {account.GBP}")
            elif f.currency == "JPY":
                account.JPY = account.JPY + f.quantity
                logger.info(f"AA account_id = {account.account_id}, JPY = {account.JPY}")
            elif f.currency == "CAD":
                account.CAD = account.CAD + f.quantity
                logger.info(f"AA account_id = {account.account_id}, CAD = {account.CAD}")
            elif f.currency == "AUD":
                account.AUD = account.AUD + f.quantity
                logger.info(f"AA account_id = {account.account_id}, AUD = {account.AUD}")
            elif f.currency == "CHF":
                account.CHF = account.CHF + f.quantity
                logger.info(f"AA account_id = {account.account_id}, CHF = {account.CHF}")

        # db.session.delete(order_to_cancel)
        db.session.commit()
        logger.info(f"Database Commit")
        fl.flash("Deposito aprovado")

        return fl.redirect(return_path)
    
    @app.route("/get_account_name")
    def get_account_name():
        """
        This function is used to automatically update names on forms. It gets
        the account_id from a java script and returns the account_name.
        """
        account_id = fl.request.args.get("account_id")
        account = Account.query.filter_by(account_id = account_id).first()
        if account:
            account_name = account.name
            name_EUR, IBAN_EUR = account.name_EUR, account.IBAN_EUR
            name_STN, IBAN_STN = account.name_STN, account.IBAN_STN
            name_USD, IBAN_USD = account.name_USD, account.IBAN_USD
            name_GBP, IBAN_GBP = account.name_GBP, account.IBAN_GBP
            name_JPY, IBAN_JPY = account.name_JPY, account.IBAN_JPY
            name_CAD, IBAN_CAD = account.name_CAD, account.IBAN_CAD
            name_AUD, IBAN_AUD = account.name_AUD, account.IBAN_AUD
            name_CHF, IBAN_CHF = account.name_CHF, account.IBAN_CHF
        else:
            account_name = "Não existe conta com esse número"
            name_EUR, IBAN_EUR = "N/A", "N/A"
            name_STN, IBAN_STN = "N/A", "N/A"
            name_USD, IBAN_USD = "N/A", "N/A"
            name_GBP, IBAN_GBP = "N/A", "N/A"
            name_JPY, IBAN_JPY = "N/A", "N/A"
            name_CAD, IBAN_CAD = "N/A", "N/A"
            name_AUD, IBAN_AUD = "N/A", "N/A"
            name_CHF, IBAN_CHF = "N/A", "N/A"
        return fl.jsonify({
            "account_name": account_name, 
            "name_EUR": name_EUR, "IBAN_EUR": IBAN_EUR,
            "name_STN": name_STN, "IBAN_STN": IBAN_STN,
            "name_USD": name_USD, "IBAN_USD": IBAN_USD,
            "name_GBP": name_GBP, "IBAN_GBP": IBAN_GBP,
            "name_JPY": name_JPY, "IBAN_JPY": IBAN_JPY,
            "name_CAD": name_CAD, "IBAN_CAD": IBAN_CAD,
            "name_AUD": name_AUD, "IBAN_AUD": IBAN_AUD,
            "name_CHF": name_CHF, "IBAN_CHF": IBAN_CHF
            })

    @app.route('/service-worker.js')
    def service_worker():
        return fl.send_from_directory('static', 'service-worker.js')
    
    return app

def create_database(app):
    if os.path.exists(f"instance/{db_name}") or os.path.exists(f"/home/PortalSTP/Portal/instance/{db_name}"):
        pass # database already exists
    else:
        from website.models import Order, Account, Payment, Flow, Bot
        from website.bots import bot_6000000
        from website.views import check_order

        with app.app_context():
            print("NO DATABASE!!! SCREAM!!!")
            # db.create_all() # database created

            # db.session.add(Account(account_id = 9885140, 
            #     name = "Scott Masters", password = "Austria", 
            #     EUR = de.Decimal("0.00"), STN = de.Decimal("0.00"),
            #     name_EUR = "Scott Andrew Masters", IBAN_EUR = "BE17 9677 9251 4921"))
            # db.session.add(Account(account_id = 9875512, 
            #     name = "Lázaro Martins", password = "Lazkatty22", 
            #     EUR = de.Decimal("0.00"), STN = de.Decimal("281.25")))
            # db.session.add(Account(account_id = 1234567, 
            #     name = "Administrador", password = "Austria", 
            #     EUR = de.Decimal("0.00"), STN = de.Decimal("0.00"),
            #     name_EUR = "Scott Andrew Masters", IBAN_EUR = "BE17 9677 9251 4921"))
            # db.session.add(Account(account_id = 6000000, 
            #     name = "EURSTNFIMM", password = "Austria", 
            #     EUR = de.Decimal("593.00"), STN = de.Decimal("29721.95")))
            # db.session.add(Account(account_id = 9018170, 
            #     name = "Lázaro Martins", password = "Lazkatty22@", 
            #     EUR = de.Decimal("0.00"), STN = de.Decimal("0.00")))
            # db.session.add(Account(account_id = 9812368, 
            #     name = "Katiliana Rodrigues", password = "lazkatty22", 
            #     EUR = de.Decimal("44.00"), STN = de.Decimal("0.00")))
            # db.session.add(Account(account_id = 9929925, 
            #     name = "Elsa Mariza", password = "Nuna25", 
            #     EUR = de.Decimal("0.00"), STN = de.Decimal("79.25")))
            # db.session.add(Account(account_id = 9033424, 
            #     name = "Ernaldson Gomes", password = "Gomes25", 
            #     EUR = de.Decimal("0.00"), STN = de.Decimal("6.50")))
            # db.session.add(Account(account_id = 9853105, 
            #     name = "Maria José", password = "1988", 
            #     EUR = de.Decimal("0.00"), STN = de.Decimal("4.25")))
            # db.session.add(Account(account_id = 9906453, 
            #     name = "Páscoa Rita", password = "1234", 
            #     EUR = de.Decimal("0.00"), STN = de.Decimal("95.50")))
            # db.session.add(Account(account_id = 9879940, 
            #     name = "Lourença Felipe", password = "2526", 
            #     EUR = de.Decimal("0.00"), STN = de.Decimal("8.75")))
            # db.session.add(Account(account_id = 9844197, 
            #     name = "Tete Cruz", password = "tete25", 
            #     EUR = de.Decimal("0.00"), STN = de.Decimal("16.90")))
            # db.session.add(Account(account_id = 9000001, 
            #     name = "Julieta Martins", password = "130997", 
            #     EUR = de.Decimal("0.00"), STN = de.Decimal("0.00")))
            # db.session.add(Account(account_id = 9814372, 
            #     name = "Joel Dos Santos", password = "Joel25", 
            #     EUR = de.Decimal("0.00"), STN = de.Decimal("5.25")))
            # db.session.add(Account(account_id = 9041487, 
            #     name = "Ana Sofia Gomes", password = "#8754*", 
            #     EUR = de.Decimal("0.00"), STN = de.Decimal("0.00")))
            # db.session.add(Account(account_id = 90000002, 
            #     name = "Stela Bouças", password = "#2054*", 
            #     EUR = de.Decimal("0.00"), STN = de.Decimal("0.00")))
            # db.session.add(Account(account_id = 9918108, 
            #     name = "Regina Cruz", password = "*1533#", 
            #     EUR = de.Decimal("0.00"), STN = de.Decimal("5.40")))
            # db.session.add(Account(account_id = 9849464, 
            #     name = "Madger Lombá", password = "palavar_passe", 
            #     EUR = de.Decimal("0.00"), STN = de.Decimal("0.00")))
            # db.session.commit()

            # bot_6000000()

            # db.session.add(Flow(currency = "STN", quantity = de.Decimal("815"), 
            #     paid_to_id = 9849464, status = 1))
            # account_0 = Account.query.filter_by(account_id = 9849464).first()
            # account_0.STN += de.Decimal("815")
            # db.session.add(Flow(currency = "STN", quantity = de.Decimal("1358"), 
            #     paid_to_id = 9033424, status = 1))
            # account_1 = Account.query.filter_by(account_id = 9033424).first()
            # account_1.STN += de.Decimal("1358")
            # db.session.commit()

            # check_order(Account.query.filter_by(account_id = 9849464).first(), 
            #     "bid", de.Decimal("30"), de.Decimal("27.15"))
            # check_order(Account.query.filter_by(account_id = 9033424).first(), 
            #     "bid", de.Decimal("40"), de.Decimal("27.15"))
            # check_order(Account.query.filter_by(account_id = 9033424).first(), 
            #     "bid", de.Decimal("10"), de.Decimal("27.20"))
            # db.session.commit()

            # db.session.add(Flow(currency = "EUR", quantity = de.Decimal("-30"), 
            #     paid_to_id = 9849464, status = 1))
            # account_0 = Account.query.filter_by(account_id = 9849464).first()
            # account_0.EUR -= de.Decimal("30")
            # db.session.add(Flow(currency = "EUR", quantity = de.Decimal("-50"), 
            #     paid_to_id = 9033424, status = 1))
            # account_1 = Account.query.filter_by(account_id = 9033424).first()
            # account_1.EUR -= de.Decimal("50")
            # db.session.add(Payment(currency = "EUR", quantity = de.Decimal("30"), 
            #     paid_from_id = 9885140, paid_to_id = 9875512))
            # account_2 = Account.query.filter_by(account_id = 9875512).first()
            # account_2.EUR += de.Decimal("30")
            # db.session.commit()

            # bot_6000000()
