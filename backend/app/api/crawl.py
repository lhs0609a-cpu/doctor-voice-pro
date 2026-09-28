"""
Blog Crawl API
블로그 글 가져오기 및 원클릭 자동화 API
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from pydantic import BaseModel, HttpUrl

from app.db.database import get_db
from app.api.deps import get_current_user, get_current_user_optional
from app.models import User
from app.services.blog_crawler import blog_crawler
from app.services.ai_service import AIService


router = APIRouter()


class CrawlRequest(BaseModel):
    """블로그 크롤링 요청"""
    url: str


class ImageInfo(BaseModel):
    """이미지 정보"""
    url: str
    alt: Optional[str] = ""
    caption: Optional[str] = ""
    width: Optional[str] = ""
    height: Optional[str] = ""


class CrawlResponse(BaseModel):
    """블로그 크롤링 응답"""
    success: bool
    title: Optional[str] = None
    content: Optional[str] = None
    platform: Optional[str] = None
    author: Optional[str] = None
    date: Optional[str] = None
    url: Optional[str] = None
    images: Optional[List[ImageInfo]] = None
    error: Optional[str] = None


@router.post("/blog", response_model=CrawlResponse)
async def crawl_blog(
    request: CrawlRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    블로그 URL에서 글 내용을 가져옵니다.

    **지원 플랫폼:**
    - 네이버 블로그 (blog.naver.com)
    - 티스토리 (*.tistory.com)
    - 기타 일반 웹페이지

    **사용법:**
    1. 블로그 글 URL 입력
    2. 제목과 본문 자동 추출
    3. 추출된 내용으로 리라이트 가능

    **예시:**
    ```
    POST /api/v1/crawl/blog
    {
        "url": "https://blog.naver.com/example/123456789"
    }
    ```

    **응답:**
    ```json
    {
        "success": true,
        "title": "블로그 글 제목",
        "content": "블로그 본문 내용...",
        "platform": "naver",
        "author": "작성자",
        "date": "2024.01.01"
    }
    ```
    """
    if not request.url:
        raise HTTPException(
            status_code=400,
            detail="URL을 입력해주세요."
        )

    # URL 유효성 검사
    url = request.url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # 크롤링 실행
    result = await blog_crawler.crawl(url)

    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "블로그 글을 가져오는데 실패했습니다.")
        )

    # 이미지 정보 변환
    images = None
    if result.get("images"):
        images = [
            ImageInfo(
                url=img.get("url", ""),
                alt=img.get("alt", ""),
                caption=img.get("caption", ""),
                width=str(img.get("width", "")),
                height=str(img.get("height", "")),
            )
            for img in result["images"]
        ]

    return CrawlResponse(
        success=True,
        title=result.get("title", ""),
        content=result.get("content", ""),
        platform=result.get("platform", ""),
        author=result.get("author", ""),
        date=result.get("date", ""),
        url=url,
        images=images
    )


@router.get("/supported-platforms")
async def get_supported_platforms():
    """
    지원하는 블로그 플랫폼 목록
    """
    return {
        "platforms": [
            {
                "name": "네이버 블로그",
                "domain": "blog.naver.com",
                "support_level": "full",
                "description": "제목, 본문, 작성자, 날짜 추출 지원"
            },
            {
                "name": "티스토리",
                "domain": "*.tistory.com",
                "support_level": "full",
                "description": "제목, 본문 추출 지원"
            },
            {
                "name": "기타 웹페이지",
                "domain": "*",
                "support_level": "partial",
                "description": "일반적인 웹페이지에서 본문 추출 시도"
            }
        ]
    }


# ==================== 원클릭 자동화 ====================

