"""
Authentication Service
사용자 인증 및 관리 서비스
"""

from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import User, DoctorProfile
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
)
from app.schemas.user import UserCreate


class AuthService:
    """
    사용자 인증 및 관리
    """

    async def register(self, db: AsyncSession, user_data: UserCreate) -> User:
        """
        새 사용자 등록

        Args:
            db: 데이터베이스 세션
            user_data: 사용자 등록 데이터

        Returns:
            생성된 User 객체

        Raises:
            ValueError: 이메일이 이미 존재하는 경우
        """
        # 이메일 중복 확인
        existing_user = await self.get_user_by_email(db, user_data.email)
        if existing_user:
            raise ValueError("이미 등록된 이메일입니다")

        # 비밀번호 해싱
        hashed_password = get_password_hash(user_data.password)

        # 사용자 생성
        user = User(
            email=user_data.email,
            hashed_password=hashed_password,
            name=user_data.name,
            hospital_name=user_data.hospital_name,
            specialty=user_data.specialty,
            subscription_tier="free",
            is_active=True,
            is_verified=False,
            is_approved=False,  # 기본적으로 승인 대기 상태
            is_admin=False,
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        # 기본 프로필 생성
        await self._create_default_profile(db, user.id)

        return user

    async def login(
        self, db: AsyncSession, email: str, password: str
    ) -> Optional[dict]:
        """
        사용자 로그인

        Args:
            db: 데이터베이스 세션
            email: 이메일
            password: 비밀번호

        Returns:
            토큰 정보 또는 None
        """
        # 사용자 조회
        user = await self.get_user_by_email(db, email)
        print(f"DEBUG: User found: {user is not None}")

        if not user:
            print("DEBUG: User not found")
            return None

        # 비밀번호 확인
        is_password_valid = verify_password(password, user.hashed_password)
        print(f"DEBUG: Password valid: {is_password_valid}")
        if not is_password_valid:
            print("DEBUG: Password invalid")
            return None

        # 활성화된 계정인지 확인
        print(f"DEBUG: is_active: {user.is_active}")
        if not user.is_active:
            print("DEBUG: Account not active")
            raise ValueError("비활성화된 계정입니다")

        # 관리자 승인 확인
        print(f"DEBUG: is_approved: {user.is_approved}, is_admin: {user.is_admin}")
        if not user.is_approved and not user.is_admin:
            print("DEBUG: Not approved and not admin")
            raise ValueError("관리자 승인 대기 중입니다. 승인 후 로그인이 가능합니다.")

        # 사용 기간 확인
        print(f"DEBUG: subscription_end_date: {user.subscription_end_date}")
        if user.subscription_end_date:
            from datetime import datetime
            if datetime.utcnow() > user.subscription_end_date:
                print("DEBUG: Subscription expired")
                raise ValueError("사용 기간이 만료되었습니다. 관리자에게 문의하세요.")

        # 토큰 생성
        print("DEBUG: Creating tokens")
        access_token = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))

        print("DEBUG: Login successful")
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user,
        }

    async def get_user_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        """이메일로 사용자 조회"""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_user_by_id(self, db: AsyncSession, user_id: UUID) -> Optional[User]:
        """ID로 사용자 조회"""
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def _create_default_profile(
        self, db: AsyncSession, user_id: UUID
    ) -> DoctorProfile:
        """기본 프로필 생성"""
        profile = DoctorProfile(
            user_id=user_id,
            writing_style={
                "formality": 5,
                "friendliness": 7,
                "technical_depth": 5,
                "storytelling": 6,
                "emotion": 6,
            },
            signature_phrases=[],
            target_audience={"age_range": "", "gender": "", "concerns": []},
            preferred_structure="AIDA",
        )

        db.add(profile)
        await db.commit()
        await db.refresh(profile)

        return profile


# Singleton instance
auth_service = AuthService()
