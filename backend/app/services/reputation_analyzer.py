"""
평판 모니터링 - AI 분석 서비스
감성 분류, 위험도 점수, 이슈 추출, 대응 답변 생성
"""
import json
import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reputation import (
    Mention, MentionSentiment, RiskLevel, MentionStatus
)
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)


class ReputationAnalyzer:
    """AI 기반 평판 분석 서비스"""

    def __init__(self):
        self.ai_service = AIService(provider="claude")

    async def analyze_mention(self, mention: Mention) -> Dict[str, Any]:
        """단일 멘션 AI 분석"""
        prompt = f"""다음은 온라인에 게시된 리뷰/멘션입니다. 분석해주세요.

플랫폼: {mention.platform.value if mention.platform else "알 수 없음"}
별점: {mention.rating if mention.rating else "없음"}
제목: {mention.title or "없음"}
내용: {mention.content}

다음 JSON 형식으로 응답해주세요:
{{
    "sentiment": "positive|neutral|negative|mixed",
    "sentiment_score": -1.0 ~ 1.0 사이 숫자,
    "risk_level": "critical|warning|normal|positive",
    "risk_score": 0~100 사이 정수,
    "issues": ["추출된 이슈 키워드 목록"],
    "spread_potential": 0~100 사이 숫자 (확산 가능성),
    "is_defamation": true/false (명예훼손 가능성),
    "summary": "한 문장 요약"
}}

분석 기준:
- risk_level "critical": 명예훼손, 허위사실, 법적 문제 가능성, 별점 1점 + 악의적 내용
- risk_level "warning": 부정적 리뷰, 불만 표현, 별점 2점 이하
- risk_level "normal": 일반적 멘션, 중립적 내용
- risk_level "positive": 긍정적 리뷰, 추천, 별점 4점 이상
- spread_potential: 자극적인 내용, 커뮤니티 게시물, 조회수 높은 글일수록 높음
- is_defamation: 구체적 허위사실 적시, 비속어를 통한 모욕이 포함된 경우

반드시 JSON만 응답하세요."""

        try:
            response = await self.ai_service.generate_text(
                prompt=prompt,
                max_tokens=500,
                temperature=0.1,
                system_prompt="당신은 온라인 평판 분석 전문가입니다. 한국어 리뷰를 분석하여 감성, 위험도, 이슈를 정확하게 분류합니다. 반드시 JSON 형식으로만 응답합니다."
            )

            # JSON 파싱
            result = self._parse_json_response(response)
            return result

        except Exception as e:
            logger.error(f"AI 분석 오류: {e}")
            # 별점 기반 fallback 분석
            return self._fallback_analysis(mention)

    async def analyze_new_mentions(self, db: AsyncSession, profile_id: str):
        """미분석 멘션들을 분석"""
        result = await db.execute(
            select(Mention).where(and_(
                Mention.profile_id == profile_id,
                Mention.analyzed_at.is_(None),
            ))
            .order_by(Mention.created_at)
            .limit(20)
        )
        mentions = result.scalars().all()

        for mention in mentions:
            try:
                analysis = await self.analyze_mention(mention)

                mention.sentiment = MentionSentiment(analysis.get("sentiment", "neutral"))
                mention.sentiment_score = analysis.get("sentiment_score", 0)
                mention.risk_level = RiskLevel(analysis.get("risk_level", "normal"))
                mention.risk_score = analysis.get("risk_score", 0)
                mention.issues = analysis.get("issues", [])
                mention.spread_potential = analysis.get("spread_potential", 0)
                mention.is_defamation = analysis.get("is_defamation", False)
                mention.ai_summary = analysis.get("summary", "")
                mention.analyzed_at = datetime.utcnow()

                await db.commit()

            except Exception as e:
                logger.error(f"멘션 분석 실패 ({mention.id}): {e}")
                continue

    async def generate_responses(
        self,
        mention_content: str,
        mention_platform: str,
        mention_rating: Optional[float],
        business_name: str,
        business_type: Optional[str],
        business_context: Optional[str] = None,
        tone: str = "professional",
    ) -> Dict[str, str]:
        """3가지 스타일의 대응 답변 생성"""
        context_info = f"\n사업장 추가 정보: {business_context}" if business_context else ""

        prompt = f"""다음 리뷰에 대해 3가지 스타일의 대응 답변을 작성해주세요.

사업장: {business_name} ({business_type or "일반"})
플랫폼: {mention_platform}
별점: {mention_rating if mention_rating else "없음"}
리뷰 내용: {mention_content}{context_info}

톤앤매너: {tone}

다음 JSON 형식으로 3가지 답변을 작성해주세요:
{{
    "apologetic": "사과형 답변 - 고객 불편에 진심으로 사과하고 개선을 약속하는 답변",
    "explanatory": "설명형 답변 - 상황을 정중하게 설명하고 오해를 풀어주는 답변",
    "compensatory": "보상형 답변 - 사과와 함께 구체적인 보상/혜택을 제안하는 답변"
}}

답변 작성 원칙:
1. 고객의 이름 대신 "고객님"으로 호칭
2. 사업장 이름으로 서명
3. 구체적이고 진정성 있는 내용
4. 플랫폼에 맞는 적절한 길이 (리뷰 답변은 200자 내외, 게시글은 300자 내외)
5. 과도한 이모지 사용 자제
6. 재방문/재이용을 유도하는 마무리

반드시 JSON만 응답하세요."""

        try:
            response = await self.ai_service.generate_text(
                prompt=prompt,
                max_tokens=1500,
                temperature=0.7,
                system_prompt="당신은 고객 서비스 전문가입니다. 부정적 리뷰에 대한 전문적이고 효과적인 대응 답변을 작성합니다. 반드시 JSON 형식으로만 응답합니다."
            )

            result = self._parse_json_response(response)

            # 3가지 스타일 모두 있는지 확인
            styles = {}
            for style in ["apologetic", "explanatory", "compensatory"]:
                if style in result:
                    styles[style] = result[style]
                else:
                    styles[style] = f"({style} 스타일 답변 생성 실패)"

            return styles

        except Exception as e:
            logger.error(f"대응 답변 생성 오류: {e}")
            return {
                "apologetic": f"안녕하세요, {business_name}입니다. 불편을 드려 진심으로 사과드립니다. 소중한 의견을 반영하여 개선하겠습니다.",
                "explanatory": f"안녕하세요, {business_name}입니다. 소중한 리뷰 감사합니다. 해당 부분에 대해 확인 후 개선하겠습니다.",
                "compensatory": f"안녕하세요, {business_name}입니다. 불편을 드려 죄송합니다. 다음 방문 시 특별한 서비스로 보답드리겠습니다.",
            }

    def _parse_json_response(self, response: str) -> dict:
        """AI 응답에서 JSON 추출"""
        # 코드 블록 내 JSON 추출
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0].strip()
        else:
            # 중괄호로 감싸진 부분 추출
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
            else:
                json_str = response

        return json.loads(json_str)

    def _fallback_analysis(self, mention: Mention) -> dict:
        """별점 기반 fallback 분석"""
        rating = mention.rating

        if rating is not None:
            if rating >= 4:
                return {
                    "sentiment": "positive",
                    "sentiment_score": 0.8,
                    "risk_level": "positive",
                    "risk_score": 0,
                    "issues": [],
                    "spread_potential": 5,
                    "is_defamation": False,
                    "summary": "긍정적 리뷰",
                }
            elif rating >= 3:
                return {
                    "sentiment": "neutral",
                    "sentiment_score": 0.0,
                    "risk_level": "normal",
                    "risk_score": 20,
                    "issues": [],
                    "spread_potential": 10,
                    "is_defamation": False,
                    "summary": "보통 리뷰",
                }
            elif rating >= 2:
                return {
                    "sentiment": "negative",
                    "sentiment_score": -0.5,
                    "risk_level": "warning",
                    "risk_score": 50,
                    "issues": [],
                    "spread_potential": 30,
                    "is_defamation": False,
                    "summary": "부정적 리뷰 - 주의 필요",
                }
            else:
                return {
                    "sentiment": "negative",
                    "sentiment_score": -0.9,
                    "risk_level": "critical",
                    "risk_score": 80,
                    "issues": [],
                    "spread_potential": 60,
                    "is_defamation": False,
                    "summary": "매우 부정적 리뷰 - 즉시 대응 필요",
                }
        else:
            return {
                "sentiment": "neutral",
                "sentiment_score": 0.0,
                "risk_level": "normal",
                "risk_score": 30,
                "issues": [],
                "spread_potential": 20,
                "is_defamation": False,
                "summary": "분석 필요",
            }
