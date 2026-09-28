"""Windows HTML paste with preservation of the user's clipboard formats."""
import ctypes
from ctypes import wintypes
from contextlib import contextmanager
import time


def cf_html(fragment):
    header = 'Version:0.9\r\nStartHTML:{:010d}\r\nEndHTML:{:010d}\r\nStartFragment:{:010d}\r\nEndFragment:{:010d}\r\n'
    before = b'<html><body><!--StartFragment-->'
    after = b'<!--EndFragment--></body></html>'
    data = fragment.encode('utf8')
    start = len(header.format(0,0,0,0).encode('ascii'))
    return header.format(start,start+len(before)+len(data)+len(after),start+len(before),start+len(before)+len(data)).encode('ascii') + before + data + after + b'\0'


@contextmanager
def temporary_html(fragment, plain):
    user = ctypes.WinDLL('user32',use_last_error=True)
    kernel = ctypes.WinDLL('kernel32',use_last_error=True)
    ole = ctypes.WinDLL('ole32',use_last_error=True)
    for name, restype, args in (
        ('GetClipboardData',wintypes.HANDLE,[wintypes.UINT]),
        ('SetClipboardData',wintypes.HANDLE,[wintypes.UINT,wintypes.HANDLE]),
        ('OpenClipboard',wintypes.BOOL,[wintypes.HWND]),
        ('RegisterClipboardFormatW',wintypes.UINT,[wintypes.LPCWSTR]),
    ):
        fn=getattr(user,name);fn.restype=restype;fn.argtypes=args
    kernel.GlobalAlloc.restype=wintypes.HGLOBAL;kernel.GlobalAlloc.argtypes=[wintypes.UINT,ctypes.c_size_t]
    kernel.GlobalLock.restype=ctypes.c_void_p;kernel.GlobalLock.argtypes=[wintypes.HGLOBAL]
    kernel.GlobalUnlock.argtypes=[wintypes.HGLOBAL]
    kernel.GlobalFree.argtypes=[wintypes.HGLOBAL]
    ole.OleDuplicateData.restype=wintypes.HANDLE
    ole.OleDuplicateData.argtypes=[wintypes.HANDLE,wintypes.UINT,wintypes.UINT]

    def open_clipboard():
        for _ in range(20):
            if user.OpenClipboard(None): return
            time.sleep(.025)
        raise RuntimeError('클립보드 사용 중입니다. 잠시 후 다시 시도하세요')

    def release(fmt, handle):
        if fmt in (2,9,0x82):
            gdi=ctypes.WinDLL('gdi32');gdi.DeleteObject.argtypes=[wintypes.HANDLE];gdi.DeleteObject(handle)
        elif fmt in (14,0x8e):
            gdi=ctypes.WinDLL('gdi32');gdi.DeleteEnhMetaFile.argtypes=[wintypes.HANDLE];gdi.DeleteEnhMetaFile(handle)
        else:
            kernel.GlobalFree(handle)

    def put(fmt, data):
        handle=kernel.GlobalAlloc(0x42,len(data))
        address=kernel.GlobalLock(handle)
        if not address: raise RuntimeError('클립보드 메모리 확보 실패')
        ctypes.memmove(address,data,len(data));kernel.GlobalUnlock(handle)
        if not user.SetClipboardData(fmt,handle):
            kernel.GlobalFree(handle)
            raise RuntimeError('HTML 클립보드 기록 실패')

    saved=[]; changed=False; sequence=None; kept_all=True
    try:
        open_clipboard()
        try:
            fmt=0
            while True:
                fmt=user.EnumClipboardFormats(fmt)
                if not fmt: break
                # 복제할 수 없는 형식(메타파일·소유자 그림·다른 앱이 늦게 그려 주는 형식)은
                # 되돌려 주지 못한다. 그렇다고 발행을 포기하면 예약한 글을 잃는다 —
                # 남의 클립보드보다 글이 올라가는 것이 먼저다(2026-09-28 실패 1건).
                if fmt in (3,0x83,0x80):
                    kept_all=False
                    continue
                original=user.GetClipboardData(fmt)
                duplicate=ole.OleDuplicateData(original,fmt,0) if original else None
                if not duplicate:
                    kept_all=False
                    continue
                saved.append((fmt,duplicate))
            user.EmptyClipboard();changed=True
            put(user.RegisterClipboardFormatW('HTML Format'),cf_html(fragment))
            put(13,plain.encode('utf-16-le')+b'\0\0')
            sequence=user.GetClipboardSequenceNumber()
        finally:
            user.CloseClipboard()
        if not kept_all:
            import logging
            logging.getLogger(__name__).info(
                '복사해 두신 내용 중 되돌릴 수 없는 형식이 있어 클립보드가 바뀔 수 있습니다(발행은 계속합니다)')
        yield
    finally:
        if changed:
            open_clipboard()
            try:
                if sequence is None or user.GetClipboardSequenceNumber()==sequence:
                    user.EmptyClipboard()
                    restored=[]
                    for fmt,handle in saved:
                        if user.SetClipboardData(fmt,handle):restored.append((fmt,handle))
                    saved=[item for item in saved if item not in restored]
            finally:
                user.CloseClipboard()
        for fmt,handle in saved:release(fmt,handle)
