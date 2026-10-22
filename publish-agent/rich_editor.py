"""Native SmartEditor toolbar formatting with DOM read-back before publication."""
import asyncio
import logging
import re
import html
import sys

log = logging.getLogger('editor')

# 툴바 단추는 금방 눌려야 한다. 15초(브라우저 기본값)를 기다렸다 포기하면, 그 사이 글 하나가
# 통째로 버려진다 — 빨리 포기하고 덮고 있는 창을 치운 뒤 다시 누르는 편이 낫다.
TOOLBAR_CLICK_MS = 4000


async def blocked(editor):
    """지금 네이버 선택창(글감 등)이 떠 있나. 못 보면 '없다'로 친다."""
    scan = getattr(editor, 'scan_blocking_layers', None)
    if scan is None:
        return False
    try:
        return bool(await scan())
    except Exception:       # noqa: BLE001  확인에 실패했다고 글을 막을 이유는 없다
        return False


async def unblock(editor, where):
    """툴바를 덮고 있는 선택창을 치운다. 못 치워도 그냥 진행한다."""
    clear = getattr(editor, 'clear_blocking_layers', None)
    if clear is None:
        return False
    try:
        return bool(await clear(where))
    except Exception:       # noqa: BLE001
        return False


async def press_toolbar(editor, button, where):
    """툴바 단추를 누른다. 막히면 선택창을 치우고 한 번 더 — 그래도 안 되면 False.

    2026-10-20 고객 신고: 위례 원고 5건이 전부
    `TimeoutError: Timeout 15000ms exceeded ... button[data-name="font-color"]` 로 실패했다.
    단추를 **찾기는 했는데 눌리지 않는다**(글감 선택창이 툴바를 덮고 있으면 이렇게 된다).
    색은 모양일 뿐인데 그것 때문에 글 전체가 '손봐야 할 글'로 떨어졌다."""
    try:
        await button.click(timeout=TOOLBAR_CLICK_MS)
        return True
    except Exception as first:      # noqa: BLE001
        log.warning('%s 단추가 눌리지 않습니다(%s) — 선택창을 치우고 다시 눌러 봅니다',
                    where, str(first).splitlines()[0][:80])
    await unblock(editor, where)
    try:
        await button.click(timeout=TOOLBAR_CLICK_MS * 2)
        return True
    except Exception as again:      # noqa: BLE001
        log.warning('%s 단추를 끝내 누르지 못했습니다: %s', where, str(again).splitlines()[0][:80])
        return False


TOGGLE_READ_MS = 1500   # 단추 상태는 금방 읽혀야 한다. 못 읽으면 '모른다'로 넘어간다.


async def toggled(button):
    """툴바 단추가 켜져 있나(굵게·기울임·밑줄). **못 읽으면 None — 모른다는 뜻.**

    예전에는 여기서 브라우저 기본 대기(15초)를 다 쓰고 터졌다. 단추가 덮였거나 네이버가
    화면을 바꾼 날, 그 한 줄 때문에 원고가 통째로 '손봐야 할 글'로 떨어졌다
    (2026-10-22 위례: "'굵게' 단추를 제때 누르지 못했습니다").
    모를 때는 **누르지 않는다** — 넣은 뒤 읽어 보고 고치는 길(_fix_toggles)이 따로 있다."""
    try:
        klass = await button.get_attribute('class', timeout=TOGGLE_READ_MS)
    except Exception:       # noqa: BLE001
        return None
    return 'se-is-selected' in (klass or '')


async def toggle_changed(button, before):
    """방금 누른 것이 먹혔나. 편집기가 단추 모양을 바꾸는 데 한 박자 걸린다."""
    for _ in range(4):
        await asyncio.sleep(.06)
        now = await toggled(button)
        if now is None:
            return False        # 모르면 '안 바뀜'으로 쳐서 뒤에서 고치게 한다
        if now != before:
            return True
    return False


