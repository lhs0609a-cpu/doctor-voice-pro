"""
카페 콘텐츠 AI 생성기
Claude API를 사용한 댓글/글 자동 생성
"""

import logging
import random
from typing import Dict, Any, Optional, List

from anthropic import AsyncAnthropic

from app.models.cafe import CafePost, CafeCommunity, CafeTone, CafeCategory, ContentType

logger = logging.getLogger(__name__)


class CafeContentGenerator:
    """AI 기반 카페 콘텐츠 생성"""

    def __init__(self, api_key: Optional[str] = None):
        self.client = AsyncAnthropic(api_key=api_key) if api_key else AsyncAnthropic()
        self.model = "claude-sonnet-4-20250514"

    # 어조별 시스템 프롬프트
    TONE_PROMPTS = {
        CafeTone.FRIENDLY: "친근하고 따뜻한 말투로 작성해주세요. 반말이나 편안한 존댓말을 사용합니다.",
        CafeTone.CASUAL: "가볍고 편한 말투로 작성해주세요. 이모티콘을 적절히 사용해도 좋습니다.",
        CafeTone.INFORMATIVE: "정보 전달에 초점을 맞춰 작성해주세요. 명확하고 도움이 되는 내용으로 작성합니다.",
        CafeTone.EMPATHETIC: "공감과 이해를 표현하는 말투로 작성해주세요. 상대방의 감정에 공감합니다.",
        CafeTone.ENTHUSIASTIC: "열정적이고 긍정적인 말투로 작성해주세요. 에너지가 느껴지도록 합니다.",
    }

    # 카페 카테고리별 힌트
    CATEGORY_HINTS = {
        CafeCategory.MOM: "맘카페 분위기에 맞게 육아, 아이, 엄마들의 관심사를 이해하는 톤으로 작성합니다.",
        CafeCategory.BEAUTY: "뷰티/성형 카페에 맞게 미용, 시술, 관리에 대한 경험 공유 톤으로 작성합니다.",
        CafeCategory.HEALTH: "건강/의료 카페에 맞게 건강 관리, 증상, 치료에 대한 정보성 톤으로 작성합니다.",
        CafeCategory.REGION: "지역 커뮤니티에 맞게 동네 정보, 로컬 팁을 공유하는 톤으로 작성합니다.",
        CafeCategory.HOBBY: "취미 카페에 맞게 관심사를 공유하는 열정적인 톤으로 작성합니다.",
        CafeCategory.OTHER: "일반적인 커뮤니티 톤으로 작성합니다.",
    }

    async def generate_comment(
        self,
        post_title: str,
        post_content: str,
        cafe_category: CafeCategory = CafeCategory.OTHER,
        tone: CafeTone = CafeTone.FRIENDLY,
        existing_comments: List[str] = None,
        include_promotion: bool = False,
        promotion_info: Dict[str, str] = None,
        max_length: int = 200,
        include_emoji: bool = True
    ) -> Dict[str, Any]:
        """
        게시글에 맞는 댓글 생성

        Args:
            post_title: 게시글 제목
            post_content: 게시글 내용
            cafe_category: 카페 카테고리
            tone: 댓글 어조
            existing_comments: 기존 댓글들 (중복 방지)
            include_promotion: 홍보 포함 여부
            promotion_info: 홍보 정보 {"blog_link": "", "place_link": "", "text": ""}
            max_length: 최대 글자수
            include_emoji: 이모지 포함 여부

        Returns:
            {"content": str, "quality_score": float, ...}
        """
        try:
            tone_prompt = self.TONE_PROMPTS.get(tone, self.TONE_PROMPTS[CafeTone.FRIENDLY])
            category_hint = self.CATEGORY_HINTS.get(cafe_category, self.CATEGORY_HINTS[CafeCategory.OTHER])

            # 기존 댓글 분석
            existing_context = ""
            if existing_comments:
                existing_context = f"\n\n기존 댓글들 (참고용, 비슷하게 작성하지 마세요):\n" + "\n".join(f"- {c[:100]}" for c in existing_comments[:5])

            # 홍보 지침
            promotion_guide = ""
            if include_promotion and promotion_info:
                promotion_guide = f"""

홍보 요소 (자연스럽게 녹여주세요):
- 블로그: {promotion_info.get('blog_link', '')}
- 플레이스: {promotion_info.get('place_link', '')}
- 홍보 문구: {promotion_info.get('text', '')}

홍보는 너무 직접적이지 않게, 자연스러운 추천이나 경험 공유 형태로 넣어주세요.
"""

            prompt = f"""당신은 네이버 카페에서 활동하는 일반 사용자입니다.
아래 게시글에 자연스러운 댓글을 작성해주세요.

{tone_prompt}
{category_hint}

## 게시글 정보
제목: {post_title}

내용:
{post_content[:1000]}
{existing_context}
{promotion_guide}

## 작성 규칙
1. {max_length}자 이내로 작성
2. {"이모지를 적절히 사용해주세요" if include_emoji else "이모지는 사용하지 마세요"}
3. 광고성 느낌이 나지 않도록 자연스럽게 작성
4. 게시글 내용에 공감하거나 도움이 되는 정보 제공
5. 한국어로 작성
6. 기존 댓글과 비슷하지 않게 작성

댓글만 작성해주세요. 다른 설명은 필요 없습니다."""

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text.strip()

            # 품질 평가
            quality = await self._evaluate_comment_quality(content, post_title, post_content)

            return {
                "content": content,
                "content_type": ContentType.COMMENT,
                "quality_score": quality.get("overall", 70),
                "naturalness_score": quality.get("naturalness", 70),
                "relevance_score": quality.get("relevance", 70),
                "tone": tone,
                "include_promotion": include_promotion,
                "promotion_text": promotion_info.get("text") if promotion_info else None,
                "blog_link": promotion_info.get("blog_link") if promotion_info else None,
                "place_link": promotion_info.get("place_link") if promotion_info else None,
            }

        except Exception as e:
            logger.error(f"댓글 생성 오류: {e}")
            raise

    async def generate_reply(
        self,
        post_title: str,
        parent_comment: str,
        cafe_category: CafeCategory = CafeCategory.OTHER,
        tone: CafeTone = CafeTone.FRIENDLY,
        max_length: int = 150,
        include_emoji: bool = True
    ) -> Dict[str, Any]:
        """
        댓글에 대한 대댓글 생성

        Args:
            post_title: 원글 제목
            parent_comment: 부모 댓글 내용
            cafe_category: 카페 카테고리
            tone: 대댓글 어조
            max_length: 최대 글자수
            include_emoji: 이모지 포함 여부

        Returns:
            {"content": str, ...}
        """
        try:
            tone_prompt = self.TONE_PROMPTS.get(tone, self.TONE_PROMPTS[CafeTone.FRIENDLY])

            prompt = f"""당신은 네이버 카페에서 활동하는 일반 사용자입니다.
아래 댓글에 대한 자연스러운 대댓글을 작성해주세요.

{tone_prompt}

## 원글 제목
{post_title}

## 대댓글 대상 댓글
{parent_comment}

## 작성 규칙
1. {max_length}자 이내로 작성
2. {"이모지를 적절히 사용" if include_emoji else "이모지 사용 안함"}
3. 댓글에 대한 공감, 추가 정보 제공, 또는 대화 이어가기
4. 자연스럽고 진정성 있게 작성
5. 한국어로 작성

대댓글만 작성해주세요."""

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text.strip()

            return {
                "content": content,
                "content_type": ContentType.REPLY,
                "quality_score": 75,  # 대댓글은 간단한 평가
                "tone": tone,
            }

        except Exception as e:
            logger.error(f"대댓글 생성 오류: {e}")
            raise

    async def generate_post(
        self,
        cafe_name: str,
        cafe_category: CafeCategory,
        topic: str,
        style: str = "review",  # review, question, info, experience
        tone: CafeTone = CafeTone.FRIENDLY,
        include_promotion: bool = True,
        promotion_info: Dict[str, str] = None,
        min_length: int = 500,
        max_length: int = 1500,
        include_emoji: bool = True
    ) -> Dict[str, Any]:
        """
        새 게시글 생성

        Args:
            cafe_name: 카페 이름
            cafe_category: 카페 카테고리
            topic: 글 주제
            style: 글 스타일 (후기/질문/정보/경험)
            tone: 글 어조
            include_promotion: 홍보 포함 여부
            promotion_info: 홍보 정보
            min_length: 최소 글자수
            max_length: 최대 글자수
            include_emoji: 이모지 포함 여부

        Returns:
            {"title": str, "content": str, ...}
        """
        try:
            tone_prompt = self.TONE_PROMPTS.get(tone, self.TONE_PROMPTS[CafeTone.FRIENDLY])
            category_hint = self.CATEGORY_HINTS.get(cafe_category, "")

            style_guide = {
                "review": "실제 경험한 것처럼 생생한 후기 형태로 작성",
                "question": "진심으로 궁금해하는 질문 형태로 작성",
                "info": "유용한 정보를 공유하는 형태로 작성",
                "experience": "개인적인 경험담을 나누는 형태로 작성",
            }.get(style, "자연스러운 경험 공유 형태로 작성")

            promotion_guide = ""
            if include_promotion and promotion_info:
                promotion_guide = f"""

홍보 정보 (글 중간이나 끝에 자연스럽게 삽입):
- 블로그: {promotion_info.get('blog_link', '')}
- 플레이스: {promotion_info.get('place_link', '')}
- 핵심 메시지: {promotion_info.get('text', '')}

"여기서 자세히 봤어요", "이 블로그 참고했어요" 같은 형태로 자연스럽게 삽입해주세요.
"""

            prompt = f"""당신은 '{cafe_name}' 카페에서 활동하는 일반 회원입니다.
아래 주제에 대한 게시글을 작성해주세요.

{tone_prompt}
{category_hint}

## 글 정보
주제: {topic}
스타일: {style_guide}
{promotion_guide}

## 작성 규칙
1. 제목과 본문을 작성해주세요
2. 본문은 {min_length}~{max_length}자 사이로 작성
3. {"이모지를 적절히 사용" if include_emoji else "이모지 사용 안함"}
4. 실제 경험담처럼 생생하게 작성
5. 광고처럼 보이지 않도록 자연스럽게 작성
6. 한국어로 작성
7. 문단을 나눠서 읽기 쉽게 작성

## 출력 형식
제목: [제목]

[본문 내용]"""

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            result = response.content[0].text.strip()

            # 제목과 본문 분리
            lines = result.split("\n", 2)
            title = ""
            content = result

            for i, line in enumerate(lines):
                if line.startswith("제목:"):
                    title = line.replace("제목:", "").strip()
                    content = "\n".join(lines[i+1:]).strip()
                    break

            if not title:
                # 첫 줄을 제목으로 사용
                title = lines[0][:100] if lines else topic
                content = "\n".join(lines[1:]) if len(lines) > 1 else result

            # 품질 평가
            quality = await self._evaluate_post_quality(title, content, topic)

            return {
                "title": title,
                "content": content,
                "content_type": ContentType.POST,
                "quality_score": quality.get("overall", 70),
                "naturalness_score": quality.get("naturalness", 70),
                "relevance_score": quality.get("relevance", 70),
                "tone": tone,
                "include_promotion": include_promotion,
                "promotion_text": promotion_info.get("text") if promotion_info else None,
                "blog_link": promotion_info.get("blog_link") if promotion_info else None,
                "place_link": promotion_info.get("place_link") if promotion_info else None,
            }

        except Exception as e:
            logger.error(f"게시글 생성 오류: {e}")
            raise

    async def analyze_post(
        self,
        title: str,
        content: str,
        keywords: List[str]
    ) -> Dict[str, Any]:
        """
        게시글 분석 (관련성, 감정, 주제)

        Args:
            title: 게시글 제목
            content: 게시글 내용
            keywords: 매칭 키워드

        Returns:
            분석 결과
        """
        try:
            prompt = f"""아래 게시글을 분석해주세요.

## 게시글
제목: {title}
내용: {content[:1500]}

## 분석 키워드
{', '.join(keywords)}

## 분석 항목
1. 관련성 점수 (0-100): 키워드와의 관련성
2. 감정: positive/negative/neutral
3. 주제 태그: 3-5개의 관련 주제
4. 댓글 추천 여부: 댓글을 달기 적합한 글인지 (true/false)
5. 추천 댓글 방향: 어떤 내용의 댓글이 적합할지

JSON 형식으로만 응답해주세요:
{{"relevance_score": 숫자, "sentiment": "문자열", "topic_tags": ["태그1", "태그2"], "should_comment": true/false, "comment_suggestion": "문자열"}}"""

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            import json
            result = response.content[0].text.strip()

            # JSON 추출
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                result = result.split("```")[1].split("```")[0]

            return json.loads(result)

        except Exception as e:
            logger.error(f"게시글 분석 오류: {e}")
            # 기본값 반환
            return {
                "relevance_score": 50,
                "sentiment": "neutral",
                "topic_tags": [],
                "should_comment": False,
                "comment_suggestion": ""
            }

    async def _evaluate_comment_quality(
        self,
        comment: str,
        post_title: str,
        post_content: str
    ) -> Dict[str, float]:
        """댓글 품질 평가"""
        try:
            prompt = f"""아래 댓글의 품질을 평가해주세요.

게시글 제목: {post_title}
게시글 내용 (요약): {post_content[:500]}

댓글: {comment}

## 평가 항목 (각 0-100점)
1. 자연스러움 (naturalness): 실제 사람이 쓴 것처럼 자연스러운가?
2. 관련성 (relevance): 게시글 내용과 관련이 있는가?
3. 종합 (overall): 전체적인 품질

JSON 형식으로만 응답:
{{"naturalness": 숫자, "relevance": 숫자, "overall": 숫자}}"""

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )

            import json
            result = response.content[0].text.strip()

            if "```json" in result:
                result = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                result = result.split("```")[1].split("```")[0]

            return json.loads(result)

        except Exception as e:
            logger.debug(f"품질 평가 오류: {e}")
            return {"naturalness": 70, "relevance": 70, "overall": 70}

    async def _evaluate_post_quality(
        self,
        title: str,
        content: str,
        topic: str
    ) -> Dict[str, float]:
        """게시글 품질 평가"""
        try:
            prompt = f"""아래 게시글의 품질을 평가해주세요.

주제: {topic}
제목: {title}
본문: {content[:1000]}

## 평가 항목 (각 0-100점)
1. 자연스러움 (naturalness): 실제 사람이 쓴 것처럼 자연스러운가?
2. 관련성 (relevance): 주제와 관련이 있는가?
3. 종합 (overall): 전체적인 품질

JSON 형식으로만 응답:
{{"naturalness": 숫자, "relevance": 숫자, "overall": 숫자}}"""

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )

            import json
            result = response.content[0].text.strip()

            if "```json" in result:
                result = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                result = result.split("```")[1].split("```")[0]

            return json.loads(result)

        except Exception as e:
            logger.debug(f"품질 평가 오류: {e}")
            return {"naturalness": 70, "relevance": 70, "overall": 70}


# 전역 인스턴스
cafe_content_generator = CafeContentGenerator()
