"""
AI Rewrite Engine - Google Gemini 를 사용한 콘텐츠 각색
다양한 업종(의료, 법률, 음식점, 뷰티, 피트니스, 교육, 부동산 등) 지원

2026-09 개편
- Claude/OpenAI 경로 제거, Gemini 단일 스택으로 정리
- SDK 를 deprecated 된 google-generativeai 에서 google-genai 로 교체
- 프롬프트를 글자수 강제 위주에서 품질 기준 위주로 재작성
"""

import re
from typing import Dict, Optional, List
from app.core.config import settings
from app.models.user import IndustryType
from app.services.industry_config import get_industry_config, get_industry_ai_prompt
from app.services.quality_scorer import quality_scorer

try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None
    genai_types = None


# 원고 생성 기본 모델
DEFAULT_MODEL = "gemini-2.5-flash"

# 사고(thinking) 예산. Gemini 2.5 계열은 기본이 무제한에 가까워서
# 상한을 두지 않으면 max_output_tokens 를 사고 토큰이 잠식해 본문이 잘린다.
# 0 이면 사고 비활성. 긴 글은 구성을 잡는 데 사고가 도움이 되므로 적당히 남긴다.
THINKING_BUDGET = 2048
# 제목/소제목 같은 짧은 보조 작업은 사고가 필요 없다.
THINKING_BUDGET_LIGHT = 0

# 분량 보정 계수.
# Gemini 2.5 Flash 는 한국어 장문에서 요청 분량을 25~30% 초과해서 쓴다.
# 다 쓴 뒤 줄이라고 시켜도 잘 줄이지 못하므로(2332자 -> 2258자 수준),
# 처음부터 이 계수를 곱한 분량을 요구해서 결과가 목표에 떨어지게 한다.
# 모델을 바꾸면 이 값을 다시 재야 한다.
LENGTH_CALIBRATION = 0.78

# 품질 심사에 쓰는 모델. 판정만 하므로 싼 모델로 충분하다.
# gemini-2.5-flash-lite 는 신규 사용자에게 막혔다(404). 3.5 계열 lite 를 쓴다.
JUDGE_MODEL = "gemini-3.5-flash-lite"
# 이 점수 미만이면 채점 결과를 지적으로 넣어 한 번 고쳐 쓴다 (100점 만점).
QUALITY_THRESHOLD = 80


class APIKeyNotConfiguredError(Exception):
    """
    AI API 키가 설정되지 않았을 때 발생하는 예외
    사용자에게 친화적인 에러 메시지를 제공합니다.
    """
    def __init__(self, provider: str = "gemini"):
        self.provider = provider
        provider_names = {"gemini": "Gemini (Google)"}
        provider_name = provider_names.get(provider, provider)
        self.message = f"{provider_name} API 키가 설정되지 않았습니다. 관리자에게 문의해주세요."
        self.user_message = "AI 서비스가 일시적으로 사용 불가합니다. 관리자 > API 키에서 Gemini 키를 등록해주세요."
        super().__init__(self.message)


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
    if provider == "gemini":
        return settings.GEMINI_API_KEY
    return None


