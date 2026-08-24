"""
이미지 유니크화 서비스 (네이버 중복사진 인식 회피 + 품질 유지)

원리:
- 네이버 중복 판정은 ① 파일 해시 ② EXIF/메타 지문 ③ 지각 해시(pHash/dHash) 3층.
- pHash 는 "화면에 무엇이 어떻게 담겼나(재구도)"에만 크게 흔들린다. 32x32 로 줄여
  저주파 DCT 만 보기 때문에 밝기·대비·감마·종횡비·노이즈는 거의 통과시킨다.
  실측(64bit 해밍 거리): 감마 0.75 → 0 / 대비 1.25 → 0 / 스트레치 15% → 0 /
  조명 그라디언트 20% → 평균 3 / 비네팅 30% → 3. 반면 비대칭 크롭 8% → 평균 12,
  14% → 평균 21. 즉 거리를 벌어주는 건 사실상 재구도 하나뿐이다.

여백을 쓰지 않는 이유(중요):
- 예전에는 넓은 액자/매트/비율 패딩으로 사진을 '축소'해 재구도 효과를 냈다.
  거리는 잘 벌렸지만 사진이 캔버스의 33~70%까지 쪼그라들어, 블로그에서
  "회색 여백만 넓고 그림이 안 보인다"는 결과가 됐다.
- 지금은 방향을 뒤집어 가장자리를 조금 덜어내는 '확대'로 같은 거리를 얻는다
  (_geom_warp). 여백이 0이라 사진이 화면을 꽉 채우고 주제는 오히려 커진다.
  프레임은 한 변 2.5% 이하의 얇은 테두리만 — 캔버스 증가는 면적 기준 1.15배 이하.
- 톤 지터/조명/노이즈는 해시엔 기여가 없으므로 '눈에 안 보이는' 수준으로만 유지한다
  (파일 해시·픽셀 지문을 흩는 용도).

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
from PIL import Image, ImageOps, ImageDraw, ImageFilter, ImageEnhance, ImageStat

# ---- 기본 파라미터 ----
MIN_DISTANCE = 12          # 원본과의 최소 pHash Hamming 거리(64bit 중) — 엄격
MIN_SIBLING_DISTANCE = 6   # 같은 원본의 과거 변형끼리 최소 거리 — dedup 추정임계(~5) 위 여유 1(여력 2배)
MIN_SSIM = 0.95            # 인코딩(압축) 충실도 하한 — 저품질 방지 (1.0=무손실)
MAX_ATTEMPTS = 16          # 구조 모드가 늘어난 만큼 탐색 폭도 확대
MAX_WIDTH = 1280           # 블로그 표시 최대폭 (하한 1080 유지)
JPEG_Q_RANGE = (88, 92)

# 회피셋(형제)에 넣을 '최근 변형' 개수. 호출측이 이 값으로 잘라서 넘긴다.
#
# 왜 상한이 필요한가: 게이트는 형제 전부와 ≥MIN_SIBLING_DISTANCE 를 요구하므로,
# 한 사진을 재사용할수록 조건이 빡빡해져 통과하는 변형을 찾기 어려워진다.
# 운영 실측 — 사진 74장을 90번씩 재사용한 시점에 형제가 장당 90개까지 쌓였고,
# 장당 시도가 1회에서 7회로 늘어 배정 한 건(12장)이 3~4분까지 갔다.
# 형제 300개(고정 하단 이미지)에서는 16회를 다 쓰고도 못 넘겨 35초를 버렸다.
#
# 막으려는 건 '같은 글/비슷한 시기의 사진끼리 중복 판정'이다. 90번 전에 쓴 변형과
# 6비트 안쪽으로 겹칠 확률은 낮고, 겹쳐도 그 사이 다른 글 수십 개가 끼어 있다.
# 최근 것만 확실히 벌리는 편이 비용 대비 효과가 훨씬 크다.
SIBLING_WINDOW = 24

# 얇은 테두리만 남긴 프레임 세트. none 은 캔버스가 전혀 안 커진다.
# vignette 는 등록만 해두고 기본에선 뺐다 — 해시 거리에 기여가 거의 없으면서
# 가장자리 톤만 눈에 띄게 바꿔서, '변화는 줄이고 사진에 집중' 방향과 어긋난다.
FRAME_STYLES = ("none", "hairline", "white_margin", "soft_shadow")

# 비율 변형 계수 — 원본 종횡비 × 계수 를 '스트레치'로 맞춘다(패딩·크롭 없음).
# ±6% 는 나란히 놓고 비교해야 겨우 보이는 수준이지만 pHash 는 확실히 움직인다.
RESHAPE_FACTORS = (None, 0.94, 0.97, 1.03, 1.06)

# 재구도(확대) 예산 — 가로/세로에서 덜어낼 비율. 시도마다 조금씩 키워
# '게이트를 넘기는 가장 약한 변형'이 채택되게 한다.
TRIM_START = 0.09
TRIM_STEP = 0.02
TRIM_MAX = 0.24
TRIM_MAX_CROP = 0.32     # allow_crop=True 일 때 상한

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
    return (k / k.sum()).astype(np.float32)


def _blur1d(a: np.ndarray, k: np.ndarray, axis: int) -> np.ndarray:
    pad = len(k) // 2
    a = np.moveaxis(a, axis, -1)
    ap = np.pad(a, [(0, 0)] * (a.ndim - 1) + [(pad, pad)], mode="edge")
    out = np.zeros_like(a, dtype=np.float32)
    n = a.shape[-1]
    for i, kv in enumerate(k):
        out += kv * ap[..., i:i + n]
    return np.moveaxis(out, -1, axis)


def _blur(a: np.ndarray, radius: float = 4.0) -> np.ndarray:
    k = _gauss_kernel(radius)
    return _blur1d(_blur1d(a, k, 1), k, 0)


def ssim(img_a: Image.Image, img_b: Image.Image, size: int = 512) -> float:
    """두 이미지를 공통 크기 그레이스케일로 맞춰 windowed SSIM 평균.

    float32 로 계산한다(종전 float64). 재는 값이 0.99대이고 임계는 0.95라
    1e-6 수준의 차이는 판정에 영향이 없는데, 512x512 배열 6개를 13탭으로
    두 축 블러하는 비용은 절반이 된다.
    """
    a = _gray_array(img_a, size).astype(np.float32)
    b = _gray_array(img_b, size).astype(np.float32)
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
# 프레임 — 전부 "얇게". 사진이 캔버스를 꽉 채우는 게 우선이다.
# (넓은 매트/액자는 해시엔 좋지만 그림을 안 보이게 만들어서 폐기했다.
#  잃은 해시 이동량은 _geom_warp 의 재구도가 그대로 대신 낸다.)
# ============================================================
def _frame_none(img: Image.Image, rng: random.Random, strength: float) -> Image.Image:
    """테두리 없음 — 사진 그대로. 기하/조명만으로 게이트를 넘길 때 쓴다."""
    return img


def _frame_vignette(img: Image.Image, rng: random.Random, strength: float) -> Image.Image:
    """가장자리만 살짝 어둡게. 기본 세트에는 없고 frame_styles 로 지정할 때만 쓴다."""
    w, h = img.size
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy = w / 2, h / 2
    r = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2)
    depth = min(0.16, rng.uniform(0.07, 0.11) * (1 + 0.3 * strength))
    vig = 1.0 - np.clip(r - 0.55, 0, 1) * depth
    return Image.fromarray(np.clip(arr * vig[..., None], 0, 255).astype(np.uint8))


def _frame_hairline(img: Image.Image, rng: random.Random, strength: float) -> Image.Image:
    """머리카락 굵기(한 변 0.4~0.9%) 테두리. 여백이라기보다 마감선에 가깝다."""
    w, h = img.size
    b = max(1, int(min(w, h) * rng.uniform(0.004, 0.009) * (1 + 0.2 * strength)))
    tone = rng.randint(238, 255)
    out = Image.new("RGB", (w + 2 * b, h + 2 * b), (tone, tone, tone))
    out.paste(img, (b, b))
    return out


def _frame_white_margin(img: Image.Image, rng: random.Random, strength: float) -> Image.Image:
    """흰 여백 — 종전 2~5% 에서 1~2% 로. 폴라로이드가 아니라 '살짝 뗀 여백' 수준."""
    w, h = img.size
    m = int(min(w, h) * min(0.022, rng.uniform(0.010, 0.017) * (1 + 0.2 * strength)))
    tone = rng.randint(248, 255)
    out = Image.new("RGB", (w + 2 * m, h + 2 * m), (tone, tone, tone))
    out.paste(img, (m, m))
    return out


def _frame_soft_shadow(img: Image.Image, rng: random.Random, strength: float) -> Image.Image:
    """얇은 여백 + 아주 작은 라운드 + 옅은 그림자(카드 느낌).
    라운드 반경은 여백보다 작게 잡아 그림 모서리를 파먹지 않게 한다."""
    w, h = img.size
    pad = int(min(w, h) * min(0.025, rng.uniform(0.013, 0.020) * (1 + 0.2 * strength)))
    pad = max(3, pad)
    radius = int(min(pad * 1.2, min(w, h) * 0.012))
    bg_tone = rng.randint(246, 255)
    canvas = Image.new("RGB", (w + 2 * pad, h + 2 * pad), (bg_tone, bg_tone, bg_tone))
    off = max(1, pad // 3)
    # 그림자는 '흐린 검은 도형'이라 색 채널이 필요 없고(전부 검정), 1/4 해상도로
    # 그린 뒤 늘려도 눈에 차이가 없다. 종전엔 풀해상도 RGBA 에 GaussianBlur 를 걸어
    # 시도당 40ms 넘게 먹었다(시도는 한 장에 여러 번 돈다).
    # → 1채널 마스크를 1/4 로 그려 흐린 뒤 늘리고, 검정을 그 마스크로 얹는다.
    S = 4
    sw, sh = max(1, canvas.width // S), max(1, canvas.height // S)
    mask = Image.new("L", (sw, sh), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [(pad + off) // S, (pad + off) // S, (pad + w + off) // S, (pad + h + off) // S],
        radius=max(radius // S, 1), fill=rng.randint(35, 60),
    )
    mask = mask.filter(ImageFilter.GaussianBlur(max(2, pad // 2) / S))
    canvas.paste((0, 0, 0), (0, 0), mask.resize(canvas.size, Image.Resampling.BILINEAR))
    if radius > 2:
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, w, h], radius=radius, fill=255)
        canvas.paste(img, (pad, pad), mask)
    else:
        canvas.paste(img, (pad, pad))
    return canvas


_FRAME_FUNCS = {
    "none": _frame_none,
    "vignette": _frame_vignette,
    "hairline": _frame_hairline,
    "white_margin": _frame_white_margin,
    "soft_shadow": _frame_soft_shadow,
}


def _geom_warp(
    img: Image.Image, rng: random.Random, strength: float,
    reshape: float | None, trim: float,
    scale: float = 1.0, max_width: int = MAX_WIDTH,
) -> Image.Image:
    """재구도(살짝 확대+이동) + 미세 회전 + 미세 원근 + 비율 스트레치를 QUAD 한 번으로.

    왜 재구도인가(실측):
      pHash 는 32x32 로 줄여 저주파 DCT 만 보기 때문에 밝기·대비·감마·종횡비를
      아무리 흔들어도 꿈쩍하지 않는다 — 감마 0.75 / 대비 1.25 / 스트레치 15% 모두
      해밍 거리 0~3. 거리를 실제로 벌어주는 건 "화면에 어디를 얼마나 담느냐"뿐이다
      (비대칭 크롭 14% → 평균 20, 8% → 평균 12).
      종전엔 넓은 액자·매트로 사진을 캔버스의 33~70%까지 '축소'해서 같은 효과를 냈는데,
      그게 블로그에서 회색 여백만 넓어 보이던 원인이었다. 여기선 반대로 가장자리를
      조금 덜어내 '확대'한다 — 거리는 같은 원리로 벌면서, 여백은 0이고 주제는 커진다.

    trim: 가로/세로에서 덜어낼 총 비율. 확대·이동·회전·원근이 전부 이 예산 안에서
          일어나므로 잘려나가는 양이 명확히 상한을 갖는다(기본 시작 9% → 최대 24%).
    """
    W, H = img.size
    # 1) 미세 회전 각도 — 짧은 변 기준으로 예산의 일부만 쓴다
    a_max = min(0.018, trim * 0.35 * min(W, H) / max(W, H))
    a = min(1.0, rng.uniform(0.35, 0.8) + 0.12 * strength) * a_max * rng.choice([-1, 1])
    ca, sa = abs(math.cos(a)), abs(math.sin(a))

    # 2) 샘플링 사각형 크기 = (1 - trim). 회전분은 아래 여유(free) 계산에서 자동 반영된다.
    s = 1.0 - trim
    hw, hh = s * W / 2, s * H / 2
    # 돌아간 사각형이 원본 밖으로 나가지 않는 범위에서 중심을 흔든다 → '비대칭 크롭'
    free_x = max(0.0, W / 2 - (hw * ca + hh * sa))
    free_y = max(0.0, H / 2 - (hw * sa + hh * ca))
    cx = W / 2 + rng.uniform(-1, 1) * free_x * 0.9
    cy = H / 2 + rng.uniform(-1, 1) * free_y * 0.9

    # 3) 원근: 네 모서리를 서로 다른 양만큼 안쪽으로 당긴다(밖으로는 안 나가 여백이 없다)
    pj = trim * 0.12
    ca_s, sa_s = math.cos(a), math.sin(a)
    pts: list[float] = []
    for dx, dy in ((-hw, -hh), (-hw, hh), (hw, hh), (hw, -hh)):  # NW, SW, SE, NE 순서
        x = cx + dx * ca_s - dy * sa_s + math.copysign(W * pj * rng.uniform(0.15, 1.0), -dx)
        y = cy + dx * sa_s + dy * ca_s + math.copysign(H * pj * rng.uniform(0.15, 1.0), -dy)
        pts += [x, y]

    # 4) 출력 크기 = 비율(±6%) × 리스케일(96~104%), 최대폭으로 클램프.
    #    pHash 는 정사각 리사이즈라 비율에 둔감하지만, 파일 지문/다른 해시 계열을
    #    흩는 데는 도움이 된다(여백은 안 생김).
    #
    #    종전엔 여기서 원본 크기로 뽑은 뒤 호출측이 LANCZOS 로 두 번 더 리샘플했다
    #    (리스케일 → 최대폭). 크기를 미리 계산해 QUAD 한 번으로 끝내면 전체 해상도
    #    리샘플이 3회에서 1회로 준다 — 시도당 35ms 절약, 화질 차이는 없다
    #    (총 배율이 0.96~1.04 라 축소량이 4% 이내).
    out_w = W * scale
    out_h = (H / reshape if reshape else H) * scale
    if out_w > max_width:
        out_h *= max_width / out_w
        out_w = max_width
    return img.transform(
        (max(1, int(round(out_w))), max(1, int(round(out_h)))),
        Image.Transform.QUAD, data=tuple(pts),
        resample=Image.Resampling.BICUBIC,
    )


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
    trim: float                # 채택된 재구도 예산(다음 호출의 시작점으로 재사용)


# ============================================================
# 코어 변형 (프레임 이전 본문)
# ============================================================
_LUMA = (299 / 1000, 587 / 1000, 114 / 1000)   # PIL 의 "L" 변환 계수


def _tone_lut(img: Image.Image, rng: random.Random) -> list[int]:
    """밝기·대비·감마를 256칸 LUT 하나로 합성한다 — point() 한 번(C 레벨)에 끝난다.

    셋 다 '픽셀 값에만' 의존하는 함수라 합성할 수 있다(대비의 기준 평균 m 은 스칼라).
        밝기(b): v ↦ v·b
        대비(c): v ↦ (v-m)·c + m,  m = 밝기 적용 후 휘도 평균
        감마(g): v ↦ (v/255)^g·255
    합치면 v ↦ 감마(clip(b·c·v + m(1-c))).

    채도만은 픽셀의 회색값에 의존해 LUT 로 못 합친다. 대신 채도는 아핀변환과
    교환법칙이 성립하므로(휘도를 보존한다) 순서를 바꿔 먼저 적용한다 —
    ImageEnhance.Color 도 C 구현이라 싸다. 결과는 종전과 동일하다.
    """
    b = rng.uniform(0.97, 1.03)
    c = rng.uniform(0.97, 1.03)
    gamma = rng.uniform(0.97, 1.03)
    # 채도는 휘도를 바꾸지 않으므로 여기서 재도 밝기·대비 기준 평균은 같다.
    r_, g_, b_ = ImageStat.Stat(img).mean[:3]
    m = round(b * (_LUMA[0] * r_ + _LUMA[1] * g_ + _LUMA[2] * b_))
    v = np.clip(b * c * np.arange(256, dtype=np.float64) + m * (1 - c), 0, 255)
    v = np.clip((v / 255.0) ** gamma * 255 + 0.5, 0, 255)
    return v.astype(np.uint8).tolist() * 3


def _light_plane(H: int, W: int, rng: random.Random, terms: int = 3) -> np.ndarray:
    """저주파 조명 그라디언트 — sin(2π(fx·x/W + fy·y/H) + φ) 를 terms 개 더한 평면.

    sin(u+v) = sin(u)cos(v) + cos(u)sin(v) 로 분리해 1차원 sin/cos 만 계산한다.
    전 픽셀에 sin 을 돌리던 종전 방식과 값은 완전히 같고(항등식), 100만 픽셀짜리
    초월함수 호출이 (H+W) 번으로 줄어 시도당 65ms → 5ms 가 된다.
    """
    x = np.arange(W, dtype=np.float32) * (2 * math.pi / W)
    y = np.arange(H, dtype=np.float32) * (2 * math.pi / H)
    plane = np.zeros((H, W), dtype=np.float32)
    for _ in range(terms):
        u = rng.uniform(-1.6, 1.6) * x + rng.uniform(0, 2 * math.pi)   # (W,)
        v = rng.uniform(-1.6, 1.6) * y                                  # (H,)
        plane += np.sin(v)[:, None] * np.cos(u)[None, :]
        plane += np.cos(v)[:, None] * np.sin(u)[None, :]
    plane /= terms  # ~[-1, 1]
    return plane


def _transform_body(
    base: Image.Image, rng: random.Random, strength: float, max_width: int,
    flip: bool = False, ratio: float | None = None, trim: float = TRIM_START,
) -> Image.Image:
    """base: 이미 exif_transpose + RGB 로 준비된 원본(시도마다 다시 만들지 않는다)."""
    # 0) 구조 모드: 좌우 반전 — 새 해시 클러스터(거의 공짜, 눈엔 자연스러움)
    img = ImageOps.mirror(base) if flip else base

    # 1) 재구도 + 회전 + 원근 + 비율 + 리스케일 + 최대폭을 QUAD 리샘플 한 번으로.
    #    여백은 만들지 않는다.
    img = _geom_warp(img, rng, strength, ratio, trim,
                     scale=rng.uniform(0.96, 1.04), max_width=max_width)

    # 2) 톤 지터 — 채도 1회 + LUT 1회로 끝낸다(종전 ImageEnhance 3종 + point 4회 왕복).
    img = ImageEnhance.Color(img).enhance(rng.uniform(0.96, 1.04))
    img = img.point(_tone_lut(img, rng))

    # 3) 조명 + 노이즈. 픽셀마다 달라야 해서 여기만 배열로 내려간다.
    arr = np.asarray(img, dtype=np.float32)
    H, W = arr.shape[:2]

    # 조명 그라디언트 — pHash 거리에는 거의 기여하지 않는다(실측: 진폭 20% 를 줘도
    # 평균 3비트). 거리는 재구도가 벌어주므로 여기는 '눈에 안 보이는' 범위만 쓴다.
    amp = min(0.05, rng.uniform(0.020, 0.035) * (1 + 0.3 * strength))
    arr *= (1.0 + amp * _light_plane(H, W, rng))[..., None]

    # 미세 휘도 노이즈 (비가시). float32 로 뽑는다 — float64 대비 절반 비용.
    sigma = 1.5 + 0.8 * strength
    noise = np.random.default_rng(rng.randint(0, 2**31)).standard_normal(
        (H, W), dtype=np.float32
    )
    arr += (noise * sigma)[..., None]

    np.clip(arr, 0, 255, out=arr)
    return Image.fromarray(arr.astype(np.uint8))


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
    allow_reframe: bool = True,  # 종횡비 ±6% 스트레치 허용(여백 안 생김)
    allow_crop: bool = False,  # True 면 가장자리 다듬기 한도를 4%→7% 로 넓힌다
    trim_start: float | None = None,   # 직전에 통과한 재구도 예산(있으면 거기서 시작)
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
    # 시도마다 만들던 것을 한 번만 만든다(시도는 최대 16회 돈다).
    base = ImageOps.exif_transpose(src).convert("RGB")

    siblings = set()
    for hx in (sibling_hashes or []):
        try:
            siblings.add(from_hex(hx))
        except (ValueError, TypeError):
            continue

    styles = list(frame_styles) if frame_styles else list(FRAME_STYLES)
    rng = random.Random(seed)

    ratios = list(RESHAPE_FACTORS) if allow_reframe else [None]

    # 재구도 예산의 시작점. 직전 통과 지점의 한 칸 아래에서 출발한다.
    cap = TRIM_MAX_CROP if allow_crop else TRIM_MAX
    base_trim = TRIM_START
    if trim_start is not None:
        base_trim = min(cap, max(TRIM_START, trim_start - TRIM_STEP))

    # 성능: 재사용 사진이 탈락하는 건 거의 항상 '거리 게이트'다. SSIM(압축충실도)은
    # 대개 여유롭게 통과하므로, 거리 게이트를 먼저 보고 통과할 때만 SSIM을 계산한다.
    # dhash 도 실제 반환하는 결과에만 계산한다(매 시도 계산하던 낭비 제거).
    # → 통과/실패 판정과 출력 바이트는 종전과 동일, 실패 시도의 비용만 크게 절감.
    best = None            # (data, ph, q, d_orig, d_sib, attempt, mode_tag, quality)
    best_key = None
    for attempt in range(max_attempts):
        strength = attempt / 2.0  # 0, 0.5, 1.0, ... 강도 상승
        # 구조 모드 선택(반전×재크롭×프레임). 뒤로 갈수록 반전을 켜 먼 영역까지 탐색.
        flip = bool(rng.getrandbits(1)) if allow_flip else False
        if allow_flip and attempt >= max_attempts // 2:
            flip = True  # 후반부: 반전 강제 → 확실히 다른 해시 클러스터로
        ratio = rng.choice(ratios)
        # 재구도 예산은 시도마다 조금씩만 키운다 → 통과하는 순간 반환되므로
        # 실제로 채택되는 건 '거리를 넘긴 가장 약한 확대'다.
        #
        # 시작점: 이 사진이 직전에 통과한 예산의 한 칸 아래(trim_start). 매번 9% 부터
        # 다시 올라가면 통과하지 못할 게 뻔한 앞쪽 시도를 반복해서 버린다 — 같은 사진은
        # 대체로 같은 지점에서 통과하기 때문이다. 한 칸 아래에서 시작하므로 '가장 약한
        # 변형을 채택한다'는 성질은 그대로다(더 약하게 통과되면 그게 먼저 잡힌다).
        trim = min(cap, base_trim + TRIM_STEP * attempt)
        body = _transform_body(base, rng, strength, max_width, flip=flip, ratio=ratio, trim=trim)
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
        mode_tag = style + ("|flip" if flip else "") + (f"|{ratio:.2f}" if ratio else "")

        dist_ok = d_orig >= min_distance and d_sib >= min_sibling_distance
        if dist_ok:
            # 거리 통과 시에만 SSIM 계산(압축 손실만 측정 → 저품질 여부)
            q = ssim(framed, framed_dec)
            if q >= min_ssim:
                return UniquifyResult(
                    image_bytes=data, phash=to_hex(ph), dhash=to_hex(dhash(framed_dec)),
                    ssim=round(q, 4), min_distance=min(d_orig, d_sib), attempts=attempt + 1,
                    frame_style=mode_tag[:30], passed=True, quality=quality, trim=trim,
                )
        else:
            q = 0.0  # 거리 게이트 이미 탈락 → SSIM 생략(판정에 불필요)

        # 최선 후보: 원본거리 우선(엄격 임계), 그다음 형제거리, 품질
        key = (min(d_orig, min_distance), min(d_sib, min_sibling_distance), q)
        if best is None or key > best_key:
            best = (data, ph, q, d_orig, d_sib, attempt, mode_tag, quality, trim)
            best_key = key

    # 게이트 미통과 → 최선 후보 반환(dhash는 여기서 한 번만 계산)
    if best is None:
        return None
    data, ph, q, d_orig, d_sib, attempt, mode_tag, quality, trim = best
    best_dec = Image.open(io.BytesIO(data)).convert("RGB")
    best_dec.load()
    return UniquifyResult(
        image_bytes=data, phash=to_hex(ph), dhash=to_hex(dhash(best_dec)),
        ssim=round(q, 4), min_distance=min(d_orig, d_sib), attempts=attempt + 1,
        frame_style=mode_tag[:30], passed=False, quality=quality, trim=trim,
    )
