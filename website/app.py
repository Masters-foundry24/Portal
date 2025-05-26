import flask as fl
import flask_sqlalchemy as fs
import os
import flask_login as fo

db = fs.SQLAlchemy()
db_name = "database.db"

app = fl.Flask(__name__)
app.config["SECRET_KEY"] = "keyyy"

# This tells flask the location where the database is stored 
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_name}"
db.init_app(app)

from website.views import views
from website.auth import auth

app.register_blueprint(views, url_prefix = "/")
app.register_blueprint(auth, url_prefix = "/")

from website.models import Order, Account, Payment, Deposit

def create_database(app):
    if not os.path.exists(f"instance/{db_name}"):
        with app.app_context():
            db.create_all() # database created
    else:
        pass # database already exists

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
    # TODO: add a time cancelled.

    # db.session.delete(order_to_cancel)
    db.session.commit()
    fl.flash("Pedido cancelado")

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