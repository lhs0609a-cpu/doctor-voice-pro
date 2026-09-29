"""블로그 하나의 상태 → 사람이 읽을 한 줄.

실행기 로그와 실행기 창이 **같은 문장**을 쓰게 하려고 한 곳에 모았다. 두 곳이 다른 말을
하면 사용자는 어느 쪽을 믿어야 할지 모른다.

문장 규칙(2026-09-29 사용자 요청: "구체적으로 어떤 액션을 하라는건지 가이드를 안내해줘,
오류가 아니라면 이해돼?"):

1. **맨 앞에 성격을 적는다.** [정상] 인지 [조치 필요] 인지가 첫 글자에서 보여야 한다.
   기다리는 중인 것을 고장으로 읽으면 멀쩡한 예약을 지우고 다시 거는 헛수고를 한다.
2. **무엇을 누르면 풀리는지**를 적는다. 이유만 적으면 "그래서 뭘 하라고?"가 된다.
3. 한 줄이다. 실행기 창의 현황 줄에 그대로 들어가야 한다.
"""
from typing import Any, Dict, Tuple

OK = "정상"
ACTION = "조치 필요"


def _int(blog: Dict[str, Any], key: str) -> int:
    try:
        return int(blog.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def blog_status(blog: Dict[str, Any], *, idle: bool = False) -> Tuple[str, str]:
    """→ (level, 한 줄). level 은 OK 또는 ACTION.

    순서가 곧 우선순위다. 여러 가지가 겹쳐 있을 때 **먼저 풀어야 하는 것**을 말한다.
    '확인 필요'가 맨 앞인 이유는 그 한 건이 그 블로그의 나머지를 전부 세우기 때문이다.

    idle 은 '방금 서버에 달라고 했는데 한 건도 안 줬다'는 뜻이다. 그럴 때만 사유 없는
    대기를 조치 필요로 본다. 그냥 현황을 보여 줄 때(idle=False)는 대기 건수가 있는 것이
    정상이다 — 아직 그 시각이 안 됐거나 이미 네이버에 걸어 둔 것이다.
    """
    label = blog.get("label") or blog.get("naver_blog_id") or "블로그"
    blocked, stalled = _int(blog, "blocked"), _int(blog, "stalled")
    pending = _int(blog, "pending")
    reason = (blog.get("hold_reason") or "").strip()
    status = (blog.get("status") or "active")

    if blocked:
        return ACTION, (
            f"[{ACTION}] '{label}' — 네이버에 올라갔는지 모르는 글이 {blocked}건 있어 "
            f"다음 글이 올라가지 않습니다(같은 글을 두 번 올리지 않으려는 안전장치입니다). "
            f"→ 홈페이지 [발행 현황]에서 그 건의 [예약 등록 확인] 또는 [미등록 확인]을 눌러 주세요. "
            f"누르는 즉시 나머지 {pending}건이 이어집니다.")

    if status == "login_required":
        return ACTION, (
            f"[{ACTION}] '{label}' — 네이버 로그인이 풀렸습니다. "
            f"→ 이 프로그램이 띄운 크롬 창에서 네이버에 로그인해 주세요. 그러면 알아서 이어집니다.")

    if status == "captcha":
        return ACTION, (
            f"[{ACTION}] '{label}' — 네이버가 보안문자를 요구했습니다. "
            f"→ 이 프로그램이 띄운 크롬 창에서 보안문자를 입력해 주세요. 그러면 알아서 이어집니다.")

    if status != "active":
        return ACTION, (
            f"[{ACTION}] '{label}' — 블로그 상태가 '{status}' 입니다. "
            f"→ 홈페이지 [병원 관리]에서 이 블로그를 '정상'으로 바꿔 주세요."
            + (f" (사유: {blog.get('status_reason')})" if blog.get("status_reason") else ""))

    if pending and reason:
        return ACTION, f"[{ACTION}] '{label}' — 대기 {pending}건이 멈춰 있습니다. {reason}"

    if pending and idle:
        return ACTION, (
            f"[{ACTION}] '{label}' — 대기 {pending}건을 서버가 내주지 않았습니다. "
            f"→ 홈페이지 [발행 현황]에서 그 건에 적힌 사유를 확인해 주세요. "
            f"사유가 없으면 잠시 뒤 다시 시도합니다(그대로 두셔도 됩니다).")

    if stalled:
        return ACTION, (
            f"[{ACTION}] '{label}' — 여러 번 실패해 멈춘 글이 {stalled}건 있습니다. "
            f"→ 홈페이지 [발행 현황]에서 사유를 보고 [재시도]를 누르거나, 새 시각으로 다시 예약해 주세요.")

    nxt = (blog.get("next_at") or "").replace("T", " ")[5:16]
    if pending and nxt:
        return OK, (f"[{OK}] '{label}' — 대기 {pending}건, 다음 글은 {nxt} 에 올라갑니다. "
                    f"그때까지 기다리는 중이라 지금 아무 일도 일어나지 않는 것이 맞습니다.")
    if nxt:
        return OK, f"[{OK}] '{label}' — 올릴 글을 모두 네이버에 걸어 뒀습니다. 다음 글은 {nxt} 에 올라갑니다."
    return OK, f"[{OK}] '{label}' — 올릴 예약이 없습니다. 홈페이지에서 예약을 걸면 바로 가져갑니다."


def overall(blogs) -> Tuple[str, str]:
    """실행기 창 현황 줄 한 개. 조치가 필요한 블로그가 있으면 그것부터 말한다.

    아무 문제가 없으면 '정상'이라고 분명히 말한다 — 조용한 화면을 고장으로 읽지 않도록."""
    if not blogs:
        return ACTION, f"[{ACTION}] 등록된 블로그가 없습니다. → 홈페이지에서 블로그를 먼저 등록해 주세요."
    lines = [blog_status(b) for b in blogs]
    for level, text in lines:
        if level == ACTION:
            return level, text
    waiting = sum(_int(b, "pending") for b in blogs)
    nexts = sorted(b["next_at"] for b in blogs if b.get("next_at"))
    when = nexts[0].replace("T", " ")[5:16] if nexts else None
    if when:
        return OK, (f"[{OK}] 대기 {waiting}건 · 다음 {when} — 그때까지 기다립니다. "
                    f"지금 아무 일도 일어나지 않는 것이 맞습니다.")
    return OK, f"[{OK}] 올릴 예약이 없습니다. 홈페이지에서 예약을 걸면 바로 가져갑니다."
