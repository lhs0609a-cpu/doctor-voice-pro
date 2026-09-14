"""사진 변형(image_uniquifier) 기본 동작 회귀 테스트.

운영 요구(2026-09-11): 사진은 잘리거나·기울거나·늘어나면 안 된다. 메타값은 매번 전부 바뀌고,
처리 방식도 매번 달라야 한다(같은 사진을 여러 글에 써도 서로 다른 파일).
python -m pytest test_image_uniquifier.py -q
"""
import io
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageOps

from app.services import image_uniquifier as U

KNOWN_MAKES = {d[0] for d in U._DEVICES}


def _photo(w=1280, h=914, exif_orientation=None) -> bytes:
    img = Image.new("RGB", (w, h), (70, 130, 90))
    d = ImageDraw.Draw(img)
    # 가장자리에 닿는 도형 — 잘리거나 기울면 가장자리 띠가 달라진다
    d.rectangle((0, 0, w // 10, h // 10), fill=(255, 255, 255))
    d.rectangle((w - w // 10, h - h // 10, w, h), fill=(255, 255, 255))
    for i in range(12):
        x, y = (i * 97) % (w - 40), (i * 61) % (h - 60)
        d.rectangle((x, y, x + 30, y + 50), fill=(250, 250, 250))
    buf = io.BytesIO()
    ex = Image.Exif()
    ex[0x010F] = "ORIGINAL-MAKE"      # 원본 메타가 새어 나가면 안 된다
    if exif_orientation:
        ex[0x0112] = exif_orientation
    img.save(buf, "JPEG", quality=95, exif=ex.tobytes())
    return buf.getvalue()


def _edge_similarity(orig: Image.Image, out: Image.Image) -> float:
    o = orig.resize(out.size, Image.Resampling.LANCZOS)
    w, h = out.size
    b = max(8, int(min(w, h) * 0.04))
    boxes = [(0, 0, w, b), (0, h - b, w, h), (0, 0, b, h), (w - b, 0, w, h)]
    return min(U.ssim(o.crop(x), out.crop(x), size=128) for x in boxes)


def _run(src: bytes, seed=7, **kw):
    r = U.uniquify(src, seed=seed, **kw)
    orig = ImageOps.exif_transpose(Image.open(io.BytesIO(src))).convert("RGB")
    out = Image.open(io.BytesIO(r.image_bytes))
    return r, orig, out


def test_default_keeps_whole_photo_without_crop_tilt_or_stretch():
    for seed in range(6):   # 어떤 레시피가 뽑혀도
        r, orig, out = _run(_photo(), seed=seed)
        rgb = out.convert("RGB")
        assert abs((rgb.width / rgb.height) / (orig.width / orig.height) - 1) < 0.005, r.frame_style   # 비율 그대로
        assert _edge_similarity(orig, rgb) > 0.93, r.frame_style                                          # 안 잘림·안 기움
        assert rgb.width <= orig.width                                                                    # 늘리지 않음
        assert r.frame_style.startswith("p:") and r.trim == 0.0
        assert r.passed and r.ssim >= U.MIN_SSIM


def test_metadata_is_replaced_whole_and_consistent():
    r, _, out = _run(_photo())
    ex = out.getexif()
    sub = ex.get_ifd(0x8769)
    assert ex.get(0x010F) in KNOWN_MAKES and ex.get(0x010F) != "ORIGINAL-MAKE"
    assert ex.get(0x0110) and ex.get(0x0131)
    shot = datetime.strptime(sub[0x9003], "%Y:%m:%d %H:%M:%S")
    now = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=9)
    assert now - timedelta(days=121) <= shot <= now - timedelta(days=1)      # 미래·먼 과거 날짜 없음
    assert (sub[0xA002], sub[0xA003]) == out.size                               # 적힌 픽셀 크기 = 실제 크기
    assert sub.get(0x8827) and sub.get(0x829D) and sub.get(0xA420)            # ISO·조리개·고유 ID
    assert 0x8825 not in ex                                                     # GPS 없음
    assert ex.get(0x0112) is None                                               # 방향 태그 없음(픽셀에 반영)


def test_every_variant_differs_in_file_recipe_and_metadata():
    src = _photo()
    results = [U.uniquify(src, seed=s) for s in range(6)]
    assert len({r.image_bytes for r in results}) == 6
    assert len({r.frame_style for r in results}) >= 4                           # 처리 조합이 매번 다르다
    ids = {Image.open(io.BytesIO(r.image_bytes)).getexif().get_ifd(0x8769)[0xA420] for r in results}
    assert len(ids) == 6


def test_phone_rotation_is_applied_not_lost():
    # 휴대폰 사진(EXIF 방향 6 = 90° 회전) — 결과가 누운 채로 들어가면 안 된다
    r, orig, out = _run(_photo(1200, 800, exif_orientation=6))
    assert orig.size == (800, 1200)
    assert out.height > out.width


def test_old_reframe_mode_still_available_explicitly():
    r = U.uniquify(_photo(), seed=7, preserve_geometry=False)
    assert not r.frame_style.startswith("p:")