def note_problem(editor, what: str) -> None:
    """글은 올리되, 사람이 손봐야 할 자리를 적어 둔다.

    2026-10-22 요청: "오류 뜨는 부분은 넘어가면서 예약발행 / 임시저장 되게 해주실 수
    있을까요?? 오류 뜬 부분은 저희가 수기로 고쳐서 바로 발행 걸겠습니다
    (지금은 오류가 뜨면 이제까지 작업한 것들이 아예 삭제되어버리네요)."
    서식 하나가 어긋났다고 다 쓴 원고를 버리면, 그때까지의 작업이 통째로 사라진다."""
    notes = getattr(editor, 'format_notes', None)
    if notes is None:
        notes = []
        try:
            editor.format_notes = notes
        except Exception:       # noqa: BLE001  가짜 편집기 등 못 붙이는 경우
            return
    log.warning('서식 확인 필요(글은 그대로 올립니다): %s', what)
    if what not in notes:
        notes.append(what)


def rgb(hex_color):
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', hex_color or ''):
        raise ValueError('잘못된 강조 색상입니다')
    return 'rgb(%d, %d, %d)' % tuple(int(hex_color[i:i+2],16) for i in (1,3,5))


async def set_color(editor, color, background=False):
    frame = await editor.frame()
    name = '글자 배경색 변경' if background else '글자색 변경'
    picker = frame.locator('button[data-name="background-color"]' if background else 'button[data-name="font-color"]')
    if not await press_toolbar(editor, picker, name):
        return False        # 색은 못 넣어도 글은 올린다 — 아래 붙여넣기 길로 넘어간다
    # Read the live palette. Its hash class names change between Naver releases.
    value = await frame.evaluate(r'''wanted => {
      const rgb='rgb('+[1,3,5].map(i=>parseInt(wanted.slice(i,i+2),16)).join(', ')+')';
      const visible=e=>e.getBoundingClientRect().width && e.getBoundingClientRect().height;
      const buttons=[...document.querySelectorAll('button.se-color-palette')].filter(visible);
      const match=buttons.find(e=>[e.getAttribute('data-color'),e.getAttribute('data-value'),e.title,e.getAttribute('aria-label')].some(v=>v&&v.toLowerCase()===wanted.toLowerCase())
        || getComputedStyle(e).backgroundColor===rgb
        || [...e.querySelectorAll('span')].some(s=>getComputedStyle(s).backgroundColor===rgb));
      if(match){match.click(); return 'palette';}
      const inputs=[...document.querySelectorAll('input')].filter(visible);
      const input=inputs.find(e=>/^#?[0-9a-f]{6}$/i.test(e.value));
      if(input){input.setAttribute('data-dv-color-input','true');return 'input';}
      return null;
    }''',color)
    if value == 'input':
        field = frame.locator('input[data-dv-color-input="true"]')
        current = await field.input_value()
        await field.fill(color if current.startswith('#') else color[1:])
        await field.press('Enter')
        await field.evaluate("e => e.removeAttribute('data-dv-color-input')")
    elif value is None:
        await press_toolbar(editor, picker, f'{name}(팔레트 닫기)')
        await editor.page.keyboard.press('Escape')
        return False
    await asyncio.sleep(.1)
    return True


