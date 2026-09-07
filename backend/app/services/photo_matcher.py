"""
글 문단(슬롯) ↔ 풀 사진 매칭. 순수 함수(LLM/DB 없음).

- Slot: 글의 어느 문단 뒤에 어떤 성격의 사진이 필요한지(LLM 플랜 또는 fallback_slots 로 생성)
- Photo: photo_tagger 가 채운 태그 정보 + 사용 이력
- score(): 슬롯-사진 적합도 점수
- assign(): 전체 (슬롯, 사진) 쌍을 점수순 그리디로 배정
- fallback_slots(): 플랜이 없을 때 문단 수 기준 균등 배치
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

STAGES: List[str] = ["도입", "진료과정", "시술", "장비소개", "마무리", "기타"]

# 단계 → 어울리는 scene
SCENE_AFFINITY: Dict[str, Set[str]] = {
    "도입": {"exterior", "reception"},
    "진료과정": {"consult", "staff"},
    "시술": {"treatment", "equipment"},
    "장비소개": {"equipment"},
    "마무리": {"reception", "exterior", "product"},
    "기타": set(),
}

W_KEYWORD = 3.0
W_STAGE = 2.0
W_SCENE = 1.5
P_TEXT = -2.0
P_RECENT = -1.5
P_USE_COUNT = -0.02


@dataclass
class Slot:
    index: int
    after_paragraph: int          # 이 번호(1-based)의 문단 "뒤"에 삽입
    need: str                     # 필요한 사진 설명(자유 텍스트)
    keywords: List[str] = field(default_factory=list)
    stage: str = "기타"           # STAGES 중 하나


@dataclass
class Photo:
    id: str
    scene: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    caption: Optional[str] = None
    has_text: Optional[bool] = None
    suitable_for: List[str] = field(default_factory=list)
    use_count: int = 0
    last_used_at: Optional[datetime] = None


def _norm(s: str) -> str:
    return "".join(s.split()).lower()


def _keyword_hits(keywords: List[str], tags: List[str]) -> List[str]:
    """키워드와 태그의 양방향 부분 문자열 일치. 일치한 태그를 순서대로 돌려준다(중복 제거)."""
    hits: List[str] = []
    norm_tags = [(_norm(t), t) for t in tags if isinstance(t, str) and t.strip()]
    for kw in keywords:
        if not isinstance(kw, str):
            continue
        nk = _norm(kw)
        if not nk:
            continue
        for nt, original in norm_tags:
            if nk in nt or nt in nk:
                if original not in hits:
                    hits.append(original)
                break  # 키워드 하나당 1회만 가산
    return hits


def _tiebreak(photo_id: str) -> float:
    h = hashlib.md5(photo_id.encode("utf-8")).hexdigest()
    return (int(h[:6], 16) % 1000) / 1_000_000.0   # 0 ~ 0.000999


def score(slot: Slot, photo: Photo, recently_used_ids: Set[str]) -> float:
    s = 0.0
    s += W_KEYWORD * len(_keyword_hits(slot.keywords, photo.tags))
    if slot.stage in (photo.suitable_for or []):
        s += W_STAGE
    if photo.scene and photo.scene in SCENE_AFFINITY.get(slot.stage, set()):
        s += W_SCENE
    if photo.has_text and slot.stage != "장비소개":
        s += P_TEXT
    if photo.id in recently_used_ids:
        s += P_RECENT
    s += P_USE_COUNT * max(0, photo.use_count or 0)
    s += _tiebreak(photo.id)
    return s


def _reason(slot: Slot, photo: Photo) -> str:
    parts: List[str] = []
    hits = _keyword_hits(slot.keywords, photo.tags)
    if hits:
        parts.append("태그 일치: " + ", ".join(hits))
    if slot.stage in (photo.suitable_for or []):
        parts.append(f"단계: {slot.stage}")
    elif photo.scene and photo.scene in SCENE_AFFINITY.get(slot.stage, set()):
        parts.append(f"장면: {photo.scene}")
    if not parts:
        parts.append("균등 배정")
    return " / ".join(parts)


def assign(
    slots: List[Slot],
    photos: List[Photo],
    recently_used_ids: Optional[Set[str]] = None,
    allow_repeat: bool = False,
) -> List[dict]:
    """전체 (슬롯, 사진) 쌍을 점수 내림차순으로 그리디 배정한다.

    - 사진은 기본적으로 한 번만 사용. allow_repeat 이고 사진 수 < 슬롯 수일 때만
      남은 슬롯에 재사용(이번 배정에서 덜 쓴 사진 우선).
    - 반환은 슬롯 순서. 사진이 없으면 [].
    """
    if not slots or not photos:
        return []
    recent = recently_used_ids or set()

    scores: Dict[Tuple[int, str], float] = {}
    pairs: List[Tuple[float, int, str]] = []
    for si, slot in enumerate(slots):
        for photo in photos:
            sc = score(slot, photo, recent)
            scores[(si, photo.id)] = sc
            pairs.append((sc, si, photo.id))
    # 점수 높은 순, 같으면 앞 슬롯, 같으면 id
    pairs.sort(key=lambda p: (-p[0], p[1], p[2]))

    photo_by_id = {p.id: p for p in photos}
    chosen: Dict[int, str] = {}
    used: Set[str] = set()
    for sc, si, pid in pairs:
        if si in chosen or pid in used:
            continue
        chosen[si] = pid
        used.add(pid)
        if len(chosen) == len(slots):
            break

    if allow_repeat and len(chosen) < len(slots):
        times: Dict[str, int] = {pid: 1 for pid in used}
        for si in range(len(slots)):
            if si in chosen:
                continue
            best_pid, best_val = None, None
            for photo in photos:
                val = scores[(si, photo.id)] - 1.0 * times.get(photo.id, 0)
                if best_val is None or val > best_val:
                    best_pid, best_val = photo.id, val
            if best_pid is None:
                continue
            chosen[si] = best_pid
            times[best_pid] = times.get(best_pid, 0) + 1

    out: List[dict] = []
    for si in sorted(chosen):
        slot = slots[si]
        pid = chosen[si]
        out.append({
            "slot": slot.index,
            "after_paragraph": slot.after_paragraph,
            "pool_image_id": pid,
            "score": round(scores[(si, pid)], 4),
            "reason": _reason(slot, photo_by_id[pid]),
        })
    return out


def fallback_slots(paragraph_count: int, image_count: int) -> List[Slot]:
    """LLM 플랜이 없을 때 문단 수 기준으로 균등 간격 슬롯을 만든다.

    단계는 상대 위치로 추정: 첫 슬롯→도입, 마지막→마무리, 중간→진료과정/시술 번갈아.
    after_paragraph 는 1-based 문단 번호(그 문단 뒤에 삽입)이며 마지막 문단 뒤에는 넣지 않는다.
    """
    if paragraph_count <= 0 or image_count <= 0:
        return []
    n = min(image_count, paragraph_count)

    positions: List[int] = []
    for i in range(n):
        pos = int(round((i + 1) * paragraph_count / (n + 1)))
        pos = max(1, min(paragraph_count, pos))
        if positions and pos <= positions[-1]:
            pos = positions[-1] + 1
        if pos > paragraph_count:
            break
        positions.append(pos)

    slots: List[Slot] = []
    count = len(positions)
    for i, pos in enumerate(positions):
        if i == 0:
            stage = "도입"
        elif i == count - 1 and count >= 2:
            stage = "마무리"
        else:
            stage = "진료과정" if (i % 2 == 1) else "시술"
        slots.append(Slot(
            index=i,
            after_paragraph=pos,
            need=f"{stage} 단계에 어울리는 사진",
            keywords=[],
            stage=stage,
        ))
    return slots
