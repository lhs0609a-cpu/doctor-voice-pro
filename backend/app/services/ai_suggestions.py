"""
AI Suggestions Service
포스팅 개선 제안 생성
"""

import anthropic
from typing import Dict, List, Optional


# DB에서 API 키 로드하는 함수
async def get_api_key_from_db(provider: str) -> Optional[str]:
    """
    DB에서 특정 provider의 API 키를 조회합니다.
    DB에 키가 없으면 환경변수에서 가져옵니다.
    """
    try:
        from app.db.database import AsyncSessionLocal
        from app.models import APIKey
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(APIKey).where(APIKey.provider == provider, APIKey.is_active == True)
            )
            key_record = result.scalar_one_or_none()
            if key_record:
                return key_record.api_key
    except Exception as e:
        print(f"[WARNING] DB에서 API 키 조회 실패: {e}")

    # DB에 없으면 환경변수에서 로드
    import os
    from app.core.config import settings
    if provider == "claude":
        return settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY")
    elif provider == "gpt":
        return settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
    elif provider == "gemini":
        return settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    return None


class AISuggestionsService:
    def __init__(self):
        pass  # API 키는 호출 시마다 DB에서 가져옴

    async def generate_suggestions(
        self, content: str, persuasion_score: float, specialty: str = "의료"
    ) -> Dict:
        """
        포스팅 내용을 분석하여 개선 제안 생성

        Returns:
            {
                "overall_assessment": str,
                "strengths": List[str],
                "improvements": List[Dict],
                "tone_suggestions": str,
                "seo_suggestions": List[str],
            }
        """

        prompt = f"""다음은 {specialty} 분야의 블로그 포스팅입니다. 현재 설득력 점수는 {persuasion_score}/100입니다.

포스팅 내용:
{content}

이 포스팅을 분석하여 다음 형식으로 개선 제안을 제공해주세요:

1. 전체 평가 (2-3문장)
2. 강점 (3개, 각 1문장)
3. 개선 사항 (3-5개, 각 제목과 설명)
4. 어조/스타일 제안 (2문장)
5. SEO 개선 제안 (3개, 각 1문장)

JSON 형식으로 답변해주세요."""

        try:
            # DB에서 Claude API 키 로드
            claude_api_key = await get_api_key_from_db("claude")
            if not claude_api_key:
                raise Exception("Claude API 키가 설정되지 않았습니다.")

            client = anthropic.Anthropic(api_key=claude_api_key, timeout=60.0)

            message = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2000,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = message.content[0].text

            # Parse JSON response
            import json

            suggestions = json.loads(response_text)

            return {
                "overall_assessment": suggestions.get("overall_assessment", ""),
                "strengths": suggestions.get("strengths", []),
                "improvements": suggestions.get("improvements", []),
                "tone_suggestions": suggestions.get("tone_suggestions", ""),
                "seo_suggestions": suggestions.get("seo_suggestions", []),
            }

        except Exception as e:
            print(f"AI suggestion error: {e}")
            return {
                "overall_assessment": "분석 중 오류가 발생했습니다.",
                "strengths": [],
                "improvements": [],
                "tone_suggestions": "",
                "seo_suggestions": [],
            }


# Singleton
ai_suggestions_service = AISuggestionsService()