READ_BACK = r'''text => {
      // 네이버는 띄어쓰기를 nbsp 로 바꾸고, HTML 로 붙여 넣은 연속 공백은 한 칸으로 합친다.
      // 글자 그대로 비교하면 방금 넣은 문구를 못 찾아 글 전체가 막힌다(2026-09-28).
      const norm=s=>s.replace(/\s+/g,' ').trim();
      const wanted=norm(text);
      const body=[...document.querySelectorAll('.se-component:not(.se-documentTitle) .se-text-paragraph')];
      const ends=p=>norm(p.textContent).endsWith(wanted);
      // 글자가 들어간 곳은 **캐럿이 있는 문단**이다. 템플릿을 불러온 글에서는 쓰는 자리 아래로
      // 템플릿 문단이 계속 남아 있어, 문서를 뒤에서부터 훑으면 엉뚱한 줄의 서식을 읽을 수 있다.
      let paragraph=null;
      const focus=(document.getSelection()||{}).focusNode;
      if(focus){
        const near=focus.nodeType===1?focus:focus.parentElement;
        const caret=near&&near.closest('.se-text-paragraph');
        if(caret&&body.includes(caret)&&ends(caret)) paragraph=caret;
      }
      if(!paragraph) paragraph=[...body].reverse().find(ends);
      if(!paragraph) return null;
      // 방금 넣은 글자가 어느 텍스트 노드인지는 **뒤에서부터** 센다. 문단 길이에서 글자 수를
      // 빼서 자리를 잡으면, 편집기가 공백을 합쳤을 때(HTML 붙여넣기는 연속 공백을 한 칸으로
      // 만든다 — 바로 위 주석) 검사 범위가 앞으로 밀려 **바로 앞 문구의 서식**을 보게 된다.
      // 그래서 멀쩡한 원고가 '서식이 요청과 다릅니다'로 막혔다(2026-10-02 사용자 신고).
      const walker=document.createTreeWalker(paragraph,NodeFilter.SHOW_TEXT);
      const nodes=[]; let node;
      while((node=walker.nextNode())) if(node.length) nodes.push(node);
      const mine=[]; let tail='';
      for(let i=nodes.length-1;i>=0;i--){
        mine.unshift(nodes[i]); tail=nodes[i].data+tail;
        if(norm(tail).length>=wanted.length) break;      // 꼬리 쪽 최소한의 노드만 집는다
      }
      return mine.map(n=>{
        const s=getComputedStyle(n.parentElement);
        let bg=s.backgroundColor, parent=n.parentElement;
        while(bg==='rgba(0, 0, 0, 0)' && parent!==paragraph){parent=parent.parentElement;bg=getComputedStyle(parent).backgroundColor;}
        const under=n.parentElement.closest('u');
        return {quote:!!paragraph.closest('.se-quotation'),bold:parseInt(s.fontWeight)>=600,italic:s.fontStyle==='italic',
          underline:!!under||s.textDecorationLine.includes('underline'),color:s.color,background:bg};
      });
    }'''


BODY_LEN = r'''() => [...document.querySelectorAll('.se-component:not(.se-documentTitle) .se-text-paragraph')]
      .reduce((n, p) => n + p.textContent.length, 0)'''

# 글자를 넣기 직전 캐럿이 있는 본문 문단의 순번(못 찾으면 -1).
CARET_AT = r'''() => {
      const body=[...document.querySelectorAll('.se-component:not(.se-documentTitle) .se-text-paragraph')];
      const sel=document.getSelection(); const f=sel&&sel.focusNode;
      if(!f) return -1;
      const near=f.nodeType===1?f:f.parentElement;
      const p=near&&near.closest('.se-text-paragraph');
      return p?body.indexOf(p):-1;
    }'''

# 그 문단의 **마지막 글자 바로 뒤** 좌표(프레임 기준). 빈 문단이면 문단 자리.
END_POINT = r'''(i) => {
      const p=[...document.querySelectorAll('.se-component:not(.se-documentTitle) .se-text-paragraph')][i];
      if(!p) return null;
      p.scrollIntoView({block:'center'});
      const r=document.createRange(); r.selectNodeContents(p);
      const rects=[...r.getClientRects()].filter(x=>x.width||x.height);
      const box=rects.length?rects[rects.length-1]:p.getBoundingClientRect();
      return {x:Math.max(box.left+1, box.right-1), y:box.top+Math.min(box.height/2, 12)};
    }'''

# 방금 넣은 문구가 **화면에서는 몇 글자인가**. 편집기는 연속 공백을 한 칸으로 합치고 끝
# 공백을 nbsp 로 바꾼다 — 보낸 글자 수(len(text))만큼 뒤로 고르면 그 차이만큼 **앞 문구까지**
# 골라진다. 2026-10-22 실측(Chromium contenteditable):
#   보낸 것  '일주일에  두세 번  두통약을 먹습니다'(21자)
#   골라진 것 '문구일주일에 두세 번 두통약을 먹습니다'  ← 앞 문구의 '문구' 두 글자가 딸려 왔다
# 그 상태로 Ctrl+I 를 누르면 앞 문구의 기울임까지 함께 뒤집혀, 고치려던 문구가 되레 기울어
# 나온다("기울임을 빼 달라고 했는데 편집기에는 그렇게 들어가지 않았습니다" — 위례·kibundang).
TAIL_LEN = r'''(text) => {
      const norm=s=>s.replace(/\s+/g,' ').trim();
      const wanted=norm(text);
      const body=[...document.querySelectorAll('.se-component:not(.se-documentTitle) .se-text-paragraph')];
      const sel=document.getSelection(); const f=sel&&sel.focusNode;
      const near=f&&(f.nodeType===1?f:f.parentElement);
      let p=near&&near.closest('.se-text-paragraph');
      if(!p||!body.includes(p)) p=[...body].reverse().find(q=>norm(q.textContent).endsWith(wanted));
      if(!p) return 0;
      // ← 는 **보이는 자리** 단위로 움직인다. DOM 에는 공백 두 칸이 그대로 있어도 캐럿은
      // 한 번에 지나간다 — 그래서 '세는 단위'도 보이는 글자여야 한다(nbsp 는 한 자리를
      // 차지하므로 합치지 않는다).
      const visual=s=>s.replace(/[^\S\u00a0]+/g, ' ').length;
      const full=p.textContent;
      for(let n=1;n<=full.length;n++){
        const tail=full.slice(full.length-n);
        if(norm(tail)===wanted) return visual(tail);
        if(norm(tail).length>wanted.length+6) break;    // 지나쳤다
      }
      return 0;
    }'''

