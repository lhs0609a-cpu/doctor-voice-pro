"""
사진 풀 AI 태깅.

- 업로드된 풀 사진(PoolImage.data, 1280px JPEG)을 Claude 비전으로 1회 인식해
  scene / tags / caption / has_text 컬럼을 채운다.
- 비용 절감을 위해 전송 전 최대 768px, JPEG q80 으로 축소한다.
- Claude 호출은 app.services.claude_client.complete_json 을 사용한다.
- tag_untagged 는 순차 호출(레이트리밋 고려)이며 progress 콜백으로 진행률을 알린다.
"""
from __future__ import annotations

import base64
import io
import logging
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.media_pool import PoolCollectionMember, PoolImage
from app.services.claude_client import complete_json, vision_model

logger = logging.getLogger(__name__)

SCENES: List[str] = [
    "exterior", "reception", "consult", "treatment", "equipment", "herbal",
    "staff", "patient", "illustration", "product", "other",
]
STAGES: List[str] = ["도입", "진료과정", "시술", "장비소개", "마무리"]

MAX_SEND_PX = 768
SEND_JPEG_QUALITY = 80
MAX_TAGS = 15
MAX_CAPTION_CHARS = 200
MAX_TAG_CHARS = 20

ProgressCallback = Callable[[int, int, str], Awaitable[None]]

_SYSTEM_PROMPT = """당신은 병원(의원·한의원) 마케팅 블로그용 사진 라이브러리를 분류하는 사진 분석가입니다.
주어진 사진 한 장을 보고 반드시 아래 형식의 JSON 객체 하나만 출력합니다. 설명 문장, 마크다운, 코드펜스 없이 JSON 만 출력하세요.

{
  "scene": "exterior|reception|consult|treatment|equipment|herbal|staff|patient|illustration|product|other 중 하나",
  "tags": ["짧은 한국어 명사 6~12개"],
  "caption": "사진을 설명하는 한국어 한 문장",
  "has_text": true 또는 false,
  "people": true 또는 false,
  "suitable_for": ["도입","진료과정","시술","장비소개","마무리"] 중 어울리는 것만 담은 배열,
  "avoid": "글에 쓰기 부적절하다면 그 사유, 아니면 null"
}

scene 기준: exterior=건물 외관/간판/거리, reception=접수처/대기실/로비, consult=진료실 상담 장면, treatment=시술/치료/침·물리치료 장면, equipment=의료 장비·기기 클로즈업, herbal=한약재/탕약/약재실, staff=의료진·직원 인물 중심, patient=환자 중심(얼굴이 드러나는 경우 포함), illustration=일러스트/도표/그래픽, product=제품·패키지, other=그 외.
tags 는 피사체, 장소, 분위기, 실내/실외, 계절, 색감을 섞어 한국어 명사로만 적습니다(예: "진료실", "실내", "밝은 톤", "의사", "겨울").
has_text 는 간판·안내문·모니터 글자 등 사진 안에 읽을 수 있는 글자가 있으면 true 입니다.
people 은 사람이 한 명이라도 보이면 true 입니다.
suitable_for 는 블로그 글 단계(도입=인사·병원 소개, 진료과정=상담·검사, 시술=치료 장면, 장비소개=기기 설명, 마무리=안내·인사) 중 이 사진이 자연스럽게 들어갈 수 있는 단계만 고릅니다.
avoid 는 환자 얼굴 노출, 흐림, 과도한 글자, 광고성 문구 등 글에 쓰기 곤란한 이유가 있을 때만 적고 없으면 null 로 둡니다."""

_USER_PROMPT = "이 사진을 분석해 위 형식의 JSON 으로만 답하세요."


# ──────────────────────────── 이미지 전처리 ────────────────────────────

def _downscale_for_send(data: bytes, max_px: int = MAX_SEND_PX, quality: int = SEND_JPEG_QUALITY) -> bytes:
    """Claude 전송용: 최대 변 max_px, JPEG quality 로 재인코딩."""
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB")
        if max(im.size) > max_px:
            im.thumbnail((max_px, max_px), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue()


# ──────────────────────────── 응답 정규화 ────────────────────────────

def _as_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "yes", "y", "1", "예", "네", "있음"):
            return True
        if s in ("false", "no", "n", "0", "아니오", "없음", "null", ""):
            return False
    return default


def _clean_tags(raw: Any) -> List[str]:
    if isinstance(raw, str):
        raw = raw.replace("，", ",").split(",")
    if not isinstance(raw, list):
        return []
    seen = set()
    out: List[str] = []
    for t in raw:
        if not isinstance(t, str):
            continue
        t = t.strip().strip("#").strip()
        if not t:
            continue
        if len(t) > MAX_TAG_CHARS:
            t = t[:MAX_TAG_CHARS]
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
        if len(out) >= MAX_TAGS:
            break
    return out


def normalize_tag_result(raw: Any) -> Dict[str, Any]:
    """Claude 응답을 검증/정규화한다. 어떤 입력이 와도 고정 스키마의 dict 를 돌려준다."""
    if not isinstance(raw, dict):
        raw = {}

    scene = raw.get("scene")
    scene = scene.strip().lower() if isinstance(scene, str) else ""
    if scene not in SCENES:
        scene = "other"

    caption = raw.get("caption")
    caption = " ".join(caption.split()) if isinstance(caption, str) else ""
    if len(caption) > MAX_CAPTION_CHARS:
        caption = caption[:MAX_CAPTION_CHARS]

    suitable_raw = raw.get("suitable_for")
    suitable_for: List[str] = []
    if isinstance(suitable_raw, list):
        for s in suitable_raw:
            if isinstance(s, str):
                s = s.strip()
                if s in STAGES and s not in suitable_for:
                    suitable_for.append(s)

    avoid = raw.get("avoid")
    if isinstance(avoid, str):
        avoid = avoid.strip()
        if avoid.lower() in ("", "null", "none", "없음"):
            avoid = None
        elif len(avoid) > MAX_CAPTION_CHARS:
            avoid = avoid[:MAX_CAPTION_CHARS]
    else:
        avoid = None

    return {
        "scene": scene,
        "tags": _clean_tags(raw.get("tags")),
        "caption": caption,
        "has_text": _as_bool(raw.get("has_text")),
        "people": _as_bool(raw.get("people")),
        "suitable_for": suitable_for,
        "avoid": avoid,
    }


