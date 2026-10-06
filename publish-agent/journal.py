"""Local durable checkpoints and result outbox; never stores browser credentials."""
import json
import logging
import sqlite3
from pathlib import Path

log = logging.getLogger("journal")

# 이 상태로 거절당한 보고는 **다음에 다시 올리면 된다** — 인증이 끊겼거나(401/403),
# 서버가 잠깐 밀어낸 것(408/425/429)뿐이다. 나머지 4xx 는 아무리 다시 보내도 같은 답이 온다.
RETRY_LATER = (401, 403, 408, 425, 429)


class Journal:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # One owner per profiles directory; another process must not recover a
        # journal whose writer is still actively working.
        self.lock = open(Path(path).parent / '.agent.lock', 'a+b')
        try:
            import os
            self.lock.seek(0)
            if os.name == 'nt':
                import msvcrt
                if self.lock.read(1) == b'':
                    self.lock.write(b'0')
                    self.lock.flush()
                self.lock.seek(0)
                msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock.close()
            raise RuntimeError('이 프로필 폴더에서 다른 실행기가 이미 동작 중입니다')
        self.db = sqlite3.connect(str(path))
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS attempts (token TEXT PRIMARY KEY, job_id TEXT NOT NULL, stage TEXT NOT NULL, report TEXT)")
        self.db.commit()

    def start(self, job):
        with self.db:
            self.db.execute("INSERT INTO attempts VALUES (?, ?, 'editing', NULL)", (job['lock_token'], job['id']))

    def finalizing(self, token):
        with self.db:
            self.db.execute("UPDATE attempts SET stage='finalizing' WHERE token=?", (token,))

    def save_result(self, token, report):
        with self.db:
            self.db.execute("UPDATE attempts SET report=? WHERE token=?", (json.dumps(report, ensure_ascii=False), token))

    def pending(self):
        return list(self.db.execute("SELECT token, job_id, stage, report FROM attempts ORDER BY rowid"))

    def acknowledge(self, token):
        with self.db:
            self.db.execute("DELETE FROM attempts WHERE token=?", (token,))

    def close(self):
        self.db.close()
        self.lock.close()


async def flush(journal, client):
    """Persist recovery decisions before transport. A failed ACK never retypes.

    **여기서 난 예외는 바퀴 하나를 통째로 삼킨다.** flush 는 run_once 의 첫 줄이라, 못 올리는
    기록이 하나 끼면 그 뒤의 블로그도 카페도 한 건도 돌지 않는다 — 그런데 바깥 루프는 계속
    돌아서 화면에는 '자동 발행 실행 중' 초록불만 켜져 있다. 저널은 계정이 아니라 **PC** 에
    붙어 있으므로 계정을 바꿔도, 블로그를 바꿔도 똑같이 막힌다(2026-10-06 사용자 신고:
    "HTTP 409: 결과를 적용할 수 없는 작업 상태입니다 … 임시저장/예약발행이 걸리지 않습니다").
    그래서 보고에 실패해도 바퀴는 굴러가야 하고, 영영 받아 주지 않을 기록은 버려야 한다."""
    import asyncio
    import inspect
    from server_client import ServerError
    # 이 기록은 디스크에 남아 다음 실행(다른 버전일 수 있다)이 읽는다. 보고 함수가 모르는
    # 칸이 하나 섞여 있으면 TypeError 로 보고 자체가 영영 실패한다 — 아는 칸만 보낸다.
    params = inspect.signature(client.report_result).parameters.values()
    known = (None if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params)
             else {p.name for p in params})
    for token, job_id, stage, serialized in journal.pending():
        report = json.loads(serialized) if serialized else {
            'ok': False, 'uncertain': stage == 'finalizing',
            'release': stage != 'finalizing', 'message': '실행기 재시작 후 복구',
        }
        journal.save_result(token, report)
        payload = report if known is None else {k: v for k, v in report.items() if k in known}
        try:
            await asyncio.to_thread(client.report_result, job_id, token, **payload)
        except ServerError as error:
            if error.status in (401, 403):
                raise                      # 인증이 끊겼다 — 바깥 루프가 멈추고 다시 연결하라고 알린다
            if error.status in RETRY_LATER or error.status >= 500:
                log.warning("결과 보고를 미룹니다(글 %s): %s — 다음 확인 때 다시 올립니다", job_id, error.detail)
                return                     # 기록은 쥔 채로. 나머지 일은 그대로 진행한다
            # 400·404·409 … 서버가 이 결과를 **영영** 받지 않는다. 잠금이 이미 풀렸거나,
            # 사용자가 '다시 시도'를 눌러 그 건이 대기로 돌아갔거나, 다른 PC 가 가져갔다.
            # 버려도 잃는 것은 없다 — 잠금이 풀린 건은 서버가 이미 '확인 필요'로 두고 사람을
            # 기다린다. 쥐고 있으면 매 바퀴 같은 자리에서 멈출 뿐이다.
            log.warning("서버가 받지 않는 기록을 버립니다(글 %s): %s. "
                        "그 글은 네이버 예약 목록과 대조해 처리하세요", job_id, error.detail)
            journal.acknowledge(token)
            continue
        except Exception as error:  # noqa: BLE001
            log.warning("결과 보고 중 연결 문제(글 %s): %s — 다음 확인 때 다시 올립니다", job_id, error)
            return                         # 네트워크가 끊겼을 뿐이다. 기록은 남긴다
        journal.acknowledge(token)
