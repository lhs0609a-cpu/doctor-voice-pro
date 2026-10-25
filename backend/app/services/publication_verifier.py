"""Confirm accessible posts after their scheduled time, without republishing.

두 갈래로 확인한다.
- 글 주소가 있는 '네이버 예약됨': 그 글 페이지(PostView)가 공개로 열리는지.
- 글 주소가 없는 '네이버 예약됨'(실행기가 성공 신호만 봤거나, 사람이 '있어요'로 대조한 글):
  예약 시각이 지나면 블로그 RSS 에서 같은 제목의 글을 찾아 주소를 채운다. 공개 글만 RSS 에 나오므로
  비공개·이웃공개 글은 건너뛴다. GRACE_HOURS 가 지나도 없으면 사람이 보도록 '확인 필요'로 돌린다
  (이때는 실행 시도가 이미 끝나 있어 블로그를 막지 않는다).
"""
import html
import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select, update
from app.models.campaign import PublishJob
from app.services.schedule_engine import kst_now

GRACE_HOURS = 12          # 예약 시각 뒤 이만큼 지나도 RSS 에 없으면 사람에게 넘긴다
RECHECK_MINUTES = 10      # 주소 없는 글은 이 간격으로만 RSS 를 다시 본다
MATCH_TOLERANCE_MIN = 3   # 예약 시각과 이만큼 안에 올라간 글이면 같은 글로 본다(예약은 10분 격자)

logger = logging.getLogger(__name__)


def public_evidence(html_text, blog_id, post_id, expected_title=None):
    soup = BeautifulSoup(html_text, 'html.parser')
    meta = soup.find('meta', attrs={'property': 'og:url'})
    title = soup.find('meta', attrs={'property': 'og:title'})
    if not meta or not title or not title.get('content'):
        return False
    if not soup.select_one('.se-main-container, #postViewArea, .post-view'):
        return False
    if expected_title and expected_title.strip() not in title.get('content', ''):
        return False
    url = urlparse(meta.get('content', ''))
    return url.scheme == 'https' and url.hostname == 'blog.naver.com' and url.path.rstrip('/') == f'/{blog_id}/{post_id}'


def _norm_title(value):
    return re.sub(r"\s+", "", html.unescape(value or "")).lower()


def rss_match(items, blog_id, title):
    """RSS 항목 중 같은 제목의 글 → 'https://blog.naver.com/{blog_id}/{글번호}', 없으면 None."""
    want = _norm_title(title)
    if not want:
        return None
    for item in items or []:
        post_no = str(item.get("post_no") or "")
        if re.fullmatch(r"[0-9]+", post_no) and _norm_title(item.get("title")) == want:
            return f"https://blog.naver.com/{blog_id}/{post_no}"
    return None


