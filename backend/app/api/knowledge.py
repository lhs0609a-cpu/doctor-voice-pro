"""
네이버 지식인 자동 답변 API
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.knowledge import (
    QuestionStatus, AnswerStatus, AnswerTone, Urgency
)
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["지식인"])


# ==================== Schemas ====================

class KeywordCreate(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=100)
    category: Optional[str] = None
    sub_category: Optional[str] = None
    priority: int = Field(default=1, ge=1, le=5)


class KeywordUpdate(BaseModel):
    keyword: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    priority: Optional[int] = Field(default=None, ge=1, le=5)
    is_active: Optional[bool] = None


class KeywordResponse(BaseModel):
    id: str
    keyword: str
    category: Optional[str]
    sub_category: Optional[str]
    is_active: bool
    priority: int
    question_count: int
    answer_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class QuestionResponse(BaseModel):
    id: str
    naver_question_id: Optional[str]
    title: str
    content: Optional[str]
    category: Optional[str]
    url: Optional[str]
    author_name: Optional[str]
    view_count: int
    answer_count: int
    reward_points: int
    matched_keywords: Optional[List[str]]
    relevance_score: float
    urgency: str
    status: str
    question_date: Optional[datetime]
    collected_at: datetime

    class Config:
        from_attributes = True


class AnswerGenerate(BaseModel):
    question_id: str
    tone: Optional[AnswerTone] = AnswerTone.PROFESSIONAL
    include_promotion: bool = True
    blog_link: Optional[str] = None
    place_link: Optional[str] = None
    template_id: Optional[str] = None


class AnswerUpdate(BaseModel):
    edited_content: Optional[str] = None
    tone: Optional[AnswerTone] = None
    include_promotion: Optional[bool] = None
    blog_link: Optional[str] = None
    place_link: Optional[str] = None


class AnswerResponse(BaseModel):
    id: str
    question_id: str
    content: str
    edited_content: Optional[str]
    final_content: Optional[str]
    tone: str
    include_promotion: bool
    promotion_text: Optional[str]
    blog_link: Optional[str]
    place_link: Optional[str]
    quality_score: Optional[float]
    professionalism_score: Optional[float]
    readability_score: Optional[float]
    status: str
    is_chosen: bool
    posted_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    template_content: str = Field(..., min_length=10)
    category: Optional[str] = None
    tone: Optional[AnswerTone] = AnswerTone.PROFESSIONAL
    question_patterns: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    variables: Optional[List[dict]] = None


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    template_content: Optional[str] = None
    category: Optional[str] = None
    tone: Optional[AnswerTone] = None
    question_patterns: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    variables: Optional[List[dict]] = None
    is_active: Optional[bool] = None


class TemplateResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    category: Optional[str]
    template_content: str
    tone: str
    question_patterns: Optional[List[str]]
    keywords: Optional[List[str]]
    variables: Optional[List[dict]]
    usage_count: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SettingsUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    auto_collect: Optional[bool] = None
    auto_generate: Optional[bool] = None
    min_relevance_score: Optional[float] = Field(default=None, ge=0, le=100)
    daily_collect_limit: Optional[int] = Field(default=None, ge=1, le=1000)
    daily_answer_limit: Optional[int] = Field(default=None, ge=1, le=100)
    working_hours: Optional[dict] = None
    exclude_keywords: Optional[List[str]] = None
    default_tone: Optional[AnswerTone] = None
    default_include_promotion: Optional[bool] = None
    default_blog_link: Optional[str] = None
    default_place_link: Optional[str] = None
    notification_enabled: Optional[bool] = None


class SettingsResponse(BaseModel):
    id: str
    is_enabled: bool
    auto_collect: bool
    auto_generate: bool
    min_relevance_score: float
    daily_collect_limit: int
    daily_answer_limit: int
    working_hours: Optional[dict]
    exclude_keywords: Optional[List[str]]
    default_tone: str
    default_include_promotion: bool
    default_blog_link: Optional[str]
    default_place_link: Optional[str]
    notification_enabled: bool
    total_collected: int
    total_answered: int
    total_chosen: int

    class Config:
        from_attributes = True


class DashboardResponse(BaseModel):
    today_collected: int
    pending_questions: int
    high_relevance_questions: int
    draft_answers: int
    week_answered: int
    total_chosen: int
    summary: dict


# ==================== 키워드 API ====================

@router.get("/keywords", response_model=List[KeywordResponse])
async def get_keywords(
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """모니터링 키워드 목록 조회"""
    service = KnowledgeService(db)
    keywords = await service.get_keywords(str(current_user.id), is_active)
    return keywords


@router.post("/keywords", response_model=KeywordResponse)
async def create_keyword(
    data: KeywordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """모니터링 키워드 추가"""
    service = KnowledgeService(db)
    keyword = await service.create_keyword(
        user_id=str(current_user.id),
        keyword=data.keyword,
        category=data.category,
        sub_category=data.sub_category,
        priority=data.priority
    )
    return keyword


@router.put("/keywords/{keyword_id}", response_model=KeywordResponse)
async def update_keyword(
    keyword_id: str,
    data: KeywordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """키워드 수정"""
    service = KnowledgeService(db)
    keyword = await service.update_keyword(
        keyword_id=keyword_id,
        user_id=str(current_user.id),
        **data.model_dump(exclude_unset=True)
    )
    if not keyword:
        raise HTTPException(status_code=404, detail="키워드를 찾을 수 없습니다")
    return keyword


@router.delete("/keywords/{keyword_id}")
async def delete_keyword(
    keyword_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """키워드 삭제"""
    service = KnowledgeService(db)
    success = await service.delete_keyword(keyword_id, str(current_user.id))
    if not success:
        raise HTTPException(status_code=404, detail="키워드를 찾을 수 없습니다")
    return {"message": "키워드가 삭제되었습니다"}


# ==================== 질문 API ====================

@router.get("/questions", response_model=List[QuestionResponse])
async def get_questions(
    status: Optional[QuestionStatus] = None,
    min_relevance: Optional[float] = Query(None, ge=0, le=100),
    keyword: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """수집된 질문 목록 조회"""
    service = KnowledgeService(db)
    questions = await service.get_questions(
        user_id=str(current_user.id),
        status=status,
        min_relevance=min_relevance,
        keyword=keyword,
        limit=limit,
        offset=offset
    )
    return questions


@router.get("/questions/{question_id}", response_model=QuestionResponse)
async def get_question(
    question_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """질문 상세 조회"""
    service = KnowledgeService(db)
    question = await service.get_question(question_id, str(current_user.id))
    if not question:
        raise HTTPException(status_code=404, detail="질문을 찾을 수 없습니다")
    return question


class CollectRequest(BaseModel):
    """질문 수집 요청"""
    keywords: Optional[List[str]] = None
    limit: int = Field(default=50, ge=1, le=100)
    use_crawler: bool = Field(default=True, description="실제 크롤링 사용 여부")
    min_reward_points: int = Field(default=0, ge=0, description="최소 내공 점수")


@router.post("/questions/collect")
async def collect_questions(
    request: Optional[CollectRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    질문 수집 실행

    네이버 지식인에서 등록된 키워드로 질문을 검색하여 수집합니다.

    - **keywords**: 검색할 키워드 목록 (없으면 등록된 키워드 사용)
    - **limit**: 최대 수집 개수 (기본 50)
    - **use_crawler**: 실제 크롤링 사용 여부 (False면 테스트용 시뮬레이션)
    - **min_reward_points**: 최소 내공 점수 필터
    """
    service = KnowledgeService(db)

    if request:
        result = await service.collect_questions(
            user_id=str(current_user.id),
            keywords=request.keywords,
            limit=request.limit,
            use_crawler=request.use_crawler,
            min_reward_points=request.min_reward_points,
        )
    else:
        result = await service.collect_questions(
            user_id=str(current_user.id),
        )

    return result


