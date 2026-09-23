"""본문 폭보다 좁은 사진을 넓혀 준다 — 네이버는 원본 크기대로 그린다.

네이버 글쓰기 본문 칸은 700px 남짓이다. 워드에 넣은 움직이는 GIF 는 400px 짜리가 많아
그대로 올리면 글 한가운데에 손바닥만 하게 박힌다(2026-09-23 실측: 400×225, 420×236).
사진은 680~740px 이라 꽉 차는데 GIF 만 작으니 더 눈에 띈다.

움직이는 GIF 는 **정수배로, 가장 가까운 픽셀을 그대로 복제해서** 넓힌다. 색을 새로 만들지
않으므로 팔레트·투명·프레임 간격이 그대로 남고, 브라우저가 늘려 보여 주는 그림과 같다.
사진은 한 번만 부드럽게(LANCZOS) 늘린다. 자르거나 비율을 바꾸지 않는다.
"""
from __future__ import annotations

import io
import logging
from typing import Tuple

from PIL import Image, ImageSequence

log = logging.getLogger(__name__)

BLOG_WIDTH = 740      # 네이버 본문 칸을 채우는 최소 가로폭
MAX_SCALE = 3         # 이보다 크게 늘리면 뭉개진다 — 작은 그림은 작은 채로 둔다


def _animated(im: Image.Image) -> bool:
    return (im.format or "").upper() == "GIF" and bool(getattr(im, "is_animated", False))


def _widen_gif(im: Image.Image, scale: int) -> bytes:
    size = (im.width * scale, im.height * scale)
    frames = [f.copy().resize(size, Image.Resampling.NEAREST) for f in ImageSequence.Iterator(im)]
    buf = io.BytesIO()
    first, rest = frames[0], frames[1:]
    first.save(buf, "GIF", save_all=True, append_images=rest,
               loop=im.info.get("loop", 0), duration=im.info.get("duration", 100),
               disposal=im.info.get("disposal", 2), transparency=im.info.get("transparency", 255)
               if "transparency" in im.info else None, optimize=False)
    return buf.getvalue()


def widen(data: bytes, content_type: str = "") -> Tuple[bytes, str]:
    """본문 폭보다 좁으면 넓힌 바이트를, 아니면 받은 그대로 돌려준다.

    어떤 이유로든 실패하면 원본을 그대로 쓴다 — 사진 때문에 발행이 막히면 안 된다.
    CPU 작업이므로 threadpool 에서 부를 것."""
    try:
        im = Image.open(io.BytesIO(data))
        if im.width <= 0 or im.width >= BLOG_WIDTH:
            return data, content_type
        if _animated(im):
            scale = min(MAX_SCALE, max(2, -(-BLOG_WIDTH // im.width)))
            return _widen_gif(im, scale), "image/gif"
        if BLOG_WIDTH / im.width > MAX_SCALE:
            return data, content_type
        height = max(1, round(im.height * BLOG_WIDTH / im.width))
        wide = im.convert("RGB").resize((BLOG_WIDTH, height), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        wide.save(buf, "JPEG", quality=88, optimize=True)
        return buf.getvalue(), "image/jpeg"
    except Exception as error:  # noqa: BLE001
        log.warning("사진을 넓히지 못했습니다(원본 그대로 올립니다): %s", error)
        return data, content_type
