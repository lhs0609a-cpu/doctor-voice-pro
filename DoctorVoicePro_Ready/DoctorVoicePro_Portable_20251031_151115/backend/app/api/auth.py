"""
Authentication API Router
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.user import UserCreate, UserLogin, TokenResponse, UserResponse
from app.services.auth_service import auth_service
from app.api.deps import get_current_user
from app.models import User

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    회원가입

    - **email**: 이메일 (필수)
    - **password**: 비밀번호 (최소 8자, 필수)
    - **name**: 이름 (선택)
    - **hospital_name**: 병원명 (선택)
    - **specialty**: 진료 과목 (선택)

    회원가입 후 관리자 승인 대기 상태가 됩니다.
    승인 후 로그인이 가능합니다.
    """
    try:
        # 사용자 등록
        user = await auth_service.register(db, user_data)

        return UserResponse.model_validate(user)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    로그인

    - **email**: 이메일
    - **password**: 비밀번호
    """
    try:
        result = await auth_service.login(db, login_data.email, login_data.password)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="이메일 또는 비밀번호가 올바르지 않습니다",
            )

        return TokenResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    현재 로그인한 사용자 정보 조회
    """
    return current_user
