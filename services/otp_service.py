from twilio.rest import Client
from core.config import settings

client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

def send_otp(phone: str) -> bool:
    try:
        client.verify.v2.services(
            settings.TWILIO_VERIFY_SERVICE_SID
        ).verifications.create(to=phone, channel="sms")
        return True
    except Exception as e:
        print(f"Error sending OTP: {e}")
        return False

def verify_otp(phone: str, code: str) -> bool:
    try:
        result = client.verify.v2.services(
            settings.TWILIO_VERIFY_SERVICE_SID
        ).verification_checks.create(to=phone, code=code)
        return result.status == "approved"
    except Exception as e:
        print(f"Error verifying OTP: {e}")
        return False