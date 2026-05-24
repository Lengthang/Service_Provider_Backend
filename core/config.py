from dotenv import load_dotenv
from decimal import Decimal
import os

load_dotenv()


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


class Settings:
    DATABASE_URL: str = _required("DATABASE_URL")
    SECRET_KEY: str = _required("SECRET_KEY")
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_VERIFY_SERVICE_SID: str = os.getenv("TWILIO_VERIFY_SERVICE_SID", "")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    # ENV: str = os.getenv("ENV", "production")
    ENV = "development"
    ESCROW_AUTO_RELEASE_HOURS: int = 24
    CURRENCY: str = os.getenv("CURRENCY", "USD")
    # Fraction (0-1) of each escrow release taken by the platform; the provider
    # receives the remainder. Override per environment via PLATFORM_COMMISSION_RATE.
    PLATFORM_COMMISSION_RATE: Decimal = Decimal(os.getenv("PLATFORM_COMMISSION_RATE", "0.15"))
    # User whose wallet collects the commission. Required when the rate is > 0.
    PLATFORM_USER_ID: str = os.getenv("PLATFORM_USER_ID", "")
settings = Settings()

if not (Decimal("0") <= settings.PLATFORM_COMMISSION_RATE <= Decimal("1")):
    raise RuntimeError("PLATFORM_COMMISSION_RATE must be between 0 and 1")