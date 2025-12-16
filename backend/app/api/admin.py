"""
Admin API Router
관리자 전용 API
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel
import anthropic
from openai import OpenAI

# Gemini SDK
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None

from app.db.database import get_db
from app.schemas.user import UserResponse
from app.schemas.admin import UserApprovalRequest, UserSubscriptionRequest
from app.api.deps import get_current_user
from app.models import User, APIKey

router = APIRouter()


# API 키 관련 스키마
class APIKeyRequest(BaseModel):
    provider: str  # claude, gpt, gemini
    api_key: str
    name: Optional[str] = None


class APIKeyResponse(BaseModel):
    id: str
    provider: str
    name: Optional[str]
    is_active: bool
    last_checked_at: Optional[datetime]
    last_status: str
    last_error: Optional[str]
    created_at: datetime
    updated_at: datetime
    api_key_preview: str  # 앞 10자만 표시


class APIKeyTestResponse(BaseModel):
    provider: str
    connected: bool
    message: str
    model: Optional[str] = None


async def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """현재 사용자가 관리자인지 확인"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다"
        )
    return current_user


@router.get("/users", response_model=List[UserResponse])
async def get_users(
    is_approved: Optional[bool] = Query(None, description="승인 상태 필터"),
    is_active: Optional[bool] = Query(None, description="활성화 상태 필터"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user)
):
    """
    사용자 목록 조회 (관리자 전용)

    - **is_approved**: 승인 상태로 필터링 (선택)
    - **is_active**: 활성화 상태로 필터링 (선택)
    - **skip**: 건너뛸 개수
    - **limit**: 조회할 최대 개수
    """
    query = select(User)

    if is_approved is not None:
        query = query.where(User.is_approved == is_approved)

    if is_active is not None:
        query = query.where(User.is_active == is_active)

    query = query.offset(skip).limit(limit).order_by(User.created_at.desc())

    result = await db.execute(query)
    users = result.scalars().all()

    return users


@router.post("/users/approve", response_model=UserResponse)
async def approve_user(
    request: UserApprovalRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user)
):
    """
    사용자 승인/거부 (관리자 전용)

    - **user_id**: 승인할 사용자 ID
    - **is_approved**: 승인 여부 (true: 승인, false: 거부)
    """
    # 사용자 조회
    result = await db.execute(select(User).where(User.id == UUID(request.user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다"
        )

    # 승인 상태 업데이트
    user.is_approved = request.is_approved
    user.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(user)

    return user


@router.post("/users/subscription", response_model=UserResponse)
async def set_user_subscription(
    request: UserSubscriptionRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user)
):
    """
    사용자 구독 기간 설정 (관리자 전용)

    - **user_id**: 사용자 ID
    - **subscription_start_date**: 구독 시작일 (선택)
    - **subscription_end_date**: 구독 종료일 (선택)
    """
    # 사용자 조회
    result = await db.execute(select(User).where(User.id == UUID(request.user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다"
        )

    # 구독 기간 업데이트
    if request.subscription_start_date:
        user.subscription_start_date = request.subscription_start_date

    if request.subscription_end_date:
        user.subscription_end_date = request.subscription_end_date

    user.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(user)

    return user


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_detail(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user)
):
    """
    특정 사용자 상세 정보 조회 (관리자 전용)
    """
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다"
        )

    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user)
):
    """
    사용자 삭제 (관리자 전용)
    """
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다"
        )

    # 관리자는 삭제할 수 없음
    if user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 계정은 삭제할 수 없습니다"
        )

    await db.delete(user)
    await db.commit()

    return None


# ===== API 키 관리 엔드포인트 =====

@router.get("/api-keys", response_model=List[APIKeyResponse])
async def get_api_keys(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user)
):
    """
    저장된 API 키 목록 조회 (관리자 전용)
    """
    result = await db.execute(select(APIKey).order_by(APIKey.provider))
    keys = result.scalars().all()

    return [
        APIKeyResponse(
            id=str(key.id),
            provider=key.provider,
            name=key.name,
            is_active=key.is_active,
            last_checked_at=key.last_checked_at,
            last_status=key.last_status,
            last_error=key.last_error,
            created_at=key.created_at,
            updated_at=key.updated_at,
            api_key_preview=key.api_key[:15] + "..." if len(key.api_key) > 15 else "***"
        )
        for key in keys
    ]


