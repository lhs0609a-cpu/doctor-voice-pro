"""
AI Rewrite Engine - Claude API를 사용한 의료 콘텐츠 각색
"""

import anthropic
from typing import Dict, Optional
from app.core.config import settings


class AIRewriteEngine:
    """
    Claude API를 사용한 콘텐츠 각색 엔진
    """

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def _build_system_prompt(self, doctor_profile: Dict, writing_perspective: str = "1인칭") -> str:
        """
        의사 프로필 기반 시스템 프롬프트 생성
        """
        writing_style = doctor_profile.get("writing_style", {})
        signature_phrases = doctor_profile.get("signature_phrases", [])
        specialty = doctor_profile.get("specialty", "의료")

        # 스타일 강도를 텍스트로 변환
        formality_text = self._get_style_text(
            writing_style.get("formality", 5), "격식", "캐주얼한", "매우 격식있는"
        )
        friendliness_text = self._get_style_text(
            writing_style.get("friendliness", 5), "친근함", "전문가다운", "친구같은"
        )
        technical_text = self._get_style_text(
            writing_style.get("technical_depth", 5),
            "전문성",
            "쉬운 용어",
            "전문 용어 사용",
        )
        storytelling_text = self._get_style_text(
            writing_style.get("storytelling", 5),
            "스토리텔링",
            "정보 중심",
            "이야기 중심",
        )
        emotion_text = self._get_style_text(
            writing_style.get("emotion", 5), "감정 표현", "객관적", "공감형"
        )

        signature_phrase_text = ""
        if signature_phrases:
            signature_phrase_text = f"\n자주 사용하는 표현: {', '.join(signature_phrases[:3])}"

        # 시점별 작성 가이드
        perspective_guide = {
            "1인칭": """
작성 시점: 1인칭 (저, 제가, 우리 병원)
- "제 경험상", "저는 ~라고 생각합니다", "진료하면서 느낀 점은" 같은 표현 사용
- 원장님이 직접 환자에게 이야기하는 느낌으로 작성
- 예: "진료실에서 환자분들을 만나다 보면...", "제가 항상 강조하는 것은..."
""",
            "3인칭": """
작성 시점: 3인칭 객관적 관점
- "의사들은", "전문가들은", "연구에 따르면" 같은 표현 사용
- 객관적이고 전문적인 정보 전달에 초점
- 예: "전문의들은 이 증상을 ~라고 설명한다", "최근 연구 결과에 따르면..."
""",
            "대화형": """
작성 시점: 직접 대화하는 느낌 (2인칭 활용)
- "여러분", "~하셨나요?", "~해보세요" 같은 직접 대화 표현 사용
- 독자에게 직접 말을 거는 것처럼 친근하고 상호작용적으로 작성
- 예: "혹시 아침에 일어났을 때 목이 칼칼하신가요?", "함께 알아볼까요?"
"""
        }

        system_prompt = f"""당신은 {specialty} 전문의이며, 환자들과 소통하는 블로그를 직접 운영하는 원장입니다.

당신의 글쓰기 특징:
- {formality_text}
- {friendliness_text}
- {technical_text}
- {storytelling_text}
- {emotion_text}{signature_phrase_text}

{perspective_guide.get(writing_perspective, perspective_guide["1인칭"])}

중요한 글쓰기 원칙:
1. 블로그 포스팅처럼 편안하고 자연스러운 말투로 작성하세요
2. 소제목은 자연스러운 한글로 (예: "왜 이런 증상이 생길까요?", "어떻게 관리하면 좋을까요?")
3. 각 문단이 자연스럽게 이어지도록 연결고리를 만드세요
4. 형식적인 구분([Attention], 1., 2. 등) 없이 이야기가 흐르듯 작성하세요
5. 사람이 쓴 따뜻하고 진정성 있는 글이어야 합니다

절대 금지:
× [Attention], [Problem] 같은 대괄호 섹션명
× 숫자 리스트 형식의 딱딱한 구조
× "지금 바로 예약", "무료 상담", "특별 할인" 같은 상업적 유인 문구
× "빠르게 연락주세요", "서둘러 예약하세요" 같은 조급한 행동 촉구"""

        return system_prompt

    def _get_style_text(
        self, value: int, label: str, low_text: str, high_text: str
    ) -> str:
        """
        스타일 값(1-10)을 텍스트로 변환
        """
        if value <= 3:
            return f"{label}: {low_text}"
        elif value >= 8:
            return f"{label}: {high_text}"
        else:
            return f"{label}: 적당한 수준"

    def _build_user_prompt(
        self,
        original_content: str,
        framework: str,
        persuasion_level: int,
        target_length: int,
        target_audience: Optional[Dict] = None,
    ) -> str:
        """
        각색 요구사항 프롬프트 생성
        """
        # 프레임워크별 지시사항
        framework_instructions = {
            "관심유도형": """독자의 관심을 자연스럽게 끌어가는 구조로 작성하세요:
- 처음에는 독자의 관심을 끄는 흥미로운 이야기나 질문으로 시작합니다
- 그다음 관련된 의학 정보와 데이터를 자연스럽게 풀어냅니다
- 해결 방법의 장점과 효과를 설명하며 독자의 궁금증을 해소합니다
- 마지막에는 실천 가능한 조언이나 다음 단계를 제안합니다
※ 각 부분이 자연스럽게 이어지도록, 섹션 구분 없이 하나의 이야기처럼 작성하세요""",
            "공감해결형": """환자의 고민에 공감하고 해결책을 제시하는 구조로 작성하세요:
- 많은 환자들이 겪는 고민과 어려움에 공감하며 시작합니다
- 그 문제가 왜 중요한지, 방치하면 어떤 일이 생기는지 친절하게 설명합니다
- 실제로 효과적인 치료법과 관리 방법을 구체적으로 안내합니다
※ 환자를 이해하고 도와주고 싶은 마음이 느껴지도록 작성하세요""",
            "스토리형": """실제 사례를 바탕으로 한 이야기 형식으로 작성하세요:
- 비슷한 증상으로 병원을 찾은 환자의 사례로 시작합니다
- 어떻게 진단하고 치료 계획을 세웠는지 과정을 설명합니다
- 치료 결과와 환자의 변화를 구체적으로 보여줍니다
- 독자들에게 도움이 되는 조언과 교훈으로 마무리합니다
※ 실제 진료실에서 있었던 일을 이야기하듯이 편안하게 작성하세요""",
            "질문답변형": """환자들이 궁금해하는 것에 답하는 형식으로 작성하세요:
- 진료실에서 자주 받는 질문들을 자연스럽게 제시합니다
- 각 질문에 대해 쉽고 친절하게 답변합니다
- 전문적이지만 어렵지 않게, 마치 환자와 대화하듯이 설명합니다
※ Q&A 같은 형식적 표시 없이 자연스러운 문답 형태로 작성하세요""",
            "정보전달형": """핵심 정보를 명확하고 체계적으로 전달하는 구조로 작성하세요:
- 주제에 대한 명확한 정의와 개념으로 시작합니다
- 원인, 증상, 진단, 치료 등을 논리적 순서로 설명합니다
- 객관적 데이터와 연구 결과를 근거로 제시합니다
- 실생활에 적용할 수 있는 실용적 정보로 마무리합니다
※ 정보 전달이 주목적이지만, 딱딱하지 않고 이해하기 쉽게 작성하세요""",
            "경험공유형": """원장의 임상 경험을 바탕으로 한 통찰을 나누는 형식으로 작성하세요:
- "제 경험상", "진료하면서 느낀 점" 같은 개인적 관점을 담습니다
- 오랜 진료 경험에서 얻은 실질적인 노하우를 공유합니다
- 환자들이 자주 오해하는 부분을 바로잡아줍니다
- 원장님만의 진료 철학과 접근법을 녹여냅니다
※ 원장님의 목소리와 개성이 느껴지도록 작성하세요""",
        }

        # 각색 레벨별 요구사항
        persuasion_requirements = {
            1: "객관적 사실만 나열. 감정 표현 최소화.",
            2: "근거와 이유를 추가. 약간의 설명 강화.",
            3: "환자의 심리와 고민을 반영. 공감 유도.",
            4: "구체적인 행동 유도 추가. 검진 예약 등 CTA 포함.",
            5: "환자 사례 중심 스토리텔링. 감정과 설득 요소 극대화.",
        }

        # 타겟 독자 정보
        audience_text = ""
        if target_audience:
            age = target_audience.get("age_range", "")
            gender = target_audience.get("gender", "")
            concerns = target_audience.get("concerns", [])

            audience_parts = []
            if age:
                audience_parts.append(f"{age}세")
            if gender and gender != "무관":
                audience_parts.append(gender)
            if concerns:
                audience_parts.append(f"주요 고민: {', '.join(concerns[:3])}")

            if audience_parts:
                audience_text = f"\n타겟 독자: {' '.join(audience_parts)}"

        user_prompt = f"""다음 의료 정보를 원장님이 직접 쓴 블로그 글로 자연스럽게 각색해주세요.

[원본 내용]
{original_content}

[글쓰기 스타일]
{framework_instructions.get(framework, "")}

[각색 강도]
{persuasion_requirements.get(persuasion_level, "")}

[목표 분량]
약 {target_length}자 정도{audience_text}

[자연스러운 글을 위한 핵심 원칙]
1. 소제목 사용
   - 자연스러운 한글 소제목 사용 (예: "왜 이런 증상이 생길까요?", "어떻게 관리하면 좋을까요?")
   - 소제목은 질문형이나 친근한 평서형으로
   - 소제목 앞뒤로 적절한 여백 유지

2. 문단 연결
   - 각 문단이 자연스럽게 이어지도록 연결 표현 사용
   - "그런데", "사실은", "이와 관련해서", "여기서 중요한 점은" 등
   - 이전 문단의 내용을 언급하며 다음 주제로 자연스럽게 전환

3. 말투와 어조
   - 환자와 대화하듯이 친근하고 공감되는 말투
   - 전문 용어는 쉬운 말로 풀어서 설명
   - 구체적인 사례나 비유를 들어 이해하기 쉽게

4. 내용 구성
   - 형식적인 구조([Attention], 1., 2. 등) 없이 이야기처럼 흐르도록
   - 자연스러운 기승전결 구조
   - 원장님의 경험과 생각이 담긴 것처럼

[절대 금지 사항]
× [Attention], [Problem] 같은 대괄호나 영어 섹션명
× "1. ~", "2. ~" 같은 숫자 리스트 구조
× "지금 바로 예약하세요", "무료 상담 신청" 같은 상업적 유인 문구
× "빠르게 연락주세요", "서둘러 예약하세요" 같은 조급한 행동 촉구
× "100% 완치", "반드시 낫습니다" 같은 절대적 표현
× "최고", "최상", "1등" 같은 비교 우위 표현
× "즉시 효과", "단 3일만에" 같은 과장 표현
× 가격, 할인, 이벤트 관련 표현

사람이 직접 쓴 것 같은 따뜻하고 자연스러운 블로그 글을 작성해주세요.
제목도 검색 최적화되면서 자극적이지 않은 자연스러운 제목으로 만들어주세요."""

        return user_prompt

    async def generate(
        self,
        original_content: str,
        doctor_profile: Dict,
        framework: str = "관심유도형",
        persuasion_level: int = 3,
        target_length: int = 1500,
        target_audience: Optional[Dict] = None,
        writing_perspective: str = "1인칭",
    ) -> str:
        """
        콘텐츠 각색 실행

        Args:
            original_content: 원본 의료 정보
            doctor_profile: 의사 프로필 정보
            framework: 글쓰기 스타일 (관심유도형, 공감해결형, 스토리형, 질문답변형, 정보전달형, 경험공유형)
            persuasion_level: 각색 레벨 (1-5)
            target_length: 목표 글자 수
            target_audience: 타겟 독자 정보
            writing_perspective: 작성 시점 (1인칭, 3인칭, 대화형)

        Returns:
            각색된 블로그 포스팅
        """
        system_prompt = self._build_system_prompt(doctor_profile, writing_perspective)
        user_prompt = self._build_user_prompt(
            original_content, framework, persuasion_level, target_length, target_audience
        )

        try:
            message = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=4096,
                temperature=0.7,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            generated_content = message.content[0].text
            return generated_content

        except Exception as e:
            raise Exception(f"AI 각색 중 오류 발생: {str(e)}")

    async def generate_title_and_meta(
        self, content: str, specialty: str
    ) -> Dict[str, str]:
        """
        콘텐츠 기반 제목 및 메타 설명 생성

        Args:
            content: 생성된 콘텐츠
            specialty: 진료 과목

        Returns:
            제목, 메타 설명, 추천 해시태그
        """
        prompt = f"""다음 블로그 글을 분석하여:

1. 네이버 검색 최적화된 제목 (50자 이내)
2. 메타 설명 (150자 이내)
3. 추천 해시태그 10개

를 생성해주세요.

[블로그 내용]
{content[:1000]}...

[형식]
제목: (여기에 제목)
메타: (여기에 메타 설명)
해시태그: #태그1 #태그2 #태그3 ..."""

        try:
            message = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=500,
                temperature=0.5,
                messages=[{"role": "user", "content": prompt}],
            )

            result = message.content[0].text

            # 결과 파싱
            lines = result.strip().split("\n")
            title = ""
            meta = ""
            hashtags = []

            for line in lines:
                if line.startswith("제목:"):
                    title = line.replace("제목:", "").strip()
                elif line.startswith("메타:"):
                    meta = line.replace("메타:", "").strip()
                elif line.startswith("해시태그:"):
                    hashtag_text = line.replace("해시태그:", "").strip()
                    hashtags = [
                        tag.strip() for tag in hashtag_text.split("#") if tag.strip()
                    ]

            return {"title": title, "meta_description": meta, "hashtags": hashtags}

        except Exception as e:
            return {
                "title": "제목 생성 실패",
                "meta_description": "",
                "hashtags": [],
            }


# Singleton instance
ai_rewrite_engine = AIRewriteEngine()
