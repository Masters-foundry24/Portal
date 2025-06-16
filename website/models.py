import flask_login as fo
from sqlalchemy.sql import func
# import datetime as dt

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

class Deposit(db.Model):
    deposit_id = db.Column(db.Integer, primary_key = True)
    time = db.Column(db.DateTime(timezone = False), default = func.now())
    currency = db.Column(db.String(6))
    quantity = db.Column(db.Numeric(9, 2)) # Negative quantity indicate a withdrawal
    paid_to_id = db.Column(db.Integer, db.ForeignKey("account.account_id"))

class Account(db.Model, fo.UserMixin):
    id = db.Column(db.Integer, primary_key = True)
    account_id = db.Column(db.Integer, unique = True)
    name = db.Column(db.String(100))
    password = db.Column(db.String(100))
    STN = db.Column(db.Numeric(9, 2))
    EUR = db.Column(db.Numeric(9, 2))
    orders = db.relationship("Order")
    # orders = db.relationship("Deposit")
    # IBAN_EUR = db.Column(db.Integer, default = 0)

class Trade(db.Model):
    trade_id = db.Column(db.Integer, primary_key = True)
    time = db.Column(db.DateTime(timezone = False), default = func.now())
    asset_0 = db.Column(db.String(6)) # asset used as a currency
    asset_1 = db.Column(db.String(6)) # asset being bought/sold
    quantity = db.Column(db.Numeric(9, 2))
    price = db.Column(db.Numeric(9, 2))
    buyer = db.Column(db.Integer, db.ForeignKey("account.account_id"))
    seller = db.Column(db.Integer, db.ForeignKey("account.account_id"))