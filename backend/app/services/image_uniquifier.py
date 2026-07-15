"""
이미지 유니크화 서비스 (네이버 중복사진 인식 회피 + 품질 유지)

원리:
- 네이버 중복 판정은 ① 파일 해시 ② EXIF/메타 지문 ③ 지각 해시(pHash/dHash) 3층.
- pHash 는 "구조 변형(액자/크롭/미세회전/비율)"에 크게 흔들리고 픽셀 노이즈엔 강하다.
  → 화질을 깎는 강한 노이즈 대신 프레임/크롭 위주로 해시 거리를 벌리고,
    톤 지터/미세 노이즈는 보조로만 사용 → 눈엔 멀쩡(고품질), 해시는 전혀 다름.

보장:
- 생성물 pHash 가 원본 + 과거 모든 변형과 Hamming 거리 ≥ MIN_DISTANCE 이고,
  본문 SSIM ≥ MIN_SSIM 을 동시에 만족할 때까지 강도를 올려가며 재시도(재롤).
  → "계속·절대 중복으로 안 걸리게 자동 변경"을 게이트로 보장.

의존성: Pillow, numpy 만 사용 (imagehash/piexif 불필요 — pHash 직접 구현, Pillow 내장 EXIF).
"""
from __future__ import annotations

import io
import math
import random
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
from PIL import Image, ImageEnhance, ImageOps, ImageDraw, ImageFilter

# ---- 기본 파라미터 ----
MIN_DISTANCE = 12          # 원본과의 최소 pHash Hamming 거리(64bit 중) — 엄격
MIN_SIBLING_DISTANCE = 6   # 같은 원본의 과거 변형끼리 최소 거리 — dedup 추정임계(~5) 위 여유 1(여력 2배)
MIN_SSIM = 0.95            # 인코딩(압축) 충실도 하한 — 저품질 방지 (1.0=무손실)
MAX_ATTEMPTS = 16          # 구조 모드가 늘어난 만큼 탐색 폭도 확대
MAX_WIDTH = 1280           # 블로그 표시 최대폭 (하한 1080 유지)
JPEG_Q_RANGE = (88, 92)

FRAME_STYLES = ("white_margin", "rounded_shadow", "film", "mat_canvas")

# 구조 모드용 종횡비(재크롭) 후보 — None 은 원본 비율 유지
REFRAME_RATIOS = (None, 1.0, 4 / 5, 5 / 4, 3 / 4, 4 / 3)

_EXIF_MAKES = [
    ("Samsung", "SM-S928N"), ("Samsung", "SM-G998N"), ("Apple", "iPhone 15 Pro"),
    ("Apple", "iPhone 14"), ("Canon", "Canon EOS R6"), ("SONY", "ILCE-7M4"),
    ("Xiaomi", "23078PND5G"), ("LGE", "LM-V500N"),
]
_EXIF_SOFTWARE = ["Photos 2.0", "Snapseed 2.21", "Adobe Lightroom", "MediaTek Camera", None]


# ============================================================
# pHash / dHash (numpy 직접 구현)
# ============================================================
def _dct_matrix(n: int) -> np.ndarray:
    k = np.arange(n).reshape(-1, 1)
    x = np.arange(n).reshape(1, -1)
    d = np.cos(np.pi * (2 * x + 1) * k / (2 * n))
    d[0, :] *= 1.0 / math.sqrt(2)
    return d * math.sqrt(2.0 / n)


_DCT32 = _dct_matrix(32)


def _gray_array(img: Image.Image, size: int) -> np.ndarray:
    g = img.convert("L").resize((size, size), Image.Resampling.LANCZOS)
    return np.asarray(g, dtype=np.float64)


def phash(img: Image.Image) -> int:
    """32x32 → DCT → 좌상단 8x8 → 중앙값 임계 → 64bit."""
    a = _gray_array(img, 32)
    dct = _DCT32 @ a @ _DCT32.T
    low = dct[:8, :8]
    med = np.median(low[1:, :])  # DC(0,0) 제외한 중앙값
    bits = (low > med).flatten()
    out = 0
    for b in bits:
        out = (out << 1) | int(b)
    return out


