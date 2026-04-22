from app.extensions import db
from app.models import Lead, Call
from app.services.twilio_service import TwilioService, normalize_phone_br


class DialerService:
    def __init__(self):
        self.twilio = TwilioService.from_env()

    def get_next_pending_lead(self, company_id=None, campaign_id=None):
        query = Lead.query.filter_by(status='new')

        if company_id:
            query = query.filter_by(company_id=company_id)

        if campaign_id:
            query = query.filter_by(campaign_id=campaign_id)

        return query.order_by(Lead.created_at.asc()).first()

    def start_call_for_lead(self, lead, host_url):
        if not lead:
            raise ValueError('Lead inválido para discagem.')

        phone_to_call = normalize_phone_br(lead.get_primary_phone() or "")

        if not phone_to_call:
            raise ValueError('Lead sem número principal para discagem.')

        status_callback_url = host_url.rstrip('/') + '/api/twilio/status'

        call_sid = self.twilio.make_call(
            to_number=phone_to_call,
            status_callback_url=status_callback_url
        )

        call = Call(
            company_id=lead.company_id,
            campaign_id=lead.campaign_id,
            lead_id=lead.id,
            phone_dialed=phone_to_call,
            call_sid=call_sid,
            status='queued',
            direction='outbound'
        )

        lead.status = 'dialing'

        db.session.add(call)
        db.session.commit()

        return call

    def dial_next(self, host_url, company_id=None, campaign_id=None):
        lead = self.get_next_pending_lead(
            company_id=company_id,
            campaign_id=campaign_id
        )

        if not lead:
            return None

        return self.start_call_for_lead(lead, host_url)