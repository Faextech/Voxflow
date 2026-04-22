"""
AutomationEngine — executes StageAutomation rules when a deal enters a stage.

Supported automation types
--------------------------
send_whatsapp   config: {message: str}
notify_agent    config: {agent_id: int | None, message: str}
create_task     config: {type: str, title: str, description: str, due_hours: int}
update_deal     config: {field: str, value: any}
"""
import logging
from datetime import datetime, timedelta

from app.extensions import db
from app.models.deal import Deal
from app.models.deal_activity import DealActivity
from app.models.deal_task import DealTask
from app.models.notification import Notification
from app.models.stage_automation import StageAutomation, AutomationLog

logger = logging.getLogger(__name__)


class AutomationEngine:
    """
    Run all active automations attached to *stage* for *deal*.

    Usage::

        engine = AutomationEngine(deal=deal, stage=new_stage)
        engine.run()
    """

    def __init__(self, deal: Deal, stage):
        self.deal = deal
        self.stage = stage

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self):
        """Iterate automations ordered by position and execute each one."""
        automations = (
            StageAutomation.query
            .filter_by(stage_id=self.stage.id, company_id=self.deal.company_id, is_active=True)
            .order_by(StageAutomation.position.asc())
            .all()
        )

        logger.debug(
            'AutomationEngine.run: deal_id=%s stage_id=%s found %d automations',
            self.deal.id, self.stage.id, len(automations),
        )

        for automation in automations:
            self._execute(automation)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _execute(self, automation: StageAutomation):
        """Dispatch to the appropriate handler; log result."""
        handler_map = {
            'send_whatsapp': self._handle_send_whatsapp,
            'notify_agent':  self._handle_notify_agent,
            'create_task':   self._handle_create_task,
            'update_deal':   self._handle_update_deal,
        }

        handler = handler_map.get(automation.type)
        if handler is None:
            logger.warning(
                'AutomationEngine: unknown automation type %r — skipping', automation.type
            )
            self._log(automation, status='skipped', error_message=f'Unknown type: {automation.type}')
            return

        try:
            handler(automation)
            self._log(automation, status='success')
        except Exception as exc:
            logger.exception(
                'AutomationEngine: error in handler %r for automation_id=%s deal_id=%s',
                automation.type, automation.id, self.deal.id,
            )
            self._log(automation, status='failed', error_message=str(exc))

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _handle_send_whatsapp(self, automation: StageAutomation):
        """
        Create a DealActivity of type 'whatsapp' representing the outbound
        message.  Actual WhatsApp delivery is expected to be handled by a
        Celery task or webhook consumer that watches for activities of this type.
        """
        config  = automation.config or {}
        message = self._interpolate(config.get('message', ''))

        activity = DealActivity(
            company_id=self.deal.company_id,
            deal_id=self.deal.id,
            agent_id=None,
            type='whatsapp',
            title='Automated WhatsApp message',
            body=message,
            metadata_={
                'automation_id': automation.id,
                'source': 'automation',
            },
            created_at=datetime.utcnow(),
        )
        db.session.add(activity)

        self.deal.last_activity_at = datetime.utcnow()
        db.session.add(self.deal)

        logger.info(
            'send_whatsapp: queued whatsapp activity for deal_id=%s', self.deal.id
        )

    def _handle_notify_agent(self, automation: StageAutomation):
        """Create an in-app Notification for the specified agent (or deal owner)."""
        config   = automation.config or {}
        agent_id = config.get('agent_id') or self.deal.agent_id
        message  = self._interpolate(config.get('message', 'You have a new CRM notification.'))

        if agent_id is None:
            logger.debug(
                'notify_agent: no agent_id for deal_id=%s — skipping', self.deal.id
            )
            return

        notification = Notification(
            company_id=self.deal.company_id,
            agent_id=agent_id,
            deal_id=self.deal.id,
            type='stage_entry',
            message=message,
            is_read=False,
            created_at=datetime.utcnow(),
        )
        db.session.add(notification)

        logger.info(
            'notify_agent: created notification for agent_id=%s deal_id=%s',
            agent_id, self.deal.id,
        )

    def _handle_create_task(self, automation: StageAutomation):
        """Create a DealTask for the deal."""
        config      = automation.config or {}
        task_type   = config.get('type', 'call')
        title       = self._interpolate(config.get('title', 'Follow up'))
        description = self._interpolate(config.get('description', ''))
        due_hours   = int(config.get('due_hours', 24))

        due_at = datetime.utcnow() + timedelta(hours=due_hours)

        task = DealTask(
            company_id=self.deal.company_id,
            deal_id=self.deal.id,
            assigned_to=self.deal.agent_id,
            type=task_type,
            title=title,
            description=description or None,
            status='pending',
            due_at=due_at,
            created_at=datetime.utcnow(),
        )
        db.session.add(task)

        logger.info(
            'create_task: created %r task for deal_id=%s due=%s',
            task_type, self.deal.id, due_at.isoformat(),
        )

    def _handle_update_deal(self, automation: StageAutomation):
        """Update an allowed field on the deal."""
        config = automation.config or {}
        field  = config.get('field')
        value  = config.get('value')

        allowed_fields = {'probability', 'agent_id', 'currency', 'lost_reason', 'expected_close_date'}

        if field not in allowed_fields:
            raise ValueError(f'update_deal: field {field!r} is not in allowed list')

        setattr(self.deal, field, value)
        self.deal.updated_at = datetime.utcnow()
        db.session.add(self.deal)

        logger.info(
            'update_deal: set deal_id=%s %s=%r', self.deal.id, field, value
        )

    # ------------------------------------------------------------------
    # Interpolation
    # ------------------------------------------------------------------

    def _interpolate(self, template: str) -> str:
        """
        Replace {{variable}} placeholders in *template* with deal/lead data.

        Supported variables
        -------------------
        {{lead_name}}        lead.name
        {{lead_phone}}       lead.numero_1
        {{lead_email}}       lead.email
        {{deal_title}}       deal.title
        {{deal_value}}       deal.value
        {{deal_stage}}       deal.stage.name (if loaded)
        {{deal_pipeline}}    deal.pipeline.name (if loaded)
        {{agent_name}}       deal.agent.name (if loaded)
        """
        if not template:
            return template

        lead  = self.deal.lead
        stage = self.deal.stage
        agent = self.deal.agent
        pipeline = self.deal.pipeline

        replacements = {
            '{{lead_name}}':     getattr(lead, 'name', '') or '',
            '{{lead_phone}}':    getattr(lead, 'numero_1', '') or '',
            '{{lead_email}}':    getattr(lead, 'email', '') or '',
            '{{deal_title}}':    self.deal.title or '',
            '{{deal_value}}':    str(self.deal.value) if self.deal.value is not None else '',
            '{{deal_stage}}':    stage.name if stage else '',
            '{{deal_pipeline}}': pipeline.name if pipeline else '',
            '{{agent_name}}':    getattr(agent, 'name', '') if agent else '',
        }

        result = template
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, value)

        return result

    # ------------------------------------------------------------------
    # Logging helper
    # ------------------------------------------------------------------

    def _log(self, automation: StageAutomation, status: str, error_message: str = None):
        log_entry = AutomationLog(
            company_id=self.deal.company_id,
            automation_id=automation.id,
            deal_id=self.deal.id,
            lead_id=self.deal.lead_id,
            type=automation.type,
            status=status,
            error_message=error_message,
            executed_at=datetime.utcnow(),
            payload={
                'stage_id':  self.stage.id,
                'config':    automation.config,
            },
        )
        db.session.add(log_entry)