def dhash(img: Image.Image) -> int:
    """9x8 → 좌우 인접 비교 → 64bit."""
    g = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    a = np.asarray(g, dtype=np.int16)
    bits = (a[:, 1:] > a[:, :-1]).flatten()
    out = 0
    for b in bits:
        out = (out << 1) | int(b)
    return out


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def to_hex(h: int) -> str:
    return format(h, "016x")


def from_hex(s: str) -> int:
    return int(s, 16)


# ============================================================
# SSIM (Pillow GaussianBlur 기반, numpy)
# ============================================================
def _gauss_kernel(radius: float) -> np.ndarray:
    sigma = max(radius / 2.0, 1.0)
    n = int(3 * sigma)
    x = np.arange(-n, n + 1)
    k = np.exp(-(x ** 2) / (2 * sigma ** 2))
    return k / k.sum()


def _blur1d(a: np.ndarray, k: np.ndarray, axis: int) -> np.ndarray:
    pad = len(k) // 2
    a = np.moveaxis(a, axis, -1)
    ap = np.pad(a, [(0, 0)] * (a.ndim - 1) + [(pad, pad)], mode="edge")
    out = np.zeros_like(a, dtype=np.float64)
    n = a.shape[-1]
    for i, kv in enumerate(k):
        out += kv * ap[..., i:i + n]
    return np.moveaxis(out, -1, axis)


def _blur(a: np.ndarray, radius: float = 4.0) -> np.ndarray:
    k = _gauss_kernel(radius)
    return _blur1d(_blur1d(a, k, 1), k, 0)


def ssim(img_a: Image.Image, img_b: Image.Image, size: int = 512) -> float:
    """두 이미지를 공통 크기 그레이스케일로 맞춰 windowed SSIM 평균."""
    a = _gray_array(img_a, size)
    b = _gray_array(img_b, size)
    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2
    mu_a, mu_b = _blur(a), _blur(b)
    mu_a2, mu_b2, mu_ab = mu_a * mu_a, mu_b * mu_b, mu_a * mu_b
    sig_a = _blur(a * a) - mu_a2
    sig_b = _blur(b * b) - mu_b2
    sig_ab = _blur(a * b) - mu_ab
    s = ((2 * mu_ab + C1) * (2 * sig_ab + C2)) / ((mu_a2 + mu_b2 + C1) * (sig_a + sig_b + C2))
    return float(np.clip(s.mean(), -1.0, 1.0))


# ============================================================
# 프레임(액자)
# ============================================================
def _frame_white_margin(img: Image.Image, rng: random.Random, strength: float) -> Image.Image:
    w, h = img.size
    m = int(min(w, h) * rng.uniform(0.02, 0.05) * (1 + 0.5 * strength))
    tone = rng.randint(248, 255)
    color = (tone, tone, tone)
    out = Image.new("RGB", (w + 2 * m, h + 2 * m), color)
    out.paste(img, (m, m))
    return out


def _frame_rounded_shadow(img: Image.Image, rng: random.Random, strength: float) -> Image.Image:
    w, h = img.size
    pad = int(min(w, h) * rng.uniform(0.04, 0.07) * (1 + 0.4 * strength))
    radius = int(min(w, h) * rng.uniform(0.03, 0.06))
    bg_tone = rng.randint(245, 255)
    canvas = Image.new("RGB", (w + 2 * pad, h + 2 * pad), (bg_tone, bg_tone, bg_tone))
    # 미세 그림자
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    off = max(2, pad // 3)
    sd.rounded_rectangle(
        [pad + off, pad + off, pad + w + off, pad + h + off],
        radius=radius, fill=(0, 0, 0, rng.randint(40, 70)),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(3, pad // 2)))
    canvas.paste(shadow, (0, 0), shadow)
    # 라운드 마스크로 이미지 합성
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w, h], radius=radius, fill=255)
    canvas.paste(img, (pad, pad), mask)
    return canvas


def _frame_film(img: Image.Image, rng: random.Random, strength: float) -> Image.Image:
    w, h = img.size
    # 증감(비네팅) + 얇은 검은 테두리
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = w / 2, h / 2
    r = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2)
    vig = 1.0 - np.clip(r - 0.6, 0, 1) * rng.uniform(0.12, 0.22)
    arr = np.clip(arr * vig[..., None], 0, 255).astype(np.uint8)
    body = Image.fromarray(arr)
    b = int(min(w, h) * rng.uniform(0.015, 0.03) * (1 + 0.4 * strength))
    tone = rng.randint(12, 30)
    out = Image.new("RGB", (w + 2 * b, h + 2 * b), (tone, tone, tone))
    out.paste(body, (b, b))
    return out


