"""Confirm accessible posts after their scheduled time, without republishing.

두 갈래로 확인한다.
- 글 주소가 있는 '네이버 예약됨': 그 글 페이지(PostView)가 공개로 열리는지.
- 글 주소가 없는 '네이버 예약됨'(실행기가 성공 신호만 봤거나, 사람이 '있어요'로 대조한 글):
  예약 시각이 지나면 블로그 RSS 에서 같은 제목의 글을 찾아 주소를 채운다. 공개 글만 RSS 에 나오므로
  비공개·이웃공개 글은 건너뛴다. GRACE_HOURS 가 지나도 없으면 사람이 보도록 '확인 필요'로 돌린다
  (이때는 실행 시도가 이미 끝나 있어 블로그를 막지 않는다).
"""
import html
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select, update
from app.models.campaign import PublishJob
from app.services.schedule_engine import kst_now

GRACE_HOURS = 12          # 예약 시각 뒤 이만큼 지나도 RSS 에 없으면 사람에게 넘긴다
RECHECK_MINUTES = 10      # 주소 없는 글은 이 간격으로만 RSS 를 다시 본다


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
        for job_id, title, scheduled_at in jobs:
            found = rss_match(feed.get("items"), blog_id, title) if feed.get("ok") else None
            if found:
                values = dict(status='published', result_url=found, published_at=datetime.utcnow(), error=None)
            elif overdue(scheduled_at, now_kst):
                values = dict(status='uncertain', error=f'예약 시각이 {GRACE_HOURS}시간 지났는데 블로그에서 이 글을 찾지 못했습니다. 네이버 블로그에서 확인해 주세요')
            else:
                values = dict(updated_at=datetime.utcnow())
            await db.execute(update(PublishJob).where(PublishJob.id == job_id, PublishJob.status == 'submitted').values(**values))
        await db.commit()
