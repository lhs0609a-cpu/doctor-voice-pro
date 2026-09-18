"""
Export API
블로그 복붙용 문서 다운로드 API
"""

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict
from pydantic import BaseModel
from uuid import UUID
import os
import tempfile
import shutil

from app.db.database import get_db
from app.api.deps import get_current_user_optional
from app.models import User
from app.services.blog_exporter import blog_exporter
from app.services.image_analyzer import image_analyzer
from app.services.image_search import image_search_service
from app.services.ai_service import AIService


router = APIRouter()


class ExportRequest(BaseModel):
    """문서 내보내기 요청"""
    content: str
    title: Optional[str] = ""
    keywords: Optional[List[str]] = None
    emphasis_phrases: Optional[List[str]] = None
    images: Optional[List[Dict]] = None
    place_url: Optional[str] = None
    place_name: Optional[str] = None


@router.post("/docx")
async def export_to_docx(
    request: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    워드 문서로 내보내기 (네이버 블로그 복붙용)

    **사용법:**
    1. 생성된 .docx 파일 다운로드
    2. 파일 열기
    3. 전체 선택 (Ctrl+A)
    4. 복사 (Ctrl+C)
    5. 네이버 블로그 에디터에 붙여넣기 (Ctrl+V)

    **장점:**
    - ✅ 색상, 강조, 인용구 모두 유지
    - ✅ 이미지도 함께 복사됨
    - ✅ 100% 완벽한 스타일 재현
    """
    try:
        # DOCX 파일 생성
        docx_file = blog_exporter.export_to_docx(
            content=request.content,
            title=request.title,
            images=request.images,
            keywords=request.keywords,
            emphasis_phrases=request.emphasis_phrases,
            place_url=request.place_url,
            place_name=request.place_name,
        )

        # 파일명 생성 (한글 파일명 URL 인코딩 - RFC 5987)
        import urllib.parse

        filename = f"{request.title or 'blog_post'}.docx"
        filename = filename.replace(' ', '_').replace('/', '_')

        # URL 인코딩된 파일명 생성 (한글 지원)
        filename_encoded = urllib.parse.quote(filename)

        # 응답 반환
        return Response(
            content=docx_file.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                # RFC 5987: filename*=UTF-8''encoded_filename
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}"
            }
        )

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ DOCX 생성 에러:\n{error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"DOCX 생성 중 오류: {str(e)}\n상세: {error_trace[:500]}"
        )


@router.post("/html")
async def export_to_html(
    request: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    네이버 블로그 전용 HTML 생성

    **사용법:**
    1. HTML 복사
    2. 네이버 블로그 에디터에서 HTML 모드로 전환
    3. 붙여넣기

    **주의:**
    - 일부 스타일이 제한될 수 있음
    - 워드 문서(.docx) 방식 추천
    """
    try:
        html_content = blog_exporter.export_to_naver_html(
            content=request.content,
            title=request.title,
            keywords=request.keywords,
            emphasis_phrases=request.emphasis_phrases,
        )

        return {
            "html": html_content,
            "usage": "네이버 블로그 HTML 모드에 붙여넣기"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"HTML 생성 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/auto-export")
async def auto_export_with_ai_analysis(
    content: str,
    title: Optional[str] = "",
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    AI가 자동으로 키워드/강조점 분석 후 문서 생성

    **동작:**
    1. AI가 콘텐츠 분석
    2. 중요 키워드 추출
    3. 강조할 문구 선정
    4. 자동 스타일 적용
    5. DOCX 파일 생성
    """
    try:
        # AI 분석으로 키워드 및 강조 문구 추출
        keywords, emphasis_phrases = await _extract_with_ai(content, title)

        # DOCX 생성
        docx_file = blog_exporter.export_to_docx(
            content=content,
            title=title,
            keywords=keywords,
            emphasis_phrases=emphasis_phrases,
        )

        # 파일명 생성 (한글 파일명 URL 인코딩)
        import urllib.parse

        filename = f"{title or 'blog_post'}_auto.docx"
        filename = filename.replace(' ', '_')

        # URL 인코딩된 파일명 생성 (한글 지원)
        filename_encoded = urllib.parse.quote(filename)

        return Response(
            content=docx_file.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                # RFC 5987: filename*=UTF-8''encoded_filename
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}"
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"자동 내보내기 중 오류가 발생했습니다: {str(e)}"
        )


async def _extract_with_ai(content: str, title: Optional[str] = "") -> tuple:
    """
    AI를 사용하여 콘텐츠에서 키워드와 강조 문구를 추출합니다.

    Returns:
        (keywords, emphasis_phrases) 튜플
    """
    import json

    try:
        ai_service = AIService()

        prompt = f"""다음 블로그 글을 분석하여 JSON 형식으로 응답해주세요.

제목: {title or '(제목 없음)'}

본문:
{content[:3000]}  # 토큰 제한을 위해 처음 3000자만 사용

다음 형식으로 응답해주세요:
{{
    "keywords": ["키워드1", "키워드2", ...],  // 핵심 키워드 최대 10개 (SEO에 중요한 단어들)
    "emphasis_phrases": ["강조문구1", "강조문구2", ...]  // 독자의 관심을 끌 핵심 문구 최대 5개
}}

규칙:
1. keywords는 SEO에 중요한 핵심 용어들 (의료/건강 관련 전문용어 우선)
2. emphasis_phrases는 독자가 꼭 기억해야 할 핵심 메시지나 숫자가 포함된 구체적 정보
3. JSON 형식만 응답하고 다른 텍스트는 포함하지 마세요"""

        system_prompt = """당신은 블로그 SEO 및 콘텐츠 분석 전문가입니다.
블로그 글에서 핵심 키워드와 강조해야 할 문구를 정확하게 추출합니다.
항상 유효한 JSON 형식으로만 응답합니다."""

        response = await ai_service.generate_text(
            prompt=prompt,
            max_tokens=500,
            temperature=0.3,
            system_prompt=system_prompt
        )

        # JSON 파싱 시도
        try:
            # JSON 블록 추출 (```json ... ``` 형식 처리)
            json_match = response
            if "```json" in response:
                json_match = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_match = response.split("```")[1].split("```")[0]

            data = json.loads(json_match.strip())
            keywords = data.get("keywords", [])[:10]
            emphasis_phrases = data.get("emphasis_phrases", [])[:5]
            return keywords, emphasis_phrases

        except json.JSONDecodeError:
            # JSON 파싱 실패시 기본 추출 사용
            print(f"⚠️ AI 응답 JSON 파싱 실패, 기본 추출 사용: {response[:200]}")
            return _extract_basic_keywords(content), _extract_emphasis_phrases(content)

    except Exception as e:
        print(f"⚠️ AI 분석 실패, 기본 추출 사용: {e}")
        return _extract_basic_keywords(content), _extract_emphasis_phrases(content)


def _extract_basic_keywords(content: str) -> List[str]:
    """기본 키워드 추출 (fallback)"""
    import re

    keywords = []

    # 의료 관련 중요 키워드
    medical_terms = [
        '치료', '검진', '예방', '진단', '수술', '처방',
        '환자', '증상', '질환', '건강', '관리', '전문의',
        '병원', '클리닉', '스케일링', '임플란트', '교정'
    ]

    for term in medical_terms:
        if term in content:
            keywords.append(term)

    return keywords[:10]  # 최대 10개


def _extract_emphasis_phrases(content: str) -> List[str]:
    """강조 문구 추출 (fallback)"""
    phrases = []

    # 중요 표현 패턴
    important_patterns = [
        r'(\d+[개월년일주]마다)',  # "6개월마다"
        r'(매일|매주|매달)',
        r'(꼭|반드시|필수)',
    ]

    import re
    for pattern in important_patterns:
        matches = re.findall(pattern, content)
        phrases.extend(matches)

    return list(set(phrases))[:5]  # 최대 5개, 중복 제거


@router.post("/with-images")
async def export_with_image_folder(
    content: str = Form(...),
    title: str = Form(""),
    keywords: Optional[str] = Form(None),  # JSON string
    emphasis_phrases: Optional[str] = Form(None),  # JSON string
    distribution_strategy: str = Form("paragraphs"),  # even, paragraphs
    images: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    이미지 폴더와 함께 워드 문서 생성

    **사용법:**
    1. 콘텐츠와 이미지 폴더를 함께 업로드
    2. AI가 이미지를 자동으로 적절한 위치에 배치
    3. 네이버 블로그 최적화 워드 문서 다운로드

    **배치 전략:**
    - even: 균등하게 분포
    - paragraphs: 문단 사이에 배치 (추천)
    """
    temp_dir = None

    try:
        # JSON 파싱
        import json
        import traceback

        print(f"📝 워드 문서 생성 시작 - 이미지 개수: {len(images)}")

        keywords_list = json.loads(keywords) if keywords else []
        emphasis_list = json.loads(emphasis_phrases) if emphasis_phrases else []

        # 임시 폴더 생성 (Fly.io 환경에서는 /tmp 사용)
        temp_dir = tempfile.mkdtemp(dir='/data')
        print(f"📁 임시 폴더 생성: {temp_dir}")

        # 업로드된 이미지 저장
        for i, upload_file in enumerate(images):
            file_path = os.path.join(temp_dir, upload_file.filename)
            print(f"💾 이미지 저장 중 ({i+1}/{len(images)}): {upload_file.filename}")
            with open(file_path, "wb") as f:
                shutil.copyfileobj(upload_file.file, f)

        print(f"🖼️ 이미지 자동 배치 시작...")
        # 이미지 자동 배치
        positioned_images = image_analyzer.prepare_images_for_export(
            folder_path=temp_dir,
            content=content,
            strategy=distribution_strategy,
            use_base64=False  # 파일 경로 사용
        )
        print(f"✅ 이미지 배치 완료: {len(positioned_images) if positioned_images else 0}개")

        print(f"📄 DOCX 생성 시작...")
        # DOCX 생성
        docx_file = blog_exporter.export_to_docx(
            content=content,
            title=title,
            keywords=keywords_list,
            emphasis_phrases=emphasis_list,
            images=positioned_images,
        )
        print(f"✅ DOCX 생성 완료")

        # 파일명 생성 (한글 파일명 URL 인코딩)
        import urllib.parse

        filename = f"{title or 'blog_post'}_with_images.docx"
        filename = filename.replace(' ', '_').replace('/', '_')

        # URL 인코딩된 파일명 생성 (한글 지원)
        filename_encoded = urllib.parse.quote(filename)

        return Response(
            content=docx_file.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                # RFC 5987: filename*=UTF-8''encoded_filename
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}"
            }
        )

    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"❌ 워드 문서 생성 에러:\n{error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"이미지 포함 문서 생성 중 오류: {str(e)}\n상세: {error_trace[:500]}"
        )
    finally:
        # 임시 폴더 정리
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


