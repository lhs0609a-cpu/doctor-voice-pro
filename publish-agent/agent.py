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


def stopping(args):
    event = getattr(args, 'stop_event', None)
    return bool(event and event.is_set())


async def interruptible_pause(seconds, args):
    deadline = time.monotonic() + seconds
    while not stopping(args) and time.monotonic() < deadline:
        await asyncio.sleep(min(1, max(0, deadline - time.monotonic())))


# ---------------------------------------------------------------- 결과
@dataclass
class JobResult:
    ok: bool
    uncertain: bool = False
    message: str = ""
    url: Optional[str] = None
    need_login: bool = False
    captcha: bool = False
    receipt_id: Optional[str] = None

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
async def run_job(editor: Any, job: Dict[str, Any], *, dry_run: bool, now: Optional[datetime] = None, before_publish=None) -> JobResult:
    """에디터(NaverEditor 또는 같은 인터페이스의 대역)로 잡 1건을 처리한다.
    예외 → JobResult 로 변환. 발행 클릭 이후의 예외만 uncertain 으로 올린다."""
    from naver_editor import BlogMismatch, CaptchaDetected, EditorError, LoginRequired, ScheduleError

    title = job.get("title") or ""
    clicked_publish = False
    try:
        # 1) 예약 시각부터 검증 — 화면을 건드리기 전에 걸러낸다
        action = job.get("finalAction") or "schedule"
        if action not in ("schedule", "publish", "draft"):
            return JobResult(ok=False, message=f"지원하지 않는 finalAction '{action}'")
        dt = None
        if action == "schedule":
            dt = parse_schedule((job.get("schedule") or {}).get("datetime"))
            safe, why = schedule_is_safe(dt, now or now_kst_naive())
            if not safe:
                return JobResult(ok=False, message=why)

        # 2) 글쓰기 페이지 + 계정 확인
        await editor.open_write_page()
        await editor.dismiss_draft_popup()
        expected = (job.get("expectedBlogId") or "").strip().lower()
        current = (await editor.read_blog_id() or "").strip().lower()
        if not expected or not current:
            raise BlogMismatch("발행 대상 또는 로그인된 블로그 ID를 확인하지 못했습니다. 계정을 확인한 뒤 다시 시도하세요.")
        if expected != current:
            raise BlogMismatch(f"로그인된 블로그가 다릅니다(예상 '{expected}', 현재 '{current}'). 엉뚱한 블로그에 발행되지 않도록 중단했습니다.")

        # 3) 제목/본문
        await editor.set_title(title)
        blocks = job.get("blocks") or [{"type": "text", "content": job.get("content") or ""}]
        # 워드에서 올라온 원고는 서버가 reformat=False 로 내린다 — 글쓴이 줄바꿈을 다시 자르지 않는다.
        reformat = (job.get("options") or {}).get("reformat", True)
        await editor.insert_body_blocks(blocks, pick_emphasize(job.get("emphasize") or []), reformat=bool(reformat))

        # 4) 임시저장은 발행 레이어를 열지 않는다 — 글만 저장하고 끝낸다.
        opts = job.get("options") or {}
        if opts.get('requiredLinks'):
            await editor.verify_links(opts['requiredLinks'])
        if action == "draft":
            if dry_run:
                log.info("[dry-run] '%s' — 임시저장 클릭 생략", title[:40])
                return JobResult(ok=False, uncertain=False, message="dry-run")
            clicked_publish = True
            out = await editor.save_draft()
            if out is None or not out.ok:
                return JobResult(ok=False, uncertain=True, message=(out.message if out else "임시저장 결과 없음"))
            return JobResult(ok=True, message=out.message)

        # 5) 발행 레이어: 공개/검색/카테고리/태그
        await editor.open_publish_layer()
        await editor.set_open_type(opts.get("openType") or "public")
        if opts.get("search") is False:
            await editor.set_search_allow(False)
        await editor.set_category(opts.get("category"))
        await editor.set_tags(job.get("tags") or [])

        # 6) 시각 — 예약은 실패하면 ScheduleError 로 여기서 끝난다(발행 클릭 금지).
        #    즉시 발행도 '현재' 라디오를 확실히 켜 둔다. 남아 있던 예약값으로 나가면 안 된다.
        if action == "schedule":
            await editor.set_schedule(dt)
        else:
            await editor.set_publish_now()

        if dry_run:
            log.info("[dry-run] '%s' — 발행 클릭 생략", title[:40])
            return JobResult(ok=False, uncertain=False, message="dry-run")

        # 7) 발행
        if action == "schedule":
            safe, why = schedule_is_safe(dt, now or now_kst_naive())
            if not safe:
                raise ScheduleError(why)
        if (await editor.read_blog_id() or "").strip().lower() != expected:
            raise BlogMismatch("발행 직전 계정 확인에 실패했습니다")
        if before_publish:
            await before_publish()
        clicked_publish = True
        out = await editor.publish()
        if out is None:
            return JobResult(ok=False, uncertain=True, message="발행 결과 없음 — 네이버 예약 목록 확인 필요")
        if out.ok and not out.uncertain:
            from urllib.parse import urlparse
            parsed = urlparse(out.url or '')
            import re
            match = re.fullmatch(rf"/{re.escape(expected)}/([0-9]+)/?", parsed.path)
            receipt_id = match.group(1) if parsed.scheme == 'https' and parsed.hostname == 'blog.naver.com' and match else None
            return JobResult(ok=True, url=out.url, message=out.message, receipt_id=receipt_id)
        return JobResult(ok=False, uncertain=bool(out.uncertain), message=out.message)

    except ScheduleError as e:
        return JobResult(ok=False, uncertain=clicked_publish, message=f"[예약설정 실패] {e}")
    except BlogMismatch as e:
        return JobResult(ok=False, uncertain=clicked_publish, message=str(e))
    except LoginRequired as e:
        return JobResult(ok=False, uncertain=clicked_publish, need_login=True, message=f"로그인이 풀렸습니다: {e}")
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
def _proxy_option(raw: str) -> Dict[str, Any]:
    """'http://id:pw@host:port' → Playwright 의 proxy 옵션.

    아이디·비밀번호는 주소에서 떼어 따로 넘긴다. 주소에 박아 두면 크롬이 그것을 무시하고
    인증 창을 띄우는데, 실행기는 그 창에 답할 사람이 없어 거기서 멈춘다."""
    from urllib.parse import urlparse, unquote
    parsed = urlparse(raw if "://" in raw else "http://" + raw)
    server = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        server += f":{parsed.port}"
    option: Dict[str, Any] = {"server": server}
    if parsed.username:
        option["username"] = unquote(parsed.username)
    if parsed.password:
        option["password"] = unquote(parsed.password)
    return option


