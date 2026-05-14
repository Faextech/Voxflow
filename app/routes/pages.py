import os
from flask import Blueprint, send_from_directory

pages_bp = Blueprint("pages", __name__)

_REACT_DIST = os.path.join(os.path.dirname(__file__), '..', 'static', 'react')


def _serve_react():
    """Serve o SPA React — qualquer rota não-API cai aqui."""
    from flask import make_response
    index = os.path.join(_REACT_DIST, 'index.html')
    if os.path.exists(index):
        response = make_response(send_from_directory(_REACT_DIST, 'index.html'))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    return (
        "<h2>React build não encontrado.</h2>"
        "<p>Execute: <code>cd frontend-react && npm run build</code></p>",
        404,
    )


@pages_bp.route("/assets/<path:filename>")
def react_assets(filename: str):
    """Serve os assets do build React (JS, CSS com hash)."""
    assets_dir = os.path.join(_REACT_DIST, 'assets')
    return send_from_directory(assets_dir, filename)


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

@pages_bp.route("/app/dashboard")
@pages_bp.route("/dashboard")
def dashboard_page():
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

# SPA catch-all movido para prefixo /v2 para evitar conflitos
@pages_bp.route("/v2", defaults={'path': ''})
@pages_bp.route("/v2/<path:path>")
def react_app(path):
    if path and os.path.isfile(os.path.join(_REACT_DIST, path)):
        return send_from_directory(_REACT_DIST, path)
    return _serve_react()