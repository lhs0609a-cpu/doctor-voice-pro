from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import List


class Settings(BaseSettings):
    """Application settings"""
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )

    # Application
    APP_NAME: str = "DoctorVoice Pro"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    SECRET_KEY: str = "change-this-in-production"

    # Database
    DATABASE_URL: str = "sqlite:///./doctorvoice.db"
    DATABASE_URL_SYNC: str = "sqlite:///./doctorvoice.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # AI APIs
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # AWS S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-northeast-2"
    S3_BUCKET_NAME: str = "doctorvoice-files"

    # JWT
    JWT_SECRET_KEY: str = "change-this-jwt-secret"
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

    # 토스페이먼츠
    TOSS_CLIENT_KEY: str = ""  # 프론트엔드용
    TOSS_SECRET_KEY: str = ""  # 서버용

    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]


settings = Settings()