TOGGLES = [('b','bold','Control+b','굵게'), ('i','italic','Control+i','기울임'), ('u','underline','Control+u','밑줄')]
FIX_MAX_CHARS = 400     # 이보다 긴 조각은 한 글자씩 골라 고치지 않는다(너무 오래 걸린다)


async def _read_back(frame, text):
    # 편집기가 화면에 반영하기 전에 읽으면 없는 것처럼 보인다 — 한 번 더 기다려 본다.
    actual = None
    for wait in (.15, .5):
        await asyncio.sleep(wait)
        actual = await frame.evaluate(READ_BACK, text)
        if actual:
            break
    return actual


async def _refocus(editor, frame, index):
    """글자가 본문에 안 들어갔다 — 캐럿을 놓쳤다. 쓰던 문단 끝을 다시 눌러 캐럿을 되돌린다.

    2026-10-21 실측(platonmarketing): '작성 중인 글이 있습니다' 창을 닫은 직후 편집기가 다시
    그려지며 캐럿이 빠졌고, 그 뒤로 친 글자는 어디에도 들어가지 않았다. 고객 화면의
    '입력한 강조 문구가 본문에 표시되지 않았습니다'가 이 모양이다."""
    point = await frame.evaluate(END_POINT, index) if index >= 0 else None
    if not point:
        await editor._refocus_body_end()
        return
    dx = dy = 0
    if frame != editor.page.main_frame:
        holder = await frame.frame_element()
        box = await holder.bounding_box()
        if box:
            dx, dy = box['x'], box['y']
    await editor.page.mouse.click(point['x'] + dx, point['y'] + dy)
    await asyncio.sleep(.25)
    await editor.page.keyboard.press('End')
    await asyncio.sleep(.1)


def _wrong_toggles(attrs, actual, in_quote):
    wrong = []
    for key, prop, shortcut, label in TOGGLES:
        if any(bool(attrs.get(key)) != s[prop] and not (s.get('quote') and not attrs.get(key)) for s in actual):
            wrong.append((key, prop, shortcut, label))
    return wrong


async def _has_selection(frame):
    """지금 고른 글자가 있나. 못 읽으면 '없다'로 친다(없는 쪽이 안전하다)."""
    try:
        return bool(await frame.evaluate(
            "() => { const s = document.getSelection(); return !!(s && String(s).length); }"))
    except Exception:       # noqa: BLE001
        return False


