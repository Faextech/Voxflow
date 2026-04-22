import logging
from datetime import datetime
from app.extensions import db
from app.models.deal import Deal
from app.models.pipeline import PipelineStage, Pipeline

logger = logging.getLogger(__name__)

def move_lead_to_stage(lead_id, stage_name):
    """
    Encontra o Deal mais recente de um Lead e o move para uma etapa específica pelo nome.
    Se a etapa não existir na pipeline do Deal, tenta encontrar em qualquer pipeline da empresa.
    """
    try:
        # 1. Busca o Deal mais recente do Lead
        deal = Deal.query.filter_by(lead_id=lead_id).order_by(Deal.created_at.desc()).first()
        if not deal:
            logger.warning(f"[CRM-UTILS] Nenhum Deal encontrado para o Lead {lead_id}")
            return False

        # 2. Busca a etapa alvo
        # Primeiro tenta na mesma pipeline do Deal
        target_stage = PipelineStage.query.filter_by(
            pipeline_id=deal.pipeline_id, 
            name=stage_name
        ).first()

        # Se não achou na mesma pipeline, busca em qualquer pipeline da mesma empresa
        if not target_stage:
            target_stage = PipelineStage.query.filter_by(
                company_id=deal.company_id, 
                name=stage_name
            ).first()

        if not target_stage:
            logger.warning(f"[CRM-UTILS] Etapa '{stage_name}' não encontrada para a empresa {deal.company_id}")
            return False

        # 3. Atualiza o Deal
        if deal.stage_id != target_stage.id:
            logger.info(f"[CRM-UTILS] Movendo Deal {deal.id} para a etapa '{stage_name}' (ID: {target_stage.id})")
            deal.stage_id = target_stage.id
            deal.updated_at = datetime.utcnow()
            deal.last_activity_at = datetime.utcnow()
            db.session.commit()
            return True
        
        return True

    except Exception as e:
        logger.error(f"[CRM-UTILS] Erro ao mover Lead {lead_id} para etapa '{stage_name}': {e}")
        db.session.rollback()
        return False
