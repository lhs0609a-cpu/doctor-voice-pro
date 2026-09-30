"""네이버 카페 글쓰기. 블로그(naver_editor)와 같은 자리에서, 같은 크롬 프로필로 돈다.

왜 서버가 아니라 여기인가
    서버에서 브라우저를 띄우면 데이터센터 IP로 계정을 돌리는 꼴이라 정지 사유 그 자체다.
    블로그를 실행기로 옮긴 이유와 같다. 운영 Docker 에는 Chromium 이 아예 없어서
    예전 서버 쪽 카페 게시(cafe_poster)는 실행조차 되지 않았다.

지켜야 할 것
    · 등록 버튼을 누른 뒤의 실패는 **다시 올리지 않는다**. 카페에 같은 글이 두 번 올라가면
      그 계정은 바로 광고로 찍힌다. 그래서 '눌렀다'는 사실을 호출자에게 분명히 돌려준다.
    · 글쓰기 화면이 안 열리면(등급 부족·가입 안 됨) 누르기 전에 멈춘다.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

log = logging.getLogger("cafe")

#: 카페 글쓰기 화면. 카페 주소(https://cafe.naver.com/xxx)에 이걸 붙인다.
WRITE_SUFFIX = "?iframe_url=/ArticleWrite.nhn"
#: 올라간 글 주소에서 글 번호를 읽는다.
POST_URL = re.compile(r"cafe\.naver\.com/([A-Za-z0-9_-]+)/(\d+)")


class CafeError(Exception):
    """글쓰기 화면까지 못 간 실패. 등록 버튼을 누르지 않았다는 뜻이다."""


class CafeLoginRequired(CafeError):
    pass


@dataclass
class CafeOutcome:
    ok: bool
    uncertain: bool = False
    url: Optional[str] = None
    message: str = ""


def cafe_write_url(cafe_url: str) -> str:
    return cafe_url.rstrip("/") + WRITE_SUFFIX


def post_url_from(raw: str) -> Optional[str]:
    m = POST_URL.search(raw or "")
    return f"https://cafe.naver.com/{m.group(1)}/{m.group(2)}" if m else None


class CafeEditor:
    def __init__(self, page: Any):
        self.page = page

    async def _write_frame(self, timeout_ms: int = 20000):
        """글쓰기 iframe. 카페는 본문이 iframe 안에 있고 이름이 카페마다 다르다."""
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            if "nid.naver.com" in (self.page.url or ""):
                raise CafeLoginRequired("카페 글쓰기에 로그인이 필요합니다")
            for frame in self.page.frames:
                try:
                    if frame.is_detached():
                        continue
                    url = frame.url or ""
                    if "ArticleWrite" in url or "write" in url.lower():
                        return frame
                except Exception:  # noqa: BLE001 — 프레임 교체 중
                    continue
            await asyncio.sleep(0.4)
        raise CafeError("카페 글쓰기 화면이 열리지 않았습니다. 그 카페에 글을 쓸 수 있는 등급인지 확인하세요")

    async def open_write(self, cafe_url: str) -> None:
        url = cafe_write_url(cafe_url)
        log.info("카페 글쓰기 열기: %s", url)
        await self.page.goto(url, wait_until="commit", timeout=30000)
        await self._write_frame()

    async def choose_board(self, board_name: Optional[str]) -> None:
        """게시판 고르기. 이름을 안 주면 카페 기본값 그대로 둔다."""
        if not (board_name or "").strip():
            return
        frame = await self._write_frame()
        try:
            picked = await frame.evaluate(
                """(name) => {
                  const wanted = String(name).replace(/\\s+/g, '');
                  for (const select of document.querySelectorAll('select')) {
                    for (const option of select.options) {
                      if ((option.textContent || '').replace(/\\s+/g, '').includes(wanted)) {
                        select.value = option.value;
                        select.dispatchEvent(new Event('change', { bubbles: true }));
                        return true;
                      }
                    }
                  }
                  return false;
                }""", board_name)
        except Exception as e:  # noqa: BLE001
            raise CafeError(f"게시판을 고르지 못했습니다: {e}")
        if not picked:
            raise CafeError(f"'{board_name}' 게시판을 찾지 못했습니다. 게시판 이름을 확인하세요")
        log.info("게시판 선택: %s", board_name)

    async def fill(self, title: str, body: str) -> None:
        frame = await self._write_frame()
        title_box = None
        for selector in ("input#subject", "input[name='subject']", "input[placeholder*='제목']",
                         ".textbox_input input", "input.textbox"):
            box = frame.locator(selector).first
            if await box.count():
                title_box = box
                break
        if title_box is None:
            raise CafeError("제목 입력칸을 찾지 못했습니다(카페 화면 변경 가능)")
        await title_box.click()
        await title_box.fill(title)

        # 본문은 스마트에디터 iframe 안이거나 contenteditable 이다. 둘 다 본다.
        for frame_candidate in [frame, *self.page.frames]:
            try:
                if frame_candidate.is_detached():
                    continue
                editable = frame_candidate.locator("[contenteditable='true']").first
                if await editable.count():
                    await editable.click()
                    await self.page.keyboard.insert_text(body)
                    log.info("제목·본문 입력 완료 (%d자)", len(body))
                    return
            except Exception:  # noqa: BLE001
                continue
        raise CafeError("본문 입력칸을 찾지 못했습니다(카페 화면 변경 가능)")

    async def submit(self, *, dry_run: bool = False, settle_sec: float = 20.0) -> Optional[CafeOutcome]:
        """등록 버튼을 누른다. **이 뒤의 실패는 전부 '모름'이다** — 다시 올리지 않는다."""
        frame = await self._write_frame()
        button = None
        for selector in ("a.BaseButton--skinGreen", "button.BaseButton--skinGreen",
                         "a#cafe-write-btn", ".btn_register", "button[type='submit']"):
            candidate = frame.locator(selector).first
            if await candidate.count():
                button = candidate
                break
        if button is None:
            raise CafeError("등록 버튼을 찾지 못했습니다(카페 화면 변경 가능)")
        if dry_run:
            log.info("[dry-run] 등록 버튼은 누르지 않습니다")
            return None

        before = self.page.url or ""
        log.info("카페 등록 클릭")
        await button.click()
        deadline = time.monotonic() + settle_sec
        while time.monotonic() < deadline:
            await asyncio.sleep(0.5)
            now = self.page.url or ""
            found = post_url_from(now)
            if found:
                log.info("올라간 글: %s", found)
                return CafeOutcome(ok=True, url=found, message="글 주소 확인")
            if now != before and "ArticleWrite" not in now:
                log.info("등록 후 화면 이동: %s", now[:100])
                return CafeOutcome(ok=True, url=post_url_from(now), message="등록 후 페이지 이동")
        return CafeOutcome(ok=False, uncertain=True,
                           message="등록을 눌렀지만 화면 변화를 확인하지 못했습니다. 카페에서 직접 확인해 주세요")
