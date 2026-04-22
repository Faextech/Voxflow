"""
RuleEngine — evaluates PipelineTransitionRules against deals and triggers
pipeline transfers when conditions are met.

Trigger types
-------------
no_answer_limit       config: {max_attempts: int}
stage_time_exceeded   config: {max_hours: int}
deal_idle             config: {idle_hours: int}
lead_status_changed   config: {to_status: str}
"""
import logging
from datetime import datetime, timedelta

from app.extensions import db
from app.models.deal import Deal
from app.models.pipeline_transition_rule import PipelineTransitionRule

logger = logging.getLogger(__name__)


class RuleEngine:
    """
    Evaluate and apply PipelineTransitionRules for a single company.

    Usage — event-driven (called when a deal changes)::

        RuleEngine(company_id=cid).evaluate_for_deal(deal)

    Usage — periodic sweep (called from a scheduler/cron)::

        RuleEngine(company_id=cid).run_periodic_check()
    """

    def __init__(self, company_id: int):
        self.company_id = company_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_for_deal(self, deal: Deal):
        """
        Check all active rules whose source pipeline matches *deal* and fire
        the first matching rule (sorted by priority desc).

        Parameters
        ----------
        deal : Deal ORM instance
        """
        if deal.status != 'open':
            return

        rules = (
            PipelineTransitionRule.query
            .filter_by(
                company_id=self.company_id,
                source_pipeline_id=deal.pipeline_id,
                is_active=True,
            )
            .order_by(PipelineTransitionRule.priority.desc())
            .all()
        )

        for rule in rules:
            try:
                if self._matches(deal, rule):
                    logger.info(
                        'RuleEngine.evaluate_for_deal: rule_id=%s matched deal_id=%s — transferring',
                        rule.id, deal.id,
                    )
                    self._apply_rule(deal, rule)
                    break  # stop after first match
            except Exception:
                logger.exception(
                    'RuleEngine.evaluate_for_deal: error evaluating rule_id=%s deal_id=%s',
                    rule.id, deal.id,
                )

    def run_periodic_check(self):
        """
        Iterate all open deals for this company and evaluate rules.
        Intended for use from a scheduler (e.g. Celery beat, APScheduler).
        """
        open_deals = (
            Deal.query
            .filter_by(company_id=self.company_id, status='open')
            .all()
        )

        logger.info(
            'RuleEngine.run_periodic_check: company_id=%s checking %d open deals',
            self.company_id, len(open_deals),
        )

        for deal in open_deals:
            self.evaluate_for_deal(deal)

    # ------------------------------------------------------------------
    # Private — matching
    # ------------------------------------------------------------------

    def _matches(self, deal: Deal, rule: PipelineTransitionRule) -> bool:
        """Return True when *deal* satisfies *rule*'s trigger conditions."""
        trigger = rule.trigger
        config  = rule.trigger_config or {}

        if trigger == 'no_answer_limit':
            return self._check_no_answer_limit(deal, config)

        if trigger == 'stage_time_exceeded':
            return self._check_stage_time_exceeded(deal, config)

        if trigger == 'deal_idle':
            return self._check_deal_idle(deal, config)

        if trigger == 'lead_status_changed':
            return self._check_lead_status_changed(deal, config)

        logger.warning(
            'RuleEngine._matches: unknown trigger %r for rule_id=%s', trigger, rule.id
        )
        return False

    def _check_no_answer_limit(self, deal: Deal, config: dict) -> bool:
        """True when the lead's dial_attempts >= max_attempts."""
        max_attempts = int(config.get('max_attempts', 3))
        lead = deal.lead
        dial_attempts = getattr(lead, 'dial_attempts', 0) or 0
        return dial_attempts >= max_attempts

    def _check_stage_time_exceeded(self, deal: Deal, config: dict) -> bool:
        """True when the deal has been in the current stage longer than max_hours."""
        max_hours = int(config.get('max_hours', 48))
        if deal.stage_entered_at is None:
            return False
        threshold = deal.stage_entered_at + timedelta(hours=max_hours)
        return datetime.utcnow() >= threshold

    def _check_deal_idle(self, deal: Deal, config: dict) -> bool:
        """True when there has been no activity on the deal for idle_hours."""
        idle_hours = int(config.get('idle_hours', 72))
        ref_time = deal.last_activity_at or deal.created_at
        if ref_time is None:
            return False
        threshold = ref_time + timedelta(hours=idle_hours)
        return datetime.utcnow() >= threshold

    def _check_lead_status_changed(self, deal: Deal, config: dict) -> bool:
        """True when the lead's current status equals to_status."""
        to_status = config.get('to_status')
        if not to_status:
            return False
        lead = deal.lead
        return getattr(lead, 'status', None) == to_status

    # ------------------------------------------------------------------
    # Private — applying a matched rule
    # ------------------------------------------------------------------

    def _apply_rule(self, deal: Deal, rule: PipelineTransitionRule):
        """
        Transfer *deal* to the rule's target pipeline/stage.
        Import PipelineTransferService at call time to avoid circular imports.
        """
        from app.services.pipeline_transfer_service import PipelineTransferService
        from app.models.pipeline import Pipeline, PipelineStage

        target_pipeline = Pipeline.query.filter_by(
            id=rule.target_pipeline_id,
            company_id=self.company_id,
        ).first()

        target_stage = PipelineStage.query.filter_by(
            id=rule.target_stage_id,
            company_id=self.company_id,
        ).first()

        if target_pipeline is None or target_stage is None:
            logger.error(
                'RuleEngine._apply_rule: rule_id=%s — target pipeline or stage not found '
                '(pipeline_id=%s stage_id=%s)',
                rule.id, rule.target_pipeline_id, rule.target_stage_id,
            )
            return

        PipelineTransferService.transfer(
            deal=deal,
            target_pipeline=target_pipeline,
            target_stage=target_stage,
            reason=f'Automatic transfer via rule: {rule.name}',
        )
