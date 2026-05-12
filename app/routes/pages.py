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


@pages_bp.route("/legacy/crm")
def legacy_crm():
    from flask import render_template
    return render_template("crm.html")

@pages_bp.route("/legacy/dashboard")
def legacy_dashboard():
    from flask import render_template
    return render_template("dashboard.html")

# ── SPA catch-all: todas as rotas de página vão para o React ──────────────────

@pages_bp.route("/", defaults={'path': ''})
@pages_bp.route("/<path:path>")
def react_app(path):
    """
    SPA fallback — qualquer rota que não seja asset ou API vai para o React.
    Também tenta servir arquivos estáticos que estejam na raiz do build (ex: favicon.svg).
    """
    # Se o arquivo existe fisicamente na pasta do React, serve ele
    if path and os.path.isfile(os.path.join(_REACT_DIST, path)):
        return send_from_directory(_REACT_DIST, path)
    
    # Caso contrário, serve o index.html (SPA Fallback)
    return _serve_react()