async def _fix_toggles(editor, frame, text, attrs, actual, in_quote):
    """방금 넣은 글자의 굵게·기울임·밑줄이 틀렸으면, 그 글자만 뒤로 골라 단축키로 고친다.

    툴바 단추 모양만 믿고 치면, 단추가 늦게 바뀌거나 선택창이 닫힌 자리에서 서식이 거꾸로
    들어간다(2026-10-20·21 위례·kibundang). 고친 뒤에는 다시 읽어 확인하고 돌려준다 —
    그래도 틀리면 아래 확인이 막는다."""
    wrong = _wrong_toggles(attrs, actual, in_quote)
    if not wrong or len(text) > FIX_MAX_CHARS:
        return actual
    keyboard = editor.page.keyboard
    # **보낸 글자 수가 아니라 화면에 찍힌 글자 수**만큼 고른다. 편집기가 공백을 합치면 그
    # 차이만큼 앞 문구까지 골라져, 고치려던 문구가 되레 뒤집힌다(2026-10-22 실측).
    try:
        picked = int(await frame.evaluate(TAIL_LEN, text) or 0)
    except Exception:       # noqa: BLE001
        picked = 0
    if not picked:
        picked = len(text)
    elif picked != len(text):
        log.info('고를 글자 수를 화면 기준으로 맞춥니다: 보낸 %d자 → 화면 %d자', len(text), picked)
    for key, prop, shortcut, label in wrong:
        for _ in range(2):          # 섞여 있으면 첫 번째 누름에 '전부 켜짐'이 될 수 있다
            log.warning('"%s" 의 %s 이(가) 요청과 달라 글자를 골라 고칩니다', text.strip()[:20], label)
            # Shift 를 **누른 채로** ← 를 친다. 'Shift+ArrowLeft' 를 따로따로 누르면 네이버가 매번
            # 고르기를 새로 시작해 한 글자만 골라진다(2026-10-21 실측: '굵은 문구' 중 '구'만 굵어졌다).
            await keyboard.down('Shift')
            try:
                for _ in range(picked):
                    await keyboard.press('ArrowLeft')
            finally:
                await keyboard.up('Shift')
            await asyncio.sleep(.05)
            await keyboard.press(shortcut)
            await asyncio.sleep(.1)
            # **고른 것이 있을 때만** 푼다. 빈 선택에서 ArrowRight 는 '푸는' 게 아니라
            # 한 칸 앞으로 가고, 문단 끝이면 **다음 문단으로 넘어간다** — 그러면 뒤따르는
            # 글이 엉뚱한 문단에 끼어든다(2026-10-22 실측, 고객 화면의 섞인 글이 이것이다).
            if await _has_selection(frame):
                await keyboard.press('ArrowRight')      # 고른 것을 풀고 캐럿을 글 끝으로
            actual = await _read_back(frame, text) or actual
            if not any(k == key for k, *_ in _wrong_toggles(attrs, actual, in_quote)):
                break
    return actual