class OneClickRequest(BaseModel):
    """원클릭 자동화 요청"""
    url: str
    # 어느 캠페인의 원고로 넣을지. 비우면 가장 최근에 손댄 캠페인에 넣는다.
    campaign_id: Optional[str] = None
    category_no: Optional[str] = None  # (옛 네이버 API 경로에서 쓰던 값 — 지금은 쓰지 않는다)
    ai_provider: str = "gemini"
    ai_model: Optional[str] = None  # 비우면 서버 기본 모델(gemini-2.5-flash)
    target_length: int = 1800
    framework: str = "관심유도형"
    persuasion_level: int = 4


class OneClickResponse(BaseModel):
    """원클릭 자동화 응답"""
    success: bool
    message: str
    # 크롤링 결과
    original_title: Optional[str] = None
    original_content_length: Optional[int] = None
    images_count: Optional[int] = None
    # 리라이트 결과
    rewritten_title: Optional[str] = None
    rewritten_content: Optional[str] = None
    rewritten_content_length: Optional[int] = None
    # 원고로 저장한 결과 — 여기서부터는 예약발행(실행기)이 이어받는다
    draft_id: Optional[str] = None
    draft_status: Optional[str] = None      # ready | needs_review
    campaign_id: Optional[str] = None
    campaign_name: Optional[str] = None
    # (옛 네이버 오픈 API 경로의 잔재. 지금은 항상 비어 있다)
    naver_post_id: Optional[str] = None
    naver_post_url: Optional[str] = None
    # 이미지 URL 목록 (사용자가 수동으로 추가해야 함)
    images: Optional[List[ImageInfo]] = None
    error: Optional[str] = None


