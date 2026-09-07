"""
AI Service - 범용 AI 텍스트 생성 서비스
"""

import anthropic
import httpx
from typing import Optional
from app.core.config import settings

# Gemini SDK 임포트 (설치되어 있는 경우)
try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None
    genai_types = None

from app.services.ai_rewrite_engine import (
    DEFAULT_MODEL as GEMINI_DEFAULT_MODEL,
    get_api_key_from_db,
)


class AIService:
    """
    범용 AI 텍스트 생성 서비스
    Claude, GPT, Gemini를 지원합니다.
    """

    def __init__(self, provider: str = "claude"):
        """
        Args:
            provider: AI 제공자 ("claude", "gpt", "gemini")
        """
        self.provider = provider

        # Claude 클라이언트 초기화
        if settings.ANTHROPIC_API_KEY:
            self.claude_client = anthropic.Anthropic(
                api_key=settings.ANTHROPIC_API_KEY,
                timeout=180.0
            )
        else:
            self.claude_client = None

        # OpenAI 클라이언트 초기화
        if settings.OPENAI_API_KEY:
            from openai import OpenAI
            http_client = httpx.Client(
                timeout=httpx.Timeout(connect=30.0, read=180.0, write=30.0, pool=30.0)
            )
            self.openai_client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                http_client=http_client,
                timeout=180.0
            )
        else:
            self.openai_client = None

        # Gemini 는 호출 시점에 DB/환경변수 키로 클라이언트를 만든다.
        # 환경변수가 비어 있어도 DB 에 키가 있을 수 있으므로 SDK 유무만 본다.
        self.gemini_available = GEMINI_AVAILABLE

    async def generate_text(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        AI를 사용하여 텍스트를 생성합니다.

        Args:
            prompt: 사용자 프롬프트
            max_tokens: 최대 토큰 수
            temperature: 창의성 정도 (0.0 ~ 1.0)
            system_prompt: 시스템 프롬프트 (선택)

        Returns:
            생성된 텍스트
        """
        # 호출 시점에 provider 를 넘기면 그쪽을 우선한다 (model 은 Gemini 경로에서만 의미 있음)
        active_provider = provider or self.provider

        # Claude 사용 (기본)
        if active_provider == "claude" and self.claude_client:
            return await self._generate_with_claude(prompt, max_tokens, temperature, system_prompt)

        # GPT 사용
        elif active_provider == "gpt" and self.openai_client:
            return await self._generate_with_gpt(prompt, max_tokens, temperature, system_prompt)

        # Gemini 사용
        elif active_provider == "gemini" and self.gemini_available:
            return await self._generate_with_gemini(prompt, max_tokens, temperature, system_prompt, model)

        # 기본값: 사용 가능한 첫 번째 제공자 사용
        if self.claude_client:
            return await self._generate_with_claude(prompt, max_tokens, temperature, system_prompt)
        elif self.openai_client:
            return await self._generate_with_gpt(prompt, max_tokens, temperature, system_prompt)
        elif self.gemini_available:
            return await self._generate_with_gemini(prompt, max_tokens, temperature, system_prompt)

        raise ValueError("사용 가능한 AI 제공자가 없습니다. API 키를 확인해주세요.")

    async def _generate_with_claude(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        system_prompt: Optional[str]
    ) -> str:
        """Claude를 사용하여 텍스트 생성"""
        try:
            messages = [{"role": "user", "content": prompt}]

            kwargs = {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages
            }

            if system_prompt:
                kwargs["system"] = system_prompt

            response = self.claude_client.messages.create(**kwargs)
            return response.content[0].text

        except Exception as e:
            print(f"[ERROR] Claude API 오류: {e}")
            raise

    async def _generate_with_gpt(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        system_prompt: Optional[str]
    ) -> str:
        """GPT를 사용하여 텍스트 생성"""
        try:
            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            messages.append({"role": "user", "content": prompt})

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )

            return response.choices[0].message.content

        except Exception as e:
            print(f"[ERROR] GPT API 오류: {e}")
            raise

    async def _generate_with_gemini(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        system_prompt: Optional[str],
        model: Optional[str] = None,
    ) -> str:
        """Gemini를 사용하여 텍스트 생성"""
        try:
            # 관리자 화면(DB)에 등록한 키를 우선 쓰고, 없으면 환경변수로 떨어진다
            api_key = await get_api_key_from_db("gemini")
            if not api_key:
                raise ValueError("Gemini API 키가 설정되지 않았습니다.")
            client = genai.Client(api_key=api_key)

            config_kwargs = {
                "max_output_tokens": max_tokens,
                "temperature": temperature,
                # 짧은 보조 작업이므로 사고 토큰을 쓰지 않는다
                "thinking_config": genai_types.ThinkingConfig(thinking_budget=0),
            }
            if system_prompt:
                config_kwargs["system_instruction"] = system_prompt

            response = client.models.generate_content(
                model=model or GEMINI_DEFAULT_MODEL,
                contents=prompt,
                config=genai_types.GenerateContentConfig(**config_kwargs),
            )

            return response.text or ""

        except Exception as e:
            print(f"[ERROR] Gemini API 오류: {e}")
            raise
