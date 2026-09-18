"""Transactional publication ownership, checkpoints and idempotent receipts.

No external calls belong in these transactions. Unknown external effects never
become retryable solely because a lease expired.
"""
from datetime import datetime, timedelta
import secrets
import re
from urllib.parse import urlparse

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.models.campaign import PublishAttempt, PublishJob

LEASE_SECONDS = 120


class Conflict(ValueError):
    pass


def eligible(now):
    return or_(
        PublishJob.status == "queued",
        and_(PublishJob.status == "failed", PublishJob.next_retry_at <= now,
             PublishJob.attempts < PublishJob.max_attempts),
    )


async def claim(db, job_id, user_id, blog_id, mode="live", now=None):
    now = now or datetime.utcnow()
    token = secrets.token_hex(24)
    changed = await db.execute(update(PublishJob).where(
        PublishJob.id == job_id, PublishJob.user_id == user_id, eligible(now),
    ).values(status="assigned", lock_token=token,
             lock_expires_at=now + timedelta(seconds=LEASE_SECONDS)))
    if changed.rowcount != 1:
        await db.rollback()
        return None
    db.add(PublishAttempt(token=token, job_id=job_id, user_id=user_id,
                          active_blog_id=blog_id, mode=mode, stage="claimed"))
    try:
        await db.commit()
    except IntegrityError:
        # Unique active_blog_id arbitrates different jobs claimed concurrently.
        await db.rollback()
        return None
    return token


async def checkpoint(db, job_id, user_id, token, stage, now=None):
    now = now or datetime.utcnow()
    if not token or stage not in ("heartbeat", "editing", "finalizing"):
        raise Conflict("유효한 잠금과 실행 단계가 필요합니다")
    attempt = await db.get(PublishAttempt, token)
    if not attempt or attempt.job_id != job_id or attempt.user_id != user_id or attempt.result:
        raise Conflict("유효한 실행 시도가 아닙니다")
    if stage == "finalizing" and attempt.mode != "live":
        raise Conflict("시험 실행은 최종 발행할 수 없습니다")
    states = ["assigned", "publishing"] if stage == "heartbeat" else ["assigned"]
    changed = await db.execute(update(PublishJob).where(
        PublishJob.id == job_id, PublishJob.user_id == user_id,
        PublishJob.lock_token == token, PublishJob.status.in_(states),
        PublishJob.lock_expires_at > now,
    ).values(lock_expires_at=now + timedelta(seconds=LEASE_SECONDS),
             **({"status": "publishing"} if stage == "finalizing" else {})))
    if changed.rowcount != 1:
        await db.rollback()
        raise Conflict("잠금이 만료되었거나 작업이 변경되었습니다")
    if stage != "heartbeat":
        attempt.stage = stage
    attempt.updated_at = now
    await db.commit()
    return {"success": True, "lease_seconds": LEASE_SECONDS}


