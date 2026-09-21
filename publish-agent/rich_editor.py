"""Native SmartEditor toolbar formatting with DOM read-back before publication."""
import asyncio
import re
import html
import sys


def rgb(hex_color):
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', hex_color or ''):
        raise ValueError('잘못된 강조 색상입니다')
    return 'rgb(%d, %d, %d)' % tuple(int(hex_color[i:i+2],16) for i in (1,3,5))


async def set_color(editor, color, background=False):
    frame = await editor.frame()
    name = '글자 배경색 변경' if background else '글자색 변경'
    await frame.locator('button[data-name="background-color"]' if background else 'button[data-name="font-color"]').click()
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
        await frame.locator('button[data-name="background-color"]' if background else 'button[data-name="font-color"]').click()
        await editor.page.keyboard.press('Escape')
        return False
    await asyncio.sleep(.1)
    return True


async def styled_text(editor, text, attrs=None, *, in_quote=False):
    """Set the native typing style, insert text, then read the rendered run back.

    SmartEditor uses a hidden input iframe and its own selection model. DOM
    selection is not the editor selection, so styling selected DOM text is unsafe.
    """
    attrs = attrs or {}
    if not text:
        return
    frame = await editor.frame()
    from naver_editor import EditorError
    for key, name, shortcut in [('b','bold','Control+b'),('i','italic','Control+i'),('u','underline','Control+u')]:
        button = frame.locator(f'button[data-name="{name}"]')
        selected = 'se-is-selected' in (await button.get_attribute('class') or '')
        if bool(attrs.get(key)) != selected:
            await editor.page.keyboard.press(shortcut)
    paste_needed = False
    for key, name, default in [('color','font-color','#000000'),('background','background-color','#ffffff')]:
        if in_quote and key == 'background' and not attrs.get(key):
            continue
        desired = attrs.get(key) or default
        indicator = frame.locator(f'button[data-name="{name}"] [data-role="color"]')
        if not await indicator.count():
            if attrs.get(key):
                raise EditorError(f'이 문단에서 {key} 서식을 적용할 수 없습니다')
            continue
        current = await indicator.evaluate('e => getComputedStyle(e).backgroundColor')
        if current != rgb(desired):
            if not await set_color(editor,desired,key == 'background'):
                paste_needed = True
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
    await asyncio.sleep(.15)
    actual = await frame.evaluate(r'''text => {
      const paragraphs=[...document.querySelectorAll('.se-component:not(.se-documentTitle) .se-text-paragraph')].reverse();
      const paragraph=paragraphs.find(p=>p.textContent.endsWith(text));
      if(!paragraph) return null;
      const start=paragraph.textContent.length-text.length;
      const walker=document.createTreeWalker(paragraph,NodeFilter.SHOW_TEXT);
      let node, offset=0; const styles=[];
      while((node=walker.nextNode())){
        const end=offset+node.length;
        if(end>start && node.length){
          const s=getComputedStyle(node.parentElement);
          let bg=s.backgroundColor, parent=node.parentElement;
          while(bg==='rgba(0, 0, 0, 0)' && parent!==paragraph){parent=parent.parentElement;bg=getComputedStyle(parent).backgroundColor;}
          const under=node.parentElement.closest('u');
          styles.push({quote:!!paragraph.closest('.se-quotation'),bold:parseInt(s.fontWeight)>=600,italic:s.fontStyle==='italic',
            underline:!!under||s.textDecorationLine.includes('underline'),color:s.color,background:bg});
        }
        offset=end;
      }
      return styles;
    }''',text)
    if not actual:
        raise EditorError('입력한 강조 문구가 본문에 표시되지 않았습니다')
    for style in actual:
        if style.get('quote') != in_quote:
            raise EditorError('일반 본문과 인용구 위치가 요청한 구조와 다릅니다')
        for key, prop in [('b','bold'),('i','italic'),('u','underline')]:
            if bool(attrs.get(key)) != style[prop] and not (style.get('quote') and not attrs.get(key)):
                raise EditorError('문구의 굵기/기울임/밑줄 서식이 요청과 다릅니다')
        for key in ('color','background'):
            if attrs.get(key) and style[key] != rgb(attrs[key]):
                raise EditorError(f'{key} 적용 값이 요청한 색상과 다릅니다')


async def insert_rich_blocks(editor, blocks):
    from naver_editor import EditorError, S
    await editor._click_paragraph(S['body_para'])
    await editor._ctrl_a()
    images = 0
    for index, block in enumerate(blocks):
        kind = block.get('type')
        if index:
            await editor._enter()
            if kind != 'image' and blocks[index-1].get('type') != 'image':
                await editor._enter()
        if kind == 'image':
            await editor._insert_image_verified(block['image'],index=images)
            images += 1
            await editor._refocus_body_end()
            continue
        if kind == 'table':
            await insert_table(editor,block)
            continue
        if kind == 'quote':
            frame = await editor.frame()
            await frame.locator('button[data-name="quotation"][data-value="default"]').click()
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
