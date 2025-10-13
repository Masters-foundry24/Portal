import flask_login as fo
from sqlalchemy.sql import func
import decimal as de
# import datetime as dt
# b[1:-1].split(", ")
from website import db

class Order(db.Model):
    order_id = db.Column(db.Integer, primary_key = True)
    time = db.Column(db.DateTime(timezone = False), default = func.now())
    time_cancelled = db.Column(db.DateTime(timezone = False), default = func.now())
    time_traded = db.Column(db.DateTime(timezone = False), default = func.now())
    asset_0 = db.Column(db.String(6)) # asset used as a currency
    asset_1 = db.Column(db.String(6)) # asset being bought/sold
    side = db.Column(db.String(6)) # "buy" or "sell"
    price = db.Column(db.Numeric(9, 2))
    quantity = db.Column(db.Numeric(9, 2))
    quantity_og = db.Column(db.Numeric(9, 2))
    active = db.Column(db.Boolean, default = True)
    account_id = db.Column(db.Integer, db.ForeignKey("account.account_id"))

class Payment(db.Model):
    payment_id = db.Column(db.Integer, primary_key = True)
    time = db.Column(db.DateTime(timezone = False), default = func.now())
    currency = db.Column(db.String(6))
    quantity = db.Column(db.Numeric(9, 2))
    paid_from_id = db.Column(db.Integer, db.ForeignKey("account.account_id"))
    paid_to_id = db.Column(db.Integer, db.ForeignKey("account.account_id"))
    status = db.Column(db.Integer, default = 1) # Options are 0 (Pending), 1 (Approved) and 2 (Cancelled)
    message = db.Column(db.String(100))

class Flow(db.Model): # Deposit or withdrawal
    flow_id = db.Column(db.Integer, primary_key = True)
    time = db.Column(db.DateTime(timezone = False), default = func.now())
    time_executed = db.Column(db.DateTime(timezone = False))
    time_cancelled = db.Column(db.DateTime(timezone = False))
    currency = db.Column(db.String(6))
    quantity = db.Column(db.Numeric(9, 2)) # Negative quantity indicate a withdrawal
    paid_to_id = db.Column(db.Integer, db.ForeignKey("account.account_id"))
    status = db.Column(db.Integer, default = 0) # Options are 0 (Pending), 1 (Approved) and 2 (Cancelled)
    message = db.Column(db.String(100))

class Account(db.Model, fo.UserMixin):
    id = db.Column(db.Integer, primary_key = True)
    account_id = db.Column(db.Integer, unique = True)
    name = db.Column(db.String(100))
    password = db.Column(db.String(100))
    STN = db.Column(db.Numeric(9, 2), default = de.Decimal("0"))
    EUR = db.Column(db.Numeric(9, 2), default = de.Decimal("0"))
    USD = db.Column(db.Numeric(9, 2), default = de.Decimal("0"))
    orders = db.relationship("Order")
    # orders = db.relationship("Deposit")
    name_EUR = db.Column(db.String(50))
    IBAN_EUR = db.Column(db.String(100))
    name_STN = db.Column(db.String(50))
    IBAN_STN = db.Column(db.String(100))
    name_USD = db.Column(db.String(50))
    IBAN_USD = db.Column(db.String(100))

class Trade(db.Model):
    trade_id = db.Column(db.Integer, primary_key = True)
    time = db.Column(db.DateTime(timezone = False), default = func.now())
    asset_0 = db.Column(db.String(6)) # asset used as a currency
    asset_1 = db.Column(db.String(6)) # asset being bought/sold
    quantity = db.Column(db.Numeric(9, 2))
    price = db.Column(db.Numeric(9, 2))
    buyer = db.Column(db.Integer, db.ForeignKey("account.account_id"))
    seller = db.Column(db.Integer, db.ForeignKey("account.account_id"))
    side = db.Column(db.String(6)) # Indicates if the order that took the quote was a bid or an ask order.

class Bot(db.Model):
    bot_id = db.Column(db.Integer, primary_key = True)
    user_id = db.Column(db.Integer, db.ForeignKey("account.account_id"))
    bids = db.Column(db.String(100), default = "[]")
    asks = db.Column(db.String(100), default = "[]")
    v1 = db.Column(db.Numeric(9, 2))
    v2 = db.Column(db.Numeric(9, 2))
    v3 = db.Column(db.Numeric(9, 2))