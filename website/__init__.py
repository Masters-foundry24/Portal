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

    from website.models import Order, Account, Payment, Flow, Bot, Trade
    from website.bots import bot_6000000, bot_6010000

    create_database(app)

    login_manager = fo.LoginManager()
    # login_view tells the manager where to send people who try to access a page 
    # that requires a login auth is the file and login is the function name.
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

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
            setattr(account, f.currency, getattr(account, f.currency) - f.quantity)
            logger.info(f"AA account_id = {account.account_id}, {f.currency} = {getattr(account, f.currency)}")

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
        logger.info(f"FA flow_id = {f.flow_id}, status = 1, time_executed = {f.time_executed}")

        # If this is a deposit we now need to put the funds in the user's 
        # account.
        if f.quantity > de.Decimal("0"):
            account_id = f.paid_to_id
            account = Account.query.filter_by(account_id = account_id).first()
            setattr(account, f.currency, getattr(account, f.currency) + f.quantity)
            logger.info(f"AA account_id = {account.account_id}, {f.currency} = {getattr(account, f.currency)}")

        db.session.commit()
        logger.info(f"Database Commit")
        fl.flash("Deposito aprovado")

        return fl.redirect(return_path)
    
    @app.route("/admin/cancel_trade/<int:id>")
    def cancel_trade(id, return_path = "/admin/review_interest"):
        """
        This function is triggered when the administrator cancels a savings
        withdrawal.

        Inputs:
            -> id: int, the id of the trade to be cancelled.
            -> return_path: str, the path where the user is returned after the 
               their trade is cancelled (usually, the same page that the 
               cancelled from).
        """
        t = Trade.query.get_or_404(id) # Trade to cancel

        t.status = 2
        # t.time = dt.datetime.now()
        logger.info(f"TA trade_id = {t.trade_id}, status = 2")

        # We need to take the money out of the RAVE account.
        account_id = t.seller
        account = Account.query.filter_by(account_id = account_id).first()
        if t.asset_1 == "SAVE_EUR":
            account.RAVE_EUR -= t.quantity

        # db.session.delete(order_to_cancel)
        db.session.commit()
        logger.info(f"Database Commit")
        fl.flash("Retira de poupança cancelado")

        return fl.redirect(return_path)
    
    @app.route("/admin/approve_trade/<int:id>")
    def approve_trade(id, return_path = "/admin/review_interest"):
        """
        This function is triggered when the administrator executes on a savings
        withdrawal.

        Inputs:
            -> id: int, the id of the trade to be excuted.
            -> return_path: str, the path where the user is returned after the 
               their trade is excuted.
        """
        t = Trade.query.get_or_404(id) # trade to approve

        t.status = 1
        # t.time = dt.datetime.now()
        logger.info(f"TA trade_id = {t.trade_id}, status = 1")

        # We need to take the money out of the RAVE and SAVE accounts and put it
        # into the main account.
        account_id = t.seller
        account = Account.query.filter_by(account_id = account_id).first()
        if t.asset_1 == "SAVE_EUR":
            account.RAVE_EUR -= t.quantity
            account.SAVE_EUR -= t.quantity
            account.EUR += t.quantity

        # db.session.delete(order_to_cancel)
        db.session.commit()
        logger.info(f"Database Commit")
        fl.flash("Retira de poupança aprovado")

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
