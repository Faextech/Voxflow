"""
PipelineTransferService — moves a deal from one pipeline to another.

The original deal is marked 'transferred' and a new deal is created in the
target pipeline/stage.  DealActivity records are added to both deals so the
history remains intact.  AutomationEngine is fired for the new deal after the
database commit.
"""
import logging
from datetime import datetime

from app.extensions import db
from app.models.deal import Deal
from app.models.deal_activity import DealActivity

logger = logging.getLogger(__name__)


class PipelineTransferService:
    """
    Usage::

        result = PipelineTransferService.transfer(
            deal=deal,
            target_pipeline=pipeline,
            target_stage=stage,
            agent_id=agent_id,
            reason='Customer re-qualified',
        )
        # result is the new Deal instance
    """

    @staticmethod
    def transfer(deal: Deal, target_pipeline, target_stage, agent_id=None, reason: str = None):
        """
        Transfer *deal* to *target_pipeline* / *target_stage*.

        Parameters
        ----------
        deal            : Deal — the source deal (must be open)
        target_pipeline : Pipeline ORM instance
        target_stage    : PipelineStage ORM instance (must belong to target_pipeline)
        agent_id        : int | None — agent for the new deal (defaults to deal.agent_id)
        reason          : str | None — human-readable reason logged in activities

        Returns
        -------
        Deal — the newly created deal

        Raises
        ------
        ValueError if deal is not open or target_stage does not belong to target_pipeline
        """
        if deal.status != 'open':
            raise ValueError(
                f'Cannot transfer deal_id={deal.id}: status is {deal.status!r}, expected "open"'
            )

        if target_stage.pipeline_id != target_pipeline.id:
            raise ValueError(
                f'target_stage {target_stage.id} does not belong to pipeline {target_pipeline.id}'
            )

        now = datetime.utcnow()
        resolved_agent_id = agent_id or deal.agent_id

        # ------------------------------------------------------------------
        # 1. Mark source deal as transferred
        # ------------------------------------------------------------------
        deal.status     = 'transferred'
        deal.updated_at = now
        db.session.add(deal)

        # Activity on source deal
        source_activity = DealActivity(
            company_id=deal.company_id,
            deal_id=deal.id,
            agent_id=resolved_agent_id,
            type='pipeline_transfer',
            title=f'Transferred to pipeline: {target_pipeline.name}',
            body=reason or f'Deal transferred to "{target_pipeline.name}" / "{target_stage.name}".',
            metadata_={
                'target_pipeline_id': target_pipeline.id,
                'target_pipeline_name': target_pipeline.name,
                'target_stage_id': target_stage.id,
                'target_stage_name': target_stage.name,
                'reason': reason,
            },
            created_at=now,
        )
        db.session.add(source_activity)

        # ------------------------------------------------------------------
        # 2. Create new deal in target pipeline
        # ------------------------------------------------------------------
        new_deal = Deal(
            company_id=deal.company_id,
            pipeline_id=target_pipeline.id,
            stage_id=target_stage.id,
            lead_id=deal.lead_id,
            agent_id=resolved_agent_id,
            title=deal.title,
            value=deal.value,
            currency=deal.currency,
            probability=target_stage.default_probability,
            status='open',
            expected_close_date=deal.expected_close_date,
            stage_entered_at=now,
            last_activity_at=now,
            created_at=now,
            updated_at=now,
        )
        db.session.add(new_deal)
        db.session.flush()  # populate new_deal.id

        # Activity on new deal referencing origin
        target_activity = DealActivity(
            company_id=new_deal.company_id,
            deal_id=new_deal.id,
            agent_id=resolved_agent_id,
            type='pipeline_transfer',
            title=f'Received from pipeline: {deal.pipeline.name if deal.pipeline else deal.pipeline_id}',
            body=reason or (
                f'Deal transferred from '
                f'"{deal.pipeline.name if deal.pipeline else deal.pipeline_id}" '
                f'/ "{deal.stage.name if deal.stage else deal.stage_id}".'
            ),
            metadata_={
                'source_deal_id': deal.id,
                'source_pipeline_id': deal.pipeline_id,
                'source_stage_id': deal.stage_id,
                'reason': reason,
            },
            created_at=now,
        )
        db.session.add(target_activity)

        # ------------------------------------------------------------------
        # 3. Commit everything
        # ------------------------------------------------------------------
        try:
            db.session.commit()
            logger.info(
                'PipelineTransferService.transfer: deal_id=%s -> new_deal_id=%s '
                'pipeline=%s stage=%s',
                deal.id, new_deal.id, target_pipeline.id, target_stage.id,
            )
        except Exception:
            db.session.rollback()
            logger.exception(
                'PipelineTransferService.transfer: commit failed for deal_id=%s', deal.id
            )
            raise

        # ------------------------------------------------------------------
        # 4. Fire automations for the new deal's stage
        #    Import deferred to avoid circular imports at module load time.
        # ------------------------------------------------------------------
        try:
            from app.services.automation_engine import AutomationEngine
            engine = AutomationEngine(deal=new_deal, stage=target_stage)
            engine.run()
            db.session.commit()
        except Exception:
            logger.exception(
                'PipelineTransferService.transfer: automation error for new_deal_id=%s',
                new_deal.id,
            )
            # Non-fatal — transfer itself succeeded

        return new_deal