@router.put("/questions/{question_id}/status")
async def update_question_status(
    question_id: str,
    status: QuestionStatus,
    skip_reason: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """질문 상태 변경"""
    service = KnowledgeService(db)
    question = await service.update_question_status(
        question_id=question_id,
        user_id=str(current_user.id),
        status=status,
        skip_reason=skip_reason
    )
    if not question:
        raise HTTPException(status_code=404, detail="질문을 찾을 수 없습니다")
    return {"message": "상태가 변경되었습니다", "status": status}


# ==================== 답변 API ====================

@router.post("/answers/generate", response_model=AnswerResponse)
async def generate_answer(
    data: AnswerGenerate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI 답변 생성"""
    service = KnowledgeService(db)
    answer = await service.generate_answer(
        question_id=data.question_id,
        user_id=str(current_user.id),
        tone=data.tone,
        include_promotion=data.include_promotion,
        blog_link=data.blog_link,
        place_link=data.place_link,
        template_id=data.template_id
    )
    if not answer:
        raise HTTPException(status_code=404, detail="질문을 찾을 수 없습니다")
    return answer


@router.get("/answers", response_model=List[AnswerResponse])
async def get_answers(
    status: Optional[AnswerStatus] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """답변 목록 조회"""
    service = KnowledgeService(db)
    answers = await service.get_answers(
        user_id=str(current_user.id),
        status=status,
        limit=limit,
        offset=offset
    )
    return answers


@router.get("/answers/{answer_id}", response_model=AnswerResponse)
async def get_answer(
    answer_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """답변 상세 조회"""
    service = KnowledgeService(db)
    answer = await service.get_answer(answer_id, str(current_user.id))
    if not answer:
        raise HTTPException(status_code=404, detail="답변을 찾을 수 없습니다")
    return answer


@router.put("/answers/{answer_id}", response_model=AnswerResponse)
async def update_answer(
    answer_id: str,
    data: AnswerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """답변 수정"""
    service = KnowledgeService(db)
    answer = await service.update_answer(
        answer_id=answer_id,
        user_id=str(current_user.id),
        **data.model_dump(exclude_unset=True)
    )
    if not answer:
        raise HTTPException(status_code=404, detail="답변을 찾을 수 없습니다")
    return answer


@router.post("/answers/{answer_id}/approve", response_model=AnswerResponse)
async def approve_answer(
    answer_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """답변 승인"""
    service = KnowledgeService(db)
    answer = await service.approve_answer(answer_id, str(current_user.id))
    if not answer:
        raise HTTPException(status_code=404, detail="답변을 찾을 수 없습니다")
    return answer


@router.post("/answers/{answer_id}/reject")
async def reject_answer(
    answer_id: str,
    reason: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """답변 반려"""
    service = KnowledgeService(db)
    answer = await service.reject_answer(answer_id, str(current_user.id), reason)
    if not answer:
        raise HTTPException(status_code=404, detail="답변을 찾을 수 없습니다")
    return {"message": "답변이 반려되었습니다"}


@router.post("/answers/{answer_id}/mark-posted", response_model=AnswerResponse)
async def mark_answer_posted(
    answer_id: str,
    naver_answer_id: Optional[str] = None,
    naver_answer_url: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """답변 등록 완료 처리"""
    service = KnowledgeService(db)
    answer = await service.mark_as_posted(
        answer_id=answer_id,
        user_id=str(current_user.id),
        naver_answer_id=naver_answer_id,
        naver_answer_url=naver_answer_url
    )
    if not answer:
        raise HTTPException(status_code=404, detail="답변을 찾을 수 없습니다")
    return answer


# ==================== 템플릿 API ====================

@router.get("/templates", response_model=List[TemplateResponse])
async def get_templates(
    category: Optional[str] = None,
    is_active: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """템플릿 목록 조회"""
    service = KnowledgeService(db)
    templates = await service.get_templates(
        user_id=str(current_user.id),
        category=category,
        is_active=is_active
    )
    return templates


@router.post("/templates", response_model=TemplateResponse)
async def create_template(
    data: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """템플릿 생성"""
    service = KnowledgeService(db)
    template = await service.create_template(
        user_id=str(current_user.id),
        name=data.name,
        template_content=data.template_content,
        category=data.category,
        tone=data.tone,
        question_patterns=data.question_patterns,
        keywords=data.keywords,
        variables=data.variables
    )
    return template


@router.put("/templates/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    data: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """템플릿 수정"""
    service = KnowledgeService(db)
    template = await service.update_template(
        template_id=template_id,
        user_id=str(current_user.id),
        **data.model_dump(exclude_unset=True)
    )
    if not template:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다")
    return template


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """템플릿 삭제"""
    service = KnowledgeService(db)
    success = await service.delete_template(template_id, str(current_user.id))
    if not success:
        raise HTTPException(status_code=404, detail="템플릿을 찾을 수 없습니다")
    return {"message": "템플릿이 삭제되었습니다"}


# ==================== 설정 API ====================

@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """자동 답변 설정 조회"""
    service = KnowledgeService(db)
    settings = await service.get_settings(str(current_user.id))
    if not settings:
        # 기본 설정 생성
        settings = await service.update_settings(str(current_user.id))
    return settings


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(
    data: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """자동 답변 설정 업데이트"""
    service = KnowledgeService(db)
    settings = await service.update_settings(
        user_id=str(current_user.id),
        **data.model_dump(exclude_unset=True)
    )
    return settings


# ==================== 대시보드 API ====================

@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """대시보드 통계"""
    service = KnowledgeService(db)
    stats = await service.get_dashboard_stats(str(current_user.id))
    return stats


@router.get("/dashboard/top-questions", response_model=List[QuestionResponse])
async def get_top_questions(
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """상위 관련성 질문 조회"""
    service = KnowledgeService(db)
    questions = await service.get_top_questions(str(current_user.id), limit)
    return questions


# ==================== 자동화 API ====================

class SchedulerStartRequest(BaseModel):
    """스케줄러 시작 요청"""
    pass


class LoginRequest(BaseModel):
    """네이버 로그인 요청"""
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class PostAnswerRequest(BaseModel):
    """답변 등록 요청"""
    answer_id: str


class PostMultipleRequest(BaseModel):
    """다중 답변 등록 요청"""
    limit: int = Field(default=5, ge=1, le=10)
    delay_between: int = Field(default=30, ge=10, le=120)


@router.post("/scheduler/start")
async def start_scheduler(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    자동화 스케줄러 시작

    설정에 따라 질문 수집, 답변 생성을 자동으로 실행합니다.
    """
    from app.services.kin_scheduler import get_scheduler

    scheduler = await get_scheduler(db, str(current_user.id))
    await scheduler.start(str(current_user.id))

    return {"message": "스케줄러가 시작되었습니다"}


@router.post("/scheduler/stop")
async def stop_scheduler(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """자동화 스케줄러 중지"""
    from app.services.kin_scheduler import get_scheduler

    scheduler = await get_scheduler(db, str(current_user.id))
    await scheduler.stop()

    return {"message": "스케줄러가 중지되었습니다"}


@router.get("/scheduler/status")
async def get_scheduler_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """스케줄러 상태 조회"""
    from app.services.kin_scheduler import get_scheduler

    scheduler = await get_scheduler(db, str(current_user.id))
    status = await scheduler.get_job_status(str(current_user.id))

    return status


@router.post("/scheduler/run-collect")
async def run_collection_job(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """질문 수집 작업 수동 실행"""
    from app.services.kin_scheduler import get_scheduler

    scheduler = await get_scheduler(db, str(current_user.id))
    result = await scheduler.run_collection_job(str(current_user.id))

    return result


@router.post("/scheduler/run-generate")
async def run_generation_job(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """답변 생성 작업 수동 실행"""
    from app.services.kin_scheduler import get_scheduler

    scheduler = await get_scheduler(db, str(current_user.id))
    result = await scheduler.run_generation_job(str(current_user.id))

    return result


# ==================== 자동 등록 API ====================

@router.post("/poster/login")
async def poster_login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    네이버 로그인 (Playwright)

    답변 자동 등록을 위해 네이버에 로그인합니다.
    """
    from app.services.kin_poster import poster_manager

    try:
        poster = await poster_manager.get_poster(db, str(current_user.id))
        await poster.initialize()
        success = await poster.login(request.username, request.password)

        if success:
            await poster.save_cookies()
            return {"success": True, "message": "로그인 성공"}
        else:
            return {"success": False, "message": "로그인 실패"}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/poster/logout")
async def poster_logout(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """네이버 로그아웃 (브라우저 종료)"""
    from app.services.kin_poster import poster_manager

    poster = await poster_manager.get_poster(db, str(current_user.id))
    await poster.close()

    return {"message": "로그아웃 완료"}


@router.post("/poster/post-answer")
async def post_single_answer(
    request: PostAnswerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    단일 답변 등록

    승인된 답변을 네이버 지식인에 등록합니다.
    """
    from app.services.kin_poster import poster_manager

    try:
        poster = await poster_manager.get_poster(db, str(current_user.id))

        # 쿠키로 로그인 시도
        if not poster._logged_in:
            await poster.initialize()
            if not await poster.load_cookies():
                raise HTTPException(
                    status_code=401,
                    detail="로그인이 필요합니다. /poster/login을 먼저 호출하세요."
                )

        result = await poster.post_answer(request.answer_id, str(current_user.id))
        return result

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/poster/post-multiple")
async def post_multiple_answers(
    request: PostMultipleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    다중 답변 등록

    승인된 답변들을 순차적으로 네이버 지식인에 등록합니다.
    """
    from app.services.kin_poster import poster_manager

    try:
        poster = await poster_manager.get_poster(db, str(current_user.id))

        # 쿠키로 로그인 시도
        if not poster._logged_in:
            await poster.initialize()
            if not await poster.load_cookies():
                raise HTTPException(
                    status_code=401,
                    detail="로그인이 필요합니다. /poster/login을 먼저 호출하세요."
                )

        result = await poster.post_multiple_answers(
            user_id=str(current_user.id),
            limit=request.limit,
            delay_between=request.delay_between
        )
        return result

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/poster/status")
async def get_poster_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """포스터 상태 조회"""
    from app.services.kin_poster import poster_manager

    try:
        poster = await poster_manager.get_poster(db, str(current_user.id))

        return {
            "initialized": poster._browser is not None,
            "logged_in": poster._logged_in,
        }
    except:
        return {
            "initialized": False,
            "logged_in": False,
        }