def _frame_mat_canvas(img: Image.Image, rng: random.Random, strength: float) -> Image.Image:
    """사진을 더 큰 매트(배경 캔버스) 위에 얹어 레이아웃이 pHash를 지배하게 한다.
    배경 톤/크기/위치/라운드를 매번 달리해 원본과 완전히 다른 해시 영역으로 이동."""
    w, h = img.size
    # 이미지가 캔버스에서 차지하는 비율(작을수록 여백↑, 해시 이동↑)
    occupy = rng.uniform(0.78, 0.92) - 0.04 * strength
    occupy = max(0.68, occupy)
    cw, ch = int(w / occupy), int(h / occupy)
    # 배경: 대체로 밝은 회색, 가끔 미세 파스텔
    if rng.random() < 0.4:
        color = (rng.randint(236, 255), rng.randint(236, 255), rng.randint(236, 255))
    else:
        t = rng.randint(240, 255)
        color = (t, t, t)
    canvas = Image.new("RGB", (cw, ch), color)
    ox = int((cw - w) * rng.uniform(0.35, 0.65))
    oy = int((ch - h) * rng.uniform(0.28, 0.60))
    radius = int(min(w, h) * rng.uniform(0.0, 0.045))
    if radius > 2:
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, w, h], radius=radius, fill=255)
        canvas.paste(img, (ox, oy), mask)
    else:
        canvas.paste(img, (ox, oy))
    return canvas


_FRAME_FUNCS = {
    "white_margin": _frame_white_margin,
    "rounded_shadow": _frame_rounded_shadow,
    "film": _frame_film,
    "mat_canvas": _frame_mat_canvas,
}


def _recrop_ratio(img: Image.Image, ratio: float, rng: random.Random) -> Image.Image:
    """중앙 근처에서 target 종횡비로 재크롭(구조 모드). 위치를 약간 흔들어 다양화."""
    w, h = img.size
    cur = w / h
    if abs(cur - ratio) < 1e-3:
        return img
    if ratio >= cur:
        # 목표가 더 넓음 → 높이를 자름
        nh = max(1, min(h, int(w / ratio)))
        top = int((h - nh) * rng.uniform(0.35, 0.65))
        return img.crop((0, top, w, top + nh))
    # 목표가 더 좁음 → 폭을 자름
    nw = max(1, min(w, int(h * ratio)))
    left = int((w - nw) * rng.uniform(0.35, 0.65))
    return img.crop((left, 0, left + nw, h))


# ============================================================
# 결과
# ============================================================
@dataclass
class UniquifyResult:
    image_bytes: bytes
    phash: str
    dhash: str
    ssim: float
    min_distance: int          # 원본+회피셋 대비 최소 pHash 거리
    attempts: int
    frame_style: str
    passed: bool               # 게이트 통과 여부
    quality: int               # 최종 JPEG 품질


