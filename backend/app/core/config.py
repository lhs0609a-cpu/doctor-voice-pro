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
    # SQL 전문 로깅. 종전엔 DEBUG 에 묶여 있어 운영에서 모든 쿼리가 파라미터까지
    # 찍혔다 — 사진 base64 가 오가는 요청에서는 로그가 폭주해 정작 필요한 줄이 묻힌다.
    # 문제 추적이 필요할 때만 SQL_ECHO=true 로 켠다.
    SQL_ECHO: bool = False

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

    # Naver Search Ad API (keywordstool - 실검색량/경쟁도)
    # 네이버 검색광고 > 도구 > API 사용관리에서 발급
    NAVER_AD_CUSTOMER_ID: str = ""
    NAVER_AD_API_KEY: str = ""
    NAVER_AD_SECRET_KEY: str = ""
    NAVER_AD_BASE_URL: str = "https://api.searchad.naver.com"

    # 토스페이먼츠
    TOSS_CLIENT_KEY: str = ""  # 프론트엔드용
    TOSS_SECRET_KEY: str = ""  # 서버용

    # Google Sheets (마케팅팀 '사용 키워드' 시트 연동)
    # 읽기만 할 때는 시트를 '링크가 있는 모든 사용자'에게 공개하면 자격증명이 필요 없다.
    # 행 추가(쓰기)나 비공개 시트 읽기에는 서비스 계정 키(JSON)가 필요하다.
    # 둘 중 하나만 설정하면 되고, 둘 다 있으면 JSON 문자열을 우선한다.
    # 서비스 계정 이메일(client_email)을 시트에 '편집자'로 공유해야 한다.
    GOOGLE_SERVICE_ACCOUNT_JSON: str = ""  # 서비스 계정 키 JSON 원문
    GOOGLE_SERVICE_ACCOUNT_FILE: str = ""  # 서비스 계정 키 JSON 파일 경로

    # 캠페인(대량 발행) 모듈 — 원고 생성/변형/사진 태깅에 쓰는 Claude 모델
    CAMPAIGN_MODEL: str = "claude-opus-5"
    CAMPAIGN_VISION_MODEL: str = ""          # 비우면 CAMPAIGN_MODEL 사용
    # 워커를 앱 프로세스 안에서 같이 돌릴지(개발/단일 서버). 별도 프로세스면 false 로 두고 `python -m app.worker`
    RUN_WORKER_IN_APP: bool = True
    # 캠페인 발행 에이전트/확장이 잡을 잠그는 시간(분). 지나면 다시 대기로 돌아간다.
    PUBLISH_LOCK_MINUTES: int = 20
    # 블로그 계정 비밀번호 암호화 키(Fernet). 비우면 SECRET_KEY 에서 파생한다.
    CAMPAIGN_ENCRYPTION_KEY: str = ""
    # 유니크화된 사진 변형 등 파일 보관 디렉터리(DB BLOB 대신). 상대경로는 backend 기준.
    MEDIA_DIR: str = "./media"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]


settings = Settings()