class BrowserPool:
    """블로그(네이버 ID)별 persistent context. 루프를 돌아도 창을 닫지 않아 포커스를 반복해서 뺏지 않는다."""

    def __init__(self, pw, profiles_dir: Path, headless: bool, window_pos: Optional[str]):
        self.pw = pw
        self.profiles_dir = profiles_dir
        self.headless = headless
        self.window_pos = window_pos
        self._ctx: Dict[str, Any] = {}

    async def page_for(self, naver_blog_id: str, proxy: Optional[str] = None):
        ctx = self._ctx.get(naver_blog_id)
        if ctx is not None:
            try:
                pages = ctx.pages
                if pages:
                    return pages[0]
                return await ctx.new_page()
            except Exception:  # noqa: BLE001
                self._ctx.pop(naver_blog_id, None)
        ctx = await self._launch(naver_blog_id, proxy)
        self._ctx[naver_blog_id] = ctx
        return ctx.pages[0] if ctx.pages else await ctx.new_page()

    async def _launch(self, naver_blog_id: str, proxy: Optional[str] = None):
        user_data_dir = self.profiles_dir / naver_blog_id
        user_data_dir.mkdir(parents=True, exist_ok=True)
        args = ["--disable-blink-features=AutomationControlled", "--no-first-run", "--no-default-browser-check", "--restore-last-session"]
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
        if proxy:
            kw["proxy"] = _proxy_option(proxy)
            log.info("블로그 '%s' 는 고정 프록시로 나갑니다: %s", naver_blog_id, kw["proxy"]["server"])
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
    # 사람이 이 창에서 로그인하는 중이면(네이버 로그인 페이지 + 아직 로그인 쿠키 없음) 페이지를 다시 열지 않는다.
    # 주기마다 글쓰기 페이지로 다시 이동하면 네이버가 로그인 페이지를 새로 띄워, 입력 중인 아이디·보안문자·
    # 기기 인증이 1분마다 지워져 로그인을 끝낼 수 없다(2026-09-11 실제 네이버 실측).
    page = getattr(editor, "page", None)
    if page is not None and "nid.naver.com" in (getattr(page, "url", "") or ""):
        try:
            cookies = await page.context.cookies("https://nid.naver.com")
        except Exception:  # noqa: BLE001
            cookies = []
        if not any(c.get("name") == "NID_AUT" for c in cookies):
            return False, "브라우저 창에서 네이버 로그인을 기다리는 중(창을 다시 열지 않음)"
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