async def styled_text(editor, text, attrs=None, *, in_quote=False):
    """Set the native typing style, insert text, then read the rendered run back.

    SmartEditor uses a hidden input iframe and its own selection model. DOM
    selection is not the editor selection, so styling selected DOM text is unsafe.
    """
    attrs = attrs or {}
    if not text:
        return
    # 공백만 있는 조각(워드가 남긴 빈칸)은 눈에 보이는 서식이 없다. 확인을 요구하면
    # 글 전체가 '강조 문구가 본문에 표시되지 않았습니다'로 막힌다(2026-09-28 실측).
    verify = bool(text.strip())
    frame = await editor.frame()
    from naver_editor import EditorError
    unsure = []         # 단추 모양으로는 들어갔는지 확인하지 못한 서식
    for key, name, shortcut, label in [('b','bold','Control+b','굵게'),
                                       ('i','italic','Control+i','기울임'),
                                       ('u','underline','Control+u','밑줄')]:
        button = frame.locator(f'button[data-name="{name}"]')
        selected = await toggled(button)
        wanted = bool(attrs.get(key))
        if selected is None:
            # 단추를 아예 못 읽었다(덮였거나 네이버가 화면을 바꿨다). 찍어 누르면 서식이
            # 거꾸로 들어간다 — 그냥 치고 나서 읽어 보고 고친다.
            unsure.append(label)
            continue
        if wanted == selected:
            continue
        await editor.page.keyboard.press(shortcut)
        if await toggle_changed(button, selected):
            continue
        # 단축키가 먹었는지 단추 모양으로 확인하지 못했다. 다시 누르면 서식이 거꾸로 들어갈 수
        # 있다(2026-10-20). 선택창이 떠 있으면 치우고 한 번 더 보되, 그래도 모르면 **누르지 않고**
        # 넣은 뒤 읽어 보고 고친다(아래 _fix_toggles). 2026-10-21 위례 원고: 링크 카드 뒤에
        # 글감 창이 떠 있다가 닫힌 자리에서 "기울임을 빼 달라고 했는데 편집기에는 그렇게
        # 들어가지 않았습니다"로 글 한 건이 또 막혔다.
        if await blocked(editor):
            await unblock(editor, f'{label} 서식')
            if await toggle_changed(button, not wanted):
                continue
        unsure.append(label)
    if unsure:
        # 붙여 넣지 않고 그대로 친 뒤, 틀린 서식만 글자를 골라 고친다(아래 _fix_toggles).
        # 1.7.8 은 여기서 서식을 입혀 붙여 넣었는데, 선택창을 치운 자리에서는 붙여넣기가
        # 본문에 들어가지 않아 "입력한 강조 문구가 본문에 표시되지 않았습니다"로 글이 또
        # 막혔다(2026-10-21 kibundang).
        log.warning('%s 서식이 툴바에 반영됐는지 확인하지 못했습니다 — 넣은 뒤 읽어 보고 고칩니다: "%s"',
                    '·'.join(unsure), text.strip()[:20])
    paste_needed = False
    colorless = False   # 색을 못 입히고 글자만 넣었다 — 색 확인은 건너뛴다
    for key, name, default in [('color','font-color','#000000'),('background','background-color','#ffffff')]:
        if in_quote and key == 'background' and not attrs.get(key):
            continue
        desired = attrs.get(key) or default
        indicator = frame.locator(f'button[data-name="{name}"] [data-role="color"]')
        if not await indicator.count():
            if attrs.get(key):
                # 사진·링크 카드 바로 뒤처럼 색 툴바가 없는 자리가 있다. 글을 버리지 말고
                # 색을 입힌 채로 붙여 넣는다(2026-10-20).
                log.warning('%s 툴바가 없는 자리입니다 — 색을 입힌 채 붙여 넣습니다: "%s"',
                            name, text.strip()[:20])
                paste_needed = True
            continue
        current = await indicator.evaluate('e => getComputedStyle(e).backgroundColor')
        if current != rgb(desired):
            if not await set_color(editor,desired,key == 'background'):
                paste_needed = True
    caret = await frame.evaluate(CARET_AT)
    before = await frame.evaluate(BODY_LEN)
    if paste_needed:
        if sys.platform != 'win32':
            raise EditorError('사용자 지정 Word 색상은 Windows 실행기에서 지원합니다')
        from html_clipboard import temporary_html
        style = ['font-weight:'+('bold' if attrs.get('b') else 'normal'),
                 'font-style:'+('italic' if attrs.get('i') else 'normal'),
                 'text-decoration:'+('underline' if attrs.get('u') else 'none')]
        for key,css in [('color','color'),('background','background-color')]:
            if attrs.get(key):
                rgb(attrs[key])
                style.append(css+':'+attrs[key])
        fragment='<span style="'+ ';'.join(style)+'">'+html.escape(text)+'</span>'
        await frame.locator('iframe[id^="input_buffer"]').evaluate('e => e.contentWindow.focus()')
        with temporary_html(fragment,text):
            await editor.page.keyboard.press('Control+v')
            await asyncio.sleep(.5)
    else:
        await editor._insert(text)
    actual = await _read_back(frame, text)
    if not actual and await frame.evaluate(BODY_LEN) == before:
        # 아무 글자도 안 들어갔다(캐럿을 놓쳤거나 붙여넣기가 안 먹었다). 쓰던 자리를 다시 눌러
        # 글자로 친다 — 색은 못 입혀도 글은 올린다. 글자가 **어딘가 들어갔으면** 또 치지 않는다
        # (두 번 들어간다) — 그때는 아래 확인이 막는다.
        log.warning('글자가 본문에 들어가지 않았습니다 — 쓰던 자리를 다시 눌러 칩니다: "%s"', text.strip()[:20])
        await _refocus(editor, frame, caret)
        await editor._insert(text)
        actual = await _read_back(frame, text)
        colorless = paste_needed
    if verify and actual:
        actual = await _fix_toggles(editor, frame, text, attrs, actual, in_quote)
    if not verify:
        return
    if not actual:
        raise EditorError('입력한 강조 문구가 본문에 표시되지 않았습니다')
    # 어디가 틀렸는지 못 적으면, 받는 사람은 원고 어디를 고쳐야 하는지 알 수 없다 —
    # 화면에는 이 문장이 그대로 '손봐야 할 글'의 이유로 뜬다(2026-10-02).
    # **여기서 글을 막지 않는다.** 글자는 다 들어갔고 모양만 다른 것이다. 막으면 다 쓴 원고를
    # 통째로 버리고 다음 차례에 처음부터 다시 쓴다 — 사람 눈에는 작업이 삭제되는 것으로 보인다.
    # 2026-10-22 요청: "오류 뜨는 부분은 넘어가면서 예약발행 / 임시저장 되게 … 오류 뜬 부분은
    # 저희가 수기로 고쳐서 바로 발행 걸겠습니다". 그래서 적어만 두고 올린다
    # (발행 결과에 '서식 N곳 확인 필요'로 따라붙는다).
    where = text.strip()[:30]
    for style in actual:
        if style.get('quote') != in_quote:
            note_problem(editor, f'"{where}" — 인용구 위치가 요청과 다릅니다')
        for key, prop, name in [('b','bold','굵게'),('i','italic','기울임'),('u','underline','밑줄')]:
            if bool(attrs.get(key)) != style[prop] and not (style.get('quote') and not attrs.get(key)):
                asked = '넣어 달라고' if attrs.get(key) else '빼 달라고'
                note_problem(editor, f'"{where}" — {name}을(를) {asked} 했는데 그대로 들어가지 않았습니다')
        for key in ('color','background'):
            if attrs.get(key) and style[key] != rgb(attrs[key]) and not colorless:
                note_problem(editor, f'"{where}" — {key} 색이 요청과 다릅니다')