class AIRewriteEngine:
    """
    Google Gemini 를 사용한 콘텐츠 각색 엔진
    """

    def __init__(self):
        # 클라이언트는 호출 시점에 DB/환경변수 키로 새로 만든다.
        # (관리자 화면에서 키를 바꿔도 재시작 없이 반영되도록)
        self.gemini_available = GEMINI_AVAILABLE
        self.last_usage: Dict = {}
        self.last_quality: Optional[Dict] = None

    async def _gemini_call(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        max_output_tokens: int = 8192,
        temperature: float = 0.4,
        thinking_budget: int = THINKING_BUDGET,
        model: Optional[str] = None,
    ) -> Dict:
        """
        Gemini 호출 공통 경로.

        Returns:
            {"text": str, "model": str, "input_tokens": int,
             "output_tokens": int, "thinking_tokens": int, "truncated": bool}
        """
        if not GEMINI_AVAILABLE:
            raise Exception("google-genai SDK 가 설치되어 있지 않습니다. requirements.txt 를 확인하세요.")

        api_key = await get_api_key_from_db("gemini")
        if not api_key:
            raise APIKeyNotConfiguredError("gemini")

        model = model or DEFAULT_MODEL
        client = genai.Client(api_key=api_key)

        config_kwargs = {
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
            "top_p": 0.95,
            # 의료/법률 콘텐츠가 과도하게 차단되지 않도록 완화
            "safety_settings": [
                genai_types.SafetySetting(category=c, threshold="BLOCK_ONLY_HIGH")
                for c in (
                    "HARM_CATEGORY_HARASSMENT",
                    "HARM_CATEGORY_HATE_SPEECH",
                    "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "HARM_CATEGORY_DANGEROUS_CONTENT",
                )
            ],
            # 도구를 안 쓰므로 자동 함수 호출 경고를 끈다
            "automatic_function_calling": genai_types.AutomaticFunctionCallingConfig(disable=True),
        }
        # Flash Lite 계열은 thinking 설정을 아예 거부한다(400). 애초에 사고를 안 하므로 생략한다.
        if "lite" not in model:
            config_kwargs["thinking_config"] = genai_types.ThinkingConfig(thinking_budget=thinking_budget)
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt

        try:
            response = client.models.generate_content(
                model=model,
                contents=user_prompt,
                config=genai_types.GenerateContentConfig(**config_kwargs),
            )
        except Exception as e:
            # 일부 모델(2.5 Pro, 3.x Flash Lite)은 thinking_budget 지정 자체를 거부한다.
            # 그 경우에만 사고 설정을 빼고 한 번 더 시도한다.
            if "INVALID_ARGUMENT" not in str(e) or "thinking_config" not in config_kwargs:
                raise
            print(f"[Gemini] {model} 이 thinking 설정을 거부해 기본값으로 재시도합니다")
            config_kwargs.pop("thinking_config")
            response = client.models.generate_content(
                model=model,
                contents=user_prompt,
                config=genai_types.GenerateContentConfig(**config_kwargs),
            )

        usage = getattr(response, "usage_metadata", None)
        input_tokens = getattr(usage, "prompt_token_count", 0) or 0
        output_tokens = getattr(usage, "candidates_token_count", 0) or 0
        thinking_tokens = getattr(usage, "thoughts_token_count", 0) or 0

        # 토큰 상한에 걸려 잘렸는지 확인 (잘린 원고를 그대로 내보내면 안 된다)
        truncated = False
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            finish_reason = str(getattr(candidates[0], "finish_reason", "") or "")
            truncated = "MAX_TOKENS" in finish_reason.upper()

        text = response.text or ""

        return {
            "text": text,
            "model": model,
            "input_tokens": input_tokens,
            # 사고 토큰도 출력 단가로 과금되므로 비용 계산에 포함한다
            "output_tokens": output_tokens + thinking_tokens,
            "thinking_tokens": thinking_tokens,
            "truncated": truncated,
        }

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

    @staticmethod
    def _plan_structure(target_length: int, top_post_rules: Optional[Dict] = None) -> Dict:
        """
        목표 글자수를 '소제목 개수 / 문단 수' 라는, 모델이 실제로 지킬 수 있는
        구조 지시로 환산한다. LLM 은 글자를 셀 수 없으므로 글자수를 직접
        강제하는 대신 구조로 분량을 통제한다.
        """
        # 짧은 글에서 소제목 하한이 3이면 분량이 강제로 늘어난다. 2 까지 허용한다.
        headings = max(2, min(7, round(target_length / 500)))
        if top_post_rules:
            hc = ((top_post_rules.get("content") or {}).get("structure") or {}).get("heading_count")
            if hc and hc.get("optimal"):
                headings = max(3, min(8, int(hc["optimal"])))

        # 도입부와 마무리가 소제목 밖에서 약 15% 를 차지한다
        body_length = target_length * 0.85
        per_heading = body_length / headings
        # 실측상 한 문단이 200~230자로 나온다
        paragraphs = max(2, min(5, round(per_heading / 215)))
        return {
            "headings": headings,
            "paragraphs_per_heading": paragraphs,
            "chars_per_heading": int(per_heading),
        }

    def _build_system_prompt(
        self,
        doctor_profile: Dict,
        writing_perspective: str = "1인칭",
        custom_writing_style: Optional[Dict] = None,
        requirements: Optional[Dict] = None,
        target_length: int = 1500,
        seo_optimization: Optional[Dict] = None,
        top_post_rules: Optional[Dict] = None,
        industry_type: IndustryType = IndustryType.MEDICAL,
    ) -> str:
        """
        프로필 기반 시스템 프롬프트 생성 (업종별 최적화)

        구성 원칙 (Gemini 3/2.5 프롬프트 가이드 기준)
        - 강조 기호나 설득체 대신 직접적인 서술을 쓴다
        - 구분자는 XML 태그 한 가지로 통일한다
        - 금지 목록보다 좋은 예/나쁜 예 대조를 우선한다
        - 역할과 제약은 시스템 프롬프트 위쪽에 둔다
        """
        industry_config = get_industry_config(industry_type)
        industry_name = industry_config.get("name", "전문")
        compliance_warning = industry_config.get("compliance_warning", "")

        writing_style = custom_writing_style if custom_writing_style else doctor_profile.get("writing_style", {})
        signature_phrases = doctor_profile.get("signature_phrases", [])
        specialty = doctor_profile.get("specialty", industry_name)

        style_lines = [
            self._get_style_text(writing_style.get("formality", 5), "격식", "캐주얼한", "매우 격식있는"),
            self._get_style_text(writing_style.get("friendliness", 5), "친근함", "전문가다운", "친구같은"),
            self._get_style_text(writing_style.get("technical_depth", 5), "전문성", "쉬운 용어", "전문 용어 사용"),
            self._get_style_text(writing_style.get("storytelling", 5), "스토리텔링", "정보 중심", "이야기 중심"),
            self._get_style_text(writing_style.get("emotion", 5), "감정 표현", "객관적", "공감형"),
            self._get_style_text(writing_style.get("humor", 5), "유머", "진지한", "유머러스한"),
            self._get_style_text(writing_style.get("question_usage", 6), "질문형 문장", "평서문 위주", "질문형 많이 사용"),
            self._get_style_text(writing_style.get("metaphor_usage", 5), "비유·은유", "직접적 표현", "비유적 표현 활용"),
            self._get_style_text(writing_style.get("sentence_length", 5), "문장 길이", "짧고 간결하게", "길고 상세하게"),
        ]
        style_text = "\n".join(f"- {s}" for s in style_lines)
        if signature_phrases:
            style_text += f"\n- 자주 쓰는 표현: {', '.join(signature_phrases[:3])}"

        perspective_guide = self._get_perspective_guide(industry_type, industry_config)
        perspective_text = perspective_guide.get(writing_perspective, perspective_guide["1인칭"]).strip()

        intro_prompt = self._get_industry_intro_prompt(industry_type, industry_config, specialty)
        structure = self._plan_structure(target_length, top_post_rules)

        customer_term = {
            IndustryType.MEDICAL: "환자",
            IndustryType.LEGAL: "의뢰인",
            IndustryType.RESTAURANT: "손님",
            IndustryType.BEAUTY: "고객",
            IndustryType.FITNESS: "회원",
            IndustryType.EDUCATION: "학생과 학부모",
            IndustryType.REALESTATE: "고객",
        }.get(industry_type, "고객")

        requirements_text = ""
        if requirements:
            common_reqs = requirements.get("common", [])
            individual_req = requirements.get("individual", "")
            if common_reqs or individual_req:
                lines = [f"- {req}" for req in common_reqs]
                if individual_req:
                    lines.append(f"- {individual_req}")
                requirements_text = "\n\n<반영할 요청사항>\n" + "\n".join(lines) + "\n</반영할 요청사항>"

        # 2026 네이버는 키워드 빈도·글자수 대신 하이퍼클로바X 기반 문맥 평가를 쓴다.
        # 따라서 '어떤 표현을 쓰라'가 아니라 '무엇이 글 안에 있어야 하는가'로 서술한다.
        seo_text = ""
        if seo_optimization and seo_optimization.get("enabled"):
            seo_items = []
            if seo_optimization.get("experience_focus"):
                seo_items.append(
                    f"현장에서 자주 마주치는 상황을 구체적으로 쓴다. 어떤 상태로 오는지, "
                    f"무엇을 먼저 확인하는지, 어떤 갈림길에서 판단이 갈리는지를 적는다. "
                    f"다만 특정 {customer_term} 한 사람의 이야기로 쓰지 않는다. "
                    "이름이나 이니셜(김OO 같은 것), 나이와 성별을 붙인 개인 사례, "
                    "그 사람이 어떻게 좋아졌다는 결과담은 쓰지 않는다. "
                    "'이런 경우가 많습니다', '대개 이렇게 진행됩니다' 처럼 반복되는 패턴으로 서술한다."
                )
            if seo_optimization.get("expertise"):
                seo_items.append(
                    "겉으로 드러나는 설명 한 단계 아래를 짚는다. 왜 그렇게 되는지의 기전, "
                    "비슷해 보이지만 다른 경우를 구분하는 기준, 판단이 갈리는 지점을 쓴다."
                )
            if seo_optimization.get("originality"):
                seo_items.append(
                    "같은 키워드의 다른 글에는 없을 내용이 최소 한 군데 있다. "
                    "흔한 오해를 바로잡거나, 통념과 다른 관찰을 근거와 함께 제시한다."
                )
            if seo_optimization.get("timeliness"):
                seo_items.append(
                    "지금 시점과 연결한다. 계절적 요인, 최근 바뀐 지침, 요즘 늘어난 문의 같은 것."
                )
            if seo_optimization.get("topic_concentration"):
                seo_items.append(
                    "주제를 하나로 좁힌다. 곁가지로 새지 않고, 모든 소제목이 그 주제의 다른 면을 다룬다."
                )
            if seo_optimization.get("trustworthiness"):
                seo_items.append(
                    "근거를 밝힌다. 학회 지침, 공공기관 자료, 연구 결과를 인용할 때는 어디서 나온 것인지 "
                    "함께 적는다. 확실하지 않은 것은 확실하지 않다고 쓴다."
                )
            if seo_optimization.get("source_authority"):
                seo_items.append(
                    "공신력 있는 출처를 우선 인용한다. 보건복지부, 질병관리청, 국민건강보험공단, 관련 학회 등."
                )
            if seo_optimization.get("multi_perspective"):
                seo_items.append(
                    "선택지가 여럿인 문제는 한쪽만 밀지 않는다. 각각의 장단점과, 어떤 경우에 어느 쪽이 "
                    "맞는지를 같이 쓴다."
                )
            if seo_optimization.get("search_intent_match"):
                seo_items.append(
                    "이 키워드로 검색한 사람의 실제 질문에 글 안에서 답이 끝난다. "
                    "읽고 나서 다시 검색하게 만들 만한 후속 궁금증까지 미리 다룬다."
                )
            if seo_items:
                seo_text = (
                    "\n\n<글에 들어가야 할 것>\n"
                    + "\n".join(f"- {s}" for s in seo_items)
                    + "\n</글에 들어가야 할 것>"
                )

        top_post_rules_text = ""
        if top_post_rules:
            lines = []
            title_rules = top_post_rules.get("title") or {}
            if title_rules.get("length"):
                ln = title_rules["length"]
                lines.append(f"- 제목 길이: {ln.get('min', 20)}~{ln.get('max', 45)}자, 최적 {ln.get('optimal', 30)}자")
            if title_rules.get("keyword_placement"):
                kp = title_rules["keyword_placement"]
                pos = {"front": "앞부분", "middle": "중간", "end": "끝부분"}.get(kp.get("best_position", "front"), "앞부분")
                lines.append(f"- 제목의 {pos}에 핵심 키워드를 넣는다 (상위글 {kp.get('rate', 80)}%가 그렇게 함)")
            content_rules = top_post_rules.get("content") or {}
            if content_rules.get("length"):
                ln = content_rules["length"]
                lines.append(f"- 상위글 본문 길이대: {ln.get('min', 1500)}~{ln.get('max', 3500)}자")
            struct = content_rules.get("structure") or {}
            if struct.get("keyword_count"):
                kc = struct["keyword_count"]
                lines.append(
                    f"- 핵심 키워드는 본문에 {kc.get('min', 5)}~{kc.get('max', 15)}회 정도 자연스럽게 "
                    "나온다. 억지로 채우지 않는다"
                )
            if lines:
                top_post_rules_text = (
                    "\n\n<상위 노출 글 분석 결과>\n실제 검색 상위 글을 분석한 수치다. 참고해서 맞춘다.\n"
                    + "\n".join(lines)
                    + "\n</상위 노출 글 분석 결과>"
                )

        # ── 이 병원만의 것 ──────────────────────────────────────────────
        # 여기가 "여기는 다르네" 를 만드는 유일한 재료다. 없으면 어느 병원 글이나 똑같아진다.
        # 자랑 나열이 되면 광고로 읽히고 의료법 비교·과장 조항에도 걸리므로,
        # 반드시 독자의 문제를 설명하는 흐름 안에서 나오도록 쓰는 법까지 지정한다.
        differentiators = doctor_profile.get("differentiators") or {}
        diff_items = differentiators.get("items") or []
        diff_philosophy = differentiators.get("philosophy") or ""
        differentiator_text = ""
        if diff_items or diff_philosophy:
            lines = []
            if diff_philosophy:
                lines.append(f"- 진료 원칙: {diff_philosophy}")
            for it in diff_items:
                if isinstance(it, dict):
                    cat = it.get("category") or ""
                    txt = it.get("text") or ""
                    lines.append(f"- {f'[{cat}] ' if cat else ''}{txt}")
                elif str(it).strip():
                    lines.append(f"- {it}")

            differentiator_text = f"""

<이 병원만의 것>
아래는 이 병원에만 있는 내용이다. 읽는 사람이 "여기는 좀 다르네" 하고 느끼게 만드는 유일한 재료다.
{chr(10).join(lines)}

쓰는 방법
- 최소 두 군데에 나눠서 녹인다. 한곳에 몰아 소개하지 않는다.
- 소개 문장으로 쓰지 않는다. 독자의 문제를 설명하다가 그래서 나는 이렇게 한다로 이어지게 쓴다.
  약한 예: 저희는 최신 초음파 장비를 갖추고 있습니다.
  좋은 예: 엑스레이만으로는 초기 연골 손상이 잘 안 보입니다. 그래서 저는 초음파로 한 번 더 봅니다. 그 한 번에서 치료 방향이 갈리는 경우가 자주 있습니다.
- 장비나 자격 자체를 자랑하지 말고, 그것 때문에 환자가 무엇을 덜 겪는지를 쓴다.
- 다른 병원과 비교하거나 최고·유일·최초 같은 말을 쓰지 않는다. 의료법 위반이다.
- 위에 적힌 것 말고 다른 장비, 자격, 실적, 수치를 지어내지 않는다.
</이 병원만의 것>"""

        compliance_text = f"\n- {compliance_warning}" if compliance_warning else ""

        system_prompt = f"""<역할>
{intro_prompt}
지금 쓰는 글은 검색으로 들어온 사람이 끝까지 읽고 도움이 됐다고 느끼는 글이어야 한다.
</역할>

<목소리>
{style_text}

{perspective_text}
</목소리>

<좋은 글의 기준>
이 글은 같은 키워드로 검색했을 때 나오는 다른 글보다 확실히 나아야 한다. 기준은 네 가지다.

1. 구체성. 일반론 대신 숫자, 기간, 상황, 장면을 쓴다.
   약한 문장: 초기에 치료하는 것이 중요합니다.
   좋은 문장: 통증이 3주를 넘기면 회복에 걸리는 시간이 눈에 띄게 길어집니다. 2주 만에 오신 분과 석 달 만에 오신 분은 경과가 확실히 다릅니다.

2. 경험. 직접 겪은 사람만 아는 디테일을 넣는다. 현장에서 실제로 오가는 말, 자주 나오는 오해, {customer_term}이 놓치는 지점.
   약한 문장: 많은 분들이 걱정하십니다.
   좋은 문장: 열에 아홉은 수술해야 하냐부터 물어보십니다. 그런데 실제로 수술까지 가는 경우는 그보다 훨씬 적습니다.

3. 정직. 모르는 것, 개인차, 한계를 그대로 말한다. 단정하지 않는 문장이 오히려 신뢰를 만든다.
   약한 문장: 이 방법이면 반드시 좋아집니다.
   좋은 문장: 대부분은 이 방법으로 나아지지만, 원인이 다른 경우에는 효과가 없습니다. 그래서 먼저 확인이 필요합니다.

4. 리듬. 문장 길이를 섞는다. 긴 설명 뒤에는 짧은 문장을 하나 둔다. 같은 종결어미를 세 번 연속 쓰지 않는다.
</좋은 글의 기준>

<반드시 지킬 네 가지>
아래는 검증된 커뮤니케이션 연구에서 나온 규칙이다. 하나라도 빠지면 글이 힘을 잃는다.

1. 겁을 준 만큼 방법을 준다.
   미루면 어떻게 되는지 말했으면, 그만큼 해결할 수 있다는 이야기를 같이 넣는다.
   위험만 크게 말하고 대처법이 약하면 읽는 사람은 겁먹는 대신 그냥 외면한다.
   위험을 말한 문단에는 반드시 "이렇게 하면 늦출 수 있습니다", "집에서도 할 수 있습니다" 가 따라붙는다.

2. 단점을 인정하면 반드시 대응을 붙인다.
   약한 예: 이 방법이 모두에게 듣는 것은 아닙니다. (인정만 하고 끝 — 오히려 불안만 남는다)
   좋은 예: 이 방법이 모두에게 듣지는 않습니다. 원인이 다른 경우가 있기 때문입니다. 그래서 저는 먼저 어느 쪽인지부터 확인합니다.

3. 읽고 나면 오늘 할 일이 남는다.
   구체적인 행동을 두세 개 넣는다. 횟수와 순서를 붙인다. (하루 10분씩, 먼저 ~하고 그다음 ~)
   그리고 언제 병원에 와야 하는지 판단 기준을 한 문장 넣는다.
   예: 통증이 3주 넘게 이어지거나 밤에 잠을 깰 정도라면 진료를 받아보세요.

4. 전문용어는 그 자리에서 푼다.
   처음 나오는 용어는 괄호나 "쉽게 말하면" 으로 한 번 풀어준다.
   피동형을 쓰지 않는다. "~되어집니다", "~되고 있습니다" 는 "~합니다", "~입니다" 로 쓴다.
</반드시 지킬 네 가지>

<구조>
- 소제목 {structure['headings']}개로 나눈다. 소제목 하나가 맡는 분량은 공백 포함 {structure['chars_per_heading']}자 안팎이고, 문단 수로는 {structure['paragraphs_per_heading']}개 정도다.
- 이 분량을 넘기지 않는다. 할 말이 남아도 소제목 하나당 배정된 만큼만 쓴다.
- 첫 문단은 읽는 사람이 자기 얘기라고 느낄 상황 하나로 연다. 인사말이나 자기소개로 시작하지 않는다.
- 소제목은 그 아래에 무슨 내용이 나오는지 정직하게 알려주는 한 줄로 쓴다. 궁금증만 자극하고 답을 안 주는 낚시성 문구는 쓰지 않는다.
- 마지막은 읽은 사람이 오늘 당장 할 수 있는 일 하나를 남기고 끝낸다.
</구조>

<표기>
- 순수한 한글 텍스트로만 쓴다. 별표, 우물정자, 붙임표, 밑줄, 백틱, 번호 목록 같은 마크다운 기호를 쓰지 않는다.
- 소제목은 앞뒤로 빈 줄을 둔 한 줄짜리 텍스트로 둔다.
- 대괄호로 묶은 섹션 이름을 쓰지 않는다.
</표기>

<쓰지 않는 표현>
- 번역체. 아래처럼 고쳐 쓴다.
  꾸준히 관리하는 것이 중요합니다 -> 꾸준히 관리해야 합니다
  조기에 발견하는 것이 좋습니다 -> 일찍 발견할수록 낫습니다
  치료가 진행되어집니다 -> 치료를 진행합니다
  그것은 흔한 증상인 것입니다 -> 흔한 증상입니다
- 습관적으로 붙는 빈 수식어: 매우, 정말, 굉장히, 아주
- AI 가 쓴 티가 나는 상투구: 결론적으로, 종합하면, ~에 대해 알아보겠습니다, 오늘은 ~에 대해 소개해드리려고 합니다
- 과장과 단정: 최고, 1등, 100%, 완치, 부작용 없는, 즉시 효과, 단 3일 만에
- 상업적 유인: 지금 바로 예약, 무료 상담, 할인, 이벤트, 서둘러 연락
- 지어낸 개인 사례: 이름이나 이니셜을 붙인 특정인의 치료 전후 이야기. 실제 사례가 아니면 쓰지 않는다{compliance_text}
</쓰지 않는 표현>

<쓰기 전에 정할 것>
본문을 쓰기 전에 다음 세 가지를 스스로 정한다. 정한 내용 자체는 출력하지 않는다.
- 이 키워드로 검색한 사람이 진짜 알고 싶은 것 한 가지
- 다른 글에는 없고 이 글에만 있을 내용 한 가지
- 소제목 {structure['headings']}개의 순서와 각각이 맡을 역할
</쓰기 전에 정할 것>{differentiator_text}{requirements_text}{seo_text}{top_post_rules_text}"""

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

    def _get_industry_intro_prompt(self, industry_type: IndustryType, industry_config: Dict, specialty: str) -> str:
        """
        업종별 시스템 프롬프트 소개 문구 생성
        """
        industry_intros = {
            IndustryType.MEDICAL: f"당신은 {specialty} 전문의이며, 환자들과 소통하는 블로그를 직접 운영하는 원장입니다.",
            IndustryType.LEGAL: f"당신은 {specialty} 전문 변호사이며, 의뢰인들과 소통하는 블로그를 직접 운영하고 있습니다.",
            IndustryType.RESTAURANT: f"당신은 {specialty} 전문점을 운영하는 대표이며, 손님들과 소통하는 블로그를 직접 운영하고 있습니다.",
            IndustryType.BEAUTY: f"당신은 {specialty} 전문 뷰티샵을 운영하는 원장이며, 고객들과 소통하는 블로그를 직접 운영하고 있습니다.",
            IndustryType.FITNESS: f"당신은 {specialty} 전문 센터를 운영하는 대표이며, 회원들과 소통하는 블로그를 직접 운영하고 있습니다.",
            IndustryType.EDUCATION: f"당신은 {specialty} 전문 교육기관을 운영하는 원장이며, 학생/학부모와 소통하는 블로그를 직접 운영하고 있습니다.",
            IndustryType.REALESTATE: f"당신은 {specialty} 전문 공인중개사이며, 고객들과 소통하는 블로그를 직접 운영하고 있습니다.",
        }

        return industry_intros.get(
            industry_type,
            f"당신은 {specialty} 분야의 전문가이며, 고객들과 소통하는 블로그를 직접 운영하고 있습니다."
        )

    def _get_perspective_guide(self, industry_type: IndustryType, industry_config: Dict) -> Dict[str, str]:
        """
        업종별 시점 작성 가이드 생성
        """
        industry_name = industry_config.get("name", "전문")
        business_label = industry_config.get("business_name_label", "업체명")

        # 업종별 맞춤 예시
        industry_examples = {
            IndustryType.MEDICAL: {
                "1인칭_examples": '"진료실에서 환자분들을 만나다 보면...", "제가 항상 강조하는 것은..."',
                "3인칭_examples": '"전문의들은 이 증상을 ~라고 설명한다", "최근 연구 결과에 따르면..."',
                "대화형_examples": '"혹시 아침에 일어났을 때 목이 칼칼하신가요?", "함께 알아볼까요?"',
                "owner_term": "원장님",
                "customer_term": "환자",
                "action_term": "진료하면서",
            },
            IndustryType.LEGAL: {
                "1인칭_examples": '"제 경험상 이런 사건에서는...", "수많은 의뢰인을 만나며 느낀 점은..."',
                "3인칭_examples": '"변호사들은 이런 상황을 ~라고 판단한다", "대법원 판례에 따르면..."',
                "대화형_examples": '"혹시 비슷한 상황에 처해 계신가요?", "이런 경우는 어떨까요?"',
                "owner_term": "변호사",
                "customer_term": "의뢰인",
                "action_term": "사건을 맡으면서",
            },
            IndustryType.RESTAURANT: {
                "1인칭_examples": '"저희 식당에서 가장 인기 있는 메뉴는...", "제가 직접 고른 재료로..."',
                "3인칭_examples": '"전문 셰프들은 이 요리를 ~하게 표현한다", "요리 전문가들에 따르면..."',
                "대화형_examples": '"오늘 점심 뭐 드실지 고민이신가요?", "맛있는 식사 어떠세요?"',
                "owner_term": "대표",
                "customer_term": "손님",
                "action_term": "가게를 운영하면서",
            },
            IndustryType.BEAUTY: {
                "1인칭_examples": '"저희 샵에서 가장 많이 하시는 시술은...", "제가 추천드리는 스타일은..."',
                "3인칭_examples": '"전문 디자이너들은 이 스타일을 ~라고 분석한다", "뷰티 트렌드에 따르면..."',
                "대화형_examples": '"요즘 머리 스타일 고민이신가요?", "새로운 변화를 원하시나요?"',
                "owner_term": "원장",
                "customer_term": "고객",
                "action_term": "시술하면서",
            },
            IndustryType.FITNESS: {
                "1인칭_examples": '"제가 회원님들께 항상 말씀드리는 것은...", "트레이너로서 느낀 점은..."',
                "3인칭_examples": '"피트니스 전문가들은 이 운동을 ~라고 설명한다", "연구 결과에 따르면..."',
                "대화형_examples": '"오늘 운동 계획 세우셨나요?", "함께 건강해지실 준비 되셨나요?"',
                "owner_term": "트레이너",
                "customer_term": "회원",
                "action_term": "지도하면서",
            },
            IndustryType.EDUCATION: {
                "1인칭_examples": '"제가 학생들을 가르치면서 느낀 점은...", "우리 학원에서 강조하는 것은..."',
                "3인칭_examples": '"교육 전문가들은 이 학습법을 ~라고 평가한다", "최신 교육 연구에 따르면..."',
                "대화형_examples": '"공부하다 막히는 부분이 있으신가요?", "함께 성적을 올려볼까요?"',
                "owner_term": "원장",
                "customer_term": "학생/학부모",
                "action_term": "가르치면서",
            },
            IndustryType.REALESTATE: {
                "1인칭_examples": '"제가 이 지역을 오래 담당하면서 느낀 점은...", "중개사로서 말씀드리면..."',
                "3인칭_examples": '"부동산 전문가들은 이 시세를 ~라고 분석한다", "시장 동향에 따르면..."',
                "대화형_examples": '"어떤 집을 찾고 계신가요?", "이 매물 한번 살펴보실까요?"',
                "owner_term": "공인중개사",
                "customer_term": "고객",
                "action_term": "중개하면서",
            },
        }

        # 기본값 (OTHER 업종)
        default_examples = {
            "1인칭_examples": '"제 경험상...", "저희 업체에서는..."',
            "3인칭_examples": '"전문가들은 ~라고 말한다", "업계에 따르면..."',
            "대화형_examples": '"어떤 서비스를 찾고 계신가요?", "함께 알아볼까요?"',
            "owner_term": "대표",
            "customer_term": "고객",
            "action_term": "운영하면서",
        }

        examples = industry_examples.get(industry_type, default_examples)

        return {
            "1인칭": f"""
작성 시점: 1인칭 (저, 제가, 우리 {business_label.replace('명', '')})
- "제 경험상", "저는 ~라고 생각합니다", "{examples['action_term']} 느낀 점은" 같은 표현 사용
- {examples['owner_term']}이 직접 {examples['customer_term']}에게 이야기하는 느낌으로 작성
- 예: {examples['1인칭_examples']}
""",
            "3인칭": f"""
작성 시점: 3인칭 객관적 관점
- "{industry_name} 전문가들은", "업계에서는", "연구에 따르면" 같은 표현 사용
- 객관적이고 전문적인 정보 전달에 초점
- 예: {examples['3인칭_examples']}
""",
            "대화형": f"""
작성 시점: 직접 대화하는 느낌 (2인칭 활용)
- "여러분", "~하셨나요?", "~해보세요" 같은 직접 대화 표현 사용
- 독자에게 직접 말을 거는 것처럼 친근하고 상호작용적으로 작성
- 예: {examples['대화형_examples']}
"""
        }

    def _build_user_prompt(
        self,
        original_content: str,
        framework: str,
        persuasion_level: int,
        target_length: int,
        target_audience: Optional[Dict] = None,
        top_post_rules: Optional[Dict] = None,
    ) -> str:
        """
        각색 요구사항 프롬프트 생성

        긴 입력에서는 지시를 데이터 뒤에 두는 편이 준수율이 높다는
        Gemini 프롬프트 가이드를 따라, 원본을 먼저 두고 지시를 뒤에 붙인다.
        """
        framework_instructions = {
            "관심유도형": (
                "흥미로운 상황이나 질문으로 열고, 관련 정보를 풀어낸 뒤, 해결 방법과 그 효과를 설명하고, "
                "실천할 수 있는 조언으로 닫는다. 단계가 겉으로 드러나지 않게 하나의 이야기처럼 잇는다."
            ),
            "공감해결형": (
                "많은 사람이 겪는 고민에 공감하며 열고, 그 문제를 방치하면 어떻게 되는지 설명한 뒤, "
                "실제로 효과가 있는 방법을 구체적으로 안내한다. 도와주고 싶은 마음이 문장에서 느껴지게 쓴다."
            ),
            "스토리형": (
                "비슷한 상황으로 찾아온 사람의 사례로 연다. 무엇을 보고 어떻게 판단했는지, 어떤 과정을 거쳤고 "
                "결과가 어땠는지를 시간 순서로 보여준다. 마지막에 읽는 사람이 가져갈 교훈을 남긴다."
            ),
            "질문답변형": (
                "실제로 자주 받는 질문들을 자연스럽게 꺼내고 하나씩 답한다. 질문과 답을 표시하는 기호나 "
                "번호 없이, 대화가 이어지듯 쓴다."
            ),
            "정보전달형": (
                "개념을 명확히 정의하고, 원인과 증상, 판단 기준, 대응 방법을 논리적 순서로 설명한다. "
                "근거를 함께 제시하고, 실생활에 적용할 수 있는 내용으로 닫는다. 딱딱해지지 않게 쓴다."
            ),
            "경험공유형": (
                "오래 일하며 얻은 실질적인 노하우를 나눈다. 자주 마주치는 오해를 바로잡고, "
                "본인만의 판단 기준과 접근법이 드러나게 쓴다."
            ),
        }

        persuasion_requirements = {
            1: "사실 위주로 담백하게. 감정 표현을 절제한다.",
            2: "사실에 근거와 이유를 덧붙인다. 설명을 한 단계 더 풀어 쓴다.",
            3: "읽는 사람의 심리와 고민을 반영한다. 공감이 느껴지게 쓴다.",
            4: "공감에 더해, 다음에 무엇을 하면 되는지 구체적인 행동을 안내한다. 다만 상업적 유인 문구는 쓰지 않는다.",
            5: "사례 중심의 스토리텔링으로 끌고 간다. 감정의 진폭을 크게 하되 과장하지 않는다.",
        }

        audience_text = ""
        if target_audience:
            age = target_audience.get("age_range", "")
            gender = target_audience.get("gender", "")
            concerns = target_audience.get("concerns", [])
            parts = []
            if age:
                parts.append(f"{age}세")
            if gender and gender != "무관":
                parts.append(gender)
            if concerns:
                parts.append(f"주요 고민은 {', '.join(concerns[:3])}")
            if parts:
                audience_text = f"\n\n<읽는 사람>\n{' / '.join(parts)}\n</읽는 사람>"

        structure = self._plan_structure(target_length, top_post_rules)

        return f"""<원본 정보>
{original_content}
</원본 정보>

<전개 방식>
{framework_instructions.get(framework, framework_instructions['정보전달형'])}
</전개 방식>

<각색 강도>
{persuasion_requirements.get(persuasion_level, persuasion_requirements[3])}
</각색 강도>{audience_text}

<분량>
글 전체가 공백 포함 {target_length}자다. 도입부와 마무리를 뺀 본문을 소제목 {structure['headings']}개로 나누면 소제목 하나당 {structure['chars_per_heading']}자, 문단 {structure['paragraphs_per_heading']}개 정도가 된다.
{target_length}자는 상한이기도 하다. 넘기지 않는다.
분량은 내용을 채워서 맞추는 것이지 문장을 늘려서 맞추는 것이 아니다. 같은 말을 다시 하거나 수식어를 덧붙여 늘리지 않는다.
</분량>

위 원본 정보를 바탕으로 블로그 글을 쓴다.
첫 줄에 제목을 한 줄로 쓰고, 빈 줄을 하나 둔 다음 본문을 시작한다.
제목은 검색 키워드가 자연스럽게 들어가되 자극적이지 않게 쓴다."""

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
        ai_provider: str = "gemini",
        ai_model: Optional[str] = None,
        seo_optimization: Optional[Dict] = None,
        top_post_rules: Optional[Dict] = None,
        industry_type: IndustryType = IndustryType.MEDICAL,
        keyword: Optional[str] = None,
        quality_check: bool = True,
    ) -> str:
        """
        콘텐츠 각색 실행 (Gemini 전용)

        분량 맞추기 방식
        - 예전에는 목표 글자수의 2.0~2.5배를 요구하며 최대 3회 전체 재생성했다.
          프롬프트가 실제 목표와 다른 숫자를 말하게 되고, 매번 처음부터 다시 쓰느라
          비용은 3배가 되면서 품질은 시도마다 들쭉날쭉했다.
        - 지금은 목표 그대로 한 번 쓰게 한 뒤, 범위를 벗어난 경우에만
          그 원고를 넘겨주고 늘리거나 줄이게 한다. 최대 2회 호출.

        Args:
            ai_provider: 하위 호환용으로 남겨둔 인자. Gemini 로 고정된다.
            ai_model: 사용할 Gemini 모델. 비우면 DEFAULT_MODEL.
            keyword: 이 글이 노리는 검색 키워드. 채점에서 주제 집중도 판정에 쓴다.
            quality_check: 품질 채점과 개선 패스를 돌릴지. 채점 결과는 self.last_quality 에 남는다.

        Returns:
            각색된 블로그 포스팅
        """
        model = ai_model or DEFAULT_MODEL
        # 모델이 요청 분량을 초과해서 쓰는 만큼 미리 깎아서 요구한다 (LENGTH_CALIBRATION 참고)
        ask_length = max(400, int(target_length * LENGTH_CALIBRATION))
        # 한국어는 Gemini 토크나이저 기준 글자당 대략 1.2~1.5 토큰.
        # 여유를 두고 2.5배 + 사고 예산 + 여유분으로 상한을 잡는다.
        max_output_tokens = min(32768, max(4096, int(target_length * 2.5) + THINKING_BUDGET + 1024))

        system_prompt = self._build_system_prompt(
            doctor_profile,
            writing_perspective,
            custom_writing_style,
            requirements,
            ask_length,
            seo_optimization,
            top_post_rules,
            industry_type,
        )
        user_prompt = self._build_user_prompt(
            original_content, framework, persuasion_level, ask_length, target_audience, top_post_rules
        )

        total_input = 0
        total_output = 0
        total_thinking = 0

        try:
            result = await self._gemini_call(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                max_output_tokens=max_output_tokens,
                temperature=0.7,
                thinking_budget=THINKING_BUDGET,
                model=model,
            )
        except APIKeyNotConfiguredError:
            raise
        except Exception as e:
            raise Exception(f"AI 각색 중 오류 발생: {str(e)}")

        total_input += result["input_tokens"]
        total_output += result["output_tokens"]
        total_thinking += result["thinking_tokens"]

        content = self._remove_markdown_formatting(result["text"])
        actual_length = len(content)

        # 안전 필터에 걸리거나 빈 응답이 오면 빈 원고를 저장하지 말고 알린다
        if not content.strip():
            raise Exception(
                "AI가 빈 응답을 반환했습니다. 원본 내용이 안전 필터에 걸렸을 수 있습니다. "
                "내용을 조금 바꿔서 다시 시도해주세요."
            )

        if result["truncated"]:
            print(f"[WARNING] 출력 토큰 상한에 걸려 원고가 잘렸습니다 (모델: {model}, 상한: {max_output_tokens})")

        # ── 품질 채점 → 부족하면 한 번 고쳐 쓴다 ──────────────────────
        report = None
        if quality_check:
            differentiators = doctor_profile.get("differentiators") or None
            report, usage_delta = await self._score(
                content, keyword=keyword, differentiators=differentiators,
                source_text=original_content,
            )
            total_input += usage_delta[0]
            total_output += usage_delta[1]
            total_thinking += usage_delta[2]
            print(f"[품질] {report['total']}점 ({report['grade']})"
                  f"{' · 의료광고법 상한 적용' if report['capped_by_law'] else ''}")

            if report["total"] < QUALITY_THRESHOLD:
                notes = quality_scorer.build_revision_notes(report)
                if notes:
                    revised, usage_delta = await self._revise(
                        content, notes, system_prompt, max_output_tokens, model, target_length
                    )
                    total_input += usage_delta[0]
                    total_output += usage_delta[1]
                    total_thinking += usage_delta[2]

                    if revised:
                        new_report, usage_delta = await self._score(
                            revised, keyword=keyword, differentiators=differentiators,
                            source_text=original_content,
                        )
                        total_input += usage_delta[0]
                        total_output += usage_delta[1]
                        total_thinking += usage_delta[2]
                        print(f"[품질] 재작성 후 {new_report['total']}점 ({new_report['grade']})"
                              f" [원점수 {new_report['raw_total']} <- {report['raw_total']}]")
                        # 나아졌을 때만 채택한다 (법 위반 감소 > 원점수 순으로 판정)
                        if quality_scorer.is_better(new_report, report):
                            content = revised
                            report = new_report
                            actual_length = len(content)
                        else:
                            print("[품질] 재작성이 더 낫지 않아 1차 원고를 유지합니다")

        # ── 분량 맞추기는 마지막에 한다 ──────────────────────────────
        # 품질 재작성이 내용을 더하면서 분량을 밀어올리기 때문에,
        # 순서를 뒤집으면 애써 맞춘 분량이 다시 어긋난다.
        fitted, usage_delta = await self._fit_length(
            content, target_length, system_prompt, max_output_tokens, model
        )
        total_input += usage_delta[0]
        total_output += usage_delta[1]
        total_thinking += usage_delta[2]
        if fitted and fitted != content:
            content = fitted
            actual_length = len(content)
            # 분량만 손봤으므로 규칙 점수만 다시 매기고 LLM 심사는 재사용한다 (호출 절약)
            if report is not None:
                rules = quality_scorer.score_rules(
                    content, keyword=keyword,
                    differentiators=doctor_profile.get("differentiators") or None,
                    source_text=original_content,
                )
                report = quality_scorer.combine(rules, report.get("llm_judge"))
                print(f"[품질] 분량 조정 후 {report['total']}점 ({report['grade']})")

        self.last_usage = {
            "ai_provider": "gemini",
            "ai_model": model,
            "input_tokens": total_input,
            "output_tokens": total_output,
            "thinking_tokens": total_thinking,
            "total_tokens": total_input + total_output,
        }
        self.last_quality = report

        print(f"[생성 완료] 목표 {target_length}자 / 실제 {actual_length}자 / 사고 토큰 {total_thinking}")
        return content

    async def _fit_length(
        self,
        content: str,
        target_length: int,
        system_prompt: str,
        max_output_tokens: int,
        model: str,
    ):
        """
        목표 분량에서 벗어났을 때만 한 번 손본다. 전체 재생성이 아니라 늘리기/줄이기다.

        Returns:
            (content or None, (input_tokens, output_tokens, thinking_tokens))
        """
        actual_length = len(content)
        min_length = int(target_length * 0.9)
        max_length = int(target_length * 1.15)
        if not content or min_length <= actual_length <= max_length:
            return None, (0, 0, 0)

        # 모델은 글자를 셀 수 없으므로 '몇 자'가 아니라 '몇 문단'으로 지시한다
        gap = abs(actual_length - target_length)
        para_count = max(1, round(gap / 215))
        pct = round(gap / actual_length * 100)

        if actual_length < min_length:
            direction = "늘려서"
            how = (
                f"설명이 가장 얕은 곳을 골라 문단 {para_count}개 분량(전체의 약 {pct}%)을 더한다. "
                "사례나 근거를 추가하는 방식으로 채운다. "
                "새 소제목을 만들지 말고 기존 소제목 아래를 채운다. "
                "같은 말을 다시 하거나 수식어를 붙여서 늘리지 않는다."
            )
        else:
            direction = "줄여서"
            how = (
                f"문단 {para_count}개 분량(전체의 약 {pct}%)을 덜어낸다. "
                "중복되는 대목을 합치고, 곁가지로 새는 문단을 통째로 지운다. "
                "남기는 문단에서도 군더더기 문장을 덜어낸다. "
                "소제목 구성과 각 소제목의 핵심 내용은 그대로 둔다."
            )

        fix_prompt = f"""<원고>
{content}
</원고>

이 원고는 지금 공백 포함 {actual_length}자인데 {target_length}자가 되어야 한다. {direction} 다시 내놓는다.
{how}

말투, 시점, 소제목 구성, 표기 규칙은 원고 그대로 유지한다.
의료광고법에 걸리는 표현을 새로 넣지 않는다.
설명 없이 고친 원고 전문만 출력한다."""

        try:
            fixed = await self._gemini_call(
                user_prompt=fix_prompt,
                system_prompt=system_prompt,
                max_output_tokens=max_output_tokens,
                temperature=0.5,
                thinking_budget=THINKING_BUDGET_LIGHT,
                model=model,
            )
        except Exception as e:
            print(f"[WARNING] 분량 보정 실패, 기존 원고를 사용합니다: {e}")
            return None, (0, 0, 0)

        used = (fixed["input_tokens"], fixed["output_tokens"], fixed["thinking_tokens"])
        fixed_content = self._remove_markdown_formatting(fixed["text"])

        # 고친 결과가 목표에 더 가까울 때만 채택한다
        if fixed_content and abs(len(fixed_content) - target_length) < abs(actual_length - target_length):
            print(f"[분량 보정] {actual_length}자 -> {len(fixed_content)}자 (목표 {target_length}자)")
            return fixed_content, used

        print(f"[분량 보정] 개선되지 않아 유지 ({actual_length}자, 보정본 {len(fixed_content)}자)")
        return None, used

    async def _score(
        self,
        content: str,
        keyword: Optional[str] = None,
        differentiators: Optional[Dict] = None,
        source_text: Optional[str] = None,
    ):
        """
        규칙 채점 + LLM 심사. 심사는 값싼 모델로 1회만 호출한다.

        Returns:
            (report, (input_tokens, output_tokens, thinking_tokens))
        """
        rules = quality_scorer.score_rules(
            content, keyword=keyword, differentiators=differentiators, source_text=source_text
        )
        judge = None
        used = (0, 0, 0)
        try:
            res = await self._gemini_call(
                user_prompt=quality_scorer.build_judge_prompt(
                    content, keyword=keyword or "", differentiators=differentiators
                ),
                max_output_tokens=2048,
                temperature=0.2,
                thinking_budget=THINKING_BUDGET_LIGHT,
                model=JUDGE_MODEL,
            )
            used = (res["input_tokens"], res["output_tokens"], res["thinking_tokens"])
            judge = quality_scorer.parse_judge(res["text"])
            if judge is None:
                print("[품질] LLM 심사 응답을 해석하지 못해 규칙 점수만 사용합니다")
        except Exception as e:
            print(f"[품질] LLM 심사 실패, 규칙 점수만 사용합니다: {e}")

        return quality_scorer.combine(rules, judge), used

    async def _revise(
        self,
        content: str,
        notes,
        system_prompt: str,
        max_output_tokens: int,
        model: str,
        target_length: int,
    ):
        """채점에서 나온 지적을 그대로 넣어 한 번 고쳐 쓴다."""
        note_text = "\n".join(f"- {n}" for n in notes)
        cur = len(content)
        if cur < target_length * 0.92:
            length_line = f"지금 {cur}자인데 {target_length}자가 되어야 한다. 내용을 채워서 늘린다."
        elif cur > target_length * 1.12:
            length_line = f"지금 {cur}자인데 {target_length}자가 되어야 한다. 중복을 덜어내서 줄인다."
        else:
            length_line = f"분량은 지금({cur}자)과 비슷하게 {target_length}자 안팎으로 유지한다."
        prompt = f"""<원고>
{content}
</원고>

<고쳐야 할 것>
{note_text}
</고쳐야 할 것>

위 지적을 하나도 빠뜨리지 말고 전부 반영해서 원고를 고친다.
내용을 더 넣으라는 지적이 있으면 실제로 문장을 추가한다.
{length_line}
지적되지 않은 부분은 건드리지 않는다. 말투, 시점, 소제목 구성, 표기 규칙은 그대로 둔다.

근거를 넣으라는 지적이 있어도 없는 출처를 지어내지 않는다.
확실히 아는 공공기관·학회 자료만 이름을 대고, 아니면 출처 없이 일반론으로 쓴다.

설명 없이 고친 원고 전문만 출력한다."""

        try:
            res = await self._gemini_call(
                user_prompt=prompt,
                system_prompt=system_prompt,
                max_output_tokens=max_output_tokens,
                temperature=0.5,
                thinking_budget=THINKING_BUDGET,
                model=model,
            )
            return (
                self._remove_markdown_formatting(res["text"]),
                (res["input_tokens"], res["output_tokens"], res["thinking_tokens"]),
            )
        except Exception as e:
            print(f"[품질] 재작성 실패: {e}")
            return None, (0, 0, 0)

    async def generate_title_and_meta(
        self, content: str, specialty: str
    ) -> Dict[str, str]:
        """
        콘텐츠 기반 제목 및 메타 설명 생성
        """
        prompt = f"""<블로그 글>
{content[:1500]}
</블로그 글>

위 글을 읽고 아래 세 가지를 만든다.

- 제목: 네이버 검색에 걸리는 핵심 키워드가 앞쪽에 들어가되 자극적이지 않은 50자 이내 제목
- 메타: 검색 결과에 미리보기로 뜰 150자 이내 요약. 글에 실제로 있는 내용만 쓴다
- 해시태그: 실제로 검색될 만한 태그 10개

아래 형식 그대로, 다른 말 없이 세 줄만 출력한다.
제목: (제목)
메타: (메타 설명)
해시태그: #태그1 #태그2 #태그3"""

        try:
            result = await self._gemini_call(
                user_prompt=prompt,
                max_output_tokens=1024,
                temperature=0.5,
                thinking_budget=THINKING_BUDGET_LIGHT,
            )
        except APIKeyNotConfiguredError:
            print("[WARNING] Gemini API 키 미설정 - 제목/메타 생성 스킵")
            return {"title": "", "meta_description": "", "hashtags": []}
        except Exception as e:
            print(f"[ERROR] 제목/메타 생성 실패: {e}")
            return {"title": "", "meta_description": "", "hashtags": []}

        title = ""
        meta = ""
        hashtags: List[str] = []
        for line in result["text"].strip().split("\n"):
            line = line.strip()
            if line.startswith("제목:"):
                title = line.replace("제목:", "").strip()
            elif line.startswith("메타:"):
                meta = line.replace("메타:", "").strip()
            elif line.startswith("해시태그:"):
                hashtag_text = line.replace("해시태그:", "").strip()
                hashtags = [tag.strip() for tag in hashtag_text.split("#") if tag.strip()]

        return {"title": title, "meta_description": meta, "hashtags": hashtags}

    async def generate_hooking_titles(
        self, content: str, specialty: str = "의료"
    ) -> List[str]:
        """
        클릭하고 싶은 제목 5개 생성
        """
        prompt = f"""<블로그 글>
{content[:1200]}
</블로그 글>

위 글의 제목 후보 5개를 만든다.

기준
- 글에 실제로 있는 내용만 제목으로 쓴다. 글이 답하지 않는 것을 궁금하게 만드는 낚시성 제목은 쓰지 않는다
- 검색 키워드가 앞쪽에 자연스럽게 들어간다
- 50자 이내
- 다섯 개의 형식을 서로 다르게 한다. 질문형, 비교형, 상황 제시형, 방법 제시형, 오해 교정형 중에서 고른다
- 최고, 100%, 완치 같은 의료광고법 위반 표현을 쓰지 않는다

번호와 제목만, 다른 말 없이 다섯 줄로 출력한다.
1. 제목
2. 제목
3. 제목
4. 제목
5. 제목"""

        try:
            result = await self._gemini_call(
                user_prompt=prompt,
                max_output_tokens=1024,
                temperature=0.8,
                thinking_budget=THINKING_BUDGET_LIGHT,
            )
        except APIKeyNotConfiguredError:
            print("[WARNING] Gemini API 키 미설정 - 후킹 제목 생성 스킵")
            return []
        except Exception as e:
            print(f"[ERROR] 후킹 제목 생성 실패: {e}")
            return []

        titles = []
        for line in result["text"].strip().split("\n"):
            match = re.match(r'^\d+\.\s*(.+)$', line.strip())
            if match:
                titles.append(match.group(1).strip())
        return titles[:5]

    async def generate_subtitles(self, content: str) -> List[str]:
        """
        본문에 들어갈 소제목 4개 생성
        """
        prompt = f"""<블로그 글>
{content}
</블로그 글>

위 글을 흐름에 따라 네 개의 단락으로 나누고, 각 단락의 소제목을 만든다.

기준
- 소제목만 읽어도 그 아래 무슨 내용이 나오는지 알 수 있게 쓴다
- 20자 이내
- 궁금증만 자극하고 답을 주지 않는 문구는 쓰지 않는다

소제목 네 개만, 한 줄에 하나씩, 다른 말 없이 출력한다."""

        try:
            result = await self._gemini_call(
                user_prompt=prompt,
                max_output_tokens=1024,
                temperature=0.6,
                thinking_budget=THINKING_BUDGET_LIGHT,
            )
        except APIKeyNotConfiguredError:
            print("[WARNING] Gemini API 키 미설정 - 소제목 생성 스킵")
            return []
        except Exception as e:
            print(f"[ERROR] 소제목 생성 실패: {e}")
            return []

        subtitles = []
        for line in result["text"].strip().split("\n"):
            line = re.sub(r'^[#\-*\d.\s]+', '', line.strip()).strip()
            if line:
                subtitles.append(line)
        return subtitles[:4]


# Singleton instance
ai_rewrite_engine = AIRewriteEngine()
