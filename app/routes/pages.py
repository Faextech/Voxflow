from flask import Blueprint

pages_bp = Blueprint("pages", __name__)

@pages_bp.route("/")
def landing_page():
    from flask import render_template
    return render_template("landing.html")

@pages_bp.route("/login")
def login_page():
    from flask import render_template
    return render_template("login.html")

@pages_bp.route("/register")
def register_page():
    from flask import render_template
    return render_template("register.html")

@pages_bp.route("/dashboard")
@pages_bp.route("/app")
def dashboard_page():
    """Redireciona /app para o dashboard legado para evitar confusão."""
    from flask import render_template
    return render_template("dashboard.html")

@pages_bp.route("/admin")
def admin_page():
    from flask import render_template
    return render_template("admin.html")

@pages_bp.route("/billing")
def billing_page():
    from flask import render_template
    return render_template("billing.html")

@pages_bp.route("/support")
def support_page():
    from flask import render_template
    return render_template("support.html")

@pages_bp.route("/crm")
@pages_bp.route("/legacy/crm")
def legacy_crm():
    from flask import render_template
    return render_template("crm.html")