async def insert_rich_blocks(editor, blocks):
    from naver_editor import EditorError, S
    await editor._click_paragraph(S['body_para'])
    if getattr(editor, 'keep_tail', False):
        # 불러온 템플릿을 지우지 않는다 — 원고는 그 위에 쓴다.
        await editor.page.keyboard.press('Control+Home')
    else:
        await editor._ctrl_a()
    images = 0
    carded = False          # 바로 앞이 링크 카드였나 — 카드는 자기 뒤에 빈 문단을 하나 남긴다
    for index, block in enumerate(blocks):
        kind = block.get('type')
        if index:
            if carded:
                carded = False      # 카드가 남긴 빈 문단이 줄바꿈 하나를 대신한다
            else:
                await editor._enter()
            if kind != 'image' and blocks[index-1].get('type') != 'image':
                await editor._enter()
        if kind == 'image':
            await editor._insert_image_verified(block['image'],index=images)
            images += 1
            await editor.center_last_image()      # 사진만 가운데로. 글자는 그대로 둔다.
            await editor._refocus_body_end()
            continue
        if kind == 'table':
            await insert_table(editor,block)
            continue
        # 주소만 있는 줄은 카드로 세운다(글 끝의 홈페이지·플레이스 주소가 이 모양이다).
        # 카드가 안 되면 주소 글자로 되돌린다 — 글이 통째로 안 나가는 것보다 낫다.
        from plan import is_bare_url
        url = (block.get('content') or '').strip()
        if kind == 'text' and is_bare_url(url):
            carded = await editor.insert_url_card(url)
            if not carded:
                await editor._insert(url)
            continue
        if kind == 'quote':
            frame = await editor.frame()
            # 못 누르면 여기서 멈춘다. 그냥 진행하면 **앞에 있던 인용구**에 글이 들어가고,
            # 확인은 '인용구 안에 있다'만 보므로 엉뚱한 자리에 박힌 채 통과한다.
            if not await press_toolbar(editor, frame.locator('button[data-name="quotation"][data-value="default"]'), '인용구'):
                raise EditorError('인용구 단추를 누르지 못했습니다 — 네이버 선택창이 떠 있는지 확인해 주세요')
            quote = frame.locator('.se-component.se-quotation').last.locator('.se-quote .se-text-paragraph').first
            await quote.click()
            await asyncio.sleep(.3)
        groups = block.get('items') if kind == 'list' else [block.get('spans') or [{'t':block.get('content','')}]]
        for number, spans in enumerate(groups or []):
            if number:
                await editor._enter()
            if kind == 'list':
                await editor._insert(f'{number+1}. ' if block.get('ordered') else '• ')
            for span in spans:
                attrs = dict(span)
                if kind == 'heading':
                    attrs['b'] = True
                for line_index, line in enumerate(span.get('t','').split('\n')):
                    if line_index:
                        await editor._enter()
                    await styled_text(editor,line,attrs,in_quote=kind == 'quote')
        if kind == 'quote':
            frame = await editor.frame()
            text = ''.join(s.get('t','') for s in (block.get('spans') or [])) or block.get('content','')
            if not await frame.locator('.se-component.se-quotation').filter(has_text=text).count():
                raise EditorError('네이버 인용구 컴포넌트에서 핵심 문장을 확인하지 못했습니다')
            await exit_component(editor)
    return images


