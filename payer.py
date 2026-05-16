# This is a script that runs daily. If it is the first day of the month then the
# script needs to pay out interst to each account with savings from the
# admin account, the pull the next month's interest into the current month
# and set next month's interst to null.

from website.models import Account, Payment, Flow, Order, Trade, Bot, Instrument
from website import create_app, db, logger
import datetime as dt
import decimal as de

def pay_interest(app, month):
    with app.app_context():
        i = Instrument.query.filter_by(name = "EUR_saving").first()
        rate = i.interest
        admin = Account.query.filter_by(account_id = 1234567).first()
        accounts = Account.query.filter_by()
        for a in accounts:
            if a.account_id != 1234567 and a.SAVE_EUR > de.Decimal("0"):
                amount = (rate * a.SAVE_EUR).quantize(de.Decimal("0.01"), rounding=de.ROUND_UP)
                a.EUR += amount
                admin.EUR -= amount
                db.session.add(Payment(
                    currency = "EUR", quantity = amount, paid_from_id = 1234567, 
                    paid_to_id = a.account_id, message = f"Juro de {month}"))
                logger.info(f"PC currency = EUR, quantity = {amount}, paid_from_id = 1234567, paid_to_id = {a.account_id}")
        i.interest = i.interest_next
        i.interest_next = None
        db.session.commit()

now = dt.datetime.now()
if now.days == 1:
    month = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
        ][now.month - 1]
    app = create_app()
    pay_interest(app, month)

print("stop")