# ──────────────────────────── Claude 호출 ────────────────────────────

async def tag_image_bytes(data: bytes) -> dict:
    """이미지 바이트 하나를 Claude 비전으로 분석해 정규화된 태그 dict 를 돌려준다.

    반환: {"scene", "tags", "caption", "has_text", "people", "suitable_for", "avoid"}
    """
    small = _downscale_for_send(data)
    b64 = base64.standard_b64encode(small).decode("ascii")
    user_content = [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
        },
        {"type": "text", "text": _USER_PROMPT},
    ]
    raw = await complete_json(_SYSTEM_PROMPT, user_content, model=vision_model(), max_tokens=1024)
    result = normalize_tag_result(raw)
    logger.debug("[photo_tagger] scene=%s tags=%s", result["scene"], result["tags"])
    return result


# ──────────────────────────── DB 연동 ────────────────────────────

async def tag_pool_image(db: AsyncSession, image_id: str) -> dict:
    """PoolImage 한 장을 태깅해 컬럼(scene/tags/caption/has_text/tagged_at)에 기록하고 커밋한다.

    실패 시 tag_error 에 사유를 남기고(커밋) 예외를 다시 던진다.
    """
    img = await db.get(PoolImage, image_id)
    if img is None:
        raise ValueError(f"풀 사진을 찾을 수 없습니다: {image_id}")

    try:
        result = await tag_image_bytes(img.data)
    except Exception as e:  # noqa: BLE001
        logger.warning("[photo_tagger] 태깅 실패 image_id=%s: %s", image_id, e)
        try:
            await db.rollback()
            img = await db.get(PoolImage, image_id)
            if img is not None:
                img.tag_error = f"{type(e).__name__}: {e}"[:2000]
                await db.commit()
        except Exception as e2:  # noqa: BLE001
            logger.error("[photo_tagger] tag_error 기록 실패 image_id=%s: %s", image_id, e2)
        raise

    img.scene = result["scene"]
    img.tags = result["tags"]
    img.caption = result["caption"] or None
    img.has_text = result["has_text"]
    img.suitable_for = list(result.get("suitable_for") or [])
    img.tagged_at = datetime.utcnow()
    img.tag_error = None
    await db.commit()
    return result


async def tag_untagged(
    db: AsyncSession,
    user_id: str,
    collection_id: Optional[str] = None,
    limit: int = 200,
    progress: Optional[ProgressCallback] = None,
) -> dict:
    """사용자의 태깅 안 된(tagged_at IS NULL) 활성 풀 사진을 순차 태깅한다.

    collection_id 가 있으면 그 목록에 속한 사진만 대상.
    progress(done, total, message) 는 async 콜백(옵션).
    반환: {"tagged": n, "failed": m, "total": t}
    """
    q = (
        select(PoolImage.id)
        .where(
            PoolImage.user_id == user_id,
            PoolImage.active.is_(True),
            PoolImage.tagged_at.is_(None),
        )
        .order_by(PoolImage.created_at.asc())
    )
    if collection_id:
        q = q.join(
            PoolCollectionMember, PoolCollectionMember.pool_image_id == PoolImage.id
        ).where(PoolCollectionMember.collection_id == collection_id)
    if limit and limit > 0:
        q = q.limit(limit)

    ids = [row[0] for row in (await db.execute(q)).all()]
    # 여러 목록에 걸친 join 중복 제거(순서 유지)
    ids = list(dict.fromkeys(ids))
    total = len(ids)

    tagged = failed = 0
    if progress:
        await progress(0, total, f"사진 인식 시작 ({total}장)")

    for i, image_id in enumerate(ids, start=1):
        try:
            res = await tag_pool_image(db, image_id)
            tagged += 1
            msg = f"[{i}/{total}] {res['scene']} · {', '.join(res['tags'][:4])}"
        except Exception as e:  # noqa: BLE001
            failed += 1
            msg = f"[{i}/{total}] 실패: {type(e).__name__}"
        if progress:
            await progress(i, total, msg)

    logger.info("[photo_tagger] user=%s collection=%s tagged=%d failed=%d total=%d",
                user_id, collection_id, tagged, failed, total)
    return {"tagged": tagged, "failed": failed, "total": total}


# ──────────────────────────── 로컬 실행 ────────────────────────────

if __name__ == "__main__":
    import asyncio
    import json
    import sys

    async def _main() -> int:
        if len(sys.argv) < 2:
            print("사용법: python -m app.services.photo_tagger <이미지파일>")
            return 2
        path = sys.argv[1]
        from app.services.claude_client import resolve_api_key
        if not await resolve_api_key():
            print("ANTHROPIC_API_KEY(또는 api_keys 테이블의 Claude 키)가 설정되지 않아 태깅을 건너뜁니다.")
            return 0
        with open(path, "rb") as f:
            data = f.read()
        result = await tag_image_bytes(data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    raise SystemExit(asyncio.run(_main()))