def _pub_kst(value):
    """RSS pub_date(ISO) → KST naive. 못 읽으면 None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone(timedelta(hours=9))).replace(tzinfo=None)
    return dt


def rss_match_by_time(items, blog_id, scheduled_at, taken=()):
    """예약한 **시각**에 올라간 글을 찾는다 — 제목이 바뀌어 있어도 찾아낸다.

    2026-10-25 실측: '확인 필요' 93건을 블로그 RSS 와 대조하니 49건은 글이 예약 시각에
    분 단위까지 정확히 올라가 있었고 **제목만 달랐다**. 운영자가 올리기 전에 제목을 손으로
    고치기 때문이다(예: '잠실산후보약을 알아보시는 분들께' → '성남잠실산후보약 알아보시는 분들께').
    제목 완전일치로만 찾던 탓에 멀쩡한 글이 전부 '확인 필요'로 떨어졌고, 그러면 원고까지
    잠겨 사람이 손도 못 댔다.

    예약은 10분 격자라 ±MATCH_TOLERANCE_MIN 분이면 옆 글과 겹치지 않는다."""
    if not scheduled_at:
        return None
    for item in items or []:
        post_no = str(item.get("post_no") or "")
        if not re.fullmatch(r"[0-9]+", post_no) or post_no in taken:
            continue
        when = _pub_kst(item.get("pub_date"))
        if when and abs((when - scheduled_at).total_seconds()) <= MATCH_TOLERANCE_MIN * 60:
            return f"https://blog.naver.com/{blog_id}/{post_no}"
    return None


def overdue(scheduled_at, now):
    return now >= scheduled_at + timedelta(hours=GRACE_HOURS)


async def _verify_by_url(db, client, job_id, blog_id, result_url, title):
    url = urlparse(result_url or '')
    match = re.fullmatch(r'/([a-zA-Z0-9_-]+)/([0-9]+)/?', url.path)
    if not match or match.group(1) != blog_id or url.scheme != 'https' or url.hostname != 'blog.naver.com':
        return
    try:
        response = await client.get('https://blog.naver.com/PostView.naver',
                                    params={'blogId': blog_id, 'logNo': match.group(2)})
    except httpx.HTTPError:
        return
    if response.status_code == 200 and public_evidence(response.text, blog_id, match.group(2), title):
        await db.execute(update(PublishJob).where(PublishJob.id == job_id, PublishJob.status == 'submitted').values(status='published', published_at=datetime.utcnow()))
    else:
        await db.execute(update(PublishJob).where(PublishJob.id == job_id, PublishJob.status == 'submitted').values(updated_at=datetime.utcnow()))
    await db.commit()


RECHECK_UNCERTAIN_HOURS = 6   # '확인 필요'로 넘긴 글을 이 간격으로 다시 들여다본다
UNCERTAIN_BATCH = 40


async def recheck_uncertain(db):
    """'확인 필요'로 넘긴 글을 **예약 시각**으로 다시 찾아 되살린다.

    제목만 보고 넘기던 시절에 쌓인 것들이 있다(2026-10-25 기준 93건 중 49건이 멀쩡히
    올라가 있었다). 되살리면 상태만 바뀌는 게 아니라 **원고 잠금도 풀린다** —
    uncertain 인 동안에는 `PUT /drafts/{id}` 가 409 라 사람이 손도 못 댔다.

    되찾지 못한 것은 그대로 둔다(그건 진짜로 안 올라간 글이다). 반환: 되살린 수."""
    now_utc = datetime.utcnow()
    stale_before = now_utc - timedelta(hours=RECHECK_UNCERTAIN_HOURS)
    rows = (await db.execute(select(PublishJob).where(
        PublishJob.status == 'uncertain',
        PublishJob.naver_blog_id.isnot(None),
        (PublishJob.open_type.is_(None)) | (PublishJob.open_type == 'public'),
        (PublishJob.updated_at.is_(None)) | (PublishJob.updated_at <= stale_before),
    ).order_by(PublishJob.updated_at).limit(UNCERTAIN_BATCH))).scalars().all()
    if not rows:
        return 0

    from app.models.campaign import Draft
    by_blog = {}
    for j in rows:
        draft = await db.get(Draft, j.draft_id)
        by_blog.setdefault(j.naver_blog_id, []).append((j.id, draft.title if draft else None, j.scheduled_at))
    await db.commit()

    from app.blogindex.collectors import fetch_rss
    revived = 0
    for blog_id, jobs in by_blog.items():
        feed = await fetch_rss(blog_id)
        items = feed.get("items") if feed.get("ok") else None
        if not items:
            continue
        taken = set()
        for job_id, title, scheduled_at in jobs:
            found = rss_match(items, blog_id, title) or rss_match_by_time(items, blog_id, scheduled_at, taken)
            if not found:
                # 다음 주기에 또 같은 것부터 보지 않도록 본 시각만 적는다.
                await db.execute(update(PublishJob).where(PublishJob.id == job_id).values(updated_at=now_utc))
                continue
            taken.add(found.rsplit('/', 1)[-1])
            changed = await db.execute(update(PublishJob).where(
                PublishJob.id == job_id, PublishJob.status == 'uncertain',
            ).values(status='published', result_url=found, published_at=now_utc, error=None))
            revived += int(changed.rowcount or 0)
        await db.commit()
    if revived:
        logger.info('[발행확인] 확인 필요였던 글 %d편을 예약 시각으로 다시 찾아 되살렸습니다', revived)
    return revived


async def verify_due(db):
    now_kst, now_utc = kst_now(), datetime.utcnow()
    rows = (await db.execute(select(PublishJob).where(
        PublishJob.status == 'submitted', PublishJob.scheduled_at <= now_kst,
    ).order_by(PublishJob.updated_at).limit(20))).scalars().all()
    # Release the read transaction before network I/O.
    from app.models.campaign import Draft
    by_url, by_rss = [], {}
    for j in rows:
        draft = await db.get(Draft, j.draft_id)
        title = draft.title if draft else None
        if j.result_url:
            by_url.append((j.id, j.naver_blog_id, j.result_url, title))
        elif (j.open_type or 'public') == 'public' and j.naver_blog_id and title \
                and (not j.updated_at or j.updated_at <= now_utc - timedelta(minutes=RECHECK_MINUTES)):
            by_rss.setdefault(j.naver_blog_id, []).append((j.id, title, j.scheduled_at))
    await db.commit()

    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
        for job_id, blog_id, result_url, title in by_url:
            await _verify_by_url(db, client, job_id, blog_id, result_url, title)

    if not by_rss:
        return
    from app.blogindex.collectors import fetch_rss
    for blog_id, jobs in by_rss.items():
        feed = await fetch_rss(blog_id)
        items = feed.get("items") if feed.get("ok") else None
        taken = set()           # 한 RSS 글을 두 예약이 나눠 갖지 않게 한다
        for job_id, title, scheduled_at in jobs:
            found = rss_match(items, blog_id, title)
            if not found:
                # 제목이 안 맞는다고 '확인 필요'로 넘기기 전에 **예약 시각**으로 한 번 더 찾는다.
                # 운영자가 올리기 전에 제목을 손보는 일이 흔하고, 그때도 글은 예약한 시각에
                # 정확히 올라가 있다(2026-10-25 실측 49건).
                found = rss_match_by_time(items, blog_id, scheduled_at, taken)
            if found:
                taken.add(found.rsplit('/', 1)[-1])
                values = dict(status='published', result_url=found, published_at=datetime.utcnow(), error=None)
            elif overdue(scheduled_at, now_kst):
                values = dict(status='uncertain', error=f'예약 시각이 {GRACE_HOURS}시간 지났는데 블로그에서 이 글을 찾지 못했습니다. 네이버 블로그에서 확인해 주세요')
            else:
                values = dict(updated_at=datetime.utcnow())
            await db.execute(update(PublishJob).where(PublishJob.id == job_id, PublishJob.status == 'submitted').values(**values))
        await db.commit()