async def insert_table(editor, block):
    """Paste a native table and verify every row, column and cell before proceeding."""
    from naver_editor import EditorError
    rows = block.get('rows') or []
    columns = max((len(row) for row in rows),default=0)
    if not rows or not columns or len(rows) > 50 or columns > 10:
        raise EditorError('자동 발행 표는 1~50행, 1~10열이어야 합니다')
    frame = await editor.frame()
    if sys.platform == 'win32':
        from html_clipboard import temporary_html
        def cell_html(spans):
            pieces=[]
            for span in spans:
                styles=[]
                for key,css in [('color','color'),('background','background-color')]:
                    if span.get(key):
                        rgb(span[key]);styles.append(css+':'+span[key])
                if span.get('b'):styles.append('font-weight:bold')
                if span.get('i'):styles.append('font-style:italic')
                if span.get('u'):styles.append('text-decoration:underline')
                content=html.escape(span.get('t','')).replace('\n','<br>')
                for key,tag in [('b','b'),('i','i'),('u','u')]:
                    if span.get(key):content=f'<{tag}>'+content+f'</{tag}>'
                pieces.append('<span style="'+';'.join(styles)+'">'+content+'</span>')
            return '<td style="border:1px solid #777;padding:8px"><p>'+''.join(pieces)+'</p></td>'
        fragment='<table style="border-collapse:collapse;width:100%"><tbody>'+''.join('<tr>'+''.join(cell_html(cell) for cell in row)+''.join('<td></td>' for _ in range(columns-len(row)))+'</tr>' for row in rows)+'</tbody></table>'
        plain='\n'.join('\t'.join(''.join(s.get('t','') for s in cell) for cell in row) for row in rows)
        count=await frame.locator('.se-component.se-table').count()
        with temporary_html(fragment,plain):
            await editor.page.keyboard.press('Control+v')
            for _ in range(30):
                await asyncio.sleep(.1)
                if await frame.locator('.se-component.se-table').count()>count:
                    break
        table=frame.locator('.se-component.se-table').last
        if await frame.locator('.se-component.se-table').count()!=count+1 or await table.locator('tbody > tr').count()!=len(rows):
            raise EditorError('Word 표 붙여넣기 결과의 행 개수가 일치하지 않습니다')
        for r,row in enumerate(rows):
            cells=table.locator('tbody > tr').nth(r).locator('td')
            if await cells.count()!=columns:
                raise EditorError('Word 표 붙여넣기 결과의 열 개수가 일치하지 않습니다')
            for c,spans in enumerate(row):
                actual=(await cells.nth(c).inner_text()).replace('\u200b','').strip()
                expected=''.join(s.get('t','') for s in spans).strip()
                if actual!=expected:raise EditorError(f'표 {r+1}행 {c+1}열 내용이 일치하지 않습니다')
        await exit_component(editor)
        return
    raise EditorError('Word 표 서식은 Windows 실행기에서 지원합니다')


async def exit_component(editor):
    frame=await editor.frame()
    last=frame.locator('.se-components-wrap > .se-component').last
    if 'se-text' not in (await last.get_attribute('class') or '').split():
        bottom=frame.locator('button.se-canvas-bottom-button')
        if await bottom.is_visible():
            await bottom.click()
        else:
            # A pasted table can already have a following empty paragraph.
            await editor.page.keyboard.press('Control+End')
            await editor.page.keyboard.press('ArrowDown')
            await editor.page.keyboard.press('Enter')
        for _ in range(20):
            if 'se-text' in (await last.get_attribute('class') or '').split():
                break
            await asyncio.sleep(.1)
    from naver_editor import S, EditorError
    if 'se-text' not in (await last.get_attribute('class') or '').split():
        raise EditorError('인용구/표 뒤의 일반 본문을 만들지 못했습니다')
    await editor._click_paragraph(S['body_para'],last=True)
    await editor.page.keyboard.press('Control+End')
