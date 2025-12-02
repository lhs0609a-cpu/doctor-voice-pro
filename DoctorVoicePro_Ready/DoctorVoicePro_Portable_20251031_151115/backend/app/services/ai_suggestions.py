"""
AI Suggestions Service
포스팅 개선 제안 생성
"""

import anthropic
import os
from typing import Dict, List


class AISuggestionsService:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

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
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
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
