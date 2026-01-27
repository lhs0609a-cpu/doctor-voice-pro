"""
블로그 영업 자동화 API
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime
import urllib.parse

from app.db.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.blog_outreach import (
    NaverBlog, BlogContact, EmailTemplate, EmailCampaign,
    EmailLog, BlogSearchKeyword, OutreachSetting, OutreachStats,
    BlogCategory, LeadGrade, BlogStatus, CampaignStatus, EmailStatus
)
from app.services.blog_outreach_crawler import BlogOutreachCrawler
from app.services.contact_extractor import ContactExtractorService
from app.services.lead_scoring_service import LeadScoringService
from app.services.email_sender_service import EmailSenderService

router = APIRouter()


# ==================== Pydantic Schemas ====================

class BlogSearchRequest(BaseModel):
    keyword: str
    category: Optional[str] = None
    max_results: int = 50


class CategoryCollectRequest(BaseModel):
    category: str
    keywords: Optional[List[str]] = None
    max_per_keyword: int = 30


class InfluencerCollectRequest(BaseModel):
    category: Optional[str] = None
    min_visitors: int = 1000
    min_neighbors: int = 500


class ScoringRequest(BaseModel):
    target_categories: Optional[List[str]] = None
    target_keywords: Optional[List[str]] = None


class EmailTemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    template_type: str = "introduction"
    subject: str
    body: str
    variables: Optional[List[dict]] = None


class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    template_type: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    variables: Optional[List[dict]] = None
    is_active: Optional[bool] = None


class CampaignCreate(BaseModel):
    name: str
    description: Optional[str] = None
    target_grades: Optional[List[str]] = None
    target_categories: Optional[List[str]] = None
    target_keywords: Optional[List[str]] = None
    min_score: float = 0
    max_contacts: Optional[int] = None
    templates: Optional[List[dict]] = None
    daily_limit: int = 50
    sending_hours_start: int = 9
    sending_hours_end: int = 18
    sending_days: Optional[List[int]] = [1, 2, 3, 4, 5]


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_grades: Optional[List[str]] = None
    target_categories: Optional[List[str]] = None
    target_keywords: Optional[List[str]] = None
    min_score: Optional[float] = None
    max_contacts: Optional[int] = None
    templates: Optional[List[dict]] = None
    daily_limit: Optional[int] = None
    status: Optional[str] = None


class OutreachSettingUpdate(BaseModel):
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    company_name: Optional[str] = None
    service_name: Optional[str] = None
    service_description: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: Optional[bool] = None
    daily_limit: Optional[int] = None
    hourly_limit: Optional[int] = None
    min_interval_seconds: Optional[int] = None
    weight_influence: Optional[float] = None
    weight_activity: Optional[float] = None
    weight_relevance: Optional[float] = None
    auto_collect: Optional[bool] = None
    auto_extract_contact: Optional[bool] = None
    auto_score: Optional[bool] = None
    track_opens: Optional[bool] = None
    track_clicks: Optional[bool] = None
    unsubscribe_text: Optional[str] = None
    # 네이버 검색 API 설정
    naver_client_id: Optional[str] = None
    naver_client_secret: Optional[str] = None


class SendEmailRequest(BaseModel):
    blog_id: str
    template_id: str
    campaign_id: Optional[str] = None
    custom_variables: Optional[dict] = None


class KeywordCreate(BaseModel):
    keyword: str
    category: Optional[str] = None
    priority: int = 1


# ==================== Blog Collection APIs ====================

@router.post("/blogs/search")
async def search_blogs(
    request: BlogSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """키워드로 블로그 검색 및 수집"""
    crawler = BlogOutreachCrawler(db)
    category = BlogCategory(request.category) if request.category else None

    result = await crawler.search_blogs(
        keyword=request.keyword,
        user_id=str(current_user.id),
        category=category,
        max_results=request.max_results
    )
    return result


@router.post("/blogs/collect/category")
async def collect_by_category(
    request: CategoryCollectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """카테고리별 블로그 수집"""
    crawler = BlogOutreachCrawler(db)
    category = BlogCategory(request.category)

    result = await crawler.collect_by_category(
        user_id=str(current_user.id),
        category=category,
        keywords=request.keywords,
        max_per_keyword=request.max_per_keyword
    )
    return result


@router.post("/blogs/collect/influencers")
async def collect_influencers(
    request: InfluencerCollectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """인플루언서 블로그 수집"""
    crawler = BlogOutreachCrawler(db)
    category = BlogCategory(request.category) if request.category else None

    result = await crawler.collect_influencers(
        user_id=str(current_user.id),
        category=category,
        min_visitors=request.min_visitors,
        min_neighbors=request.min_neighbors
    )
    return result


@router.get("/blogs")
async def get_blogs(
    category: Optional[str] = None,
    grade: Optional[str] = None,
    status: Optional[str] = None,
    has_contact: Optional[bool] = None,
    min_score: float = 0,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """블로그 목록 조회"""
    conditions = [NaverBlog.user_id == str(current_user.id)]

    if category:
        conditions.append(NaverBlog.category == BlogCategory(category))

    if grade:
        conditions.append(NaverBlog.lead_grade == LeadGrade(grade))

    if status:
        conditions.append(NaverBlog.status == BlogStatus(status))

    if has_contact is not None:
        conditions.append(NaverBlog.has_contact == has_contact)

    if min_score > 0:
        conditions.append(NaverBlog.lead_score >= min_score)

    # Count query
    count_query = select(func.count()).select_from(NaverBlog).where(and_(*conditions))
    total = (await db.execute(count_query)).scalar() or 0

    # Data query
    data_query = select(NaverBlog).where(and_(*conditions)).order_by(desc(NaverBlog.lead_score)).offset(skip).limit(limit)
    result = await db.execute(data_query)
    blogs = result.scalars().all()

    return {
        "total": total,
        "blogs": [
            {
                "id": b.id,
                "blog_id": b.blog_id,
                "blog_url": b.blog_url,
                "blog_name": b.blog_name,
                "owner_nickname": b.owner_nickname,
                "category": b.category.value if b.category else None,
                "visitor_daily": b.visitor_daily,
                "neighbor_count": b.neighbor_count,
                "lead_score": b.lead_score,
                "lead_grade": b.lead_grade.value if b.lead_grade else None,
                "status": b.status.value if b.status else None,
                "has_contact": b.has_contact,
                "is_influencer": b.is_influencer,
                "last_post_date": b.last_post_date.isoformat() if b.last_post_date else None,
                "created_at": b.created_at.isoformat() if b.created_at else None
            } for b in blogs
        ]
    }


@router.get("/blogs/{blog_id}")
async def get_blog_detail(
    blog_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """블로그 상세 조회"""
    result = await db.execute(
        select(NaverBlog).where(
            and_(NaverBlog.id == blog_id, NaverBlog.user_id == str(current_user.id))
        )
    )
    blog = result.scalar_one_or_none()

    if not blog:
        raise HTTPException(status_code=404, detail="블로그를 찾을 수 없습니다")

    # 연락처 조회
    contacts_result = await db.execute(
        select(BlogContact).where(BlogContact.blog_id == blog_id)
    )
    contacts = contacts_result.scalars().all()

    # 이메일 로그 조회
    logs_result = await db.execute(
        select(EmailLog).where(EmailLog.blog_id == blog_id).order_by(desc(EmailLog.created_at)).limit(10)
    )
    email_logs = logs_result.scalars().all()

    return {
        "id": blog.id,
        "blog_id": blog.blog_id,
        "blog_url": blog.blog_url,
        "blog_name": blog.blog_name,
        "owner_nickname": blog.owner_nickname,
        "profile_image": blog.profile_image,
        "introduction": blog.introduction,
        "category": blog.category.value if blog.category else None,
        "tags": blog.tags,
        "keywords": blog.keywords,
        "visitor_daily": blog.visitor_daily,
        "visitor_total": blog.visitor_total,
        "neighbor_count": blog.neighbor_count,
        "post_count": blog.post_count,
        "last_post_date": blog.last_post_date.isoformat() if blog.last_post_date else None,
        "last_post_title": blog.last_post_title,
        "lead_score": blog.lead_score,
        "lead_grade": blog.lead_grade.value if blog.lead_grade else None,
        "influence_score": blog.influence_score,
        "activity_score": blog.activity_score,
        "relevance_score": blog.relevance_score,
        "status": blog.status.value if blog.status else None,
        "is_influencer": blog.is_influencer,
        "has_contact": blog.has_contact,
        "notes": blog.notes,
        "contacts": [
            {
                "id": c.id,
                "email": c.email,
                "phone": c.phone,
                "instagram": c.instagram,
                "youtube": c.youtube,
                "kakao_channel": c.kakao_channel,
                "source": c.source.value if c.source else None,
                "is_primary": c.is_primary,
                "is_verified": c.is_verified
            } for c in contacts
        ],
        "email_history": [
            {
                "id": e.id,
                "subject": e.subject,
                "status": e.status.value if e.status else None,
                "sent_at": e.sent_at.isoformat() if e.sent_at else None,
                "opened_at": e.opened_at.isoformat() if e.opened_at else None
            } for e in email_logs
        ],
        "created_at": blog.created_at.isoformat() if blog.created_at else None,
        "updated_at": blog.updated_at.isoformat() if blog.updated_at else None
    }


@router.delete("/blogs/{blog_id}")
async def delete_blog(
    blog_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """블로그 삭제"""
    result = await db.execute(
        select(NaverBlog).where(and_(
            NaverBlog.id == blog_id,
            NaverBlog.user_id == str(current_user.id)
        ))
    )
    blog = result.scalar_one_or_none()

    if not blog:
        raise HTTPException(status_code=404, detail="블로그를 찾을 수 없습니다")

    await db.delete(blog)
    await db.commit()

    return {"success": True, "message": "블로그가 삭제되었습니다"}


@router.put("/blogs/{blog_id}/status")
async def update_blog_status(
    blog_id: str,
    status: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """블로그 상태 변경"""
    result = await db.execute(
        select(NaverBlog).where(and_(
            NaverBlog.id == blog_id,
            NaverBlog.user_id == str(current_user.id)
        ))
    )
    blog = result.scalar_one_or_none()

    if not blog:
        raise HTTPException(status_code=404, detail="블로그를 찾을 수 없습니다")

    blog.status = BlogStatus(status)
    blog.updated_at = datetime.utcnow()
    await db.commit()

    return {"success": True, "status": status}


# ==================== Contact Extraction APIs ====================

@router.post("/contacts/extract/{blog_id}")
async def extract_contacts(
    blog_id: str,
    auto_generate_naver_email: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """블로그에서 연락처 추출

    Args:
        blog_id: 블로그 DB ID
        auto_generate_naver_email: 블로그 ID 기반 네이버 이메일 자동 생성 (기본값: True)
    """
    extractor = ContactExtractorService(db)
    result = await extractor.extract_contacts(
        blog_id=blog_id,
        user_id=str(current_user.id),
        auto_generate_naver_email=auto_generate_naver_email
    )
    return result


@router.post("/contacts/extract-batch")
async def extract_contacts_batch(
    limit: int = 50,
    auto_generate_naver_email: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """배치 연락처 추출

    Args:
        limit: 최대 처리 개수
        auto_generate_naver_email: 블로그 ID 기반 네이버 이메일 자동 생성 (기본값: True)
    """
    extractor = ContactExtractorService(db)
    result = await extractor.extract_contacts_batch(
        user_id=str(current_user.id),
        limit=limit,
        auto_generate_naver_email=auto_generate_naver_email
    )
    return result


@router.post("/contacts/generate-naver-emails")
async def generate_naver_emails(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """블로그 ID 기반 네이버 이메일 일괄 생성 (빠른 처리)

    Playwright 없이 블로그 ID만으로 이메일 주소를 생성합니다.
    예: myblog123 → myblog123@naver.com

    Args:
        limit: 최대 처리 개수 (기본값: 100)
    """
    from app.models.blog_outreach import BlogContact, ContactSource

    user_id = str(current_user.id)

    # 연락처가 없는 블로그 조회
    result = await db.execute(
        select(NaverBlog).where(
            and_(
                NaverBlog.user_id == user_id,
                NaverBlog.has_contact == False
            )
        ).limit(limit)
    )
    blogs = result.scalars().all()

    if not blogs:
        return {
            "success": True,
            "processed": 0,
            "generated": 0,
            "message": "처리할 블로그가 없습니다"
        }

    generated = 0
    for blog in blogs:
        if not blog.blog_id:
            continue

        # 이미 같은 이메일이 있는지 확인
        naver_email = f"{blog.blog_id.lower().strip()}@naver.com"
        existing = await db.execute(
            select(BlogContact).where(
                and_(
                    BlogContact.blog_id == blog.id,
                    BlogContact.email == naver_email
                )
            )
        )
        if existing.scalar_one_or_none():
            continue

        # 네이버 이메일 연락처 생성
        contact = BlogContact(
            blog_id=blog.id,
            email=naver_email,
            source=ContactSource.PROFILE,
            source_url=blog.blog_url,
            is_primary=True,
            is_verified=False
        )
        db.add(contact)

        # 블로그 상태 업데이트
        blog.has_contact = True
        blog.status = BlogStatus.CONTACT_FOUND

        generated += 1

    await db.commit()

    return {
        "success": True,
        "processed": len(blogs),
        "generated": generated,
        "message": f"{generated}개의 네이버 이메일이 생성되었습니다"
    }


# ==================== Lead Scoring APIs ====================

@router.post("/scoring/score/{blog_id}")
async def score_blog(
    blog_id: str,
    request: Optional[ScoringRequest] = None,
    include_breakdown: bool = True,  # P2: 점수 산정 근거 포함 옵션
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """블로그 스코어링 (P2: score_breakdown으로 점수 산정 근거 제공)"""
    scorer = LeadScoringService(db)

    target_categories = None
    target_keywords = None

    if request:
        if request.target_categories:
            target_categories = [BlogCategory(c) for c in request.target_categories]
        target_keywords = request.target_keywords

    result = await scorer.score_blog(
        blog_id=blog_id,
        user_id=str(current_user.id),
        target_categories=target_categories,
        target_keywords=target_keywords,
        include_breakdown=include_breakdown
    )
    return result


@router.post("/scoring/batch")
async def score_blogs_batch(
    request: Optional[ScoringRequest] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """배치 스코어링"""
    scorer = LeadScoringService(db)

    target_categories = None
    target_keywords = None

    if request:
        if request.target_categories:
            target_categories = [BlogCategory(c) for c in request.target_categories]
        target_keywords = request.target_keywords

    result = await scorer.score_blogs_batch(
        user_id=str(current_user.id),
        target_categories=target_categories,
        target_keywords=target_keywords,
        limit=limit
    )
    return result


@router.post("/scoring/rescore-all")
async def rescore_all(
    request: Optional[ScoringRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """전체 재스코어링"""
    scorer = LeadScoringService(db)

    target_categories = None
    target_keywords = None

    if request:
        if request.target_categories:
            target_categories = [BlogCategory(c) for c in request.target_categories]
        target_keywords = request.target_keywords

    result = await scorer.rescore_all(
        user_id=str(current_user.id),
        target_categories=target_categories,
        target_keywords=target_keywords
    )
    return result


@router.get("/scoring/top-leads")
async def get_top_leads(
    grade: Optional[str] = None,
    category: Optional[str] = None,
    has_contact: Optional[bool] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """상위 리드 조회"""
    scorer = LeadScoringService(db)

    lead_grade = LeadGrade(grade) if grade else None
    blog_category = BlogCategory(category) if category else None

    leads = await scorer.get_top_leads(
        user_id=str(current_user.id),
        grade=lead_grade,
        category=blog_category,
        has_contact=has_contact,
        limit=limit
    )
    return {"leads": leads}


@router.get("/scoring/stats")
async def get_scoring_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """스코어링 통계"""
    scorer = LeadScoringService(db)
    stats = await scorer.get_scoring_stats(str(current_user.id))
    return stats


# ==================== Email Template APIs ====================

@router.post("/templates")
async def create_template(
    request: EmailTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """이메일 템플릿 생성"""
    template = EmailTemplate(
        user_id=str(current_user.id),
        name=request.name,
        description=request.description,
        template_type=request.template_type,
        subject=request.subject,
        body=request.body,
        variables=request.variables,
        is_active=True
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    return {"success": True, "template_id": template.id}


@router.get("/templates")
async def get_templates(
    template_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """템플릿 목록 조회"""
    conditions = [EmailTemplate.user_id == str(current_user.id)]

    if template_type:
        conditions.append(EmailTemplate.template_type == template_type)

    result = await db.execute(
        select(EmailTemplate).where(and_(*conditions)).order_by(desc(EmailTemplate.created_at))
    )
    templates = result.scalars().all()

    return {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "template_type": t.template_type,
                "subject": t.subject,
                "body": t.body,
                "variables": t.variables,
                "is_active": t.is_active,
                "usage_count": t.usage_count,
                "open_rate": t.open_rate,
                "reply_rate": t.reply_rate,
                "created_at": t.created_at.isoformat() if t.created_at else None
            } for t in templates
        ]
    }


@router.get("/templates/{template_id}")
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """템플릿 상세 조회"""
    result = await db.execute(
        select(EmailTemplate).where(and_(
            EmailTemplate.id == template_id,
            EmailTemplate.user_id == str(current_user.id)
        ))
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다")

    return {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "template_type": template.template_type,
        "subject": template.subject,
        "body": template.body,
        "variables": template.variables,
        "is_active": template.is_active,
        "usage_count": template.usage_count,
        "open_rate": template.open_rate,
        "reply_rate": template.reply_rate,
        "created_at": template.created_at.isoformat() if template.created_at else None
    }


@router.put("/templates/{template_id}")
async def update_template(
    template_id: str,
    request: EmailTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """템플릿 수정"""
    result = await db.execute(
        select(EmailTemplate).where(and_(
            EmailTemplate.id == template_id,
            EmailTemplate.user_id == str(current_user.id)
        ))
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다")

    update_data = request.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(template, key, value)

    template.updated_at = datetime.utcnow()
    await db.commit()

    return {"success": True}


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """템플릿 삭제"""
    result = await db.execute(
        select(EmailTemplate).where(and_(
            EmailTemplate.id == template_id,
            EmailTemplate.user_id == str(current_user.id)
        ))
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다")

    await db.delete(template)
    await db.commit()

    return {"success": True, "message": "템플릿이 삭제되었습니다"}


# ==================== Campaign APIs ====================

@router.post("/campaigns")
async def create_campaign(
    request: CampaignCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """캠페인 생성"""
    campaign = EmailCampaign(
        user_id=str(current_user.id),
        name=request.name,
        description=request.description,
        target_grades=request.target_grades,
        target_categories=request.target_categories,
        target_keywords=request.target_keywords,
        min_score=request.min_score,
        max_contacts=request.max_contacts,
        templates=request.templates,
        daily_limit=request.daily_limit,
        sending_hours_start=request.sending_hours_start,
        sending_hours_end=request.sending_hours_end,
        sending_days=request.sending_days,
        status=CampaignStatus.DRAFT
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)

    return {"success": True, "campaign_id": campaign.id}


@router.get("/campaigns")
async def get_campaigns(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """캠페인 목록 조회"""
    conditions = [EmailCampaign.user_id == str(current_user.id)]

    if status:
        conditions.append(EmailCampaign.status == CampaignStatus(status))

    result = await db.execute(
        select(EmailCampaign).where(and_(*conditions)).order_by(desc(EmailCampaign.created_at))
    )
    campaigns = result.scalars().all()

    return {
        "campaigns": [
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "status": c.status.value if c.status else None,
                "target_grades": c.target_grades,
                "target_categories": c.target_categories,
                "min_score": c.min_score,
                "daily_limit": c.daily_limit,
                "total_targets": c.total_targets,
                "total_sent": c.total_sent,
                "total_opened": c.total_opened,
                "total_replied": c.total_replied,
                "started_at": c.started_at.isoformat() if c.started_at else None,
                "created_at": c.created_at.isoformat() if c.created_at else None
            } for c in campaigns
        ]
    }


@router.get("/campaigns/{campaign_id}")
async def get_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """캠페인 상세 조회"""
    result = await db.execute(
        select(EmailCampaign).where(and_(
            EmailCampaign.id == campaign_id,
            EmailCampaign.user_id == str(current_user.id)
        ))
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=404, detail="캠페인을 찾을 수 없습니다")

    return {
        "id": campaign.id,
        "name": campaign.name,
        "description": campaign.description,
        "status": campaign.status.value if campaign.status else None,
        "target_grades": campaign.target_grades,
        "target_categories": campaign.target_categories,
        "target_keywords": campaign.target_keywords,
        "min_score": campaign.min_score,
        "max_contacts": campaign.max_contacts,
        "templates": campaign.templates,
        "daily_limit": campaign.daily_limit,
        "sending_hours_start": campaign.sending_hours_start,
        "sending_hours_end": campaign.sending_hours_end,
        "sending_days": campaign.sending_days,
        "total_targets": campaign.total_targets,
        "total_sent": campaign.total_sent,
        "total_opened": campaign.total_opened,
        "total_clicked": campaign.total_clicked,
        "total_replied": campaign.total_replied,
        "total_bounced": campaign.total_bounced,
        "started_at": campaign.started_at.isoformat() if campaign.started_at else None,
        "completed_at": campaign.completed_at.isoformat() if campaign.completed_at else None,
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None
    }


@router.put("/campaigns/{campaign_id}")
async def update_campaign(
    campaign_id: str,
    request: CampaignUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """캠페인 수정"""
    result = await db.execute(
        select(EmailCampaign).where(and_(
            EmailCampaign.id == campaign_id,
            EmailCampaign.user_id == str(current_user.id)
        ))
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=404, detail="캠페인을 찾을 수 없습니다")

    update_data = request.dict(exclude_unset=True)

    if "status" in update_data:
        update_data["status"] = CampaignStatus(update_data["status"])
        if update_data["status"] == CampaignStatus.ACTIVE and not campaign.started_at:
            update_data["started_at"] = datetime.utcnow()
        elif update_data["status"] == CampaignStatus.COMPLETED:
            update_data["completed_at"] = datetime.utcnow()

    for key, value in update_data.items():
        setattr(campaign, key, value)

    campaign.updated_at = datetime.utcnow()
    await db.commit()

    return {"success": True}


@router.post("/campaigns/{campaign_id}/start")
async def start_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """캠페인 시작"""
    result = await db.execute(
        select(EmailCampaign).where(and_(
            EmailCampaign.id == campaign_id,
            EmailCampaign.user_id == str(current_user.id)
        ))
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=404, detail="캠페인을 찾을 수 없습니다")

    campaign.status = CampaignStatus.ACTIVE
    campaign.started_at = datetime.utcnow()
    campaign.updated_at = datetime.utcnow()
    await db.commit()

    return {"success": True, "message": "캠페인이 시작되었습니다"}


@router.post("/campaigns/{campaign_id}/pause")
async def pause_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """캠페인 일시정지"""
    result = await db.execute(
        select(EmailCampaign).where(and_(
            EmailCampaign.id == campaign_id,
            EmailCampaign.user_id == str(current_user.id)
        ))
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=404, detail="캠페인을 찾을 수 없습니다")

    campaign.status = CampaignStatus.PAUSED
    campaign.updated_at = datetime.utcnow()
    await db.commit()

    return {"success": True, "message": "캠페인이 일시정지되었습니다"}


@router.post("/campaigns/{campaign_id}/send-batch")
async def send_campaign_batch(
    campaign_id: str,
    batch_size: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """캠페인 배치 발송"""
    sender = EmailSenderService(db)
    result = await sender.send_campaign_batch(
        user_id=str(current_user.id),
        campaign_id=campaign_id,
        batch_size=batch_size
    )
    return result


@router.delete("/campaigns/{campaign_id}")
async def delete_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """캠페인 삭제"""
    result = await db.execute(
        select(EmailCampaign).where(and_(
            EmailCampaign.id == campaign_id,
            EmailCampaign.user_id == str(current_user.id)
        ))
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        raise HTTPException(status_code=404, detail="캠페인을 찾을 수 없습니다")

    await db.delete(campaign)
    await db.commit()

    return {"success": True, "message": "캠페인이 삭제되었습니다"}


# ==================== Email Sending APIs ====================

@router.post("/email/send")
async def send_email(
    request: SendEmailRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """이메일 발송"""
    sender = EmailSenderService(db)
    result = await sender.send_with_template(
        user_id=str(current_user.id),
        blog_id=request.blog_id,
        template_id=request.template_id,
        campaign_id=request.campaign_id,
        custom_variables=request.custom_variables
    )
    return result


@router.get("/email/stats")
async def get_email_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """이메일 발송 통계"""
    sender = EmailSenderService(db)
    stats = await sender.get_sending_stats(str(current_user.id))
    return stats


@router.get("/email/logs")
async def get_email_logs(
    campaign_id: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """이메일 발송 로그"""
    conditions = [EmailLog.user_id == str(current_user.id)]

    if campaign_id:
        conditions.append(EmailLog.campaign_id == campaign_id)

    if status:
        conditions.append(EmailLog.status == EmailStatus(status))

    count_result = await db.execute(
        select(func.count()).select_from(EmailLog).where(and_(*conditions))
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(EmailLog).where(and_(*conditions)).order_by(desc(EmailLog.created_at)).offset(skip).limit(limit)
    )
    logs = result.scalars().all()

    return {
        "total": total,
        "logs": [
            {
                "id": l.id,
                "to_email": l.to_email,
                "to_name": l.to_name,
                "subject": l.subject,
                "status": l.status.value if l.status else None,
                "sent_at": l.sent_at.isoformat() if l.sent_at else None,
                "opened_at": l.opened_at.isoformat() if l.opened_at else None,
                "clicked_at": l.clicked_at.isoformat() if l.clicked_at else None,
                "replied_at": l.replied_at.isoformat() if l.replied_at else None,
                "error_message": l.error_message,
                "created_at": l.created_at.isoformat() if l.created_at else None
            } for l in logs
        ]
    }


@router.post("/email/logs/{log_id}/mark-replied")
async def mark_email_replied(
    log_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """이메일 회신 마킹"""
    sender = EmailSenderService(db)
    success = await sender.mark_replied(log_id)
    return {"success": success}


# ==================== Tracking APIs (Public) ====================

@router.get("/track/open/{tracking_id}")
async def track_open(
    tracking_id: str,
    db: AsyncSession = Depends(get_db)
):
    """오픈 추적 (1x1 픽셀)"""
    sender = EmailSenderService(db)
    await sender.track_open(tracking_id)

    # 1x1 투명 GIF 반환
    gif = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
    return Response(content=gif, media_type="image/gif")


@router.get("/track/click/{tracking_id}")
async def track_click(
    tracking_id: str,
    url: str,
    db: AsyncSession = Depends(get_db)
):
    """클릭 추적 및 리다이렉트"""
    # URL 검증 - 허용된 도메인만 리다이렉트 (Open Redirect 방지)
    decoded_url = urllib.parse.unquote(url)
    parsed = urllib.parse.urlparse(decoded_url)

    # 허용된 도메인 목록 (프로토콜 포함)
    ALLOWED_DOMAINS = [
        "blog.naver.com",
        "m.blog.naver.com",
        "in.naver.com",
        "www.instagram.com",
        "instagram.com",
        "www.youtube.com",
        "youtube.com",
        "youtu.be",
    ]

    # 도메인 검증
    if parsed.netloc and parsed.netloc not in ALLOWED_DOMAINS:
        raise HTTPException(
            status_code=400,
            detail="허용되지 않은 URL입니다"
        )

    # 상대 URL 또는 유효한 절대 URL인 경우에만 허용
    if not parsed.scheme or parsed.scheme not in ["http", "https"]:
        raise HTTPException(
            status_code=400,
            detail="유효하지 않은 URL 형식입니다"
        )

    sender = EmailSenderService(db)
    await sender.track_click(tracking_id, url)

    # 원래 URL로 리다이렉트
    return RedirectResponse(url=decoded_url)


# ==================== Settings APIs ====================

@router.get("/settings")
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """영업 설정 조회"""
    result = await db.execute(
        select(OutreachSetting).where(OutreachSetting.user_id == str(current_user.id))
    )
    settings = result.scalar_one_or_none()

    if not settings:
        return {"settings": None}

    return {
        "settings": {
            "id": settings.id,
            "sender_name": settings.sender_name,
            "sender_email": settings.sender_email,
            "company_name": settings.company_name,
            "service_name": settings.service_name,
            "service_description": settings.service_description,
            "smtp_host": settings.smtp_host,
            "smtp_port": settings.smtp_port,
            "smtp_username": settings.smtp_username,
            "smtp_configured": bool(settings.smtp_password_encrypted),
            "smtp_use_tls": settings.smtp_use_tls,
            "daily_limit": settings.daily_limit,
            "hourly_limit": settings.hourly_limit,
            "min_interval_seconds": settings.min_interval_seconds,
            "weight_influence": settings.weight_influence,
            "weight_activity": settings.weight_activity,
            "weight_relevance": settings.weight_relevance,
            "auto_collect": settings.auto_collect,
            "auto_extract_contact": settings.auto_extract_contact,
            "auto_score": settings.auto_score,
            "track_opens": settings.track_opens,
            "track_clicks": settings.track_clicks,
            "unsubscribe_text": settings.unsubscribe_text,
            # 네이버 API 설정
            "naver_client_id": settings.naver_client_id,
            "naver_api_configured": bool(settings.naver_client_secret_encrypted)
        }
    }


@router.put("/settings")
async def update_settings(
    request: OutreachSettingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """영업 설정 업데이트"""
    result = await db.execute(
        select(OutreachSetting).where(OutreachSetting.user_id == str(current_user.id))
    )
    settings = result.scalar_one_or_none()

    if not settings:
        settings = OutreachSetting(user_id=str(current_user.id))
        db.add(settings)

    update_data = request.dict(exclude_unset=True)

    # SMTP 비밀번호 암호화
    if "smtp_password" in update_data and update_data["smtp_password"]:
        sender = EmailSenderService(db)
        settings.smtp_password_encrypted = sender.encrypt_password(update_data["smtp_password"])
        del update_data["smtp_password"]

    # 네이버 API Secret 암호화
    if "naver_client_secret" in update_data and update_data["naver_client_secret"]:
        sender = EmailSenderService(db)
        settings.naver_client_secret_encrypted = sender.encrypt_password(update_data["naver_client_secret"])
        del update_data["naver_client_secret"]

    for key, value in update_data.items():
        if hasattr(settings, key):
            setattr(settings, key, value)

    settings.updated_at = datetime.utcnow()
    await db.commit()

    return {"success": True, "message": "설정이 저장되었습니다"}


# ==================== Keyword APIs ====================

@router.post("/keywords")
async def create_keyword(
    request: KeywordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """검색 키워드 추가"""
    keyword = BlogSearchKeyword(
        user_id=str(current_user.id),
        keyword=request.keyword,
        category=BlogCategory(request.category) if request.category else None,
        priority=request.priority,
        is_active=True
    )
    db.add(keyword)
    await db.commit()
    await db.refresh(keyword)

    return {"success": True, "keyword_id": keyword.id}


@router.get("/keywords")
async def get_keywords(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """키워드 목록 조회"""
    result = await db.execute(
        select(BlogSearchKeyword).where(
            BlogSearchKeyword.user_id == str(current_user.id)
        ).order_by(desc(BlogSearchKeyword.priority))
    )
    keywords = result.scalars().all()

    return {
        "keywords": [
            {
                "id": k.id,
                "keyword": k.keyword,
                "category": k.category.value if k.category else None,
                "is_active": k.is_active,
                "priority": k.priority,
                "total_collected": k.total_collected,
                "last_collected_at": k.last_collected_at.isoformat() if k.last_collected_at else None
            } for k in keywords
        ]
    }


@router.delete("/keywords/{keyword_id}")
async def delete_keyword(
    keyword_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """키워드 삭제"""
    result = await db.execute(
        select(BlogSearchKeyword).where(and_(
            BlogSearchKeyword.id == keyword_id,
            BlogSearchKeyword.user_id == str(current_user.id)
        ))
    )
    keyword = result.scalar_one_or_none()

    if not keyword:
        raise HTTPException(status_code=404, detail="키워드를 찾을 수 없습니다")

    await db.delete(keyword)
    await db.commit()

    return {"success": True, "message": "키워드가 삭제되었습니다"}


# ==================== Dashboard Stats ====================

@router.get("/dashboard")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """대시보드 통계"""
    user_id = str(current_user.id)

    # 블로그 통계
    total_result = await db.execute(
        select(func.count()).select_from(NaverBlog).where(NaverBlog.user_id == user_id)
    )
    total_blogs = total_result.scalar() or 0

    contact_result = await db.execute(
        select(func.count()).select_from(NaverBlog).where(and_(
            NaverBlog.user_id == user_id,
            NaverBlog.has_contact == True
        ))
    )
    with_contact = contact_result.scalar() or 0

    # 등급별 통계
    grades = {}
    for grade in LeadGrade:
        grade_result = await db.execute(
            select(func.count()).select_from(NaverBlog).where(and_(
                NaverBlog.user_id == user_id,
                NaverBlog.lead_grade == grade
            ))
        )
        grades[grade.value] = grade_result.scalar() or 0

    # 캠페인 통계
    campaign_result = await db.execute(
        select(func.count()).select_from(EmailCampaign).where(and_(
            EmailCampaign.user_id == user_id,
            EmailCampaign.status == CampaignStatus.ACTIVE
        ))
    )
    active_campaigns = campaign_result.scalar() or 0

    # 이메일 통계
    sender = EmailSenderService(db)
    email_stats = await sender.get_sending_stats(user_id)

    return {
        "blogs": {
            "total": total_blogs,
            "with_contact": with_contact,
            "grades": grades
        },
        "campaigns": {
            "active": active_campaigns
        },
        "email": email_stats
    }


# ==================== Unsubscribe APIs (Public) ====================

class UnsubscribeRequest(BaseModel):
    email: str
    reason: Optional[str] = None


@router.get("/unsubscribe/{tracking_id}")
async def unsubscribe_page(
    tracking_id: str,
    db: AsyncSession = Depends(get_db)
):
    """수신거부 페이지 (HTML 반환)"""
    result = await db.execute(
        select(EmailLog).where(EmailLog.tracking_id == tracking_id)
    )
    log = result.scalar_one_or_none()

    if not log:
        return Response(
            content="""
            <!DOCTYPE html>
            <html lang="ko">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>유효하지 않은 링크</title>
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                           display: flex; align-items: center; justify-content: center;
                           min-height: 100vh; margin: 0; background: #f5f5f5; }
                    .container { text-align: center; padding: 40px; background: white;
                                border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 400px; }
                    h1 { color: #333; margin-bottom: 16px; }
                    p { color: #666; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>유효하지 않은 링크</h1>
                    <p>이 수신거부 링크는 유효하지 않거나 이미 처리되었습니다.</p>
                </div>
            </body>
            </html>
            """,
            media_type="text/html"
        )

    # 이미 수신거부된 경우
    if log.status == EmailStatus.UNSUBSCRIBED:
        return Response(
            content=f"""
            <!DOCTYPE html>
            <html lang="ko">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>수신거부 완료</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                           display: flex; align-items: center; justify-content: center;
                           min-height: 100vh; margin: 0; background: #f5f5f5; }}
                    .container {{ text-align: center; padding: 40px; background: white;
                                border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 400px; }}
                    h1 {{ color: #22c55e; margin-bottom: 16px; }}
                    p {{ color: #666; }}
                    .check {{ font-size: 48px; margin-bottom: 16px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="check">✓</div>
                    <h1>이미 처리됨</h1>
                    <p>{log.to_email} 주소는 이미 수신거부 처리되었습니다.</p>
                </div>
            </body>
            </html>
            """,
            media_type="text/html"
        )

    # 수신거부 폼 표시
    return Response(
        content=f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>수신거부</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                       display: flex; align-items: center; justify-content: center;
                       min-height: 100vh; margin: 0; background: #f5f5f5; padding: 20px; box-sizing: border-box; }}
                .container {{ text-align: center; padding: 40px; background: white;
                            border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 450px; width: 100%; }}
                h1 {{ color: #333; margin-bottom: 8px; font-size: 24px; }}
                .email {{ color: #666; margin-bottom: 24px; font-size: 14px; }}
                .reasons {{ text-align: left; margin-bottom: 24px; }}
                .reason {{ display: block; margin: 12px 0; padding: 12px; border: 1px solid #e5e5e5;
                          border-radius: 8px; cursor: pointer; transition: all 0.2s; }}
                .reason:hover {{ border-color: #3b82f6; background: #f0f7ff; }}
                .reason input {{ margin-right: 8px; }}
                .btn {{ background: #ef4444; color: white; border: none; padding: 14px 28px;
                       border-radius: 8px; font-size: 16px; cursor: pointer; width: 100%;
                       transition: background 0.2s; }}
                .btn:hover {{ background: #dc2626; }}
                .btn:disabled {{ background: #ccc; cursor: not-allowed; }}
                .note {{ font-size: 12px; color: #999; margin-top: 16px; }}
                .success {{ display: none; }}
                .success.show {{ display: block; }}
                .form {{ display: block; }}
                .form.hide {{ display: none; }}
                .check {{ font-size: 48px; margin-bottom: 16px; color: #22c55e; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="form" id="form">
                    <h1>이메일 수신거부</h1>
                    <p class="email">{log.to_email}</p>

                    <div class="reasons">
                        <label class="reason">
                            <input type="radio" name="reason" value="not_interested">
                            관심 없는 내용입니다
                        </label>
                        <label class="reason">
                            <input type="radio" name="reason" value="too_frequent">
                            이메일을 너무 자주 받습니다
                        </label>
                        <label class="reason">
                            <input type="radio" name="reason" value="not_subscribed">
                            구독한 적이 없습니다
                        </label>
                        <label class="reason">
                            <input type="radio" name="reason" value="other" checked>
                            기타
                        </label>
                    </div>

                    <button class="btn" onclick="unsubscribe()">수신거부</button>
                    <p class="note">수신거부 처리 후에는 더 이상 이메일을 받지 않습니다.</p>
                </div>

                <div class="success" id="success">
                    <div class="check">✓</div>
                    <h1>수신거부 완료</h1>
                    <p class="email">{log.to_email}</p>
                    <p>더 이상 이메일을 받지 않습니다.</p>
                </div>
            </div>

            <script>
                async function unsubscribe() {{
                    const reason = document.querySelector('input[name="reason"]:checked')?.value || 'other';
                    const btn = document.querySelector('.btn');
                    btn.disabled = true;
                    btn.textContent = '처리 중...';

                    try {{
                        const response = await fetch('/api/v1/outreach/unsubscribe/{tracking_id}', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify({{ email: '{log.to_email}', reason: reason }})
                        }});

                        if (response.ok) {{
                            document.getElementById('form').classList.add('hide');
                            document.getElementById('success').classList.add('show');
                        }} else {{
                            alert('처리 중 오류가 발생했습니다. 다시 시도해주세요.');
                            btn.disabled = false;
                            btn.textContent = '수신거부';
                        }}
                    }} catch (e) {{
                        alert('처리 중 오류가 발생했습니다.');
                        btn.disabled = false;
                        btn.textContent = '수신거부';
                    }}
                }}
            </script>
        </body>
        </html>
        """,
        media_type="text/html"
    )


@router.post("/unsubscribe/{tracking_id}")
async def process_unsubscribe(
    tracking_id: str,
    request: UnsubscribeRequest,
    db: AsyncSession = Depends(get_db)
):
    """수신거부 처리"""
    result = await db.execute(
        select(EmailLog).where(EmailLog.tracking_id == tracking_id)
    )
    log = result.scalar_one_or_none()

    if not log:
        raise HTTPException(status_code=404, detail="유효하지 않은 링크입니다")

    # 이메일 로그 상태 업데이트
    log.status = EmailStatus.UNSUBSCRIBED
    log.error_message = f"수신거부 사유: {request.reason}"

    # 해당 블로그 상태 업데이트
    if log.blog_id:
        blog_result = await db.execute(
            select(NaverBlog).where(NaverBlog.id == log.blog_id)
        )
        blog = blog_result.scalar_one_or_none()
        if blog:
            blog.status = BlogStatus.NOT_INTERESTED
            blog.notes = f"수신거부 ({request.reason})"

    await db.commit()

    return {"success": True, "message": "수신거부 처리되었습니다"}


# ==================== Scheduler APIs ====================

@router.post("/scheduler/start")
async def start_scheduler(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """스케줄러 시작"""
    from app.services.outreach_scheduler import get_outreach_scheduler

    scheduler = get_outreach_scheduler(db, str(current_user.id))
    result = await scheduler.start(str(current_user.id))
    return result


@router.post("/scheduler/stop")
async def stop_scheduler(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """스케줄러 중지"""
    from app.services.outreach_scheduler import get_outreach_scheduler

    scheduler = get_outreach_scheduler(db, str(current_user.id))
    result = await scheduler.stop()
    return result


@router.get("/scheduler/status")
async def get_scheduler_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """스케줄러 상태 조회"""
    from app.services.outreach_scheduler import get_outreach_scheduler

    scheduler = get_outreach_scheduler(db, str(current_user.id))
    return scheduler.get_status()
