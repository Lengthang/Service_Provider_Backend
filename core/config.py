from dotenv import load_dotenv
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
settings = Settings()