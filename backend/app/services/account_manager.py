"""
다중 네이버 계정 관리 서비스
- 계정 로테이션
- 워밍업 관리
- 일일 제한 관리
"""

import uuid
import json
import random
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from cryptography.fernet import Fernet
from app.core.config import settings
from app.models.viral_common import NaverAccount, AccountStatus


class AccountManagerService:
    """네이버 계정 관리 서비스"""

    def __init__(self):
        # 암호화 키 (환경변수에서 로드, 없으면 생성)
        self._encryption_key = getattr(settings, 'ENCRYPTION_KEY', None)
        if self._encryption_key:
            self._fernet = Fernet(self._encryption_key.encode())
        else:
            self._fernet = None

    def _encrypt(self, text: str) -> str:
        """텍스트 암호화"""
        if self._fernet and text:
            return self._fernet.encrypt(text.encode()).decode()
        return text

    def _decrypt(self, encrypted: str) -> str:
        """텍스트 복호화"""
        if self._fernet and encrypted:
            try:
                return self._fernet.decrypt(encrypted.encode()).decode()
            except:
                return encrypted
        return encrypted

    async def create_account(
        self,
        db: AsyncSession,
        user_id: str,
        account_id: str,
        password: str,
        account_name: Optional[str] = None,
        use_for_knowledge: bool = True,
        use_for_cafe: bool = True
    ) -> NaverAccount:
        """계정 생성"""
        account = NaverAccount(
            id=str(uuid.uuid4()),
            user_id=user_id,
            account_id=account_id,
            account_name=account_name or account_id,
            encrypted_password=self._encrypt(password),
            use_for_knowledge=use_for_knowledge,
            use_for_cafe=use_for_cafe
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)
        return account

    async def get_accounts(
        self,
        db: AsyncSession,
        user_id: str,
        status: Optional[AccountStatus] = None,
        platform: Optional[str] = None  # knowledge / cafe
    ) -> List[NaverAccount]:
        """계정 목록 조회"""
        query = select(NaverAccount).where(NaverAccount.user_id == user_id)

        if status:
            query = query.where(NaverAccount.status == status.value)

        if platform == "knowledge":
            query = query.where(NaverAccount.use_for_knowledge == True)
        elif platform == "cafe":
            query = query.where(NaverAccount.use_for_cafe == True)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_next_available_account(
        self,
        db: AsyncSession,
        user_id: str,
        platform: str,
        activity_type: str = "comment"  # answer, comment, post
    ) -> Optional[NaverAccount]:
        """다음 사용 가능한 계정 가져오기 (로테이션)"""
        # 오늘 날짜로 리셋 확인
        today = date.today()

        # 활성 계정 조회
        query = select(NaverAccount).where(
            and_(
                NaverAccount.user_id == user_id,
                NaverAccount.status == AccountStatus.ACTIVE.value
            )
        )

        if platform == "knowledge":
            query = query.where(NaverAccount.use_for_knowledge == True)
        elif platform == "cafe":
            query = query.where(NaverAccount.use_for_cafe == True)

        result = await db.execute(query)
        accounts = list(result.scalars().all())

        if not accounts:
            return None

        # 일일 카운터 리셋 필요한 계정 처리
        for account in accounts:
            if account.last_reset_date != today:
                account.today_answers = 0
                account.today_comments = 0
                account.today_posts = 0
                account.last_reset_date = today

        # 사용 가능한 계정 필터링
        available_accounts = []
        for account in accounts:
            # 일일 제한 확인
            if activity_type == "answer" and account.today_answers >= account.daily_answer_limit:
                continue
            if activity_type == "comment" and account.today_comments >= account.daily_comment_limit:
                continue
            if activity_type == "post" and account.today_posts >= account.daily_post_limit:
                continue

            # 최소 간격 확인
            if account.last_activity_at:
                elapsed = (datetime.utcnow() - account.last_activity_at).total_seconds()
                if elapsed < account.min_activity_interval:
                    continue

            available_accounts.append(account)

        if not available_accounts:
            return None

        # 마지막 활동 시간 기준 정렬 (가장 오래된 것 우선)
        available_accounts.sort(
            key=lambda x: x.last_activity_at or datetime.min
        )

        # 상위 3개 중 랜덤 선택 (패턴 회피)
        top_accounts = available_accounts[:min(3, len(available_accounts))]
        selected = random.choice(top_accounts)

        await db.commit()
        return selected

    async def record_activity(
        self,
        db: AsyncSession,
        account_id: str,
        activity_type: str,  # answer, comment, post
        success: bool = True
    ):
        """활동 기록"""
        result = await db.execute(
            select(NaverAccount).where(NaverAccount.id == account_id)
        )
        account = result.scalar_one_or_none()

        if account:
            account.last_activity_at = datetime.utcnow()

            if success:
                if activity_type == "answer":
                    account.today_answers += 1
                    account.total_answers += 1
                elif activity_type == "comment":
                    account.today_comments += 1
                    account.total_comments += 1
                elif activity_type == "post":
                    account.today_posts += 1

            await db.commit()

    async def record_adoption(
        self,
        db: AsyncSession,
        account_id: str
    ):
        """채택 기록"""
        result = await db.execute(
            select(NaverAccount).where(NaverAccount.id == account_id)
        )
        account = result.scalar_one_or_none()

        if account:
            account.total_adoptions += 1
            if account.total_answers > 0:
                account.adoption_rate = account.total_adoptions / account.total_answers
            await db.commit()

    async def record_like(
        self,
        db: AsyncSession,
        account_id: str
    ):
        """좋아요 기록"""
        result = await db.execute(
            select(NaverAccount).where(NaverAccount.id == account_id)
        )
        account = result.scalar_one_or_none()

        if account:
            account.total_likes += 1
            await db.commit()

    async def update_status(
        self,
        db: AsyncSession,
        account_id: str,
        status: AccountStatus,
        reason: Optional[str] = None
    ):
        """계정 상태 업데이트"""
        result = await db.execute(
            select(NaverAccount).where(NaverAccount.id == account_id)
        )
        account = result.scalar_one_or_none()

        if account:
            account.status = status.value
            account.updated_at = datetime.utcnow()
            await db.commit()

    async def start_warming_up(
        self,
        db: AsyncSession,
        account_id: str
    ):
        """워밍업 시작"""
        result = await db.execute(
            select(NaverAccount).where(NaverAccount.id == account_id)
        )
        account = result.scalar_one_or_none()

        if account:
            account.status = AccountStatus.WARMING.value
            account.is_warming_up = True
            account.warming_start_date = date.today()
            account.warming_day = 1

            # 워밍업 중에는 제한 축소
            account.daily_answer_limit = 2
            account.daily_comment_limit = 5
            account.daily_post_limit = 0
            account.min_activity_interval = 600  # 10분

            await db.commit()

    async def progress_warming_up(
        self,
        db: AsyncSession,
        account_id: str
    ):
        """워밍업 진행 (일일 호출)"""
        result = await db.execute(
            select(NaverAccount).where(NaverAccount.id == account_id)
        )
        account = result.scalar_one_or_none()

        if account and account.is_warming_up:
            account.warming_day += 1

            # 점진적 제한 완화 (7일 계획)
            if account.warming_day <= 7:
                day = account.warming_day
                account.daily_answer_limit = min(2 + day, 10)
                account.daily_comment_limit = min(5 + day * 2, 20)
                account.daily_post_limit = min(day // 3, 3)
                account.min_activity_interval = max(600 - day * 50, 300)
            else:
                # 워밍업 완료
                account.is_warming_up = False
                account.status = AccountStatus.ACTIVE.value
                account.daily_answer_limit = 10
                account.daily_comment_limit = 20
                account.daily_post_limit = 3
                account.min_activity_interval = 300

            await db.commit()

    async def save_session(
        self,
        db: AsyncSession,
        account_id: str,
        cookies: Dict[str, Any],
        expires_at: Optional[datetime] = None
    ):
        """세션 저장"""
        result = await db.execute(
            select(NaverAccount).where(NaverAccount.id == account_id)
        )
        account = result.scalar_one_or_none()

        if account:
            account.session_cookies = json.dumps(cookies)
            account.session_expires_at = expires_at or (datetime.utcnow() + timedelta(days=1))
            account.last_login_at = datetime.utcnow()
            account.login_fail_count = 0
            await db.commit()

    async def get_session(
        self,
        db: AsyncSession,
        account_id: str
    ) -> Optional[Dict[str, Any]]:
        """세션 가져오기"""
        result = await db.execute(
            select(NaverAccount).where(NaverAccount.id == account_id)
        )
        account = result.scalar_one_or_none()

        if account and account.session_cookies:
            # 세션 만료 확인
            if account.session_expires_at and account.session_expires_at > datetime.utcnow():
                return json.loads(account.session_cookies)

        return None

    async def record_login_failure(
        self,
        db: AsyncSession,
        account_id: str
    ):
        """로그인 실패 기록"""
        result = await db.execute(
            select(NaverAccount).where(NaverAccount.id == account_id)
        )
        account = result.scalar_one_or_none()

        if account:
            account.login_fail_count += 1

            # 3회 이상 실패 시 계정 휴식
            if account.login_fail_count >= 3:
                account.status = AccountStatus.RESTING.value

            await db.commit()

    async def get_account_stats(
        self,
        db: AsyncSession,
        user_id: str
    ) -> Dict[str, Any]:
        """계정 통계"""
        accounts = await self.get_accounts(db, user_id)

        total = len(accounts)
        active = sum(1 for a in accounts if a.status == AccountStatus.ACTIVE.value)
        warming = sum(1 for a in accounts if a.status == AccountStatus.WARMING.value)
        resting = sum(1 for a in accounts if a.status == AccountStatus.RESTING.value)
        blocked = sum(1 for a in accounts if a.status == AccountStatus.BLOCKED.value)

        total_answers = sum(a.total_answers for a in accounts)
        total_adoptions = sum(a.total_adoptions for a in accounts)
        total_comments = sum(a.total_comments for a in accounts)
        total_likes = sum(a.total_likes for a in accounts)

        today_answers = sum(a.today_answers for a in accounts)
        today_comments = sum(a.today_comments for a in accounts)
        today_posts = sum(a.today_posts for a in accounts)

        avg_adoption_rate = total_adoptions / total_answers if total_answers > 0 else 0

        return {
            "total_accounts": total,
            "active": active,
            "warming": warming,
            "resting": resting,
            "blocked": blocked,
            "total_answers": total_answers,
            "total_adoptions": total_adoptions,
            "total_comments": total_comments,
            "total_likes": total_likes,
            "today_answers": today_answers,
            "today_comments": today_comments,
            "today_posts": today_posts,
            "avg_adoption_rate": avg_adoption_rate
        }

    async def delete_account(
        self,
        db: AsyncSession,
        account_id: str,
        user_id: str
    ) -> bool:
        """계정 삭제"""
        result = await db.execute(
            select(NaverAccount).where(
                and_(
                    NaverAccount.id == account_id,
                    NaverAccount.user_id == user_id
                )
            )
        )
        account = result.scalar_one_or_none()

        if account:
            await db.delete(account)
            await db.commit()
            return True
        return False


# 싱글톤 인스턴스
account_manager = AccountManagerService()
