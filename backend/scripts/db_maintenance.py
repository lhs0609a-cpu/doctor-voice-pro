"""볼륨을 되찾는다 — 오래된 캐시를 지우고, 파일 크기를 실제로 줄인다.

배경(2026-09-28 실측, fly 라이브):
  /data 볼륨 974MB 중 406MB 사용. 그 대부분이 SQLite 한 파일(405MB)이고,
  내용은 글 분석 캐시 182MB + posts 107MB + 사진 46MB + post_versions 40MB 였다.
  auto_vacuum 이 0 이라 행을 지워도 파일은 영영 줄지 않는다. 그래서 워드 100건을
  두 배치만 넣으면 볼륨이 차고, 차는 순간 SQLite 가 'database or disk is full' 을
  내며 예약뿐 아니라 로그인·API 전체가 멈춘다.

하는 일:
  1) 다시 만들 수 있는 것만 보관 기간대로 지운다(글 분석 캐시·검색 캐시·지수 스냅샷·
     끝난 발행 영수증). 원고·사진·예약은 건드리지 않는다.
  2) 끝난 발행 시도가 안고 있는 payload(사진 base64, 건당 1~2MB)를 비운다.
  3) auto_vacuum 을 incremental 로 바꾼다 → 앞으로는 앱이 스스로 조금씩 되돌려준다.
  4) VACUUM 으로 지금 쌓인 빈 공간을 한 번에 운영체제에 돌려준다.

사용(컨테이너 안에서):
  python scripts/db_maintenance.py --dry-run     # 무엇이 얼마나 지워지는지만 계산
  python scripts/db_maintenance.py               # 정리 + VACUUM
  python scripts/db_maintenance.py --skip-vacuum # 지우기만(여유 공간이 부족할 때)
"""
import argparse
import os
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 보관 기간은 앱과 같은 값을 쓴다(app/services/storage_reclaim.py 가 원본).
try:
    from app.services.storage_reclaim import (
        ATTEMPT_DAYS, POST_CACHE_DAYS, POST_CACHE_MAX_ROWS, SERP_CACHE_DAYS, SNAPSHOT_DAYS,
    )
except Exception:  # noqa: BLE001 — 앱 설정 없이도 돌아야 한다
    POST_CACHE_DAYS, SERP_CACHE_DAYS, SNAPSHOT_DAYS, ATTEMPT_DAYS = 45, 3, 60, 14
    POST_CACHE_MAX_ROWS = 10_000

MB = 1048576

# (표시 이름, 테이블, 시각 컬럼, 보관일, 추가 조건)
PRUNE = (
    ("글 분석 캐시", "blog_post_analysis_cache", "created_at", POST_CACHE_DAYS, ""),
    ("검색 결과 캐시", "blog_serp_cache", "fetched_at", SERP_CACHE_DAYS, ""),
    ("지수 스냅샷", "blog_index_snapshots", "created_at", SNAPSHOT_DAYS, ""),
    ("끝난 발행 영수증", "campaign_publish_attempts", "updated_at", ATTEMPT_DAYS,
     "AND result IS NOT NULL"),
)


def db_file() -> Path:
    url = os.getenv("DATABASE_URL_SYNC") or os.getenv("DATABASE_URL") or "sqlite:///./doctorvoice.db"
    if "sqlite" not in url:
        sys.exit(f"SQLite 전용 스크립트입니다: {url}")
    _, _, tail = url.partition("///")
    return Path(tail.replace("+aiosqlite", ""))


def sizes(path: Path) -> str:
    usage = shutil.disk_usage(path.parent if path.parent.exists() else Path("."))
    return (f"DB {path.stat().st_size / MB:.0f}MB · "
            f"볼륨 {usage.used / MB:.0f}/{usage.total / MB:.0f}MB "
            f"(여유 {usage.free / MB:.0f}MB, {usage.used * 100 / usage.total:.0f}% 사용)")


