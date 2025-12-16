"""
DIA/CRANK SEO Score Analyzer
글 작성 후 네이버 검색 알고리즘 점수 분석
"""

from typing import Dict, Optional
import anthropic
from app.core.config import settings


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
    if provider == "claude":
        return settings.ANTHROPIC_API_KEY
    elif provider == "gpt":
        return settings.OPENAI_API_KEY
    elif provider == "gemini":
        return settings.GEMINI_API_KEY
    return None


class DIACRANKAnalyzer:
    """DIA/CRANK 점수 분석기"""

    def __init__(self):
        pass  # API 키는 호출 시마다 DB에서 가져옴

    async def analyze(self, content: str, title: str = "") -> Dict:
        """
        콘텐츠의 DIA/CRANK 점수 분석

        Args:
            content: 분석할 블로그 콘텐츠
            title: 제목 (선택)

        Returns:
            DIA/CRANK 분석 결과
        """
        prompt = f"""당신은 네이버 블로그 SEO 전문가입니다. 다음 블로그 글을 DIA와 CRANK 알고리즘 기준으로 분석하세요.

[블로그 글]
제목: {title}

{content[:2000]}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 DIA (Deep Intent Analysis) 분석 기준
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. **경험 정보 (Experience)** - 100점 만점
   평가 기준:
   * 90-100점: 실제 경험 3건 이상, 구체적 묘사 풍부
   * 70-89점: 실제 경험 1-2건, 일부 구체적
   * 50-69점: 경험 언급은 있으나 추상적
   * 0-49점: 이론적 내용만, 경험 없음

2. **정보성 (Information Quality)** - 100점 만점
   평가 기준:
   * 90-100점: 근거 명확, 정보 정확하고 유용
   * 70-89점: 대체로 정확, 일부 근거 제시
   * 50-69점: 기본 정보만 제공
   * 0-49점: 정보 부족 또는 부정확

3. **독창성 (Originality)** - 100점 만점
   평가 기준:
   * 90-100점: 매우 독창적, 차별화된 관점
   * 70-89점: 일부 독창적 요소 포함
   * 50-69점: 일반적 내용이 대부분
   * 0-49점: 흔한 정보만 나열

4. **적시성 (Timeliness)** - 100점 만점
   평가 기준:
   * 90-100점: 최신 연구/트렌드 다수 반영
   * 70-89점: 일부 최신 정보 포함
   * 50-69점: 최신성은 있으나 약함
   * 0-49점: 시기와 무관한 일반론

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 C-RANK 분석 기준
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. **Context (주제 집중도)** - 100점 만점
   평가 기준:
   * 90-100점: 주제 매우 집중, 일관성 완벽
   * 70-89점: 주제 집중도 양호
   * 50-69점: 주제가 다소 산만
   * 0-49점: 여러 주제 혼재, 산만함

2. **Content (콘텐츠 품질)** - 100점 만점
   평가 기준:
   * 90-100점: 전문성 높고 깊이 있음
   * 70-89점: 전문적이나 일부 개선 필요
   * 50-69점: 기본 수준
   * 0-49점: 품질 낮음

3. **Chain (참여도)** - 100점 만점
   평가 기준:
   * 90-100점: 참여 유도 우수
   * 70-89점: 일부 참여 유도
   * 50-69점: 참여 유도 약함
   * 0-49점: 일방적 전달

4. **Creator (작성자 신뢰도)** - 100점 만점
   평가 기준:
   * 90-100점: 신뢰도 매우 높음
   * 70-89점: 신뢰할 만함
   * 50-69점: 보통 수준
   * 0-49점: 신뢰도 낮음

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 응답 형식 (반드시 이 JSON 형식으로만 응답)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{{
  "dia_score": {{
    "total": 85,
    "experience": {{
      "score": 90,
      "analysis": "실제 진료 사례 3건 포함, Before/After 구체적 묘사 우수",
      "suggestions": ["환자의 나이/성별 등 더 구체적인 정보 추가 권장"]
    }},
    "information": {{
      "score": 85,
      "analysis": "의학적 정보 정확성 높음",
      "suggestions": ["최신 연구 결과 추가 시 점수 향상"]
    }},
    "originality": {{
      "score": 80,
      "analysis": "원장님만의 관점 잘 드러남",
      "suggestions": ["차별화된 인사이트 더 강조"]
    }},
    "timeliness": {{
      "score": 85,
      "analysis": "최신 트렌드 반영",
      "suggestions": ["2024년 최신 연구 추가"]
    }}
  }},
  "crank_score": {{
    "total": 88,
    "context": {{
      "score": 92,
      "analysis": "주제 집중도 우수",
      "suggestions": []
    }},
    "content": {{
      "score": 87,
      "analysis": "전문성 높음",
      "suggestions": ["전문 용어 설명 추가"]
    }},
    "chain": {{
      "score": 85,
      "analysis": "독자 참여 유도 양호",
      "suggestions": ["댓글 유도 멘트 추가"]
    }},
    "creator": {{
      "score": 90,
      "analysis": "전문가 신뢰도 높음",
      "suggestions": []
    }}
  }},
  "overall_grade": "A+",
  "estimated_ranking": "상위 5%",
  "summary": "전반적으로 매우 우수한 SEO 품질입니다."
}}

등급 기준:
- S: 95-100점 (상위 1%)
- A+: 90-94점 (상위 5%)
- A: 85-89점 (상위 10%)
- B+: 80-84점 (상위 20%)
- B: 70-79점 (상위 30%)
- C: 60-69점 (평균)
- D: 60점 미만 (개선 필요)

반드시 JSON만 출력하세요."""

        try:
            # DB에서 Claude API 키 로드
            claude_api_key = await get_api_key_from_db("claude")
            if not claude_api_key:
                raise Exception("Claude API 키가 설정되지 않았습니다.")

            claude_client = anthropic.Anthropic(api_key=claude_api_key, timeout=60.0)

            response = claude_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4000,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )

            import json
            result_text = response.content[0].text
            # JSON 추출
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            return json.loads(result_text)

        except Exception as e:
            print(f"DIA/CRANK 분석 오류: {e}")
            return self._get_default_analysis()

    def _get_default_analysis(self) -> Dict:
        """기본 분석 결과"""
        return {
            "dia_score": {
                "total": 0,
                "experience": {"score": 0, "analysis": "분석 실패", "suggestions": []},
                "information": {"score": 0, "analysis": "분석 실패", "suggestions": []},
                "originality": {"score": 0, "analysis": "분석 실패", "suggestions": []},
                "timeliness": {"score": 0, "analysis": "분석 실패", "suggestions": []}
            },
            "crank_score": {
                "total": 0,
                "context": {"score": 0, "analysis": "분석 실패", "suggestions": []},
                "content": {"score": 0, "analysis": "분석 실패", "suggestions": []},
                "chain": {"score": 0, "analysis": "분석 실패", "suggestions": []},
                "creator": {"score": 0, "analysis": "분석 실패", "suggestions": []}
            },
            "overall_grade": "N/A",
            "estimated_ranking": "분석 불가",
            "summary": "분석 중 오류가 발생했습니다."
        }


# Singleton
dia_crank_analyzer = DIACRANKAnalyzer()
