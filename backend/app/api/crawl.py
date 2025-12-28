"""
Blog Crawl API
블로그 글 가져오기 및 원클릭 자동화 API
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from pydantic import BaseModel, HttpUrl
from datetime import datetime, timedelta

from app.db.database import get_db
from app.api.deps import get_current_user, get_current_user_optional
from app.models import User, NaverConnection
from app.services.blog_crawler import blog_crawler
from app.services.naver_blog_service import naver_blog_service
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
    category_no: Optional[str] = None  # 네이버 블로그 카테고리
    ai_provider: str = "gpt"  # gpt, gemini, claude
    ai_model: str = "gpt-4o-mini"
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
    # 네이버 발행 결과
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
    """
    원클릭 자동화: URL → 크롤링 → AI 리라이트 → 네이버 블로그 임시저장

    **동작 순서:**
    1. 입력된 블로그 URL에서 글+이미지 크롤링
    2. AI로 콘텐츠 리라이트
    3. 네이버 블로그에 비공개(임시저장)로 발행

    **필수 조건:**
    - 네이버 블로그 연동 필요
    - 로그인 필요

    **참고:**
    - 이미지는 자동 발행되지 않습니다 (네이버 API 제한)
    - 이미지 URL 목록이 반환되므로 수동으로 추가하세요
    """
    import traceback

    try:
        # 1. 네이버 연동 확인
        conn_result = await db.execute(
            select(NaverConnection).where(NaverConnection.user_id == current_user.id)
        )
        connection = conn_result.scalar_one_or_none()

        if not connection:
            raise HTTPException(
                status_code=400,
                detail="네이버 블로그 연동이 필요합니다. 설정에서 네이버 계정을 연동해주세요."
            )

        # 토큰 만료 확인 및 갱신
        if datetime.utcnow() >= connection.token_expires_at:
            token_response = await naver_blog_service.refresh_access_token(
                connection.refresh_token
            )
            if not token_response:
                raise HTTPException(
                    status_code=401,
                    detail="네이버 토큰이 만료되었습니다. 다시 연동해주세요."
                )
            connection.access_token = token_response.get("access_token")
            expires_in = token_response.get("expires_in", 3600)
            connection.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            await db.commit()

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

        # 4. 네이버 블로그에 임시저장 (비공개)
        category_no = None
        if request.category_no:
            try:
                category_no = int(request.category_no)
            except ValueError:
                pass

        if not category_no and connection.default_category_no:
            try:
                category_no = int(connection.default_category_no)
            except ValueError:
                pass

        naver_result = await naver_blog_service.create_post(
            access_token=connection.access_token,
            title=rewritten_title or "제목 없음",
            content=rewritten_content,
            category_no=category_no,
            open_type="2",  # 비공개 (임시저장)
            tag=None
        )

        if not naver_result:
            return OneClickResponse(
                success=False,
                message="네이버 블로그 임시저장 실패",
                original_title=original_title,
                original_content_length=len(original_content),
                images_count=len(images),
                rewritten_title=rewritten_title,
                rewritten_content=rewritten_content,
                rewritten_content_length=len(rewritten_content),
                images=[
                    ImageInfo(
                        url=img.get("url", ""),
                        alt=img.get("alt", ""),
                        caption=img.get("caption", ""),
                    )
                    for img in images
                ],
                error="네이버 블로그 API 오류가 발생했습니다."
            )

        naver_post_id = naver_result.get("logNo")
        naver_post_url = f"{connection.blog_url}/{naver_post_id}" if naver_post_id else None

        return OneClickResponse(
            success=True,
            message="원클릭 자동화 완료! 네이버 블로그에 임시저장되었습니다.",
            original_title=original_title,
            original_content_length=len(original_content),
            images_count=len(images),
            rewritten_title=rewritten_title,
            rewritten_content=rewritten_content,
            rewritten_content_length=len(rewritten_content),
            naver_post_id=naver_post_id,
            naver_post_url=naver_post_url,
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
