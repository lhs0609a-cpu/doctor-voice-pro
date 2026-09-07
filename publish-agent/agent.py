#!/usr/bin/env python
"""닥터보이스 프로 발행 에이전트 — 트레이 없는 CLI 데몬.

서버에서 예약 발행 잡을 가져와(claim) 네이버 SmartEditor ONE 에 '예약발행'으로 등록하고 결과를 보고한다.
네이버 계정(블로그)마다 크롬 프로필을 따로 두어 로그인 세션을 유지한다.

    python agent.py --server http://127.0.0.1:8010 --email me@x.com --password '...' [--blog 라벨|아이디] [--once] [--dry-run]

안전 규칙(절대 깨지 말 것)
- 예약 날짜/시각 설정이 실패하면 ScheduleError → 발행 버튼을 누르지 않고 실패 보고.
- 로그인된 블로그가 기대한 블로그와 다르면 그 블로그의 잡은 손대지 않는다.
- --dry-run 은 최종 발행 클릭만 생략하고 ok=false, uncertain=false, message='dry-run' 으로 보고한다.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import random
import sys
import time
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from plan import parse_schedule, schedule_is_safe, pick_emphasize  # noqa: E402
from server_client import ServerClient, ServerError  # noqa: E402

log = logging.getLogger("agent")
KST = timezone(timedelta(hours=9), "KST")  # 서머타임 없음 → tzdata 불필요

RETRYABLE_BLOG_STATUS = ("active", "login_required", "captcha")


# ---------------------------------------------------------------- 결과
@dataclass
class JobResult:
    ok: bool
    uncertain: bool = False
    message: str = ""
    url: Optional[str] = None
    need_login: bool = False
    captcha: bool = False

    def as_report(self) -> Dict[str, Any]:
        return asdict(self)


def now_kst_naive() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)


# ---------------------------------------------------------------- 로깅
def setup_logging(log_dir: Path, verbose: bool) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)-5s [%(name)s] %(message)s", "%H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(sh)
    fh = logging.FileHandler(log_dir / f"agent-{datetime.now():%Y-%m-%d}.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-5s [%(name)s] %(message)s"))
    root.addHandler(fh)
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # 윈도 콘솔 한글
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------- 블로그 선택
def select_blogs(summary: List[Dict[str, Any]], want: Optional[str]) -> List[Dict[str, Any]]:
    """--blog 가 있으면 라벨/네이버ID/blog_ref_id 일치 1개, 없으면 pending>0 이고 재시도 가능한 상태인 것 전부."""
    if want:
        w = want.strip().lower()
        hit = [b for b in summary if w in {str(b.get("label", "")).lower(), str(b.get("naver_blog_id", "")).lower(), str(b.get("blog_ref_id", "")).lower()}]
        return hit[:1]
    return [b for b in summary if (b.get("pending") or 0) > 0 and (b.get("status") or "active") in RETRYABLE_BLOG_STATUS]


# ---------------------------------------------------------------- 잡 1건
async def run_job(editor: Any, job: Dict[str, Any], *, dry_run: bool, now: Optional[datetime] = None) -> JobResult:
    """에디터(NaverEditor 또는 같은 인터페이스의 대역)로 잡 1건을 처리한다.
    예외 → JobResult 로 변환. 발행 클릭 이후의 예외만 uncertain 으로 올린다."""
    from naver_editor import BlogMismatch, CaptchaDetected, EditorError, LoginRequired, ScheduleError

    title = job.get("title") or ""
    clicked_publish = False
    try:
        # 1) 예약 시각부터 검증 — 화면을 건드리기 전에 걸러낸다
        sched = (job.get("schedule") or {}).get("datetime")
        if (job.get("finalAction") or "schedule") != "schedule":
            return JobResult(ok=False, message=f"지원하지 않는 finalAction '{job.get('finalAction')}' (에이전트는 예약발행만 수행)")
        dt = parse_schedule(sched)
        safe, why = schedule_is_safe(dt, now or now_kst_naive())
        if not safe:
            return JobResult(ok=False, message=why)

        # 2) 글쓰기 페이지 + 계정 확인
        await editor.open_write_page()
        await editor.dismiss_draft_popup()
        expected = (job.get("expectedBlogId") or "").strip().lower()
        current = (await editor.read_blog_id() or "").strip().lower()
        if expected and current and expected != current:
            raise BlogMismatch(f"로그인된 블로그가 다릅니다(예상 '{expected}', 현재 '{current}'). 엉뚱한 블로그에 발행되지 않도록 중단했습니다.")

        # 3) 제목/본문
        await editor.set_title(title)
        blocks = job.get("blocks") or [{"type": "text", "content": job.get("content") or ""}]
        await editor.insert_body_blocks(blocks, pick_emphasize(job.get("emphasize") or []))

        # 4) 발행 레이어: 공개/검색/카테고리/태그
        opts = job.get("options") or {}
        await editor.open_publish_layer()
        await editor.set_open_type(opts.get("openType") or "public")
        if opts.get("search") is False:
            await editor.set_search_allow(False)
        await editor.set_category(opts.get("category"))
        await editor.set_tags(job.get("tags") or [])

        # 5) 예약 시각 — 실패하면 ScheduleError 로 여기서 끝난다(발행 클릭 금지)
        await editor.set_schedule(dt)

        if dry_run:
            log.info("[dry-run] '%s' — 발행 클릭 생략", title[:40])
            return JobResult(ok=False, uncertain=False, message="dry-run")

        # 6) 발행
        clicked_publish = True
        out = await editor.publish()
        if out is None:
            return JobResult(ok=False, message="발행 결과 없음")
        if out.ok:
            return JobResult(ok=True, url=out.url, message=out.message)
        return JobResult(ok=False, uncertain=bool(out.uncertain), message=out.message)

    except ScheduleError as e:
        return JobResult(ok=False, message=f"[예약설정 실패] {e}")
    except BlogMismatch as e:
        return JobResult(ok=False, message=str(e))
    except LoginRequired as e:
        return JobResult(ok=False, need_login=True, message=f"로그인이 풀렸습니다: {e}")
    except CaptchaDetected as e:
        if clicked_publish:
            return JobResult(ok=False, uncertain=True, captcha=True, message=f"발행 클릭 후 캡차: {e}. 네이버 예약 목록에서 확인하세요")
        return JobResult(ok=False, captcha=True, message=f"네이버가 캡차를 요구했습니다: {e}")
    except EditorError as e:
        return JobResult(ok=False, uncertain=clicked_publish, message=str(e))
    except Exception as e:  # noqa: BLE001
        log.error("예상 못한 오류: %s\n%s", e, traceback.format_exc())
        return JobResult(ok=False, uncertain=clicked_publish, message=f"{type(e).__name__}: {e}"[:400])


# ---------------------------------------------------------------- 브라우저
class BrowserPool:
    """블로그(네이버 ID)별 persistent context. 루프를 돌아도 창을 닫지 않아 포커스를 반복해서 뺏지 않는다."""

    def __init__(self, pw, profiles_dir: Path, headless: bool, window_pos: Optional[str]):
        self.pw = pw
        self.profiles_dir = profiles_dir
        self.headless = headless
        self.window_pos = window_pos
        self._ctx: Dict[str, Any] = {}

    async def page_for(self, naver_blog_id: str):
        ctx = self._ctx.get(naver_blog_id)
        if ctx is not None:
            try:
                pages = ctx.pages
                if pages:
                    return pages[0]
                return await ctx.new_page()
            except Exception:  # noqa: BLE001
                self._ctx.pop(naver_blog_id, None)
        ctx = await self._launch(naver_blog_id)
        self._ctx[naver_blog_id] = ctx
        return ctx.pages[0] if ctx.pages else await ctx.new_page()

    async def _launch(self, naver_blog_id: str):
        user_data_dir = self.profiles_dir / naver_blog_id
        user_data_dir.mkdir(parents=True, exist_ok=True)
        args = ["--disable-blink-features=AutomationControlled", "--no-first-run", "--no-default-browser-check"]
        if self.window_pos:
            args.append(f"--window-position={self.window_pos}")
        kw: Dict[str, Any] = dict(
            user_data_dir=str(user_data_dir),
            headless=self.headless,
            viewport={"width": 1280, "height": 900},
            args=args,
            ignore_default_args=["--enable-automation"],
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )
        try:
            ctx = await self.pw.chromium.launch_persistent_context(channel="chrome", **kw)
            log.info("브라우저(chrome 채널) 시작: 프로필 %s", user_data_dir)
        except Exception as e:  # noqa: BLE001
            log.info("chrome 채널 사용 불가(%s) → 번들 Chromium", str(e).splitlines()[0][:80])
            ctx = await self.pw.chromium.launch_persistent_context(**kw)
            log.info("브라우저(Chromium) 시작: 프로필 %s", user_data_dir)
        ctx.set_default_timeout(15000)
        return ctx

    async def close(self, naver_blog_id: Optional[str] = None) -> None:
        keys = [naver_blog_id] if naver_blog_id else list(self._ctx)
        for k in keys:
            ctx = self._ctx.pop(k, None)
            if ctx is not None:
                try:
                    await ctx.close()
                except Exception:  # noqa: BLE001
                    pass


# ---------------------------------------------------------------- 블로그 1개 처리
async def ensure_login(editor: Any, client: ServerClient, blog: Dict[str, Any]) -> Tuple[bool, str]:
    """글쓰기 페이지가 열릴 때까지 로그인 처리. (성공 여부, 사유)"""
    from naver_editor import CaptchaDetected, EditorError, LoginRequired

    ref = blog["blog_ref_id"]
    try:
        await editor.open_write_page()
        return True, ""
    except CaptchaDetected as e:
        client.set_blog_status(ref, "captcha", f"네이버가 캡차를 요구했습니다. 에이전트 브라우저 창에서 직접 풀어 주세요. ({e})")
        return False, str(e)
    except LoginRequired:
        pass
    except EditorError as e:
        return False, str(e)

    # 로그인 페이지 → 저장된 계정으로 1회 자동 로그인
    try:
        cred = client.credential(ref)
    except ServerError as e:
        client.set_blog_status(ref, "login_required", f"계정 정보를 서버에서 읽지 못했습니다: {e.detail}")
        return False, str(e)
    if not cred.get("login_id") or not cred.get("login_pw"):
        client.set_blog_status(ref, "login_required", "저장된 네이버 아이디/비밀번호가 없습니다. 앱에서 계정을 등록하거나 에이전트 브라우저 창에서 직접 로그인하세요.")
        return False, "계정 정보 없음"
    try:
        await editor.try_login(cred["login_id"], cred["login_pw"])
        await editor.open_write_page()
        return True, ""
    except CaptchaDetected as e:
        client.set_blog_status(ref, "captcha", f"로그인 중 캡차/기기 인증이 나타났습니다. 에이전트 브라우저 창에서 직접 한 번 완료해 주세요. ({e})")
        return False, str(e)
    except LoginRequired as e:
        client.set_blog_status(ref, "login_required", f"자동 로그인에 실패했습니다. 에이전트 브라우저 창에서 직접 로그인하세요. ({e})")
        return False, str(e)
    except EditorError as e:
        return False, str(e)


async def process_blog(client: ServerClient, pool: BrowserPool, blog: Dict[str, Any], args: argparse.Namespace) -> None:
    from naver_editor import WRITE_URL, NaverEditor

    label, ref, naver_id = blog.get("label") or blog.get("naver_blog_id"), blog["blog_ref_id"], blog["naver_blog_id"]
    log.info("=== 블로그 '%s' (%s) 대기 %s건, 상태 %s ===", label, naver_id, blog.get("pending"), blog.get("status"))

    page = await pool.page_for(naver_id)
    # DV_WRITE_URL: 테스트용(가짜 에디터 페이지). 평소엔 비워 두면 네이버 글쓰기 URL.
    editor = NaverEditor(page, captcha_wait_sec=args.captcha_wait, write_url=os.environ.get("DV_WRITE_URL") or WRITE_URL)

    ok, why = await ensure_login(editor, client, blog)
    if not ok:
        log.warning("블로그 '%s' 건너뜀: %s", label, why)
        return

    current = (await editor.read_blog_id() or "").lower()
    if current and naver_id and current != naver_id.lower():
        reason = f"로그인된 블로그가 다릅니다(예상 '{naver_id}', 현재 '{current}'). 에이전트 브라우저 창에서 '{naver_id}' 계정으로 다시 로그인하세요."
        client.set_blog_status(ref, "login_required", reason)
        log.warning(reason)
        return
    if (blog.get("status") or "active") != "active":
        log.info("로그인 확인됨 → 블로그 상태를 active 로 복구")
        client.set_blog_status(ref, "active", "에이전트가 로그인을 확인했습니다")

    jobs = client.claim(ref, limit=args.max_per_blog, include_images=not args.no_images)
    log.info("클레임 %d건", len(jobs))
    for i, job in enumerate(jobs):
        if i > 0:
            pause = random.uniform(args.min_gap, args.max_gap)
            log.info("다음 글까지 %.0f초 대기", pause)
            await asyncio.sleep(pause)
        log.info("--- 잡 %s '%s' 예약 %s ---", job.get("id"), (job.get("title") or "")[:40], (job.get("schedule") or {}).get("datetime"))
        result = await run_job(editor, job, dry_run=args.dry_run)
        log.info("결과: ok=%s uncertain=%s need_login=%s captcha=%s — %s", result.ok, result.uncertain, result.need_login, result.captcha, result.message[:200])
        try:
            r = client.report_result(job["id"], job.get("lock_token"), **result.as_report())
            log.info("서버 보고 → 상태 %s", (r or {}).get("status"))
        except ServerError as e:
            log.error("결과 보고 실패(%s). 잠금은 20분 뒤 풀립니다", e)
        if result.need_login or result.captcha:
            log.warning("로그인/캡차 문제 → 이 블로그의 나머지 잡은 다음 주기로 미룹니다")
            break


# ---------------------------------------------------------------- 메인 루프
async def run_once(client: ServerClient, pool: BrowserPool, args: argparse.Namespace) -> int:
    summary = client.summary()
    blogs = select_blogs(summary, args.blog)
    if args.blog and not blogs:
        log.error("--blog '%s' 에 해당하는 블로그가 없습니다. 등록된 블로그: %s", args.blog, ", ".join(f"{b.get('label')}({b.get('naver_blog_id')})" for b in summary) or "없음")
        return 0
    if not blogs:
        log.info("처리할 블로그 없음(대기 잡 0건)")
        return 0
    for b in blogs:
        if args.blog and (b.get("pending") or 0) == 0:
            log.info("블로그 '%s' 대기 잡 0건", b.get("label"))
            continue
        try:
            await process_blog(client, pool, b, args)
        except Exception as e:  # noqa: BLE001
            log.error("블로그 '%s' 처리 중 오류: %s\n%s", b.get("label"), e, traceback.format_exc())
            await pool.close(b["naver_blog_id"])
    return len(blogs)


async def main_async(args: argparse.Namespace) -> int:
    from playwright.async_api import async_playwright

    client = ServerClient(args.server)
    try:
        client.login(args.email, args.password)
    except Exception as e:  # noqa: BLE001
        log.error("서버 로그인 실패: %s", e)
        return 2
    log.info("서버 로그인 OK: %s", args.server)

    profiles_dir = Path(args.profiles_dir).resolve()
    async with async_playwright() as pw:
        pool = BrowserPool(pw, profiles_dir, headless=args.headless, window_pos=args.window_pos)
        try:
            while True:
                started = time.monotonic()
                try:
                    await run_once(client, pool, args)
                except ServerError as e:
                    log.error("서버 오류: %s", e)
                except Exception as e:  # noqa: BLE001
                    log.error("주기 실행 오류: %s\n%s", e, traceback.format_exc())
                if args.once:
                    break
                wait = max(5.0, args.interval - (time.monotonic() - started))
                log.info("다음 확인까지 %.0f초 대기 (Ctrl+C 로 종료)", wait)
                await asyncio.sleep(wait)
        finally:
            await pool.close()
            client.close()
    return 0


def parse_bool(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="닥터보이스 프로 네이버 예약발행 에이전트")
    p.add_argument("--server", default=os.environ.get("DV_SERVER", "http://127.0.0.1:8010"))
    p.add_argument("--email", default=os.environ.get("DV_EMAIL"), required=not os.environ.get("DV_EMAIL"))
    p.add_argument("--password", default=os.environ.get("DV_PASSWORD"), required=not os.environ.get("DV_PASSWORD"))
    p.add_argument("--blog", help="라벨 또는 네이버 블로그 ID. 지정하면 그 블로그만")
    p.add_argument("--once", action="store_true", help="한 번만 돌고 종료")
    p.add_argument("--dry-run", action="store_true", help="최종 발행 클릭만 생략(ok=false, message='dry-run' 으로 보고)")
    p.add_argument("--headless", type=parse_bool, default=False, help="true/false (기본 false — 로그인·캡차를 사람이 볼 수 있어야 함)")
    p.add_argument("--profiles-dir", default=str(HERE / "profiles"))
    p.add_argument("--log-dir", default=str(HERE / "logs"))
    p.add_argument("--interval", type=int, default=300, help="루프 주기(초)")
    p.add_argument("--max-per-blog", type=int, default=5, help="한 주기에 블로그당 최대 발행 수")
    p.add_argument("--min-gap", type=int, default=20, help="글 사이 최소 대기(초)")
    p.add_argument("--max-gap", type=int, default=60, help="글 사이 최대 대기(초)")
    p.add_argument("--captcha-wait", type=int, default=180, help="발행 단계 캡차를 사람이 풀 때까지 기다리는 시간(초)")
    p.add_argument("--no-images", action="store_true", help="사진 없이(서버 include_images=false)")
    p.add_argument("--window-pos", help="브라우저 창 위치 'x,y' (예: 2000,0 — 보조 모니터/화면 밖으로 밀어 방해 최소화)")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(Path(args.log_dir), args.verbose)
    log.info("발행 에이전트 시작 (dry-run=%s, once=%s, headless=%s)", args.dry_run, args.once, args.headless)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    try:
        return asyncio.run(main_async(args))
    except KeyboardInterrupt:
        log.info("종료(Ctrl+C)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