@router.post("/one-click", response_model=OneClickResponse)
async def one_click_automation(
    request: OneClickRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """원클릭 자동화: URL → 크롤링 → AI 리라이트 → **원고로 저장**

    예전에는 여기서 네이버 오픈 API(blog/writePost.json)로 임시저장까지 했다. 그 길은
    두 군데서 막혀 있었다 — 연동 콜백 주소가 localhost 로 박혀 있어 운영에서는 연동이
    끝나지 않고, 그 API 자체가 더 이상 열리지 않는다. 그래서 **아무도 성공할 수 없는
    버튼**이었다(2026-09-28: 연동 기록 0건, 누르면 '네이버 블로그 연동이 필요합니다').

    이 제품이 실제로 글을 올리는 길은 PC 실행기다. 그래서 여기서는 원고까지만 만들고,
    발행은 예약발행이 이어받는다. 사용자에게는 버튼 하나인 것이 그대로다.

    **동작 순서:**
    1. 입력한 블로그 URL 에서 글+이미지 가져오기
    2. AI 로 리라이트
    3. 캠페인의 원고로 저장(검수까지) → 예약발행에서 시각만 고르면 올라간다
    """
    import traceback
    from app.models.campaign import Campaign, Client, Draft
    from app.services import campaign_writer as writer

    try:
        # 1. 어느 캠페인의 원고로 넣을지 — 비우면 가장 최근에 손댄 캠페인
        uid = str(current_user.id)
        if request.campaign_id:
            campaign = (await db.execute(select(Campaign).where(
                Campaign.id == request.campaign_id, Campaign.user_id == uid))).scalars().first()
            if not campaign:
                raise HTTPException(status_code=404, detail="캠페인을 찾을 수 없습니다")
        else:
            campaign = (await db.execute(select(Campaign).where(Campaign.user_id == uid)
                                         .order_by(Campaign.updated_at.desc()))).scalars().first()
        if not campaign:
            return OneClickResponse(
                success=False,
                message="원고를 넣을 곳이 없습니다",
                error="먼저 원스톱 자동화에서 병원과 블로그를 등록해 주세요. 그 다음 이 버튼이 원고를 거기에 넣습니다.")

        # 2. 블로그 글 크롤링
        url = request.url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        crawl_result = await blog_crawler.crawl(url)

        if not crawl_result["success"]:
            return OneClickResponse(
                success=False,
                message="블로그 크롤링 실패",
                error=crawl_result.get("error", "블로그 글을 가져오지 못했습니다.")
            )

        original_content = crawl_result.get("content", "")
        original_title = crawl_result.get("title", "")
        images = crawl_result.get("images", [])

        if len(original_content) < 50:
            return OneClickResponse(
                success=False,
                message="크롤링된 콘텐츠가 너무 짧습니다",
                error="본문이 50자 미만입니다. URL을 확인해주세요."
            )

        # 3. AI 리라이트
        ai_service = AIService()

        rewrite_prompt = f"""다음 블로그 글을 리라이트해주세요.

**원본 글:**
{original_content[:3000]}

**리라이트 요구사항:**
- 설득 프레임워크: {request.framework}
- 설득력 레벨: {request.persuasion_level}/5
- 목표 글자수: {request.target_length}자
- 의료법 준수 (과장/허위 광고 금지)
- 원본의 핵심 정보는 유지하되 표현을 새롭게

**출력 형식:**
제목: (새 제목)
---
(본문 내용)
"""

        system_prompt = """당신은 의료 블로그 전문 작가입니다.
- 의료법을 준수하면서 설득력 있는 글을 작성합니다.
- 과장/허위 광고는 절대 하지 않습니다.
- 전문성과 신뢰감을 주는 글을 작성합니다."""

        rewritten = await ai_service.generate_text(
            prompt=rewrite_prompt,
            max_tokens=4000,
            temperature=0.7,
            system_prompt=system_prompt,
            provider=request.ai_provider,
            model=request.ai_model
        )

        # 제목과 본문 분리
        rewritten_title = original_title
        rewritten_content = rewritten

        if "---" in rewritten:
            parts = rewritten.split("---", 1)
            title_part = parts[0].strip()
            if title_part.startswith("제목:"):
                rewritten_title = title_part.replace("제목:", "").strip()
            if len(parts) > 1:
                rewritten_content = parts[1].strip()

        # 4. 캠페인의 원고로 저장 — 예약발행이 여기서 이어받는다.
        #    원고 화면에서 손으로 넣은 글과 **똑같은 검사**를 거친다(의료광고 표현 자동 수정,
        #    병원 금칙어). 다른 문으로 들어왔다고 검수를 건너뛰면 그 글만 사고를 낸다.
        client = await db.get(Client, campaign.client_id)
        body_text = writer.reflow(rewritten_content)
        title_text, body_text, _blocks, fixes = writer.sanitize_blocks(None, rewritten_title or "제목 없음", body_text)
        checks = writer.run_static_checks(title_text, body_text, client.forbidden_words if client else [])
        if fixes:
            checks["auto_fixed"] = fixes[:30]
        checks["source_url"] = url
        draft = Draft(
            user_id=uid, client_id=campaign.client_id, campaign_id=campaign.id,
            source="crawl", title=title_text[:200], body=body_text,
            char_count=writer.count_chars(body_text),
            status="ready" if checks["ok"] else "needs_review", checks=checks,
        )
        db.add(draft)
        await db.commit()

        done = ("원고로 저장했습니다. 예약발행에서 시각만 고르면 그대로 올라갑니다."
                if draft.status == "ready"
                else "원고로 저장했습니다. 검수에 걸린 표현이 있어 확인이 필요합니다.")
        return OneClickResponse(
            success=True,
            message=done,
            original_title=original_title,
            original_content_length=len(original_content),
            images_count=len(images),
            rewritten_title=title_text,
            rewritten_content=body_text,
            rewritten_content_length=len(body_text),
            draft_id=draft.id,
            draft_status=draft.status,
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            images=[
                ImageInfo(
                    url=img.get("url", ""),
                    alt=img.get("alt", ""),
                    caption=img.get("caption", ""),
                )
                for img in images
            ]
        )

    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"❌ 원클릭 자동화 에러:\n{error_trace}")
        return OneClickResponse(
            success=False,
            message="원클릭 자동화 실패",
            error=str(e)
        )
