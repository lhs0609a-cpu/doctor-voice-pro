"""
서버 예약 엔진.

입력: 발행할 원고 N건, 블로그 목록(하루 한도·시간대·최소 간격), 시작일, 기간(일)
출력: 각 원고에 (블로그, 예약시각) 배정. 시각은 KST naive, 10분 단위(네이버 예약은 10분 단위만 가능).

규칙
- 블로그별로 하루 한도 안에서, 시간대(window) 안에서, 최소 간격을 지키며 랜덤하게 흩는다.
- 이미 잡힌 자리(PublishJob 활성 상태 + ScheduleMark + 옛 queued_posts)와 겹치지 않는다.
- 블로그가 여러 개면 라운드로빈으로 고르게 나눈다(한 블로그에 몰리지 않게).
- 자리가 모자라면 남은 건수를 돌려준다(호출자가 기간을 늘리거나 한도를 올리라고 안내).
- 결정론성: seed 를 주면 같은 입력에 같은 결과(미리보기 ↔ 확정 일치).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Dict, Iterable, List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Blog, PublishJob, JOB_ACTIVE
from app.models.publish_queue import QueuedPost, ScheduleMark

SLOT_MINUTES = 10


@dataclass
class BlogPlan:
    ref_id: str                    # campaign_blogs.id
    naver_blog_id: str
    daily_limit: int = 3
    window_start: str = "09:00"
    window_end: str = "21:00"
    min_gap_minutes: int = 120
    taken: Set[datetime] = field(default_factory=set)   # 이미 잡힌 자리(KST naive, 10분 단위)


def _parse_hhmm(s: str, default: time) -> time:
    try:
        h, m = (s or "").split(":")
        return time(int(h), int(m))
    except Exception:  # noqa: BLE001
        return default


def floor_slot(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0, minute=(dt.minute // SLOT_MINUTES) * SLOT_MINUTES)


def kst_now() -> datetime:
    """서버 타임존과 무관하게 KST 현재 시각(naive)."""
    return datetime.utcnow() + timedelta(hours=9)


async def load_taken_slots(db: AsyncSession, user_id: str, blogs: Iterable[BlogPlan]) -> None:
    """블로그별로 이미 잡힌 자리를 채운다(활성 발행건 + 예약 기록 + 옛 대량 큐)."""
    by_ref = {b.ref_id: b for b in blogs}
    by_naver = {b.naver_blog_id: b for b in blogs}

    rows = (await db.execute(
        select(PublishJob.blog_ref_id, PublishJob.scheduled_at).where(
            PublishJob.user_id == user_id, PublishJob.status.in_(list(JOB_ACTIVE)),
        )
    )).all()
    for ref, at in rows:
        if ref in by_ref and at:
            by_ref[ref].taken.add(floor_slot(at))

    marks = (await db.execute(
        select(ScheduleMark.blog_id, ScheduleMark.scheduled_at).where(ScheduleMark.user_id == user_id)
    )).all()
    for bid, at in marks:
        b = by_naver.get(bid or "")
        if b and at:
            b.taken.add(floor_slot(at))

    # 옛 대량 큐(블로그 정보 없음) — 블로그가 하나뿐일 때만 그 블로그 자리로 친다
    if len(by_ref) == 1:
        only = next(iter(by_ref.values()))
        qrows = (await db.execute(
            select(QueuedPost.scheduled_at).where(
                QueuedPost.user_id == user_id, QueuedPost.status.in_(["queued", "registered"]),
            )
        )).all()
        for (at,) in qrows:
            if at:
                only.taken.add(floor_slot(at))


def _day_slots(day: date, b: BlogPlan, earliest: datetime, rng: random.Random) -> List[datetime]:
    """하루 안에서 후보 시각을 한도만큼 뽑는다. 시간대를 한도 수만큼 구간으로 나눠 각 구간 안에서 랜덤."""
    start = datetime.combine(day, _parse_hhmm(b.window_start, time(9, 0)))
    end = datetime.combine(day, _parse_hhmm(b.window_end, time(21, 0)))
    if end <= start:
        end = start + timedelta(hours=8)
    if start < earliest:
        start = floor_slot(earliest + timedelta(minutes=SLOT_MINUTES))
    if start >= end:
        return []
    span = (end - start).total_seconds() / 60
    n = max(1, b.daily_limit)
    seg = span / n
    picks: List[datetime] = []
    last: Optional[datetime] = None
    # 이미 그날 잡힌 자리도 간격 계산에 포함
    same_day_taken = sorted(t for t in b.taken if t.date() == day)
    for i in range(n):
        lo = start + timedelta(minutes=seg * i)
        hi = start + timedelta(minutes=seg * (i + 1) - SLOT_MINUTES)
        if hi < lo:
            hi = lo
        for _ in range(20):
            offset = rng.uniform(0, max(0.0, (hi - lo).total_seconds() / 60))
            cand = floor_slot(lo + timedelta(minutes=offset))
            if cand in b.taken:
                continue
            if last and (cand - last) < timedelta(minutes=b.min_gap_minutes):
                continue
            if any(abs((cand - t).total_seconds()) < b.min_gap_minutes * 60 for t in same_day_taken):
                continue
            picks.append(cand)
            last = cand
            break
    return picks


def allocate(
    count: int,
    blogs: List[BlogPlan],
    start_day: date,
    days: int,
    *,
    earliest: Optional[datetime] = None,
    seed: Optional[int] = None,
) -> Tuple[List[Tuple[str, datetime]], int]:
    """
    count 건을 blogs 에 배정. 반환 ([(blog_ref_id, scheduled_at)...] 시각순, 미배정 건수).
    하루 단위로 돌며 블로그를 라운드로빈으로 섞어 고르게 채운다.
    """
    rng = random.Random(seed if seed is not None else 0)
    earliest = earliest or (kst_now() + timedelta(minutes=30))
    assigned: List[Tuple[str, datetime]] = []
    remaining = count
    if not blogs or count <= 0:
        return [], count

    # 이미 잡힌 자리 기준으로 하루 남은 한도 계산
    for d in range(days):
        if remaining <= 0:
            break
        day = start_day + timedelta(days=d)
        day_picks: Dict[str, List[datetime]] = {}
        for b in blogs:
            used_today = sum(1 for t in b.taken if t.date() == day)
            free = max(0, b.daily_limit - used_today)
            if free <= 0:
                continue
            picks = _day_slots(day, b, earliest, rng)[:free]
            day_picks[b.ref_id] = picks
        # 라운드로빈: 각 블로그에서 한 개씩 번갈아 가져간다
        order = [b.ref_id for b in blogs]
        rng.shuffle(order)
        progress = True
        while remaining > 0 and progress:
            progress = False
            for ref in order:
                if remaining <= 0:
                    break
                picks = day_picks.get(ref) or []
                if picks:
                    at = picks.pop(0)
                    assigned.append((ref, at))
                    next(b for b in blogs if b.ref_id == ref).taken.add(at)
                    remaining -= 1
                    progress = True
    assigned.sort(key=lambda x: x[1])
    return assigned, remaining


def blog_plan_from_model(b: Blog) -> BlogPlan:
    return BlogPlan(
        ref_id=b.id,
        naver_blog_id=b.blog_id,
        daily_limit=b.daily_limit or 3,
        window_start=b.window_start or "09:00",
        window_end=b.window_end or "21:00",
        min_gap_minutes=b.min_gap_minutes or 120,
    )


def calendar_view(assigned: List[Tuple[str, datetime]], label_by_ref: Dict[str, str]) -> List[Dict]:
    """달력 미리보기용: 날짜별 건수/블로그별 건수."""
    by_day: Dict[str, Dict] = {}
    for ref, at in assigned:
        d = at.date().isoformat()
        cell = by_day.setdefault(d, {"date": d, "total": 0, "blogs": {}})
        cell["total"] += 1
        name = label_by_ref.get(ref, ref)
        cell["blogs"][name] = cell["blogs"].get(name, 0) + 1
    return [by_day[k] for k in sorted(by_day)]
