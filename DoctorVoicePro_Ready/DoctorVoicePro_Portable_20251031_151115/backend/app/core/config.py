from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings"""

    # Application
    APP_NAME: str = "DoctorVoice Pro"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    SECRET_KEY: str

    # Database
    DATABASE_URL: str
    DATABASE_URL_SYNC: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # AI APIs
    ANTHROPIC_API_KEY: str
    OPENAI_API_KEY: str = ""

    # AWS S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-northeast-2"
    S3_BUCKET_NAME: str = "doctorvoice-files"

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:5001"

    # Email
    SENDGRID_API_KEY: str = ""
    FROM_EMAIL: str = "noreply@doctorvoice.com"

    # Naver Blog API
    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""

    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
