from flask import Blueprint, redirect, render_template, url_for

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    """Landing page pública — rota raiz do site."""
    return render_template("landing.html")


@pages_bp.route("/app")
def dashboard():
    """Dashboard principal (requer login via JS)."""
    return render_template("dashboard.html")


@pages_bp.route("/login")
def login_page():
    return render_template("login.html")


@pages_bp.route("/register")
def register_page():
    return render_template("register.html")


@pages_bp.route("/operacao")
def operacao():
    return redirect("/app")


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


@pages_bp.route("/admin")
def admin_panel():
    return render_template("admin.html")