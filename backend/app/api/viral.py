"""
바이럴 확장 기능 API
- 다중 계정 관리
- 성과 추적
- 알림
- 프록시
- A/B 테스트
- 일일 리포트
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from app.db.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.viral_common import (
    AccountStatus, NotificationType, ProxyType, ABTestStatus
)

# Services
from app.services.account_manager import account_manager
from app.services.performance_tracker import performance_tracker
from app.services.notification_service import notification_service
from app.services.proxy_manager import proxy_manager
from app.services.ab_test_service import ab_test_service, AB_TEST_TEMPLATES
from app.services.daily_report_service import daily_report_service

router = APIRouter()


# ==================== Schemas ====================

class AccountCreate(BaseModel):
    account_id: str
    password: str
    account_name: Optional[str] = None
    use_for_knowledge: bool = True
    use_for_cafe: bool = True


class AccountUpdate(BaseModel):
    account_name: Optional[str] = None
    use_for_knowledge: Optional[bool] = None
    use_for_cafe: Optional[bool] = None
    daily_answer_limit: Optional[int] = None
    daily_comment_limit: Optional[int] = None
    daily_post_limit: Optional[int] = None
    min_activity_interval: Optional[int] = None


class NotificationChannelCreate(BaseModel):
    channel_type: str  # slack, telegram, discord, kakao, email, webhook
    channel_name: str
    config: Dict[str, Any]
    notify_types: Optional[List[str]] = None


class ProxyCreate(BaseModel):
    proxy_type: str = "http"  # http, https, socks5
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    name: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None


class ProxyImport(BaseModel):
    proxy_list: str
    proxy_type: str = "http"


class ABTestCreate(BaseModel):
    name: str
    description: str
    test_type: str  # tone, length, structure, promotion, timing
    platform: str   # knowledge, cafe
    variants: List[Dict[str, Any]]
    traffic_split: Optional[Dict[str, float]] = None
    target_sample_size: int = 100


# ==================== 계정 관리 ====================

@router.post("/accounts")
async def create_account(
    data: AccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """네이버 계정 추가"""
    account = await account_manager.create_account(
        db=db,
        user_id=str(current_user.id),
        account_id=data.account_id,
        password=data.password,
        account_name=data.account_name,
        use_for_knowledge=data.use_for_knowledge,
        use_for_cafe=data.use_for_cafe
    )
    return {"id": account.id, "account_name": account.account_name}


@router.get("/accounts")
async def get_accounts(
    platform: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """계정 목록 조회"""
    account_status = AccountStatus(status) if status else None
    accounts = await account_manager.get_accounts(
        db=db,
        user_id=str(current_user.id),
        status=account_status,
        platform=platform
    )
    return [
        {
            "id": a.id,
            "account_id": a.account_id,
            "account_name": a.account_name,
            "status": a.status,
            "use_for_knowledge": a.use_for_knowledge,
            "use_for_cafe": a.use_for_cafe,
            "today_answers": a.today_answers,
            "today_comments": a.today_comments,
            "total_answers": a.total_answers,
            "total_adoptions": a.total_adoptions,
            "adoption_rate": a.adoption_rate,
            "is_warming_up": a.is_warming_up,
            "warming_day": a.warming_day,
            "last_activity_at": a.last_activity_at
        }
        for a in accounts
    ]


@router.put("/accounts/{account_id}")
async def update_account(
    account_id: str,
    data: AccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """계정 설정 업데이트"""
    from sqlalchemy import select, and_
    from app.models.viral_common import NaverAccount

    result = await db.execute(
        select(NaverAccount).where(
            and_(
                NaverAccount.id == account_id,
                NaverAccount.user_id == str(current_user.id)
            )
        )
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    for key, value in data.dict(exclude_unset=True).items():
        if hasattr(account, key) and value is not None:
            setattr(account, key, value)

    await db.commit()
    return {"success": True}


@router.post("/accounts/{account_id}/warmup")
async def start_warmup(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """워밍업 시작"""
    await account_manager.start_warming_up(db, account_id)
    return {"success": True}


@router.delete("/accounts/{account_id}")
async def delete_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """계정 삭제"""
    success = await account_manager.delete_account(
        db, account_id, str(current_user.id)
    )
    if not success:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"success": True}


@router.get("/accounts/stats")
async def get_account_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """계정 통계"""
    return await account_manager.get_account_stats(db, str(current_user.id))


# ==================== 성과 추적 ====================

@router.get("/performance/summary")
async def get_performance_summary(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """성과 요약"""
    return await performance_tracker.get_summary(db, str(current_user.id), days)


@router.get("/performance/daily")
async def get_daily_performance(
    platform: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """일별 성과"""
    start = date.fromisoformat(start_date) if start_date else None
    end = date.fromisoformat(end_date) if end_date else None

    stats = await performance_tracker.get_daily_stats(
        db, str(current_user.id), platform, start, end
    )

    return [
        {
            "date": s.date.isoformat(),
            "platform": s.platform,
            "answers_posted": s.answers_posted,
            "answers_adopted": s.answers_adopted,
            "comments_posted": s.comments_posted,
            "posts_created": s.posts_created,
            "likes_received": s.likes_received,
            "replies_received": s.replies_received,
            "blog_clicks": s.blog_clicks,
            "place_clicks": s.place_clicks
        }
        for s in stats
    ]


@router.get("/performance/top-content")
async def get_top_content(
    platform: str,
    metric: str = "clicks",  # clicks, likes, replies
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """최고 성과 콘텐츠"""
    return await performance_tracker.get_top_performing_content(
        db, str(current_user.id), platform, metric, limit
    )


# ==================== 알림 ====================

@router.post("/notifications/channels")
async def create_notification_channel(
    data: NotificationChannelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """알림 채널 생성"""
    channel = await notification_service.create_channel(
        db=db,
        user_id=str(current_user.id),
        channel_type=data.channel_type,
        channel_name=data.channel_name,
        config=data.config,
        notify_types=data.notify_types
    )
    return {"id": channel.id, "channel_name": channel.channel_name}


@router.get("/notifications/channels")
async def get_notification_channels(
    channel_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """알림 채널 목록"""
    channels = await notification_service.get_channels(
        db, str(current_user.id), channel_type
    )
    return [
        {
            "id": c.id,
            "channel_type": c.channel_type,
            "channel_name": c.channel_name,
            "is_active": c.is_active,
            "notify_types": c.notify_types,
            "total_sent": c.total_sent,
            "fail_count": c.fail_count,
            "last_sent_at": c.last_sent_at
        }
        for c in channels
    ]


@router.post("/notifications/channels/{channel_id}/test")
async def test_notification_channel(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """알림 채널 테스트"""
    success = await notification_service.test_channel(
        db, channel_id, str(current_user.id)
    )
    return {"success": success}


@router.delete("/notifications/channels/{channel_id}")
async def delete_notification_channel(
    channel_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """알림 채널 삭제"""
    success = await notification_service.delete_channel(
        db, channel_id, str(current_user.id)
    )
    if not success:
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"success": True}


@router.get("/notifications/logs")
async def get_notification_logs(
    channel_id: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """알림 로그"""
    logs = await notification_service.get_notification_logs(
        db, str(current_user.id), channel_id, limit=limit
    )
    return [
        {
            "id": l.id,
            "notification_type": l.notification_type,
            "title": l.title,
            "message": l.message,
            "is_sent": l.is_sent,
            "sent_at": l.sent_at,
            "error_message": l.error_message,
            "created_at": l.created_at
        }
        for l in logs
    ]


# ==================== 프록시 ====================

@router.post("/proxies")
async def add_proxy(
    data: ProxyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """프록시 추가"""
    proxy = await proxy_manager.add_proxy(
        db=db,
        user_id=str(current_user.id),
        proxy_type=ProxyType(data.proxy_type),
        host=data.host,
        port=data.port,
        username=data.username,
        password=data.password,
        name=data.name,
        country=data.country,
        region=data.region
    )
    return {"id": proxy.id, "name": proxy.name}


@router.post("/proxies/import")
async def import_proxies(
    data: ProxyImport,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """프록시 일괄 가져오기"""
    result = await proxy_manager.import_proxies(
        db=db,
        user_id=str(current_user.id),
        proxy_list=data.proxy_list,
        proxy_type=ProxyType(data.proxy_type)
    )
    return result


@router.get("/proxies")
async def get_proxies(
    proxy_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """프록시 목록"""
    pt = ProxyType(proxy_type) if proxy_type else None
    proxies = await proxy_manager.get_proxies(
        db, str(current_user.id), pt, is_active
    )
    return [
        {
            "id": p.id,
            "name": p.name,
            "proxy_type": p.proxy_type,
            "host": p.host,
            "port": p.port,
            "is_active": p.is_active,
            "is_healthy": p.is_healthy,
            "response_time_ms": p.response_time_ms,
            "success_rate": p.success_rate,
            "usage_count": p.usage_count,
            "last_used_at": p.last_used_at,
            "last_check_at": p.last_check_at
        }
        for p in proxies
    ]


@router.post("/proxies/{proxy_id}/test")
async def test_proxy(
    proxy_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """프록시 테스트"""
    return await proxy_manager.test_proxy(
        db, proxy_id, str(current_user.id)
    )


@router.post("/proxies/check-all")
async def check_all_proxies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """모든 프록시 헬스체크"""
    return await proxy_manager.check_all_proxies(
        db, str(current_user.id)
    )


@router.delete("/proxies/{proxy_id}")
async def delete_proxy(
    proxy_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """프록시 삭제"""
    success = await proxy_manager.delete_proxy(
        db, proxy_id, str(current_user.id)
    )
    if not success:
        raise HTTPException(status_code=404, detail="Proxy not found")
    return {"success": True}


@router.get("/proxies/stats")
async def get_proxy_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """프록시 통계"""
    return await proxy_manager.get_proxy_stats(db, str(current_user.id))


# ==================== A/B 테스트 ====================

@router.get("/ab-tests/templates")
async def get_ab_test_templates():
    """A/B 테스트 템플릿"""
    return AB_TEST_TEMPLATES


@router.post("/ab-tests")
async def create_ab_test(
    data: ABTestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """A/B 테스트 생성"""
    test = await ab_test_service.create_test(
        db=db,
        user_id=str(current_user.id),
        name=data.name,
        description=data.description,
        test_type=data.test_type,
        platform=data.platform,
        variants=data.variants,
        traffic_split=data.traffic_split,
        target_sample_size=data.target_sample_size
    )
    return {"id": test.id, "name": test.name}


@router.get("/ab-tests")
async def get_ab_tests(
    status: Optional[str] = None,
    platform: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """A/B 테스트 목록"""
    test_status = ABTestStatus(status) if status else None
    tests = await ab_test_service.get_tests(
        db, str(current_user.id), test_status, platform
    )
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "test_type": t.test_type,
            "platform": t.platform,
            "status": t.status,
            "variants": t.variants,
            "current_sample_size": t.current_sample_size,
            "target_sample_size": t.target_sample_size,
            "winner_variant": t.winner_variant,
            "started_at": t.started_at,
            "completed_at": t.completed_at
        }
        for t in tests
    ]


@router.post("/ab-tests/{test_id}/start")
async def start_ab_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """A/B 테스트 시작"""
    test = await ab_test_service.start_test(
        db, test_id, str(current_user.id)
    )
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    return {"success": True, "status": test.status}


@router.post("/ab-tests/{test_id}/stop")
async def stop_ab_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """A/B 테스트 중지"""
    test = await ab_test_service.stop_test(
        db, test_id, str(current_user.id)
    )
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    return {"success": True, "status": test.status}


@router.get("/ab-tests/{test_id}/analysis")
async def analyze_ab_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """A/B 테스트 분석"""
    return await ab_test_service.analyze_test(
        db, test_id, str(current_user.id)
    )


@router.delete("/ab-tests/{test_id}")
async def delete_ab_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """A/B 테스트 삭제"""
    success = await ab_test_service.delete_test(
        db, test_id, str(current_user.id)
    )
    if not success:
        raise HTTPException(status_code=404, detail="Test not found")
    return {"success": True}


# ==================== 일일 리포트 ====================

@router.get("/reports/daily")
async def get_daily_reports(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """일일 리포트 목록"""
    start = date.fromisoformat(start_date) if start_date else None
    end = date.fromisoformat(end_date) if end_date else None

    reports = await daily_report_service.get_reports(
        db, str(current_user.id), start, end, limit
    )

    return [
        {
            "id": r.id,
            "date": r.date.isoformat(),
            "knowledge_answers": r.knowledge_answers,
            "knowledge_adoptions": r.knowledge_adoptions,
            "cafe_comments": r.cafe_comments,
            "cafe_posts": r.cafe_posts,
            "blog_clicks": r.blog_clicks,
            "place_clicks": r.place_clicks,
            "highlights": r.highlights,
            "recommendations": r.recommendations,
            "is_sent": r.is_sent
        }
        for r in reports
    ]


@router.post("/reports/daily/generate")
async def generate_daily_report(
    report_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """일일 리포트 생성"""
    target_date = date.fromisoformat(report_date) if report_date else None
    report = await daily_report_service.generate_report(
        db, str(current_user.id), target_date
    )
    return {"id": report.id, "date": report.date.isoformat()}


@router.post("/reports/daily/send")
async def send_daily_report(
    report_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """일일 리포트 발송"""
    target_date = date.fromisoformat(report_date) if report_date else None
    report = await daily_report_service.send_daily_report(
        db, str(current_user.id), target_date
    )
    return {"success": report.is_sent}


@router.get("/reports/weekly")
async def get_weekly_summary(
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """주간 요약"""
    end = date.fromisoformat(end_date) if end_date else None
    return await daily_report_service.get_weekly_summary(
        db, str(current_user.id), end
    )


@router.get("/reports/monthly")
async def get_monthly_summary(
    year: int = Query(...),
    month: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """월간 요약"""
    return await daily_report_service.get_monthly_summary(
        db, str(current_user.id), year, month
    )
