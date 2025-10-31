# This page has received basic logging.

import flask as fl
import flask_login as fo
import decimal as de

from website.models import Account
from website import db, logger # A dot will import from __init__.py

auth = fl.Blueprint("auth", __name__)

@auth.route('/', methods = ["GET", "POST"])
def login():
    """
    This is the home page which also serves as the login page.
    """
    retry = False
    if fl.request.method == "POST":
        data = fl.request.form
        account_id = data.get("account_id")
        password = data.get("password")

        account = Account.query.filter_by(account_id = account_id).first()
        if account:
            if account.password == password:
                fl.flash("Conectado com sucesso", category = "s")
                fo.login_user(account, remember = True)
                return fl.redirect("/")
            else:
                retry = True
                fl.flash("Senha ou número de conta incorretos", category = "e")
        else:
            fl.flash("Número de conta incorreta incorreta", category = "e")
        
    return fl.render_template("home.html", user = fo.current_user, retry = retry)

@auth.route('/logout')
@fo.login_required
def logout():
    """
    When called, this function will logout the user, and then return them to the
    homepage.
    """
    fo.logout_user()
    return fl.redirect("/")

@auth.route('/admin/signup', methods = ["GET", "POST"])
def admin_signup():
    """
    This is a page for Lázaro to use to sign up new users. We use the admin
    password because during beta testing new users aren't supposed to sign 
    themselves up to the Portal.

    If the account is created successfully then we will return Lázaro to the 
    homepage, otherwise the signup form will be loaded again.
    """
    if fl.request.method == "POST":
        data = fl.request.form
        account_id = data.get("account_id")
        name = data.get("name")
        phone = data.get("phone")
        email = data.get("email")
        password = data.get("password")
        password_admin = data.get("password_admin")

        account = Account.query.filter_by(account_id = account_id).first()

        if password_admin != "Austria":
            # Incorrect password
            fl.flash("Senha do administrador não é certo.", category = "e")
        elif account:
            # There is already an account with this number
            fl.flash("Uma conta com este número já existe", category = "e")
        elif len(account_id) != 7:
            # Account number must have exactly 7 digits
            fl.flash("O número da conta deve ter exatamente 7 dígitos", category = "e")
        else:
            # Now that the account is valid we will add it to the database.
            if email == "" and phone == "":
                db.session.add(Account(
                    account_id = account_id, name = name, password = password))
                logger.info(f"AC account_id = {account_id}, name = {name}, password = {password}")
            elif email == "":
                db.session.add(Account(
                    account_id = account_id, name = name, password = password, 
                    phone = phone))
                logger.info(f"AC account_id = {account_id}, name = {name}, password = {password}, phone = {phone}")
            elif phone == "":
                db.session.add(Account(
                    account_id = account_id, name = name, password = password, 
                    email = email))
                logger.info(f"AC account_id = {account_id}, name = {name}, password = {password}, email = {email}")
            else:
                db.session.add(Account(
                    account_id = account_id, name = name, password = password, 
                    phone = phone, email = email))
                logger.info(f"AC account_id = {account_id}, name = {name}, password = {password}, phone = {phone}, email = {email}")
            db.session.commit()
            logger.info(f"Database Commit")
            fl.flash(f"Nova conta {account_id} criada para {name}", category = "s")
            return fl.redirect("/")

    return fl.render_template("/admin/signup.html", user = fo.current_user)

@auth.route('/signup', methods = ["GET", "POST"])
def signup():
    """
    This is a page for uses to sign up by providing the details for their 
    profile. Unlike the admin version, this page is seriously idiot proofed with 
    as much as possible providing imidate feedback through javascript.
    """
    if fl.request.method == "POST":
        data = fl.request.form
        account_id = data.get("account_id")
        name = data.get("name")
        phone = data.get("phone")
        email = data.get("email")
        password_1 = data.get("password_1")
        password_2 = data.get("password__2")

        account = Account.query.filter_by(account_id = account_id).first()

        if password_1 != password_2:
            # Incorrect password
            fl.flash("Senhas não são iguais.", category = "e")
        elif account:
            # There is already an account with this number
            fl.flash("Uma conta com este número já existe", category = "e")
        elif len(account_id) != 7:
            # Account number must have exactly 7 digits
            fl.flash("O número da conta deve ter exatamente 7 dígitos", category = "e")
        else:
            # Now that the account is valid we will add it to the database.
            if email == "" and phone == "":
                db.session.add(Account(
                    account_id = account_id, name = name, password = password_1))
                logger.info(f"AC account_id = {account_id}, name = {name}, password = {password_1}")
            elif email == "":
                db.session.add(Account(
                    account_id = account_id, name = name, password = password_1, 
                    phone = phone))
                logger.info(f"AC account_id = {account_id}, name = {name}, password = {password_1}, phone = {phone}")
            elif phone == "":
                db.session.add(Account(
                    account_id = account_id, name = name, password = password_1, 
                    email = email))
                logger.info(f"AC account_id = {account_id}, name = {name}, password = {password_1}, email = {email}")
            else:
                db.session.add(Account(
                    account_id = account_id, name = name, password = password_1, 
                    phone = phone, email = email))
                logger.info(f"AC account_id = {account_id}, name = {name}, password = {password_1}, phone = {phone}, email = {email}")
            db.session.commit()
            logger.info(f"Database Commit")
            fl.flash(f"Nova conta {account_id} criada para {name}", category = "s")
            return fl.redirect("/")

    return fl.render_template("/signup.html", user = fo.current_user)

