"""
캠페인 모듈 공용 Claude API 클라이언트.

- 키 해석: api_keys 테이블(provider='claude', is_active) → settings.ANTHROPIC_API_KEY
- 모델: settings.CAMPAIGN_MODEL (기본 claude-opus-5), 사진 태깅은 CAMPAIGN_VISION_MODEL
- 텍스트/JSON 호출 헬퍼. 응답에서 JSON 블록을 관대하게 추출한다.
- 모든 호출은 스트리밍으로 받아 긴 출력에서 HTTP 타임아웃을 피한다.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, List, Optional

import anthropic

from app.core.config import settings

logger = logging.getLogger(__name__)


class ClaudeNotConfigured(Exception):
    def __init__(self) -> None:
        super().__init__("Claude API 키가 설정되지 않았습니다. 관리자 > API 키에서 Claude 키를 등록하세요.")


async def resolve_api_key() -> Optional[str]:
    try:
        from app.services.ai_rewrite_engine import get_api_key_from_db
        key = await get_api_key_from_db("claude")
        if key:
            return key
    except Exception as e:  # noqa: BLE001
        logger.warning("[claude] DB 키 조회 실패: %s", e)
    return settings.ANTHROPIC_API_KEY or None


async def get_client() -> anthropic.AsyncAnthropic:
    key = await resolve_api_key()
    if not key:
        raise ClaudeNotConfigured()
    return anthropic.AsyncAnthropic(api_key=key, max_retries=2, timeout=600.0)


def text_model() -> str:
    return getattr(settings, "CAMPAIGN_MODEL", "") or "claude-opus-5"


def vision_model() -> str:
    return getattr(settings, "CAMPAIGN_VISION_MODEL", "") or text_model()


async def complete_text(
    system: str,
    user_content: Any,
    *,
    model: Optional[str] = None,
    max_tokens: int = 16000,
    effort: Optional[str] = None,
) -> str:
    """단일 턴 텍스트 완성. user_content 는 문자열 또는 content 블록 리스트(이미지 포함 가능)."""
    client = await get_client()
    kwargs: dict = {}
    if effort:
        kwargs["output_config"] = {"effort": effort}
    async with client.messages.stream(
        model=model or text_model(),
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_content}],
        **kwargs,
    ) as stream:
        msg = await stream.get_final_message()
    if getattr(msg, "stop_reason", None) == "refusal":
        raise RuntimeError("모델이 요청을 거부했습니다(안전 정책). 원고 내용을 확인하세요.")
    parts: List[str] = []
    for block in msg.content:
        if getattr(block, "type", "") == "text":
            parts.append(block.text)
    return "".join(parts).strip()


_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def extract_json(text: str) -> Any:
    """응답 텍스트에서 JSON 을 뽑는다. 코드펜스 → 첫 { 또는 [ 부터 끝까지 순으로 시도."""
    if not text:
        raise ValueError("빈 응답")
    m = _JSON_FENCE.search(text)
    candidates = [m.group(1)] if m else []
    candidates.append(text)
    for c in candidates:
        c = c.strip()
        try:
            return json.loads(c)
        except Exception:  # noqa: BLE001
            pass
        # 첫 여는 괄호부터 마지막 닫는 괄호까지
        for open_ch, close_ch in (("{", "}"), ("[", "]")):
            i, j = c.find(open_ch), c.rfind(close_ch)
            if i >= 0 and j > i:
                try:
                    return json.loads(c[i : j + 1])
                except Exception:  # noqa: BLE001
                    continue
    raise ValueError("응답에서 JSON 을 찾지 못했습니다: " + text[:200])


async def complete_json(
    system: str,
    user_content: Any,
    *,
    model: Optional[str] = None,
    max_tokens: int = 16000,
    effort: Optional[str] = None,
) -> Any:
    text = await complete_text(system, user_content, model=model, max_tokens=max_tokens, effort=effort)
    return extract_json(text)
