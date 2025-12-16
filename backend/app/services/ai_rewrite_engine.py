"""
AI Rewrite Engine - OpenAI GPT, Anthropic Claude, Google Gemini API를 사용한 의료 콘텐츠 각색
"""

from openai import OpenAI
import anthropic
import httpx
import re
from typing import Dict, Optional, List
from app.core.config import settings

# Gemini SDK 임포트 (설치되어 있는 경우)
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None


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


class AIRewriteEngine:
    """
    OpenAI GPT, Anthropic Claude, Google Gemini API를 사용한 콘텐츠 각색 엔진
    """

    def __init__(self):
        # 타임아웃 설정: 연결 30초, 읽기 180초 (AI 생성에 충분한 시간)
        http_client = httpx.Client(timeout=httpx.Timeout(connect=30.0, read=180.0, write=30.0, pool=30.0))
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY, http_client=http_client, timeout=180.0)
        self.claude_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=180.0)

        # Gemini 클라이언트 초기화
        self.gemini_available = GEMINI_AVAILABLE and bool(settings.GEMINI_API_KEY)
        if self.gemini_available:
            genai.configure(api_key=settings.GEMINI_API_KEY)

    def _remove_markdown_formatting(self, text: str) -> str:
        """
        Markdown 형식 제거 (**, ##, *, -, _, 등)
        """
        # ** 굵은 글씨 제거
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)

        # * 또는 _ 이탤릭 제거
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'_(.+?)_', r'\1', text)

        # ## 제목 표시 제거 (제목은 유지하되 ## 만 제거)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

        # - 또는 * 리스트 기호 제거
        text = re.sub(r'^\s*[-*]\s+', '', text, flags=re.MULTILINE)

        # 번호 리스트 기호 제거 (1. 2. 등)
        text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)

        # 백틱 코드 블록 제거
        text = re.sub(r'`(.+?)`', r'\1', text)

        # > 인용구 제거
        text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)

        # [링크](url) 형식 제거
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)

        # 수평선 제거 (---, ***, ___)
        text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)

        # 여러 개의 연속된 빈 줄을 2개로 제한
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()

    def _build_system_prompt(
        self,
        doctor_profile: Dict,
        writing_perspective: str = "1인칭",
        custom_writing_style: Optional[Dict] = None,
        requirements: Optional[Dict] = None,
        target_length: int = 1500,
        seo_optimization: Optional[Dict] = None,
        top_post_rules: Optional[Dict] = None,
    ) -> str:
        """
        의사 프로필 기반 시스템 프롬프트 생성
        """
        # custom_writing_style이 제공되면 우선 사용, 없으면 doctor_profile에서 가져옴
        writing_style = custom_writing_style if custom_writing_style else doctor_profile.get("writing_style", {})
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
        humor_text = self._get_style_text(
            writing_style.get("humor", 5), "유머", "진지한", "유머러스한"
        )
        question_text = self._get_style_text(
            writing_style.get("question_usage", 6), "질문형 문장", "평서문 위주", "질문형 많이 사용"
        )
        metaphor_text = self._get_style_text(
            writing_style.get("metaphor_usage", 5), "비유·은유", "직접적 표현", "비유적 표현 활용"
        )
        sentence_length_text = self._get_style_text(
            writing_style.get("sentence_length", 5), "문장 길이", "짧고 간결하게", "길고 상세하게"
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

        # 요청사항 추가
        requirements_text = ""
        if requirements:
            common_reqs = requirements.get("common", [])
            individual_req = requirements.get("individual", "")

            if common_reqs or individual_req:
                requirements_text = "\n\n특별 요청사항 (반드시 반영):"
                if common_reqs:
                    requirements_text += "\n[공통 요청사항]"
                    for req in common_reqs:
                        requirements_text += f"\n- {req}"
                if individual_req:
                    requirements_text += f"\n[개별 요청사항]\n- {individual_req}"

        # SEO 최적화 (DIA/CRANK) 지침 추가
        seo_text = ""
        if seo_optimization and seo_optimization.get("enabled"):
            seo_text = "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            seo_text += "🔍 네이버 검색 최적화 (DIA/CRANK) 가이드\n"
            seo_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

            if seo_optimization.get("experience_focus"):
                seo_text += """
📌 실제 경험 중심 작성 (DIA: 경험 정보)
- 직접 경험한 진료 사례를 구체적으로 작성하세요
- "실제로 진료했던 환자분", "진료실에서 자주 보는 케이스" 같은 실제 경험 표현 사용
- Before/After 같은 구체적인 변화 과정을 상세히 기술
- 환자의 증상, 진단 과정, 치료 결과를 생생하게 묘사
- 단순 이론이 아닌 실제 임상 경험에서 나온 인사이트 제공
"""

            if seo_optimization.get("expertise"):
                seo_text += """
📌 전문성과 깊이 강화 (C-Rank: Content 품질)
- 의학적 근거와 연구 결과를 자연스럽게 인용하세요
- 전문가만이 알 수 있는 세밀한 관찰과 진단 노하우 공유
- "전문의 입장에서", "임상 경험상" 같은 전문성 표현 활용
- 복잡한 의학 정보를 정확하면서도 이해하기 쉽게 설명
- 최신 의학 트렌드와 치료법에 대한 깊이 있는 분석
"""

            if seo_optimization.get("originality"):
                seo_text += """
📌 독창성 강조 (DIA: 독창성)
- 다른 곳에서 볼 수 없는 원장님만의 고유한 관점과 인사이트 제공
- 일반적인 정보를 넘어선 차별화된 조언과 팁 제시
- "제 경험상", "저만의 방법은" 같은 개인적 접근법 강조
- 환자들이 흔히 오해하는 부분을 독특한 시각으로 바로잡기
- 진료 철학과 접근 방식에서 나오는 차별화된 내용
"""

            if seo_optimization.get("timeliness"):
                seo_text += """
📌 적시성 반영 (DIA: 적시성)
- 최신 의학 정보와 최근 연구 결과 언급
- "최근에", "요즘", "올해" 같은 시의성 있는 표현 사용
- 계절, 유행, 트렌드와 연관된 타이밍 관련 정보 제공
- 새로운 치료법이나 변화된 의학적 가이드라인 반영
- 현재 환자들이 관심 있어 하는 이슈와 연결
"""

            if seo_optimization.get("topic_concentration"):
                seo_text += """
📌 주제 집중도 향상 (C-Rank: Context)
- 하나의 핵심 주제에 집중하여 일관성 있게 작성
- 관련 없는 주제로 벗어나지 않고 메인 토픽을 깊이 있게 다루기
- 핵심 키워드를 자연스럽게 반복하여 주제 명확성 강화
- 모든 문단이 중심 주제와 긴밀하게 연결되도록 구성
- 산만하지 않고 하나의 의료 주제를 완벽하게 설명하는 데 집중
"""

            seo_text += """
✅ 이러한 DIA/CRANK 최적화 요소들을 자연스럽게 녹여서 작성하되,
   여전히 따뜻하고 진정성 있는 원장님의 목소리가 느껴지도록 하세요.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        # 상위글 분석 기반 규칙 추가
        top_post_rules_text = ""
        if top_post_rules:
            top_post_rules_text = "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            top_post_rules_text += "📊 상위 노출 글 분석 기반 최적화 규칙\n"
            top_post_rules_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            top_post_rules_text += "이 규칙은 실제 네이버 검색 상위 1~3위 글을 분석한 결과입니다.\n\n"

            if top_post_rules.get("title"):
                title_rules = top_post_rules["title"]
                if title_rules.get("length"):
                    length = title_rules["length"]
                    top_post_rules_text += f"📌 제목 규칙\n"
                    top_post_rules_text += f"   - 제목 길이: {length.get('min', 20)}~{length.get('max', 45)}자 (최적: {length.get('optimal', 30)}자)\n"
                if title_rules.get("keyword_placement"):
                    kp = title_rules["keyword_placement"]
                    position_map = {"front": "앞부분", "middle": "중간", "end": "끝부분"}
                    best_pos = position_map.get(kp.get("best_position", "front"), "앞부분")
                    top_post_rules_text += f"   - 키워드 위치: {best_pos}에 배치 권장 (상위글 {kp.get('rate', 80)}%가 키워드 포함)\n"

            if top_post_rules.get("content"):
                content_rules = top_post_rules["content"]
                if content_rules.get("length"):
                    length = content_rules["length"]
                    top_post_rules_text += f"\n📌 본문 규칙\n"
                    top_post_rules_text += f"   - 본문 길이: {length.get('min', 1500)}~{length.get('max', 3500)}자 (최적: {length.get('optimal', 2000)}자)\n"
                if content_rules.get("structure"):
                    struct = content_rules["structure"]
                    if struct.get("heading_count"):
                        hc = struct["heading_count"]
                        top_post_rules_text += f"   - 소제목 개수: {hc.get('min', 3)}~{hc.get('max', 8)}개 (최적: {hc.get('optimal', 5)}개)\n"
                    if struct.get("keyword_count"):
                        kc = struct["keyword_count"]
                        top_post_rules_text += f"   - 키워드 반복: {kc.get('min', 5)}~{kc.get('max', 15)}회 (자연스럽게)\n"

            if top_post_rules.get("media"):
                media_rules = top_post_rules["media"]
                if media_rules.get("images"):
                    images = media_rules["images"]
                    top_post_rules_text += f"\n📌 이미지 규칙 (참고용)\n"
                    top_post_rules_text += f"   - 이미지 개수: {images.get('min', 5)}~{images.get('max', 15)}장 (최적: {images.get('optimal', 10)}장)\n"

            top_post_rules_text += "\n✅ 이 분석 결과를 참고하여 상위 노출에 최적화된 글을 작성하세요.\n"
            top_post_rules_text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

        system_prompt = f"""당신은 {specialty} 전문의이며, 환자들과 소통하는 블로그를 직접 운영하는 원장입니다.

당신의 글쓰기 특징:
- {formality_text}
- {friendliness_text}
- {technical_text}
- {storytelling_text}
- {emotion_text}
- {humor_text}
- {question_text}
- {metaphor_text}
- {sentence_length_text}{signature_phrase_text}

{perspective_guide.get(writing_perspective, perspective_guide["1인칭"])}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
★★★ 🚨 최우선 필수사항: 글자수를 반드시 {target_length}자로 맞추세요! 🚨 ★★★
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️⚠️⚠️ 이것이 가장 중요한 요구사항입니다! 다른 모든 것보다 우선합니다! ⚠️⚠️⚠️

🎯 필수 목표: 정확히 {target_length}자 (공백 포함, 띄어쓰기 포함, 한글 기준)
📊 최소 요구: {int(target_length * 0.95)}자 (절대 이보다 짧으면 안됨!)
📊 최대 허용: {int(target_length * 1.05)}자 (이보다 길어도 안됨!)

💡 글자수 예시:
"안녕하세요. 반갑습니다." = 14자 (공백 포함)
"피부과 전문의 김철수입니다." = 16자 (공백 포함)

✅ 반드시 따라야 할 작성 절차:
1단계: 먼저 {target_length}자 분량으로 내용을 충분히 작성합니다
2단계: 작성 완료 후 공백 포함해서 정확히 글자수를 셉니다
3단계: 현재 글자수가 {int(target_length * 0.95)}자 ~ {int(target_length * 1.05)}자 범위에 있는지 확인합니다
4단계: 범위를 벗어나면 반드시 아래 방법으로 조정합니다

📏 글자수 조정 방법:
🔺 글자수가 부족할 때 ({int(target_length * 0.95)}자 미만):
   • 환자 사례를 구체적으로 추가하세요 (예: "한 30대 여성분은...", "40대 남성 환자분께서...")
   • 설명을 더 풀어서 상세하게 작성하세요 (예시와 비유 추가)
   • 환자들이 궁금해할 추가 팁을 넣으세요 ("이런 점도 주의하세요", "도움이 되는 방법은...")
   • 원장님의 경험담을 추가하세요 ("제 경험상...", "진료하면서 느낀 점은...")
   • 관련 주의사항이나 관리 방법을 더 넣으세요

🔻 글자수가 초과할 때 ({int(target_length * 1.05)}자 초과):
   • 중복되는 내용을 찾아서 하나로 통합하세요
   • 불필요한 수식어를 제거하세요 ("매우 아주 정말" → "매우")
   • 같은 의미를 반복하는 문장을 정리하세요
   • 핵심 메시지만 남기고 부수적 내용은 제거하세요

🎯 목표 달성 기준:
✓ {int(target_length * 0.95)}자 이상 {int(target_length * 1.05)}자 이하
✓ 공백, 띄어쓰기 모두 포함해서 카운트
✓ 이모지는 글자수에 포함하지 않음

반드시 이 범위에 들어오도록 작성하세요!

중요한 글쓰기 원칙:
1. 블로그 포스팅처럼 편안하고 자연스러운 말투로 작성하세요
2. 소제목은 클릭하고 싶게 만드는 매력적인 후킹 카피로 작성하세요
   - 호기심을 자극하는 질문형이나 강렬한 평서형 사용
   - 예: "왜 10명 중 9명은 이걸 놓칠까요?", "생각보다 훨씬 간단한 해결법"
3. 각 문단이 자연스럽게 이어지도록 연결고리를 만드세요
4. 형식적인 구분([Attention], 1., 2. 등) 없이 이야기가 흐르듯 작성하세요
5. 사람이 쓴 따뜻하고 진정성 있는 글이어야 합니다
6. Markdown 형식(**, ##, *, -, _ 등)을 절대 사용하지 마세요 - 순수한 한글 텍스트로만 작성

절대 금지:
× [Attention], [Problem] 같은 대괄호 섹션명
× 숫자 리스트 형식의 딱딱한 구조
× "지금 바로 예약", "무료 상담", "특별 할인" 같은 상업적 유인 문구
× "빠르게 연락주세요", "서둘러 예약하세요" 같은 조급한 행동 촉구
× **, ##, *, -, _ 등의 Markdown 형식 기호{requirements_text}{seo_text}{top_post_rules_text}"""

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

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
★★★ 🚨 최우선 필수사항: 글자수를 반드시 {target_length}자로 맞추세요! 🚨 ★★★
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️⚠️⚠️ 이것이 가장 중요한 요구사항입니다! 다른 모든 것보다 우선합니다! ⚠️⚠️⚠️

🎯 필수 목표: 정확히 {target_length}자 (공백 포함, 띄어쓰기 포함, 한글 기준)
📊 최소 요구: {int(target_length * 0.95)}자 (절대 이보다 짧으면 안됨!)
📊 최대 허용: {int(target_length * 1.05)}자 (이보다 길어도 안됨!)

💡 글자수 세는 방법 예시:
"안녕하세요. 피부과 전문의입니다." = 20자 (공백, 마침표 모두 포함)
"여러분께 도움이 되는 정보를 알려드리겠습니다." = 27자 (공백 포함)

✅ 반드시 따라야 할 작성 절차:
1단계: 먼저 {target_length}자 분량으로 내용을 충분히 작성합니다
2단계: 작성 완료 후 공백 포함해서 정확히 글자수를 셉니다
3단계: 현재 글자수가 {int(target_length * 0.95)}자 ~ {int(target_length * 1.05)}자 범위에 있는지 확인합니다
4단계: 범위를 벗어나면 반드시 아래 방법으로 조정합니다

📏 글자수 조정 가이드:
🔺 글자수가 부족할 때 ({int(target_length * 0.95)}자 미만):
   • 환자 사례를 구체적으로 추가하세요 (예: "한 30대 여성분은...", "실제로 진료했던 40대 남성 환자분...")
   • 설명을 더 풀어서 상세하게 작성하세요 (예시와 비유를 풍부하게)
   • 환자들이 궁금해할 추가 팁을 넣으세요 ("이런 점도 주의하시면 좋아요", "도움이 되는 생활 습관은...")
   • 원장님의 임상 경험담을 추가하세요 ("제 경험상...", "진료실에서 많이 보는 케이스는...")
   • 관련 주의사항, 예방법, 관리 방법을 더 상세히 넣으세요

🔻 글자수가 초과할 때 ({int(target_length * 1.05)}자 초과):
   • 중복되는 내용을 찾아서 하나로 통합하세요
   • 불필요한 수식어를 제거하세요 ("매우 아주 정말 굉장히" → "매우")
   • 같은 의미를 반복하는 문장을 정리하세요
   • 핵심 메시지만 남기고 부수적인 내용은 과감히 제거하세요

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 현재 목표: {target_length}자
✅ 최소 요구: {int(target_length * 0.95)}자 (이보다 짧으면 실패!)
✅ 최대 허용: {int(target_length * 1.05)}자 (이보다 길면 실패!)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

반드시 {int(target_length * 0.95)}자 ~ {int(target_length * 1.05)}자 범위에 들어오도록 작성하세요!{audience_text}

[자연스러운 글을 위한 핵심 원칙]
1. 소제목 사용 - 후킹 카피 스타일로!
   - 소제목은 클릭하고 싶게 만드는 매력적인 후킹 카피로 작성하세요
   - 호기심을 자극하는 질문형 (예: "왜 10명 중 9명은 이걸 놓칠까요?", "아침마다 이런 증상, 혹시 나만?")
   - 또는 강렬한 평서형 (예: "생각보다 훨씬 간단한 해결법", "의외로 많은 사람들이 모르는 진실")
   - 숫자를 활용한 구체성 (예: "3가지만 바꾸면 달라지는 것들", "5분이면 충분한 관리법")
   - 감정을 건드리는 표현 (예: "이제 걱정 끝, 확실한 방법", "후회하기 전에 꼭 알아야 할 것")
   - 소제목 앞뒤로 적절한 여백 유지
   - Markdown 기호(##) 없이 순수 텍스트로만 작성

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

5. 형식 규칙
   - 절대로 Markdown 형식 기호를 사용하지 마세요
   - **, ##, *, -, _, ` 등의 특수 기호 금지
   - 순수한 한글 텍스트로만 작성

[절대 금지 사항]
× [Attention], [Problem] 같은 대괄호나 영어 섹션명
× "1. ~", "2. ~" 같은 숫자 리스트 구조
× "지금 바로 예약하세요", "무료 상담 신청" 같은 상업적 유인 문구
× "빠르게 연락주세요", "서둘러 예약하세요" 같은 조급한 행동 촉구
× "100% 완치", "반드시 낫습니다" 같은 절대적 표현
× "최고", "최상", "1등" 같은 비교 우위 표현
× "즉시 효과", "단 3일만에" 같은 과장 표현
× 가격, 할인, 이벤트 관련 표현
× **, ##, *, -, _, ` 등의 Markdown 형식 기호
× 번역체/직역체 표현 (예: "저 역시 매우 ~합니다", "그것은 ~한 것입니다", "~하는 것이 중요합니다")
× 어색한 피동형 (예: "~되어집니다", "~되어지고 있습니다")
× 불필요한 "것" 남용 (예: "~하는 것이 좋은 것입니다" → "~하면 좋습니다")

[자연스러운 한국어 작성 원칙]
✓ 원본이 번역체여도 반드시 자연스러운 한국어로 다시 작성하세요
✓ 한국 사람이 일상에서 실제로 쓰는 표현으로 바꾸세요
✓ "~입니다", "~해요", "~하죠" 등 자연스러운 종결어미 사용
✓ 주어-목적어-서술어 순서가 자연스럽게 흐르도록 작성
✓ 영어 직역 느낌이 나지 않도록 문장을 재구성하세요

사람이 직접 쓴 것 같은 따뜻하고 자연스러운 블로그 글을 작성해주세요.
제목도 검색 최적화되면서 자극적이지 않은 자연스러운 제목으로 만들어주세요.
반드시 순수한 텍스트로만 작성하고, 어떤 Markdown 형식도 사용하지 마세요."""

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
        custom_writing_style: Optional[Dict] = None,
        requirements: Optional[Dict] = None,
        ai_provider: str = "gpt",
        ai_model: Optional[str] = None,
        seo_optimization: Optional[Dict] = None,
        top_post_rules: Optional[Dict] = None,
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
            custom_writing_style: 사용자가 지정한 말투 설정 (프로필보다 우선)
            requirements: 특별 요청사항 (common/individual)
            ai_provider: AI 제공자 ("claude" 또는 "gpt")
            ai_model: 사용할 모델 (예: "gpt-4o", "claude-sonnet-4-5-20250929")
            seo_optimization: SEO 최적화 설정 (DIA/CRANK)

        Returns:
            각색된 블로그 포스팅
        """
        # 목표 글자수 범위 설정 (±5%)
        min_length = int(target_length * 0.95)
        max_length = int(target_length * 1.05)

        # 최대 재시도 횟수
        max_retries = 3
        best_result = None
        best_diff = float('inf')

        for attempt in range(max_retries):
            # 시도 횟수에 따라 보정 배수 조정
            # 1차: 2.0배, 2차: 2.3배, 3차: 2.5배
            multiplier = 2.0 + (attempt * 0.3)
            adjusted_target_length = int(target_length * multiplier)

            system_prompt = self._build_system_prompt(
                doctor_profile,
                writing_perspective,
                custom_writing_style,
                requirements,
                adjusted_target_length,
                seo_optimization,
                top_post_rules
            )
            user_prompt = self._build_user_prompt(
                original_content, framework, persuasion_level, adjusted_target_length, target_audience
            )

            # 한국어 글자수에 맞는 max_tokens 계산
            # 한국어는 1글자당 약 2.5-3 토큰 필요
            calculated_max_tokens = int(adjusted_target_length * 4) + 1500
            # 최소 4000, 최대 16000 토큰으로 제한
            max_tokens = max(4000, min(calculated_max_tokens, 16000))

            # 토큰 사용량 저장 변수
            input_tokens = 0
            output_tokens = 0

            try:
                if ai_provider == "claude":
                    # DB에서 API 키 로드 (없으면 환경변수 사용)
                    claude_api_key = await get_api_key_from_db("claude")
                    if not claude_api_key:
                        raise Exception("Claude API 키가 설정되지 않았습니다.")

                    # 매번 새로운 클라이언트 생성 (DB 키 사용)
                    claude_client = anthropic.Anthropic(api_key=claude_api_key, timeout=180.0)

                    # Claude API 호출
                    model = ai_model or "claude-sonnet-4-5-20250929"
                    response = claude_client.messages.create(
                        model=model,
                        max_tokens=max_tokens,
                        temperature=0.4,
                        system=system_prompt,
                        messages=[
                            {"role": "user", "content": user_prompt}
                        ],
                    )
                    generated_content = response.content[0].text
                    # Claude 토큰 사용량
                    input_tokens = response.usage.input_tokens
                    output_tokens = response.usage.output_tokens
                elif ai_provider == "gemini":
                    # DB에서 Gemini API 키 로드
                    gemini_api_key = await get_api_key_from_db("gemini")
                    if not gemini_api_key:
                        raise Exception("Gemini API 키가 설정되지 않았습니다.")

                    if not GEMINI_AVAILABLE:
                        raise Exception("Gemini SDK가 설치되어 있지 않습니다.")

                    # Gemini 설정 (매번 새로 설정)
                    genai.configure(api_key=gemini_api_key)

                    model = ai_model or "gemini-2.0-flash-exp"

                    # Gemini 모델 생성 설정
                    generation_config = genai.GenerationConfig(
                        temperature=0.4,
                        max_output_tokens=max_tokens,
                        top_p=0.95,
                        top_k=40,
                    )

                    # 안전 설정 (의료 콘텐츠 허용)
                    safety_settings = [
                        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
                    ]

                    gemini_model = genai.GenerativeModel(
                        model_name=model,
                        generation_config=generation_config,
                        safety_settings=safety_settings,
                        system_instruction=system_prompt,
                    )

                    response = gemini_model.generate_content(user_prompt)
                    generated_content = response.text
                    # Gemini 토큰 사용량 (usage_metadata에서 추출)
                    if hasattr(response, 'usage_metadata'):
                        input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0)
                        output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0)
                else:
                    # DB에서 GPT API 키 로드
                    gpt_api_key = await get_api_key_from_db("gpt")
                    if not gpt_api_key:
                        raise Exception("GPT API 키가 설정되지 않았습니다.")

                    # 매번 새로운 클라이언트 생성 (DB 키 사용)
                    http_client = httpx.Client(timeout=httpx.Timeout(connect=30.0, read=180.0, write=30.0, pool=30.0))
                    openai_client = OpenAI(api_key=gpt_api_key, http_client=http_client, timeout=180.0)

                    # GPT API 호출
                    model = ai_model or "gpt-4o-mini"
                    response = openai_client.chat.completions.create(
                        model=model,
                        max_tokens=max_tokens,
                        temperature=0.4,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                    )
                    generated_content = response.choices[0].message.content
                    # GPT 토큰 사용량
                    input_tokens = response.usage.prompt_tokens
                    output_tokens = response.usage.completion_tokens

                # 토큰 사용량 저장 (클래스 변수에 저장하여 외부에서 접근 가능)
                self.last_usage = {
                    "ai_provider": ai_provider,
                    "ai_model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                }

                # Markdown 형식 제거
                generated_content = self._remove_markdown_formatting(generated_content)

                # 실제 글자수 확인 (공백 포함)
                actual_length = len(generated_content)
                diff = abs(actual_length - target_length)

                # 최선의 결과 저장
                if diff < best_diff:
                    best_diff = diff
                    best_result = generated_content

                # 목표 범위 내에 들어오면 즉시 반환
                if min_length <= actual_length <= max_length:
                    print(f"✅ 목표 글자수 달성! (목표: {target_length}자, 실제: {actual_length}자, 시도: {attempt + 1}회)")
                    return generated_content

                # 범위를 벗어났지만 마지막 시도가 아니면 재시도
                if attempt < max_retries - 1:
                    print(f"⚠️ 글자수 미달성 (목표: {target_length}자, 실제: {actual_length}자) - {attempt + 2}차 시도 중...")
                    continue

            except Exception as e:
                # 에러 발생 시 best_result가 있으면 반환, 없으면 에러 발생
                if best_result:
                    print(f"⚠️ AI 생성 중 에러 발생, 최선의 결과 반환 (목표: {target_length}자, 실제: {len(best_result)}자)")
                    return best_result
                raise Exception(f"AI 각색 중 오류 발생: {str(e)}")

        # 모든 시도 후 최선의 결과 반환
        actual_length = len(best_result) if best_result else 0
        print(f"📊 최선의 결과 반환 (목표: {target_length}자, 실제: {actual_length}자, {max_retries}회 시도)")
        return best_result if best_result else ""

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
            # DB에서 GPT API 키 로드
            gpt_api_key = await get_api_key_from_db("gpt")
            if not gpt_api_key:
                raise Exception("GPT API 키가 설정되지 않았습니다.")

            http_client = httpx.Client(timeout=httpx.Timeout(connect=30.0, read=60.0, write=30.0, pool=30.0))
            openai_client = OpenAI(api_key=gpt_api_key, http_client=http_client, timeout=60.0)

            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",  # 간단한 작업에는 mini 모델 사용
                max_tokens=500,
                temperature=0.5,
                messages=[{"role": "user", "content": prompt}],
            )

            result = response.choices[0].message.content

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

    async def generate_hooking_titles(
        self, content: str, specialty: str = "의료"
    ) -> List[str]:
        """
        클릭하고 싶은 후킹성 제목 5개 생성

        Args:
            content: 본문 내용
            specialty: 진료 과목

        Returns:
            후킹성 제목 5개
        """
        prompt = f"""다음 블로그 글의 핵심 내용을 파악하여, 클릭하고 싶어지는 매력적인 제목 5개를 만들어주세요.

[블로그 내용]
{content[:800]}

[제목 작성 가이드]
- 호기심을 자극하면서도 자극적이지 않게
- 검색 키워드가 자연스럽게 포함되도록
- 50자 이내
- 질문형, 비교형, 팁 제공형 등 다양한 형식 활용
- 의료법 위반 표현(최고, 100%, 완치 등) 금지

[형식]
1. 제목1
2. 제목2
3. 제목3
4. 제목4
5. 제목5"""

        try:
            # DB에서 GPT API 키 로드
            gpt_api_key = await get_api_key_from_db("gpt")
            if not gpt_api_key:
                raise Exception("GPT API 키가 설정되지 않았습니다.")

            http_client = httpx.Client(timeout=httpx.Timeout(connect=30.0, read=60.0, write=30.0, pool=30.0))
            openai_client = OpenAI(api_key=gpt_api_key, http_client=http_client, timeout=60.0)

            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=600,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
            )

            result = response.choices[0].message.content

            # 결과 파싱
            titles = []
            for line in result.strip().split("\n"):
                # "1. ", "2. " 등의 패턴 제거
                match = re.match(r'^\d+\.\s*(.+)$', line.strip())
                if match:
                    titles.append(match.group(1).strip())

            return titles[:5]

        except Exception as e:
            print(f"Error generating titles: {e}")
            return ["제목 생성 실패"] * 5

    async def generate_subtitles(self, content: str) -> List[str]:
        """
        본문에 들어갈 매력적인 소제목 4개 생성

        Args:
            content: 본문 내용

        Returns:
            소제목 4개
        """
        prompt = f"""다음 블로그 글을 4개의 섹션으로 나누고, 각 섹션에 어울리는 매력적인 소제목을 만들어주세요.

[블로그 내용]
{content}

[소제목 작성 가이드]
- 호기심을 유발하는 질문형 또는 친근한 평서형
- 각 소제목이 내용의 흐름을 자연스럽게 나타내도록
- 20자 이내
- "## " 마크다운 형식 사용

[예시]
## 왜 이런 증상이 생기는 걸까요?
## 효과적인 관리 방법은?
## 실제 환자분들의 경험
## 궁금한 점들, 정리해드려요

위와 같은 스타일로 4개의 소제목만 생성해주세요."""

        try:
            # DB에서 GPT API 키 로드
            gpt_api_key = await get_api_key_from_db("gpt")
            if not gpt_api_key:
                raise Exception("GPT API 키가 설정되지 않았습니다.")

            http_client = httpx.Client(timeout=httpx.Timeout(connect=30.0, read=60.0, write=30.0, pool=30.0))
            openai_client = OpenAI(api_key=gpt_api_key, http_client=http_client, timeout=60.0)

            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=400,
                temperature=0.6,
                messages=[{"role": "user", "content": prompt}],
            )

            result = response.choices[0].message.content

            # "## " 패턴으로 소제목 추출
            subtitles = []
            for line in result.strip().split("\n"):
                if line.startswith("##"):
                    subtitle = line.replace("##", "").strip()
                    subtitles.append(subtitle)

            return subtitles[:4]

        except Exception as e:
            print(f"Error generating subtitles: {e}")
            return ["소제목 생성 실패"] * 4


# Singleton instance
ai_rewrite_engine = AIRewriteEngine()
