"""카페 일감의 잠금과 영수증. 블로그(publish_protocol)와 **모양은 같고 코드는 다르다**.

왜 따로 두는가(2026-09-30 사용자 결정)
    블로그 잠금은 운영 사고를 거치며 다듬은 것이다 — '결과를 모르는 발행 하나가 그 블로그를
    멈춘다', '같은 영수증을 두 건이 가져가면 믿지 않는다' 같은 규칙은 실제로 글을 잃고 나서
    얻은 것이다. 카페를 끼워 넣으려고 그 코드를 일반화하면 그 규칙들이 흔들린다.
    잠금 단위도 다르다 — 블로그는 '블로그 하나', 카페는 '계정 하나'다.

지키는 것은 블로그와 같다.
    · 하나의 일감은 한 실행기만 가져간다(UPDATE 의 rowcount 로 판정).
    · 결과를 모르는 채 잠금이 풀리면 'uncertain' 이다. 다시 올리지 않는다 —
      카페에 같은 글이 두 번 올라가면 그 계정은 바로 광고로 찍힌다.
    · 같은 결과를 두 번 보고해도 한 번만 반영된다.
"""
from datetime import datetime, timedelta
import secrets

from sqlalchemy import and_, or_, update
from sqlalchemy.exc import IntegrityError

from app.models.cafe_job import CafeJob

LEASE_SECONDS = 180          # 카페는 글쓰기 화면이 느려 블로그(120초)보다 넉넉히 준다


class Conflict(ValueError):
    pass


def eligible(now):
    """지금 가져갈 수 있는 일감인가. 예약 시각이 지났고, 대기 중이거나 재시도 차례다."""
    return and_(
        CafeJob.scheduled_at <= now,
        or_(CafeJob.status == "queued",
            and_(CafeJob.status == "failed", CafeJob.next_retry_at <= now,
                 CafeJob.attempts < CafeJob.max_attempts)),
    )


async def claim(db, job_id, user_id, account_id, now=None):
    """→ lock_token. 이미 남이 가져갔거나 그 계정이 바쁘면 None."""
    now = now or datetime.utcnow()
    token = secrets.token_hex(24)
    try:
        changed = await db.execute(update(CafeJob).where(
            CafeJob.id == job_id, CafeJob.user_id == user_id, eligible(now),
        ).values(status="assigned", lock_token=token, busy_account_id=account_id,
                 lock_expires_at=now + timedelta(seconds=LEASE_SECONDS)))
        if changed.rowcount != 1:
            await db.rollback()
            return None
        await db.commit()
    except IntegrityError:
        # busy_account_id 유니크 — 그 계정이 이미 다른 일감을 쥐고 있다(확인 안 된 글 포함).
        # SQLite 는 커밋이 아니라 UPDATE 그 자리에서 걸린다. 둘 다 여기서 받는다.
        await db.rollback()
        return None
    return token


async def checkpoint(db, job_id, user_id, token, stage="heartbeat", now=None):
    """실행기가 살아 있다고 알린다. 'posting' 은 등록 버튼을 누르기 직전이다."""
    now = now or datetime.utcnow()
    if not token or stage not in ("heartbeat", "posting"):
        raise Conflict("유효한 잠금과 단계가 필요합니다")
    states = ["assigned", "posting"] if stage == "heartbeat" else ["assigned"]
    changed = await db.execute(update(CafeJob).where(
        CafeJob.id == job_id, CafeJob.user_id == user_id, CafeJob.lock_token == token,
        CafeJob.status.in_(states), CafeJob.lock_expires_at > now,
    ).values(lock_expires_at=now + timedelta(seconds=LEASE_SECONDS),
             **({"status": "posting"} if stage == "posting" else {})))
    if changed.rowcount != 1:
        await db.rollback()
        raise Conflict("잠금이 만료되었거나 작업이 변경되었습니다")
    await db.commit()
    return {"success": True, "lease_seconds": LEASE_SECONDS}


async def result(db, job_id, user_id, token, body, now=None):
    """실행기의 보고를 받는다. 같은 보고를 두 번 해도 한 번만 반영된다."""
    now = now or datetime.utcnow()
    if not token:
        raise Conflict("잠금 토큰이 필요합니다")
    job = await db.get(CafeJob, job_id)
    if not job or job.user_id != user_id:
        raise Conflict("유효한 작업이 아닙니다")
    if job.lock_token != token:
        # 이미 끝난 일감에 같은 결과를 다시 보고한 경우는 조용히 받아 준다.
        if job.status in ("submitted", "uncertain", "failed", "cancelled"):
            return {"success": True, "status": job.status}
        raise Conflict("다른 실행기가 소유한 작업입니다")

    posting = job.status == "posting"
    if body.get("ok"):
        # 등록 버튼까지 누르고 성공 신호를 봤다. 글 주소가 있으면 그것이 증거다.
        status = "submitted" if posting else "uncertain"
    elif body.get("uncertain") or posting:
        # 등록을 누른 뒤에 끊긴 것은 '모른다'이다. 다시 올리면 같은 글이 두 번 올라간다.
        status = "uncertain"
    elif body.get("release"):
        status = "queued"          # 시작도 못 했다(확장 미연결 등) — 시도 횟수를 쓰지 않는다
    else:
        status = "failed"

    attempts = (job.attempts or 0) + (0 if status == "queued" else 1)
    retry_at = (now + timedelta(minutes=15 * attempts)
                if status == "failed" and attempts < (job.max_attempts or 3) else None)
    error = body.get("message") or ("카페에 올라갔는지 직접 확인해 주세요" if status == "uncertain" else None)
    changed = await db.execute(update(CafeJob).where(
        CafeJob.id == job_id, CafeJob.user_id == user_id, CafeJob.lock_token == token,
    ).values(status=status, attempts=attempts, next_retry_at=retry_at,
             lock_expires_at=None, lock_token=None,
             # 'uncertain' 은 사람이 확인할 때까지 그 계정을 붙잡는다 — 같은 계정으로 또
             # 올리다가 같은 글이 두 번 올라가는 것을 막는다.
             busy_account_id=job.account_id if status == "uncertain" else None,
             result_url=body.get("url"), error=error))
    if changed.rowcount != 1:
        await db.rollback()
        raise Conflict("결과를 적용할 수 없는 작업 상태입니다")
    await db.commit()
    return {"success": True, "status": status}


async def recover_expired(db, user_id, now=None):
    """잠금만 풀리고 결과가 오지 않은 일감. 올라갔는지 모르므로 'uncertain' 이다."""
    now = now or datetime.utcnow()
    await db.execute(update(CafeJob).where(
        CafeJob.user_id == user_id, CafeJob.status.in_(["assigned", "posting"]),
        CafeJob.lock_expires_at <= now,
    ).values(status="uncertain", lock_token=None, lock_expires_at=None, next_retry_at=None,
             error="실행기 연결이 끊겼습니다. 카페에 올라갔는지 확인해 주세요"))
    await db.commit()
