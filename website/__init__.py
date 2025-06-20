# A file with the specific __init__.py name turns our website into a python package.

import flask as fl
import flask_sqlalchemy as fs
import datetime as dt
import os
import flask_login as fo
import decimal as de

db = fs.SQLAlchemy()
db_name = "database.db"

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

    from website.models import Order, Account, Payment, Deposit, Bot
    from website.bots import bot_6000000

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
    def cancel_order(id, return_path = "/market"):
        """
        This function is triggered when the user cancels and order of theirs. It
        simply marks that order inactive in the database.

        Inputs:
            -> id: int, the id of the order to be cancelled.
            -> return_path: str, the path where the user is returned after the 
               their order is cancelled (usually, the same page that the 
               cancelled from).
        """
        order_to_cancel = Order.query.get_or_404(id)

        order_to_cancel.active = False
        order_to_cancel.time_cancelled = dt.datetime.now()

        # db.session.delete(order_to_cancel)
        db.session.commit()
        fl.flash("Pedido cancelado")

        if fo.current_user.account_id != 6000000:
            bot_6000000()
        return fl.redirect(return_path)
    
    @app.route("/cancel_from_account/<int:id>")
    def cancel_order_from_account(id):
        """
        This function only exists as a wrapper to ensure that we are returned to
        the correct page after cancelling an order.
        """
        return cancel_order(id, "/my_account")
    
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
        else:
            account_name = "Não existe conta com esse número"
        return fl.jsonify({"account_name": account_name})

    return app

def create_database(app):
    if not os.path.exists(f"instance/{db_name}"):
        from website.models import Order, Account, Payment, Deposit, Bot
        with app.app_context():
            db.create_all() # database created

            db.session.add(Account(account_id = 9885140, 
                name = "Scott Masters", password = "Austria", 
                EUR = de.Decimal("0.00"), STN = de.Decimal("0.00")))
            db.session.add(Account(account_id = 9875512, 
                name = "Lázaro Martins", password = "Lazkatty22", 
                EUR = de.Decimal("0.00"), STN = de.Decimal("281.25")))
            db.session.add(Account(account_id = 1234567, 
                name = "Administrador", password = "Austria", 
                EUR = de.Decimal("0.00"), STN = de.Decimal("0.00")))
            db.session.add(Account(account_id = 6000000, 
                name = "EURSTNFIMM", password = "Austria", 
                EUR = de.Decimal("593.00"), STN = de.Decimal("29721.95")))
            db.session.add(Account(account_id = 9018170, 
                name = "Lázaro Martins", password = "Lazkatty22@", 
                EUR = de.Decimal("0.00"), STN = de.Decimal("0.00")))
            db.session.add(Account(account_id = 9812368, 
                name = "Katiliana Rodrigues", password = "lazkatty22", 
                EUR = de.Decimal("44.00"), STN = de.Decimal("0.00")))
            db.session.add(Account(account_id = 9929925, 
                name = "Elsa Mariza", password = "Nuna25", 
                EUR = de.Decimal("0.00"), STN = de.Decimal("79.25")))
            db.session.add(Account(account_id = 9033424, 
                name = "Ernaldson Gomes", password = "Gomes25", 
                EUR = de.Decimal("0.00"), STN = de.Decimal("6.50")))
            db.session.add(Account(account_id = 9853105, 
                name = "Maria José", password = "1988", 
                EUR = de.Decimal("0.00"), STN = de.Decimal("4.25")))
            db.session.add(Account(account_id = 9906453, 
                name = "Páscoa Rita", password = "1234", 
                EUR = de.Decimal("0.00"), STN = de.Decimal("95.50")))
            db.session.add(Account(account_id = 9879940, 
                name = "Lourença Felipe", password = "2526", 
                EUR = de.Decimal("0.00"), STN = de.Decimal("8.75")))
            db.session.add(Account(account_id = 9844197, 
                name = "Tete Cruz", password = "tete25", 
                EUR = de.Decimal("0.00"), STN = de.Decimal("16.90")))
            db.session.add(Account(account_id = 9000001, 
                name = "Julieta Martins", password = "130997", 
                EUR = de.Decimal("0.00"), STN = de.Decimal("0.00")))
            db.session.add(Account(account_id = 9814372, 
                name = "Joel Dos Santos", password = "Joel25", 
                EUR = de.Decimal("0.00"), STN = de.Decimal("5.25")))
            db.session.add(Account(account_id = 9041487, 
                name = "Ana Sofia Gomes", password = "#8754*", 
                EUR = de.Decimal("0.00"), STN = de.Decimal("0.00")))
            db.session.add(Account(account_id = 90000002, 
                name = "Stela Bouças", password = "#2054*", 
                EUR = de.Decimal("0.00"), STN = de.Decimal("0.00")))
            db.session.add(Account(account_id = 9918108, 
                name = "Regina Cruz", password = "*1533#", 
                EUR = de.Decimal("0.00"), STN = de.Decimal("5.40")))
            db.session.commit()
    else:
        pass # database already exists