def top_tables(conn: sqlite3.Connection, n: int = 8) -> None:
    try:
        rows = conn.execute(
            "SELECT name, SUM(pgsize) b FROM dbstat GROUP BY name ORDER BY b DESC LIMIT ?", (n,)
        ).fetchall()
    except sqlite3.Error:
        return
    for name, b in rows:
        print(f"    {(b or 0) / MB:8.1f} MB  {name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="계산만 하고 아무것도 바꾸지 않는다")
    ap.add_argument("--skip-vacuum", action="store_true", help="지우기만 하고 VACUUM 은 하지 않는다")
    args = ap.parse_args()

    path = db_file()
    if not path.exists():
        sys.exit(f"DB 파일이 없습니다: {path}")
    print(f"DB: {path}")
    print(f"  전: {sizes(path)}")
    before_bytes = path.stat().st_size

    conn = sqlite3.connect(str(path), isolation_level=None, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    print("  큰 테이블:")
    top_tables(conn)

    total = 0
    for label, table, column, days, extra in PRUNE:
        where = f"{column} < datetime('now', '-{int(days)} days') {extra}".strip()
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]
        except sqlite3.Error as error:
            print(f"  - {label}: 건너뜀({error})")
            continue
        print(f"  - {label}({table}) {days}일 넘은 행: {n}")
        if n and not args.dry_run:
            # 한 번에 다 지우면 쓰기 잠금을 오래 잡는다 — 2천 행씩 끊는다.
            left = n
            while left > 0:
                cur = conn.execute(
                    f"DELETE FROM {table} WHERE rowid IN "
                    f"(SELECT rowid FROM {table} WHERE {where} LIMIT 2000)")
                if not cur.rowcount:
                    break
                left -= cur.rowcount
            total += n

    # 글 분석 캐시는 행 수로도 묶는다(하루 10MB 씩 늘어난다).
    try:
        rows = conn.execute("SELECT COUNT(*) FROM blog_post_analysis_cache").fetchone()[0]
        over = rows - POST_CACHE_MAX_ROWS
        print(f"  - 글 분석 캐시 상한({POST_CACHE_MAX_ROWS}행) 초과: {max(0, over)}행 / 현재 {rows}행")
        if over > 0 and not args.dry_run:
            conn.execute(
                "DELETE FROM blog_post_analysis_cache WHERE post_url IN "
                "(SELECT post_url FROM blog_post_analysis_cache ORDER BY created_at ASC LIMIT ?)", (over,))
            total += over
    except sqlite3.Error as error:
        print(f"  - 캐시 상한 적용 건너뜀({error})")

    # 끝난 시도가 아직 안고 있는 원고·사진(base64)
    try:
        n, b = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(LENGTH(payload)),0) FROM campaign_publish_attempts "
            "WHERE payload IS NOT NULL AND payload <> 'null' AND result IS NOT NULL").fetchone()
        print(f"  - 끝난 시도의 payload: {n}건 {b / MB:.1f}MB")
        if n and not args.dry_run:
            conn.execute("UPDATE campaign_publish_attempts SET payload=NULL "
                         "WHERE payload IS NOT NULL AND result IS NOT NULL")   # 'null' 문자열도 실제 NULL 로
    except sqlite3.Error as error:
        print(f"  - payload 정리 건너뜀({error})")

    if args.dry_run:
        print("--dry-run: 변경 없이 종료")
        return

    # 앞으로는 앱이 조금씩 되돌려줄 수 있게 한다. 전환은 VACUUM 이 있어야 반영된다.
    mode = conn.execute("PRAGMA auto_vacuum").fetchone()[0]
    if int(mode or 0) != 2:
        # auto_vacuum 전환은 VACUUM 을 거쳐야 파일에 반영된다(SQLite 규칙).
        print(f"  auto_vacuum {mode} → 2(incremental) 로 전환")
        conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
        args.skip_vacuum = False

    if not args.skip_vacuum:
        usage = shutil.disk_usage(path.parent)
        need = path.stat().st_size + 32 * MB           # VACUUM 은 임시로 사본을 만든다
        if usage.free < need:
            print(f"  VACUUM 보류: 여유 {usage.free / MB:.0f}MB < 필요 {need / MB:.0f}MB. "
                  f"볼륨을 늘리고 다시 실행하세요(fly volumes extend).")
        else:
            print("  VACUUM 실행 중…")
            conn.execute("VACUUM")
    print(f"  auto_vacuum={conn.execute('PRAGMA auto_vacuum').fetchone()[0]} "
          f"freelist={conn.execute('PRAGMA freelist_count').fetchone()[0]}")
    conn.close()

    print(f"  후: {sizes(path)}")
    print(f"지운 행 {total}개 · 파일 {(before_bytes - path.stat().st_size) / MB:.0f}MB 회수")


if __name__ == "__main__":
    main()
