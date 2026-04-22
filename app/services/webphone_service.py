import os
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant


class WebphoneService:
    @staticmethod
    def generate_token(identity: str) -> str:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        api_key = os.getenv("TWILIO_API_KEY")
        api_secret = os.getenv("TWILIO_API_SECRET")
        twiml_app_sid = os.getenv("TWILIO_TWIML_APP_SID")

        if not account_sid:
            raise ValueError("TWILIO_ACCOUNT_SID não configurado")
        if not api_key:
            raise ValueError("TWILIO_API_KEY não configurado")
        if not api_secret:
            raise ValueError("TWILIO_API_SECRET não configurado")
        if not twiml_app_sid:
            raise ValueError("TWILIO_TWIML_APP_SID não configurado")

        token = AccessToken(
            account_sid,
            api_key,
            api_secret,
            identity=identity,
            ttl=86400,  # 24 horas — evita expiração durante sessões longas
        )

        voice_grant = VoiceGrant(
            outgoing_application_sid=twiml_app_sid,
            incoming_allow=True
        )

        token.add_grant(voice_grant)

        jwt_token = token.to_jwt()

        if isinstance(jwt_token, bytes):
            return jwt_token.decode("utf-8")

        return jwt_token