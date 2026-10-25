"""실측: 실제 네이버 편집기에서 '임시저장 → 다시 열기 → 이어쓰기'가 되는지 확인한다.

**발행하지 않는다.** 임시저장까지만 하고, 그 글을 다시 불러와 제목·본문이 그대로인지 본다.
안전장치(남의 글·반쯤 쓰인 글은 거절)도 같은 화면에서 확인한다.

사용:
  python live_resume_check.py --blog platonmarketing
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.async_api import async_playwright

from naver_editor import LoginRequired, NaverEditor

log = logging.getLogger("live")

TITLE = "[점검용 임시저장] 이어쓰기 동작 확인 — 발행하지 않습니다"
PARAGRAPHS = [
    "이 글은 닥터보이스 실행기의 '이어쓰기' 동작을 확인하려고 만든 임시저장입니다.",
    "본문이 끝까지 들어갔는지 글자 수로 재기 때문에, 문단을 여러 개 넣어 둡니다.",
    "발행하지 않으며, 확인이 끝나면 네이버 임시저장함에서 지우면 됩니다.",
    "세 번째 문단입니다. 이어받은 뒤에도 이 문장이 그대로 남아 있어야 합니다.",
]
BLOCKS = [{"type": "text", "content": p} for p in PARAGRAPHS]
WANT_CHARS = sum(len(p) for p in PARAGRAPHS)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blog", required=True, help="네이버 블로그 ID (프로필 폴더 이름)")
    ap.add_argument("--profiles-dir", default="profiles")
    ap.add_argument("--login-wait", type=int, default=900, help="로그인을 기다리는 초")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    profile = Path(args.profiles_dir).resolve() / args.blog
    if not profile.is_dir():
        print(f"프로필이 없습니다: {profile}")
        return 2

    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(profile), headless=False,
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled", "--no-first-run",
                  "--no-default-browser-check"],
            ignore_default_args=["--enable-automation"],
            locale="ko-KR", timezone_id="Asia/Seoul")
        ctx.set_default_timeout(15000)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        editor = NaverEditor(page)
        failures = []
        try:
            # --- 1단계: 글을 쓰고 임시저장한다 -------------------------------
            print("\n[1] 글쓰기 화면을 열고 본문을 넣습니다")
            try:
                await editor.open_write_page()
            except LoginRequired:
                # 기다리는 동안 **페이지를 다시 옮기지 않는다** — 옮기면 입력하던 로그인이
                # 날아간다(2026-10-23). 주소만 지켜보다가 들어오면 이어서 한다.
                print("\n  네이버 로그인이 필요합니다.")
                print("  → 방금 열린 크롬 창에서 네이버에 로그인해 주세요. 끝나면 자동으로 이어집니다.")
                print(f"  (최대 {args.login_wait // 60}분 기다립니다)")
                for _ in range(args.login_wait):
                    await asyncio.sleep(1)
                    if "nid.naver.com" not in (page.url or ""):
                        break
                else:
                    print("  ✗ 로그인을 기다리다 시간이 다 됐습니다.")
                    return 3
                await asyncio.sleep(2)
                await editor.open_write_page()
            who = (await editor.read_blog_id() or "").strip().lower()
            if who != args.blog.lower():
                print(f"  ✗ 로그인된 블로그가 '{who}' 입니다(기대 '{args.blog}'). "
                      f"이 창에서 네이버에 로그인한 뒤 다시 실행하세요.")
                return 3
            print(f"  로그인 확인: {who}")
            await editor.dismiss_draft_popup()
            await editor.clear_blocking_layers("점검 시작")
            await editor.set_title(TITLE)
            await editor.insert_body_blocks(BLOCKS, [], reformat=False)
            print(f"  본문 {WANT_CHARS}자 입력 완료")
            out = await editor.save_draft()
            print(f"  임시저장: {'성공' if (out and out.ok) else '실패'}")
            if not (out and out.ok):
                return 4
            await asyncio.sleep(2)

            # --- 2단계: 화면을 떠났다가 다시 와서 이어받는다 -----------------
            print("\n[2] 글쓰기 화면을 다시 열어 이어쓰기를 시도합니다")
            await editor.open_write_page()
            ok = await editor.restore_draft(TITLE, WANT_CHARS)
            print(f"  이어쓰기: {'성공' if ok else '실패'}")
            if not ok:
                failures.append("우리 글을 이어받지 못했습니다")

            # --- 3단계: 안전장치 — 남의 글이면 거절해야 한다 ------------------
            print("\n[3] 안전장치: 제목이 다르면 거절해야 합니다")
            await editor.open_write_page()
            refused = await editor.restore_draft("전혀 다른 글 제목입니다", WANT_CHARS)
            print(f"  거절했나: {'예(정상)' if not refused else '아니오(위험)'}")
            if refused:
                failures.append("남의 글을 이어받았습니다 — 위험")

            # --- 4단계: 안전장치 — 본문이 모자라면 거절해야 한다 --------------
            print("\n[4] 안전장치: 본문이 모자라면 거절해야 합니다")
            await editor.open_write_page()
            short = await editor.restore_draft(TITLE, WANT_CHARS * 3)
            print(f"  거절했나: {'예(정상)' if not short else '아니오(위험)'}")
            if short:
                failures.append("반쯤 쓰인 글을 이어받았습니다 — 위험")
        finally:
            await ctx.close()

    print("\n" + "=" * 56)
    if failures:
        for f in failures:
            print("  ✗ " + f)
        return 1
    print("  ✓ 이어쓰기와 안전장치 4가지 모두 실제 네이버에서 확인됐습니다")
    print("  · 네이버 임시저장함에 '[점검용 임시저장]' 글이 하나 남습니다 — 지우셔도 됩니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