@router.post("/analyze-images")
async def analyze_image_folder(
    images: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    이미지 폴더 분석 (미리보기)

    실제 문서를 생성하지 않고, 어떤 이미지가 인식되었는지 확인
    """
    temp_dir = None

    try:
        # 임시 폴더 생성 (Fly.io 환경에서는 /tmp 사용)
        temp_dir = tempfile.mkdtemp(dir='/data')

        # 업로드된 이미지 저장
        for upload_file in images:
            file_path = os.path.join(temp_dir, upload_file.filename)
            with open(file_path, "wb") as f:
                shutil.copyfileobj(upload_file.file, f)

        # 이미지 스캔
        scanned_images = image_analyzer.scan_folder(temp_dir)

        return {
            "total": len(scanned_images),
            "images": [
                {
                    "filename": img['filename'],
                    "format": img['format'],
                    "size_kb": round(img['size'] / 1024, 2),
                }
                for img in scanned_images
            ],
            "supported_formats": image_analyzer.SUPPORTED_FORMATS,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"이미지 분석 중 오류: {str(e)}"
        )
    finally:
        # 임시 폴더 정리
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


@router.post("/search-images")
async def search_images(
    keywords: List[str],
    count: int = 4,
    orientation: str = "landscape",
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    키워드로 무료 이미지 자동 검색 (Unsplash/Pexels)

    **사용법:**
    - keywords: 검색할 키워드 리스트 (예: ["치과", "임플란트"])
    - count: 가져올 이미지 개수 (기본 4개)
    - orientation: landscape(가로), portrait(세로), squarish(정사각형)

    **반환:**
    - 이미지 정보 리스트 (URL, 설명, 출처 등)
    """
    try:
        images = await image_search_service.search_images(
            keywords=keywords,
            count=count,
            orientation=orientation
        )

        return {
            "images": images,
            "total": len(images),
            "keywords": keywords
        }

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ 이미지 검색 에러:\n{error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"이미지 검색 중 오류: {str(e)}"
        )


@router.post("/docx-with-auto-images")
async def export_docx_with_auto_images(
    request: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    자동 이미지 검색 + DOCX 생성 (원클릭!)

    **동작:**
    1. 키워드로 무료 이미지 자동 검색 (Unsplash/Pexels)
    2. 이미지를 콘텐츠에 자동 배치
    3. 네이버 블로그용 DOCX 파일 생성

    **장점:**
    - 이미지 수동 업로드 불필요
    - 키워드만으로 자동 완성
    - 저작권 걱정 없는 무료 이미지
    """
    temp_dir = None

    try:
        # 1. 키워드로 이미지 검색
        keywords = request.keywords or []
        if not keywords:
            # 키워드가 없으면 제목에서 추출
            keywords = [request.title] if request.title else ["의료", "건강"]

        print(f"🔍 이미지 검색 키워드: {keywords}")

        images_data = await image_search_service.search_images(
            keywords=keywords,
            count=4,  # 4개 이미지
            orientation="landscape"
        )

        print(f"✅ {len(images_data)}개 이미지 검색 완료")

        # 2. 이미지 다운로드
        temp_dir = tempfile.mkdtemp(dir='/data')
        downloaded_images = []

        for i, img_data in enumerate(images_data):
            try:
                # 이미지 다운로드
                img_bytes = await image_search_service.download_image(img_data["url"])

                # 임시 파일로 저장
                img_path = os.path.join(temp_dir, f"image_{i + 1}.jpg")
                with open(img_path, "wb") as f:
                    f.write(img_bytes)

                downloaded_images.append({
                    "path": img_path,
                    "caption": img_data.get("caption", ""),
                })

                print(f"📥 이미지 {i + 1} 다운로드 완료")

            except Exception as e:
                print(f"⚠️ 이미지 {i + 1} 다운로드 실패: {e}")
                continue

        # 3. 이미지를 콘텐츠에 자동 배치
        positioned_images = image_analyzer.prepare_images_for_export(
            folder_path=temp_dir,
            content=request.content,
            strategy="paragraphs",  # 문단 사이에 배치
            use_base64=False
        )

        print(f"📍 이미지 배치 완료: {len(positioned_images)}개")

        # 4. DOCX 생성
        docx_file = blog_exporter.export_to_docx(
            content=request.content,
            title=request.title,
            keywords=request.keywords,
            emphasis_phrases=request.emphasis_phrases,
            images=positioned_images,
        )

        # 5. 파일명 생성
        import urllib.parse
        filename = f"{request.title or 'blog_post'}_auto_images.docx"
        filename = filename.replace(' ', '_').replace('/', '_')
        filename_encoded = urllib.parse.quote(filename)

        print(f"✅ DOCX 생성 완료: {filename}")

        return Response(
            content=docx_file.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}"
            }
        )

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ 자동 이미지 DOCX 생성 에러:\n{error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"자동 이미지 DOCX 생성 중 오류: {str(e)}"
        )
    finally:
        # 임시 폴더 정리
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
