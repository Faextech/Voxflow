from flask import Blueprint, redirect, render_template, url_for

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def dashboard():
    return render_template("dashboard.html")


@pages_bp.route("/login-page")
def login_page():
    return render_template("login.html")


@pages_bp.route("/register-page")
def register_page():
    return render_template("register.html")


@pages_bp.route("/operacao")
def operacao():
    return redirect(url_for("pages.dashboard"))


@pages_bp.route("/crm")
def crm():
    return render_template("crm.html")


@pages_bp.route("/test-webphone")
def test_webphone_page():
    return render_template("test_webphone.html")


@pages_bp.route("/suporte")
def support_page():
    return render_template("support.html")


@pages_bp.route("/credito")
def billing_page():
    return render_template("billing.html")