async def result(db, job_id, user_id, token, body, now=None):
    now = now or datetime.utcnow()
    if not token:
        raise Conflict("잠금 토큰이 필요합니다")
    attempt = await db.get(PublishAttempt, token)
    if not attempt or attempt.job_id != job_id or attempt.user_id != user_id:
        raise Conflict("유효한 실행 시도가 아닙니다")
    if attempt.result:
        if attempt.result["request"] != body:
            raise Conflict("이미 기록한 결과와 다른 결과입니다")
        return attempt.result["ack"]
    j = await db.get(PublishJob, job_id)
    if not j or j.user_id != user_id or j.lock_token != token:
        raise Conflict("다른 실행기가 소유한 작업입니다")
    finalizing = attempt.stage == "finalizing" or j.status == "publishing"
    # 이 블로그의 글 주소 + 같은 글 번호가 함께 와야 '주소로 확인된 예약'이다.
    url = urlparse(body.get('url') or '')
    receipt = str(body.get('receipt_id') or '')
    identified = bool(re.fullmatch(r'[0-9]+', receipt)) and url.scheme == 'https' and url.hostname == 'blog.naver.com' and url.path.rstrip('/') == f'/{j.naver_blog_id}/{receipt}'
    release = body.get("release") and not finalizing and not body.get("ok")
    uncertain = bool(body.get("uncertain")) or (finalizing and not body.get("ok"))
    if attempt.mode == "dry_run":
        status = "dry_run"
    elif release:
        status = "queued"
    elif uncertain:
        status = "uncertain"
    elif body.get("ok"):
        # 실행기가 최종 발행 단계(finalizing)를 거쳐 성공 신호(발행 창 닫힘·페이지 이동)를 봤다 → 네이버 예약됨.
        # 글 번호가 있으면 그 주소로, 없으면 예약 시각 뒤 RSS 로 공개를 확인한다(publication_verifier).
        # 번호가 없다고 uncertain 으로 두면 active_blog_id 가 풀리지 않아 그 블로그의 다음 글이 전부 멈춘다
        # (2026-09-11 E2E 재현). 재시도는 하지 않으므로 중복 게시 위험은 늘지 않는다.
        # finalizing 없이 온 성공 보고는 여전히 증거가 없다 → uncertain.
        status = "submitted" if finalizing else "uncertain"
    elif body.get("need_login") or body.get("captcha"):
        status = "queued"
    else:
        status = "failed"
    attempts = (j.attempts or 0) + (0 if release or attempt.mode == "dry_run" else 1)
    retry_at = now + timedelta(minutes=10 * attempts) if status == "failed" and attempts < (j.max_attempts or 3) else None
    if status == "submitted":
        # 확인된 주소만 남긴다(엉뚱한 주소가 남으면 공개 확인이 그 주소만 보다가 영영 못 끝낸다).
        result_url, error = (body.get("url") if identified else None), None
    else:
        result_url = body.get("url")
        error = body.get("message") or ("네이버 예약 목록에서 등록 결과를 확인하세요" if status == "uncertain" else None)
    values = dict(status=status, attempts=attempts, next_retry_at=retry_at,
                  lock_expires_at=None, result_url=result_url, error=error)
    changed = await db.execute(update(PublishJob).where(
        PublishJob.id == job_id, PublishJob.user_id == user_id,
        PublishJob.lock_token == token, PublishJob.status.in_(["assigned", "publishing", "uncertain"]),
    ).values(**values))
    if changed.rowcount != 1:
        await db.rollback()
        attempt = await db.get(PublishAttempt, token, populate_existing=True)
        if attempt and attempt.result and attempt.result["request"] == body:
            return attempt.result["ack"]
        raise Conflict("결과를 적용할 수 없는 작업 상태입니다")
    # Serialize concurrent reports through the job UPDATE, then read the receipt
    # again so a competing report cannot increment attempts twice.
    await db.refresh(attempt)
    if attempt.result:
        recorded = attempt.result
        await db.rollback()
        if recorded["request"] != body:
            raise Conflict("이미 기록한 결과와 다른 결과입니다")
        return recorded["ack"]
    ack = {"success": True, "status": status}
    attempt.result = {"request": body, "ack": ack}
    attempt.stage = "done"
    attempt.updated_at = now
    # Uncertain blocks this profile until explicitly reconciled.
    if status != "uncertain":
        attempt.active_blog_id = None
    await db.commit()
    return ack


async def recover_expired(db, user_id, now=None):
    now = now or datetime.utcnow()
    await db.execute(update(PublishJob).where(
        PublishJob.user_id == user_id, PublishJob.status.in_(["assigned", "publishing"]),
        PublishJob.lock_expires_at <= now,
    ).values(status="uncertain", next_retry_at=None,
             error="실행기 연결이 끊겼습니다. 복구 결과 또는 네이버 예약 목록 확인을 기다립니다"))
    await db.commit()