# ============================================================
# 코어 변형 (프레임 이전 본문)
# ============================================================
def _transform_body(
    src: Image.Image, rng: random.Random, strength: float, max_width: int,
    flip: bool = False, ratio: float | None = None,
) -> Image.Image:
    img = ImageOps.exif_transpose(src).convert("RGB")

    # 0) 구조 모드: 좌우 반전 — 새 해시 클러스터(거의 공짜, 눈엔 자연스러움)
    if flip:
        img = ImageOps.mirror(img)

    # 0b) 구조 모드: 종횡비 재크롭 — 레이아웃 자체를 바꿔 해시 영역 이동
    if ratio:
        img = _recrop_ratio(img, ratio, rng)

    # 1) 미세 회전 후 경계 크롭
    ang = rng.uniform(0.4, 1.2) * (1 + 0.5 * strength) * rng.choice([-1, 1])
    img = img.rotate(ang, resample=Image.Resampling.BICUBIC, expand=False)
    w, h = img.size
    cut = int(min(w, h) * (0.02 + 0.01 * strength))
    img = img.crop((cut, cut, w - cut, h - cut))

    # 2) 랜덤 크롭 (가장자리 1~4% + 강도)
    w, h = img.size
    fx1 = rng.uniform(0.01, 0.04) + 0.01 * strength
    fx2 = rng.uniform(0.01, 0.04) + 0.01 * strength
    fy1 = rng.uniform(0.01, 0.04) + 0.01 * strength
    fy2 = rng.uniform(0.01, 0.04) + 0.01 * strength
    img = img.crop((int(w * fx1), int(h * fy1), int(w * (1 - fx2)), int(h * (1 - fy2))))

    # 3) 리스케일 (96~104%) → 최대폭 제한 (원본이 작으면 업스케일 안 함)
    scale = rng.uniform(0.96, 1.04)
    w, h = img.size
    img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
    if img.width > max_width:
        r = max_width / img.width
        img = img.resize((max_width, max(1, int(img.height * r))), Image.Resampling.LANCZOS)

    # 4) 톤 지터 (밝기/대비/채도/감마/색상)
    img = ImageEnhance.Brightness(img).enhance(rng.uniform(0.97, 1.03))
    img = ImageEnhance.Contrast(img).enhance(rng.uniform(0.97, 1.03))
    img = ImageEnhance.Color(img).enhance(rng.uniform(0.96, 1.04))
    gamma = rng.uniform(0.97, 1.03)
    lut = [min(255, int((i / 255.0) ** gamma * 255 + 0.5)) for i in range(256)] * 3
    img = img.point(lut)

    arr = np.asarray(img, dtype=np.float32)
    H, W = arr.shape[:2]
    gy, gx = np.mgrid[0:H, 0:W].astype(np.float32)

    # 5) 저주파 조명 그라디언트 — pHash(저주파 DCT)를 흔드는 핵심 지렛대.
    #    부드러운 사인 2개 합성(±수%)이라 시각적으론 미세, 해시엔 큰 변화.
    plane = np.zeros((H, W), dtype=np.float32)
    for _ in range(3):
        fx = rng.uniform(-1.6, 1.6)
        fy = rng.uniform(-1.6, 1.6)
        phs = rng.uniform(0, 2 * math.pi)
        plane += np.sin(2 * math.pi * (fx * gx / W + fy * gy / H) + phs)
    plane /= 3.0  # ~[-1, 1]
    amp = min(0.08, rng.uniform(0.025, 0.045) * (1 + 0.5 * strength))
    arr = arr * (1.0 + amp * plane)[..., None]

    # 6) 미세 휘도 노이즈 (비가시)
    sigma = 1.5 + 0.8 * strength
    noise = np.random.default_rng(rng.randint(0, 2**31)).normal(0, sigma, (H, W))
    arr = np.clip(arr + noise[..., None], 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def _inject_exif(rng: random.Random) -> bytes:
    exif = Image.Exif()
    make, model = rng.choice(_EXIF_MAKES)
    exif[0x010F] = make          # Make
    exif[0x0110] = model         # Model
    sw = rng.choice(_EXIF_SOFTWARE)
    if sw:
        exif[0x0131] = sw        # Software
    # 촬영시각 지터 (지난 30일 내 임의 시각, 초 단위까지 랜덤)
    yy = 2026
    mo = rng.randint(1, 7)
    dd = rng.randint(1, 28)
    exif[0x0132] = f"{yy}:{mo:02d}:{dd:02d} {rng.randint(6,22):02d}:{rng.randint(0,59):02d}:{rng.randint(0,59):02d}"
    return exif.tobytes()


# ============================================================
# 공개 API
# ============================================================
def uniquify(
    src_bytes: bytes,
    *,
    sibling_hashes: Iterable[str] | None = None,
    min_distance: int = MIN_DISTANCE,
    min_sibling_distance: int = MIN_SIBLING_DISTANCE,
    min_ssim: float = MIN_SSIM,
    max_attempts: int = MAX_ATTEMPTS,
    max_width: int = MAX_WIDTH,
    frame_styles: Iterable[str] | None = None,
    allow_flip: bool = False,  # 좌우 반전 금지(글씨/제품 이미지가 뒤집혀 보임)
    allow_reframe: bool = True,
    seed: int | None = None,
) -> UniquifyResult:
    """원본 바이트 → 유니크화된 JPEG + 검증 결과.

    sibling_hashes: 같은 원본으로 과거에 만든 변형들의 pHash(hex) 목록.
    게이트: (원본과 ≥min_distance) AND (모든 형제와 ≥min_sibling_distance) AND (SSIM≥min_ssim).
    미충족 시 강도를 올려 재시도, 끝내 못 넘기면 passed=False 인 최선 후보 반환
    (호출측이 풀에서 덜 쓴 다른 사진으로 대체하도록).
    """
    src = Image.open(io.BytesIO(src_bytes))
    src.load()
    orig_ph = phash(src)

    siblings = set()
    for hx in (sibling_hashes or []):
        try:
            siblings.add(from_hex(hx))
        except (ValueError, TypeError):
            continue

    styles = list(frame_styles) if frame_styles else list(FRAME_STYLES)
    rng = random.Random(seed)

    ratios = list(REFRAME_RATIOS) if allow_reframe else [None]

    best = None
    best_key = None
    for attempt in range(max_attempts):
        strength = attempt / 2.0  # 0, 0.5, 1.0, ... 강도 상승
        # 구조 모드 선택(반전×재크롭×프레임). 뒤로 갈수록 반전을 켜 먼 영역까지 탐색.
        flip = bool(rng.getrandbits(1)) if allow_flip else False
        if allow_flip and attempt >= max_attempts // 2:
            flip = True  # 후반부: 반전 강제 → 확실히 다른 해시 클러스터로
        ratio = rng.choice(ratios)
        body = _transform_body(src, rng, strength, max_width, flip=flip, ratio=ratio)
        style = rng.choice(styles)
        framed = _FRAME_FUNCS[style](body, rng, strength)

        quality = rng.randint(*JPEG_Q_RANGE)
        buf = io.BytesIO()
        framed.save(buf, "JPEG", quality=quality, exif=_inject_exif(rng), optimize=True)
        data = buf.getvalue()

        # 네이버가 실제로 받는 것 = 인코딩된 파일. 해시/품질은 디코딩본 기준.
        framed_dec = Image.open(io.BytesIO(data)).convert("RGB")
        framed_dec.load()
        ph = phash(framed_dec)
        d_orig = hamming(ph, orig_ph)
        d_sib = min((hamming(ph, s) for s in siblings), default=64)
        q = ssim(framed, framed_dec)  # 압축 손실만 측정(정렬됨) → 저품질 여부

        passed = d_orig >= min_distance and d_sib >= min_sibling_distance and q >= min_ssim
        mode_tag = style + ("|flip" if flip else "") + (f"|{ratio:.2f}" if ratio else "")
        result = UniquifyResult(
            image_bytes=data, phash=to_hex(ph), dhash=to_hex(dhash(framed_dec)),
            ssim=round(q, 4), min_distance=min(d_orig, d_sib), attempts=attempt + 1,
            frame_style=mode_tag[:30], passed=passed, quality=quality,
        )
        if passed:
            return result
        # 최선 후보: 원본거리 우선(엄격 임계), 그다음 형제거리, 품질
        key = (min(d_orig, min_distance), min(d_sib, min_sibling_distance), q)
        if best is None or key > best_key:
            best, best_key = result, key

    return best  # 게이트 미통과 시 최선 후보 (passed=False)
