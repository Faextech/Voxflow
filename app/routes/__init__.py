from app.routes.auth import auth_bp
from app.routes.leads import leads_bp
from app.routes.calls import calls_bp
from app.routes.twilio import twilio_bp
from app.routes.pages import pages_bp

from app.api.routes.operator_routes import operator_bp
from app.api.routes.call_routes import call_bp
from app.api.routes.dev_routes import dev_bp
from app.api.routes.webphone_routes import webphone_bp
from app.api.routes.test_call import test_call_bp
from app.api.routes.twilio_voice import twilio_voice_bp
from app.api.routes.operator_workspace_routes import operator_workspace_bp
from app.api.routes.dialer import dialer_bp
from app.api.routes.lead_management import lead_management_bp
from app.api.routes.settings_routes import settings_bp
from app.api.routes.auto_dialer import auto_dialer_bp
from app.api.routes.crm_pipelines import crm_pipelines_bp
from app.api.routes.crm_automations import crm_automations_bp
from app.api.routes.crm_notifications import crm_notifications_bp
from app.api.routes.supervisor_routes import supervisor_bp
from app.api.routes.crm_init_routes import crm_init_bp
from app.api.routes.user_routes import user_routes_bp
from app.api.routes.analytics import analytics_bp
from app.api.routes.support_routes import support_bp
from app.api.routes.billing_routes import billing_bp
from app.api.routes.admin_routes import admin_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(leads_bp, url_prefix='/api')
    app.register_blueprint(calls_bp, url_prefix='/api')
    app.register_blueprint(twilio_bp)  # já tem prefixo dentro do arquivo
    app.register_blueprint(pages_bp)

    app.register_blueprint(operator_bp)
    app.register_blueprint(call_bp)
    app.register_blueprint(dev_bp)
    app.register_blueprint(webphone_bp)
    app.register_blueprint(test_call_bp)
    app.register_blueprint(twilio_voice_bp)
    app.register_blueprint(operator_workspace_bp)
    app.register_blueprint(dialer_bp)
    app.register_blueprint(lead_management_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(auto_dialer_bp)
    app.register_blueprint(crm_pipelines_bp)
    app.register_blueprint(crm_automations_bp)
    app.register_blueprint(crm_notifications_bp)
    app.register_blueprint(supervisor_bp)
    app.register_blueprint(crm_init_bp)
    app.register_blueprint(user_routes_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(support_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(admin_bp)