async def sync_categories(client: ServerClient, editor: Any) -> int:
    """앱의 카테고리 드롭다운을 채운다(확장 SYNC_CATEGORIES 대체).

    카테고리는 네이버 에디터 안에만 있어서 서버가 스스로 알 수 없다. 캐시가 비어 있을 때만
    발행 레이어를 열어 목록만 읽고 글쓰기 화면으로 되돌린다. 실패해도 발행은 계속한다."""
    try:
        cached = await asyncio.to_thread(client.categories)
        if (cached or {}).get("categories"):
            return 0
        await editor.open_publish_layer()
        items = await editor.read_categories()
        if items:
            await asyncio.to_thread(client.put_categories, items)
            log.info("카테고리 %d개를 서버에 저장했습니다", len(items))
        return len(items)
    except Exception as e:  # noqa: BLE001
        log.info("카테고리 동기화 건너뜀: %s", e)
        return 0
    finally:
        try:
            await editor.open_write_page()  # 레이어를 연 채로 두지 않는다
        except Exception:  # noqa: BLE001
            pass


def _job_slot(job: Dict[str, Any]) -> Optional[datetime]:
    """잡에 적힌 예약 시각(KST). '+09:00' 꼬리를 떼고 10분 단위로 내린다."""
    raw = ((job.get("schedule") or {}).get("datetime") or "").strip()
    if not raw:
        return None
    try:
        at = datetime.fromisoformat(raw.replace("+09:00", ""))
    except ValueError:
        return None
    return at.replace(minute=(at.minute // 10) * 10, second=0, microsecond=0)


async def sync_reservations(client: ServerClient, editor: Any, blog: Dict[str, Any]) -> Optional[List[datetime]]:
    """네이버에 이미 걸린 예약 목록을 읽어 서버 장부에 갈아 끼운다.

    서버는 이 목록이 있어야 남의 예약을 피해 자리를 잡는다. 목록은 로그인한 브라우저
    안에만 있으므로 읽어 오는 것은 실행기 몫이다(카테고리 동기화와 같은 구조).
    반환은 '지금 네이버에 잡혀 있는 시각들' — 못 읽었으면 None. 발행은 어느 쪽이든 계속한다."""
    ref = blog["blog_ref_id"]
    urls = [os.environ["DV_RESERVE_URL"]] if os.environ.get("DV_RESERVE_URL") else None
    try:
        items = await editor.read_reservations(blog["naver_blog_id"], urls=urls)
    except Exception as e:  # noqa: BLE001  목록을 못 본 것뿐이다. 발행을 멈출 이유가 아니다
        log.info("예약 목록 확인 건너뜀: %s", e)
        items = None
        note = str(e)[:300]
    else:
        note = "예약 목록 화면을 찾지 못했습니다"
    finally:
        try:
            await editor.open_write_page()       # 목록 화면에 머물지 않는다
        except Exception:  # noqa: BLE001
            pass
    try:
        if items is None:
            await asyncio.to_thread(client.put_reservations, ref, ok=False, note=note)
            log.warning("블로그 '%s' 예약 목록을 읽지 못했습니다 → 서버가 간격을 넓혀 잡습니다",
                        blog.get("label") or blog.get("naver_blog_id"))
            return None
        await asyncio.to_thread(client.put_reservations, ref, ok=True, items=items)
        log.info("네이버 예약 %d건을 서버에 알렸습니다", len(items))
        return [r["at"] for r in items]
    except ServerError as e:
        log.info("예약 목록 보고 실패: %s", e.detail)
        return [r["at"] for r in items] if items is not None else None


async def process_queue_jobs(client: ServerClient, editor: Any, blog: Dict[str, Any],
                             args: argparse.Namespace, *, claim_unassigned: bool) -> int:
    """대량 발행 큐(붙여넣기 대량·저장글)를 처리한다.

    캠페인 잡과 달리 서버 잠금이 없다. 서버는 건네준 즉시 registered 로 표시하므로
    한 건씩 가져와 곧바로 결과를 보고한다. dry-run 은 결과를 왜곡하므로 아예 가져오지 않는다."""
    if args.dry_run:
        return 0
    done = 0
    while done < args.max_per_blog and not stopping(args):
        try:
            jobs = await asyncio.to_thread(client.queue_jobs, limit=1, blog_ref_id=blog["blog_ref_id"],
                                           claim_unassigned=claim_unassigned)
        except ServerError as e:
            log.warning("발행 큐를 읽지 못했습니다: %s", e.detail)
            return done
        if not jobs:
            return done
        job = jobs[0]
        job["expectedBlogId"] = blog["naver_blog_id"]
        if done:
            await interruptible_pause(random.uniform(args.min_gap, args.max_gap), args)
            if stopping(args):
                return done
        log.info("--- 큐 글 %s '%s' (%s) ---", job.get("id"), (job.get("title") or "")[:40], job.get("finalAction"))
        result = await run_job(editor, job, dry_run=False)
        message = result.message
        if result.uncertain:
            message = f"[확인 필요] {message}"
        try:
            await asyncio.to_thread(client.queue_result, job["id"], ok=bool(result.ok and not result.uncertain),
                                    message=message)
        except ServerError as e:
            log.error("큐 결과 보고 실패(글 %s): %s", job.get("id"), e.detail)
        done += 1
        if result.need_login or result.captcha:
            log.warning("로그인/캡차 문제 → 이 블로그의 남은 큐는 다음 주기로 미룹니다")
            return done
    return done


async def process_blog(client: ServerClient, pool: BrowserPool, blog: Dict[str, Any], args: argparse.Namespace,
                       *, claim_unassigned: bool = False) -> None:
    from naver_editor import WRITE_URL, NaverEditor

    label, ref, naver_id = blog.get("label") or blog.get("naver_blog_id"), blog["blog_ref_id"], blog["naver_blog_id"]
    log.info("=== 블로그 '%s' (%s) 대기 %s건, 상태 %s ===", label, naver_id, blog.get("pending"), blog.get("status"))

    try:
        proxy = await asyncio.to_thread(client.proxy_for, ref)
    except Exception as e:  # noqa: BLE001  프록시를 못 읽었다고 발행을 멈추지는 않는다
        log.warning("블로그 '%s' 프록시 설정을 읽지 못했습니다(%s) → PC 회선으로 진행", label, e)
        proxy = None
    page = await pool.page_for(naver_id, proxy)
    # DV_WRITE_URL: 테스트용(가짜 에디터 페이지). 평소엔 비워 두면 네이버 글쓰기 URL.
    editor = NaverEditor(page, captcha_wait_sec=args.captcha_wait, write_url=os.environ.get("DV_WRITE_URL") or WRITE_URL)

    ok, why = await ensure_login(editor, client, blog)
    if not ok:
        log.warning("블로그 '%s' 건너뜀: %s", label, why)
        return

    current = (await editor.read_blog_id() or "").lower()
    if not current or not naver_id or current != naver_id.lower():
        reason = f"로그인된 블로그가 다릅니다(예상 '{naver_id}', 현재 '{current}'). 에이전트 브라우저 창에서 '{naver_id}' 계정으로 다시 로그인하세요."
        client.set_blog_status(ref, "login_required", reason)
        log.warning(reason)
        return
    if (blog.get("status") or "active") != "active":
        log.info("로그인 확인됨 → 블로그 상태를 active 로 복구")
        client.set_blog_status(ref, "active", "에이전트가 로그인을 확인했습니다")

    await sync_categories(client, editor)
    # 예약 목록 훑기는 **발행 뒤**로 미룬다. 사용자가 예약을 걸면 그 글이 네이버에 등록되는 것이
    # 먼저다 — 목록을 먼저 열다 로그인·화면 변경으로 시간을 쓰면 그만큼 등록이 늦어진다.
    taken: set = set()

    from journal import flush
    journal = args.journal
    for i in range(args.max_per_blog):
        if stopping(args):
            break
        await flush(journal, client)
        if i > 0:
            pause = random.uniform(args.min_gap, args.max_gap)
            log.info("다음 글까지 %.0f초 대기", pause)
            await interruptible_pause(pause, args)
            if stopping(args):
                break
        jobs = await asyncio.to_thread(client.claim, ref, limit=1, include_images=not args.no_images,
                                       mode="dry_run" if args.dry_run else "live")
        if not jobs:
            break
        job = jobs[0]
        journal.start(job)
        token = job["lock_token"]
        lost_lease = asyncio.Event()

        async def keep_lease():
            while True:
                await asyncio.sleep(30)
                try:
                    await asyncio.to_thread(client.checkpoint, job["id"], token)
                except Exception:
                    lost_lease.set()
                    return

        async def before_publish():
            if stopping(args):
                raise RuntimeError('사용자가 실행 중단을 요청했습니다')
            if lost_lease.is_set():
                raise RuntimeError("서버 연결이 끊겨 발행을 중단했습니다")
            journal.finalizing(token)
            await asyncio.to_thread(client.checkpoint, job["id"], token, "finalizing")

        log.info("--- 잡 %s '%s' 예약 %s ---", job.get("id"), (job.get("title") or "")[:40], (job.get("schedule") or {}).get("datetime"))
        # 서버의 장부는 언제나 몇 분 과거다. 방금 눈으로 본 목록과 대조해 그 칸이 차 있으면
        # 올리지 않고 자리를 옮긴다 — 같은 시각에 두 글이 걸리는 것만은 막아야 한다.
        slot = _job_slot(job)
        if slot and slot in taken:
            log.warning("예약 %s 자리가 이미 차 있습니다 → 발행하지 않고 옮깁니다", slot.strftime("%m/%d %H:%M"))
            try:
                moved = await asyncio.to_thread(client.reschedule, job["id"], token,
                                                reason=f"{slot.strftime('%m/%d %H:%M')} 에 이미 예약된 글이 있습니다",
                                                taken_at=[slot])
                log.info("→ %s 으로 옮겼습니다", moved.get("scheduled_at"))
                journal.acknowledge(token)     # 서버가 잠금을 풀었다 — 복구 대상이 아니다
            except ServerError as e:
                # 잠금은 리스 만료로 저절로 풀린다. 다음 주기에 다시 본다.
                log.error("자리를 옮기지 못했습니다: %s", e.detail)
                journal.save_result(token, {'ok': False, 'uncertain': False, 'release': True,
                                            'message': '예약 자리가 차 있어 발행하지 않았습니다'})
            continue
        await asyncio.to_thread(client.checkpoint, job["id"], token, "editing")
        heartbeat = asyncio.create_task(keep_lease())
        try:
            result = await run_job(editor, job, dry_run=args.dry_run, before_publish=before_publish)
            journal.save_result(token, result.as_report())
        finally:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
        log.info("결과: ok=%s uncertain=%s need_login=%s captcha=%s — %s", result.ok, result.uncertain, result.need_login, result.captcha, result.message[:200])
        await flush(journal, client)
        if result.need_login or result.captcha:
            log.warning("로그인/캡차 문제 → 이 블로그의 나머지 잡은 다음 주기로 미룹니다")
            return

    if not stopping(args):
        queued = await process_queue_jobs(client, editor, blog, args, claim_unassigned=claim_unassigned)
        if queued:
            log.info("발행 큐 %d건 처리", queued)

    # 올릴 것을 다 올린 뒤에 네이버 예약 목록을 훑어 서버 장부를 맞춘다(서버가 청하면).
    if blog.get("wants_scan") and not stopping(args):
        await sync_reservations(client, editor, blog)


# ---------------------------------------------------------------- 메인 루프
async def run_once(client: ServerClient, pool: BrowserPool, args: argparse.Namespace) -> int:
    from journal import flush
    await flush(args.journal, client)
    summary = await asyncio.to_thread(client.summary)
    blogs = select_blogs(summary, args.blog)
    if args.blog and not blogs:
        log.error("--blog '%s' 에 해당하는 블로그가 없습니다. 등록된 블로그: %s", args.blog, ", ".join(f"{b.get('label')}({b.get('naver_blog_id')})" for b in summary) or "없음")
        return 0
    if not blogs:
        log.info("처리할 블로그 없음(대기 잡 0건)")
        return 0
    for b in blogs:
        if stopping(args):
            break
        try:
            # 블로그가 하나뿐이면 대상 지정 없는 예전 큐도 이 블로그 몫으로 본다.
            await process_blog(client, pool, b, args, claim_unassigned=len(summary) <= 1)
        except Exception as e:  # noqa: BLE001
            log.error("블로그 '%s' 처리 중 오류: %s\n%s", b.get("label"), e, traceback.format_exc())
            await pool.close(b["naver_blog_id"])
    return len(blogs)


async def main_async(args: argparse.Namespace) -> int:
    from playwright.async_api import async_playwright
    from journal import Journal
    import hashlib

    namespace = hashlib.sha256(f"{args.server}|{args.email}".encode()).hexdigest()[:20]
    args.journal = Journal(Path(args.profiles_dir) / f"journal-{namespace}.sqlite3")

    client = ServerClient(args.server)
    try:
        # 홈페이지와 자동 연결된 PC는 기기 키로, 아니면 이메일·비밀번호로 로그인한다.
        if getattr(args, 'device_secret', None):
            client.device_login(args.device_id, args.device_secret)
        else:
            client.login(args.email, args.password)
    except Exception as e:  # noqa: BLE001
        log.error("서버 로그인 실패: %s", e)
        client.close()
        args.journal.close()
        return 2
    log.info("서버 로그인 OK: %s", args.server)

    profiles_dir = Path(args.profiles_dir).resolve()
    async with async_playwright() as pw:
        pool = BrowserPool(pw, profiles_dir, headless=args.headless, window_pos=args.window_pos)
        try:
            while not stopping(args):
                started = time.monotonic()
                try:
                    await run_once(client, pool, args)
                except ServerError as e:
                    # 인증이 끊기면(토큰 만료·다른 PC에서 재연결) 이 루프는 아무것도 할 수 없다.
                    # 그런데도 계속 돌면 화면에는 '자동 발행 실행 중' 초록불이 켜진 채
                    # 발행 요청은 한 번도 가지 않는다(2026-09-23 실측). 멈추고 알린다.
                    if e.status in (401, 403):
                        log.error("서버 인증이 끊어졌습니다 — 다시 연결한 뒤 이어서 발행합니다")
                        return 3
                    log.error("서버 오류: %s", e)
                except Exception as e:  # noqa: BLE001
                    log.error("주기 실행 오류: %s\n%s", e, traceback.format_exc())
                if args.once:
                    break
                wait = max(5.0, args.interval - (time.monotonic() - started))
                log.info("다음 확인까지 %.0f초 대기 (Ctrl+C 로 종료)", wait)
                await interruptible_pause(wait, args)
        finally:
            await pool.close()
            client.close()
            args.journal.close()
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