@router.post("/api-keys", response_model=APIKeyResponse)
async def save_api_key(
    request: APIKeyRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user)
):
    """
    API 키 저장/업데이트 (관리자 전용)
    - provider가 이미 존재하면 업데이트
    - 없으면 새로 생성
    """
    if request.provider not in ["claude", "gpt", "gemini"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="지원하지 않는 provider입니다. (claude, gpt, gemini 중 선택)"
        )

    # 기존 키 확인
    result = await db.execute(
        select(APIKey).where(APIKey.provider == request.provider)
    )
    existing_key = result.scalar_one_or_none()

    if existing_key:
        # 기존 키 업데이트
        existing_key.api_key = request.api_key
        existing_key.name = request.name
        existing_key.updated_at = datetime.utcnow()
        existing_key.last_status = "unknown"
        existing_key.last_error = None
        await db.commit()
        await db.refresh(existing_key)
        key = existing_key
    else:
        # 새로운 키 생성
        import uuid
        key = APIKey(
            id=uuid.uuid4(),
            provider=request.provider,
            api_key=request.api_key,
            name=request.name,
            is_active=True,
            last_status="unknown",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(key)
        await db.commit()
        await db.refresh(key)

    return APIKeyResponse(
        id=str(key.id),
        provider=key.provider,
        name=key.name,
        is_active=key.is_active,
        last_checked_at=key.last_checked_at,
        last_status=key.last_status,
        last_error=key.last_error,
        created_at=key.created_at,
        updated_at=key.updated_at,
        api_key_preview=key.api_key[:15] + "..." if len(key.api_key) > 15 else "***"
    )


@router.delete("/api-keys/{provider}")
async def delete_api_key(
    provider: str,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user)
):
    """
    API 키 삭제 (관리자 전용)
    """
    result = await db.execute(
        select(APIKey).where(APIKey.provider == provider)
    )
    key = result.scalar_one_or_none()

    if not key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{provider} API 키가 존재하지 않습니다"
        )

    await db.delete(key)
    await db.commit()

    return {"message": f"{provider} API 키가 삭제되었습니다"}


@router.post("/api-keys/{provider}/test", response_model=APIKeyTestResponse)
async def test_api_key(
    provider: str,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user)
):
    """
    API 키 연결 테스트 (관리자 전용)
    """
    # DB에서 API 키 조회
    result = await db.execute(
        select(APIKey).where(APIKey.provider == provider)
    )
    key_record = result.scalar_one_or_none()

    if not key_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{provider} API 키가 저장되어 있지 않습니다"
        )

    api_key = key_record.api_key
    connected = False
    message = ""
    model = None

    try:
        if provider == "claude":
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )
            connected = True
            message = "Claude API 연결 성공"
            model = "claude-sonnet-4-5-20250929"

        elif provider == "gpt":
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )
            connected = True
            message = "GPT API 연결 성공"
            model = "gpt-4o-mini"

        elif provider == "gemini":
            if not GEMINI_AVAILABLE:
                message = "Gemini SDK가 설치되어 있지 않습니다"
            else:
                genai.configure(api_key=api_key)
                # 안정적인 gemini-2.0-flash 모델 사용
                gemini_model = genai.GenerativeModel('gemini-2.0-flash')
                response = gemini_model.generate_content(
                    "test",
                    generation_config=genai.GenerationConfig(max_output_tokens=10)
                )
                connected = True
                message = "Gemini API 연결 성공"
                model = "gemini-2.0-flash"
        else:
            message = f"지원하지 않는 provider: {provider}"

    except Exception as e:
        message = f"연결 실패: {str(e)}"

    # DB에 테스트 결과 저장
    key_record.last_checked_at = datetime.utcnow()
    key_record.last_status = "connected" if connected else "failed"
    key_record.last_error = None if connected else message
    await db.commit()

    return APIKeyTestResponse(
        provider=provider,
        connected=connected,
        message=message,
        model=model
    )


@router.get("/api-keys/status")
async def get_all_api_keys_status(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user)
):
    """
    모든 API 키의 연결 상태 조회 (관리자 전용)
    """
    providers = ["claude", "gpt", "gemini"]
    statuses = {}

    for provider in providers:
        result = await db.execute(
            select(APIKey).where(APIKey.provider == provider)
        )
        key = result.scalar_one_or_none()

        if key:
            statuses[provider] = {
                "configured": True,
                "is_active": key.is_active,
                "last_status": key.last_status,
                "last_checked_at": key.last_checked_at.isoformat() if key.last_checked_at else None,
                "last_error": key.last_error,
                "api_key_preview": key.api_key[:15] + "..." if len(key.api_key) > 15 else "***"
            }
        else:
            statuses[provider] = {
                "configured": False,
                "is_active": False,
                "last_status": "not_configured",
                "last_checked_at": None,
                "last_error": None,
                "api_key_preview": None
            }

    return statuses
