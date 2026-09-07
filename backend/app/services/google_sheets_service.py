"""
Google Sheets 연동 - 마케팅팀 '사용 키워드' 시트 읽기/쓰기.

마케팅팀은 이미 사용한 블로그/카페 키워드를 구글 시트의 탭("블로그", "카페" 등)에
기록한다. 이 모듈은 그 시트를 읽어 키워드 중복 여부를 확인하고, 필요하면
발행 결과(키워드, 날짜, 병원, 발행 URL)를 행으로 추가한다.

인증 경로는 두 가지:
- 읽기(자격증명 없음): 시트가 '링크가 있는 모든 사용자'에게 공개돼 있으면
  gviz CSV 내보내기 URL 로 그대로 읽는다. 별도 설정이 필요 없다.
- 읽기/쓰기(서비스 계정): settings.GOOGLE_SERVICE_ACCOUNT_JSON 또는
  GOOGLE_SERVICE_ACCOUNT_FILE 에 서비스 계정 키가 있으면 OAuth2 JWT bearer
  플로우로 access token 을 받아 Sheets API v4 를 호출한다. 외부 google 라이브러리
  없이 cryptography 로 RS256 서명만 직접 한다. 토큰은 모듈 메모리에 캐시하며
  만료 5분 전까지 재사용한다.

모든 실패는 SheetsError(한국어 메시지)로 감싼다. 메시지는 개발자가 아닌
마케터가 읽고 조치할 수 있는 문장이어야 한다.

search_volume_service.py 의 httpx 비동기 패턴을 따른다.
"""
import base64
import csv
import io
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from app.core.config import settings

logger = logging.getLogger(__name__)

# 네트워크 타임아웃(초). 시트가 크더라도 CSV 내보내기는 수 초 내에 끝난다.
TIMEOUT = 20.0

TOKEN_URL = "https://oauth2.googleapis.com/token"
SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
DOCS_BASE = "https://docs.google.com/spreadsheets/d"

# access token 만료 몇 초 전에 갱신할지.
TOKEN_REFRESH_MARGIN = 300

# 시트 ID: URL 의 /spreadsheets/d/<ID>/ 구간. 영숫자, '-', '_' 로만 구성된다.
_SHEET_ID_IN_URL = re.compile(r"/spreadsheets/(?:u/\d+/)?d/([A-Za-z0-9_-]+)")
# URL 없이 ID 만 넘어온 경우. 실제 ID 는 44자 안팎이지만 넉넉히 20자 이상으로 본다.
_BARE_SHEET_ID = re.compile(r"^[A-Za-z0-9_-]{20,}$")
_GID_IN_URL = re.compile(r"[#?&]gid=(\d+)")
_WHITESPACE = re.compile(r"\s+")


class SheetsError(Exception):
    """구글 시트 연동 실패. message 는 마케터가 읽고 조치할 수 있는 한국어 문장."""


# ---------------------------------------------------------------------------
# URL / 문자열 유틸
# ---------------------------------------------------------------------------

def parse_sheet_id(url_or_id: str) -> Optional[str]:
    """
    시트 URL 또는 ID 문자열에서 스프레드시트 ID 를 뽑는다.

    허용 형태:
    - https://docs.google.com/spreadsheets/d/<ID>/edit#gid=0
    - https://docs.google.com/spreadsheets/d/<ID>/edit?usp=sharing
    - https://docs.google.com/spreadsheets/u/1/d/<ID>/...
    - <ID> 만 단독으로
    알 수 없는 형태면 None.
    """
    s = (url_or_id or "").strip()
    if not s:
        return None
    m = _SHEET_ID_IN_URL.search(s)
    if m:
        return m.group(1)
    if _BARE_SHEET_ID.match(s):
        return s
    return None


def parse_gid(url: str) -> Optional[str]:
    """URL 에 gid=... 가 있으면 그 값(문자열), 없으면 None."""
    m = _GID_IN_URL.search(url or "")
    return m.group(1) if m else None


def normalize_keyword(text: str) -> str:
    """
    키워드 비교용 정규화: 모든 공백 제거 + 소문자.
    "임플란트 가격" == "임플란트가격" == "임플란트  가격 " 으로 본다.
    """
    return _WHITESPACE.sub("", text or "").lower()


def _require_sheet_id(sheet_url: str) -> str:
    sheet_id = parse_sheet_id(sheet_url)
    if not sheet_id:
        raise SheetsError(
            "구글 시트 주소를 인식할 수 없습니다. 브라우저 주소창의 시트 URL "
            "(https://docs.google.com/spreadsheets/d/... 형태)을 그대로 붙여넣어 주세요."
        )
    return sheet_id


def _a1_tab(tab: str) -> str:
    """A1 표기용 탭 이름 인용. 탭 이름 안의 작은따옴표는 두 번 써서 이스케이프한다."""
    return "'" + (tab or "").replace("'", "''") + "'"


def _strip_trailing_empty(rows: List[List[str]]) -> List[List[str]]:
    """끝에 붙은 완전히 빈 행은 제거한다(행 번호 안정성을 위해 중간 빈 행은 남긴다)."""
    end = len(rows)
    while end > 0 and not any(cell.strip() for cell in rows[end - 1]):
        end -= 1
    return rows[:end]


# ---------------------------------------------------------------------------
# 공개 시트 읽기 (자격증명 없음)
# ---------------------------------------------------------------------------

def _looks_like_csv(resp: httpx.Response) -> bool:
    """
    응답이 실제 CSV 인지. 비공개 시트는 로그인 페이지(HTML)로 리다이렉트되고,
    잘못된 탭 이름은 오류 HTML 이 오므로 content-type 과 최종 URL 로 걸러낸다.
    """
    if resp.status_code != 200:
        return False
    if "accounts.google.com" in str(resp.url):
        return False
    ctype = resp.headers.get("content-type", "").lower()
    if "text/csv" in ctype:
        return True
    if "html" in ctype or "json" in ctype or "javascript" in ctype:
        return False
    # content-type 이 모호하면 본문으로 판단.
    head = resp.content[:64].lstrip()
    return not head.startswith(b"<")


def _parse_csv(content: bytes) -> List[List[str]]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = [[cell for cell in row] for row in reader]
    return _strip_trailing_empty(rows)


async def _fetch_csv(client: httpx.AsyncClient, url: str) -> Optional[List[List[str]]]:
    """URL 에서 CSV 를 받아 파싱. CSV 가 아니거나 실패하면 None."""
    try:
        resp = await client.get(url)
    except httpx.TimeoutException:
        raise SheetsError(
            "구글 시트 응답이 20초 안에 오지 않았습니다. 잠시 후 다시 시도해 주세요."
        )
    except httpx.HTTPError as e:
        raise SheetsError(f"구글 시트에 연결하지 못했습니다. 네트워크 상태를 확인해 주세요. ({e})")
    if not _looks_like_csv(resp):
        logger.info(
            "sheets public csv rejected: status=%s ctype=%s url=%s",
            resp.status_code, resp.headers.get("content-type"), resp.url,
        )
        return None
    return _parse_csv(resp.content)


async def read_tab_public(sheet_url: str, tab: str) -> List[List[str]]:
    """
    '링크가 있는 모든 사용자' 공개 시트를 자격증명 없이 읽는다.

    1) gviz CSV: .../gviz/tq?tqx=out:csv&sheet=<탭> (탭 이름으로 지정)
    2) 폴백 export CSV: .../export?format=csv&gid=<gid>
       - gid 는 sheet_url 에 포함된 값만 쓴다. 탭 이름→gid 변환은 API 없이는
         불가능하므로, tab 이 비어 있을 때(=URL 에 열린 탭 그대로)만 사용한다.
    3) 둘 다 실패하면 원인을 진단해 SheetsError.
    """
    sheet_id = _require_sheet_id(sheet_url)
    tab = (tab or "").strip()

    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        if tab:
            gviz = (
                f"{DOCS_BASE}/{sheet_id}/gviz/tq?tqx=out:csv"
                f"&sheet={quote(tab, safe='')}"
            )
            rows = await _fetch_csv(client, gviz)
            if rows is not None:
                return rows
        else:
            gid = parse_gid(sheet_url) or "0"
            rows = await _fetch_csv(
                client, f"{DOCS_BASE}/{sheet_id}/export?format=csv&gid={gid}"
            )
            if rows is not None:
                return rows

        # 진단: 탭 이름 없이 첫 탭을 읽어 본다. 이게 되면 시트는 공개 상태이고
        # 탭 이름이 문제, 안 되면 시트 자체가 비공개.
        probe = await _fetch_csv(
            client, f"{DOCS_BASE}/{sheet_id}/gviz/tq?tqx=out:csv"
        )

    if probe is not None and tab:
        raise SheetsError(
            f"탭 이름을 찾을 수 없습니다: '{tab}'. 시트 하단의 탭 이름과 "
            "띄어쓰기까지 똑같이 입력했는지 확인해 주세요."
        )
    raise SheetsError(
        "구글 시트를 읽을 수 없습니다. 시트가 '링크가 있는 모든 사용자'에게 "
        "공개되어 있는지 확인하세요. (공유 > 일반 액세스 > '링크가 있는 모든 사용자' > 뷰어)"
    )


# ---------------------------------------------------------------------------
# 서비스 계정 인증 (OAuth2 JWT bearer, RS256)
# ---------------------------------------------------------------------------

_sa_cache: Dict[str, Any] = {"key": None, "info": None}
_token_cache: Dict[str, Any] = {"token": None, "expires_at": 0.0}


def _load_service_account() -> Optional[Dict[str, Any]]:
    """
    설정에서 서비스 계정 키 JSON 을 로드한다. JSON 문자열이 우선, 없으면 파일.
    같은 설정값이면 파싱 결과를 재사용한다. 둘 다 비어 있으면 None.
    """
    raw = (settings.GOOGLE_SERVICE_ACCOUNT_JSON or "").strip()
    path = (settings.GOOGLE_SERVICE_ACCOUNT_FILE or "").strip()
    cache_key = ("json", raw) if raw else ("file", path)
    if _sa_cache["key"] == cache_key:
        return _sa_cache["info"]

    info: Optional[Dict[str, Any]] = None
    if raw:
        try:
            info = json.loads(raw)
        except ValueError:
            raise SheetsError(
                "GOOGLE_SERVICE_ACCOUNT_JSON 값이 올바른 JSON 이 아닙니다. "
                "구글 클라우드에서 내려받은 서비스 계정 키 파일 내용을 그대로 넣어 주세요."
            )
    elif path:
        p = Path(path)
        if not p.is_file():
            raise SheetsError(
                f"서비스 계정 키 파일을 찾을 수 없습니다: {path}. "
                "GOOGLE_SERVICE_ACCOUNT_FILE 경로를 확인해 주세요."
            )
        try:
            info = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            raise SheetsError(
                f"서비스 계정 키 파일이 올바른 JSON 이 아닙니다: {path}"
            )

    if info is not None:
        missing = [k for k in ("client_email", "private_key") if not info.get(k)]
        if missing:
            raise SheetsError(
                "서비스 계정 키에 필요한 항목이 없습니다: " + ", ".join(missing)
                + ". 구글 클라우드 콘솔에서 '키 > 새 키 만들기(JSON)'로 다시 내려받아 주세요."
            )

    _sa_cache["key"] = cache_key
    _sa_cache["info"] = info
    return info


def is_write_configured() -> bool:
    """서비스 계정 키가 설정되어 있는지(= 행 추가/비공개 시트 읽기 가능 여부)."""
    try:
        return _load_service_account() is not None
    except SheetsError:
        # 설정은 돼 있으나 잘못된 경우. 실제 호출 시 상세 메시지로 실패한다.
        return bool(
            (settings.GOOGLE_SERVICE_ACCOUNT_JSON or "").strip()
            or (settings.GOOGLE_SERVICE_ACCOUNT_FILE or "").strip()
        )


def service_account_email() -> Optional[str]:
    """시트에 공유해야 하는 서비스 계정 이메일. 안내 문구용."""
    try:
        info = _load_service_account()
    except SheetsError:
        return None
    return info.get("client_email") if info else None


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def make_jwt(info: Dict[str, Any], now: Optional[int] = None) -> str:
    """
    서비스 계정 키로 서명한 OAuth2 assertion JWT(RS256).
    iss=client_email, scope=spreadsheets, aud=token endpoint, exp=now+3600.
    """
    now = int(now if now is not None else time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {
        "iss": info["client_email"],
        "scope": SHEETS_SCOPE,
        "aud": TOKEN_URL,
        "iat": now,
        "exp": now + 3600,
    }
    signing_input = (
        _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        + "."
        + _b64url(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
    )
    try:
        private_key = serialization.load_pem_private_key(
            info["private_key"].encode("utf-8"), password=None
        )
    except (ValueError, TypeError) as e:
        raise SheetsError(
            f"서비스 계정 키의 private_key 를 읽을 수 없습니다. 키 파일을 다시 내려받아 주세요. ({e})"
        )
    signature = private_key.sign(
        signing_input.encode("ascii"), padding.PKCS1v15(), hashes.SHA256()
    )
    return signing_input + "." + _b64url(signature)


async def _get_access_token() -> str:
    """
    캐시된 access token 을 돌려주거나, 만료 5분 전이면 새로 발급한다.
    """
    if _token_cache["token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["token"]

    info = _load_service_account()
    if info is None:
        raise SheetsError(
            "구글 서비스 계정이 설정되어 있지 않습니다. 시트에 쓰려면 "
            "GOOGLE_SERVICE_ACCOUNT_JSON 또는 GOOGLE_SERVICE_ACCOUNT_FILE 을 설정해 주세요."
        )

    assertion = make_jwt(info)
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(TOKEN_URL, data=data)
    except httpx.TimeoutException:
        raise SheetsError("구글 인증 서버 응답이 20초 안에 오지 않았습니다. 잠시 후 다시 시도해 주세요.")
    except httpx.HTTPError as e:
        raise SheetsError(f"구글 인증 서버에 연결하지 못했습니다. 네트워크 상태를 확인해 주세요. ({e})")

    if resp.status_code != 200:
        detail = ""
        try:
            detail = resp.json().get("error_description") or resp.json().get("error") or ""
        except ValueError:
            detail = resp.text[:200]
        logger.warning("google token exchange failed: %s %s", resp.status_code, detail)
        raise SheetsError(
            "구글 서비스 계정 인증에 실패했습니다. 키 파일이 삭제되었거나 만료되지 "
            f"않았는지 확인해 주세요. ({detail or resp.status_code})"
        )

    body = resp.json()
    token = body.get("access_token")
    if not token:
        raise SheetsError("구글 인증 서버가 access token 을 돌려주지 않았습니다. 잠시 후 다시 시도해 주세요.")
    expires_in = int(body.get("expires_in") or 3600)
    _token_cache["token"] = token
    _token_cache["expires_at"] = time.time() + expires_in - TOKEN_REFRESH_MARGIN
    return token


def _clear_token_cache() -> None:
    _token_cache["token"] = None
    _token_cache["expires_at"] = 0.0


def _api_error(resp: httpx.Response, tab: str) -> SheetsError:
    """Sheets API 오류 응답 → 마케터가 조치할 수 있는 한국어 메시지."""
    message = ""
    try:
        message = (resp.json().get("error") or {}).get("message") or ""
    except ValueError:
        message = resp.text[:200]
    logger.warning("sheets api error: %s %s", resp.status_code, message)

    email = service_account_email() or "서비스 계정 이메일"
    if resp.status_code == 403:
        return SheetsError(
            f"시트에 접근 권한이 없습니다. 시트 공유 설정에서 '{email}' 을(를) "
            "'편집자'로 추가했는지 확인하세요."
        )
    if resp.status_code == 404:
        return SheetsError(
            "시트를 찾을 수 없습니다. 시트 URL 이 정확한지, 시트가 삭제되지 않았는지 확인해 주세요."
        )
    if resp.status_code == 400 and "range" in message.lower():
        return SheetsError(
            f"탭 이름을 찾을 수 없습니다: '{tab}'. 시트 하단의 탭 이름과 "
            "띄어쓰기까지 똑같이 입력했는지 확인해 주세요."
        )
    if resp.status_code == 401:
        return SheetsError("구글 인증이 만료되었습니다. 다시 시도해 주세요.")
    if resp.status_code == 429:
        return SheetsError("구글 시트 요청 한도를 초과했습니다. 1분 뒤 다시 시도해 주세요.")
    return SheetsError(f"구글 시트 요청이 실패했습니다. ({resp.status_code}: {message or '알 수 없는 오류'})")


async def _sheets_request(
    method: str, url: str, tab: str, **kwargs: Any
) -> Dict[str, Any]:
    """access token 을 붙여 Sheets API 호출. 401 이면 토큰을 버리고 한 번 재시도."""
    for attempt in (1, 2):
        token = await _get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.request(method, url, headers=headers, **kwargs)
        except httpx.TimeoutException:
            raise SheetsError("구글 시트 응답이 20초 안에 오지 않았습니다. 잠시 후 다시 시도해 주세요.")
        except httpx.HTTPError as e:
            raise SheetsError(f"구글 시트에 연결하지 못했습니다. 네트워크 상태를 확인해 주세요. ({e})")

        if resp.status_code == 401 and attempt == 1:
            _clear_token_cache()
            continue
        if resp.status_code != 200:
            raise _api_error(resp, tab)
        try:
            return resp.json()
        except ValueError:
            raise SheetsError("구글 시트 응답을 해석할 수 없습니다. 잠시 후 다시 시도해 주세요.")
    raise SheetsError("구글 인증이 만료되었습니다. 다시 시도해 주세요.")  # unreachable


async def read_tab_authenticated(sheet_url: str, tab: str) -> List[List[str]]:
    """
    서비스 계정으로 탭 전체를 읽는다 (values:get).
    시트가 서비스 계정 이메일에 공유돼 있어야 한다(뷰어 이상).
    """
    sheet_id = _require_sheet_id(sheet_url)
    tab = (tab or "").strip()
    if not tab:
        raise SheetsError("읽을 탭 이름을 입력해 주세요. (예: 블로그)")
    url = f"{SHEETS_API}/{sheet_id}/values/{quote(_a1_tab(tab), safe='')}"
    body = await _sheets_request("GET", url, tab)
    values = body.get("values") or []
    rows = [["" if c is None else str(c) for c in row] for row in values]
    return _strip_trailing_empty(rows)


async def append_rows(sheet_url: str, tab: str, rows: List[List[str]]) -> int:
    """
    탭 끝에 행을 추가한다 (values:append, USER_ENTERED, range='<탭>'!A1).
    USER_ENTERED 라서 날짜/숫자 문자열은 시트가 알아서 형식을 잡는다.
    추가된 행 수를 돌려준다. rows 가 비어 있으면 호출 없이 0.
    """
    sheet_id = _require_sheet_id(sheet_url)
    tab = (tab or "").strip()
    if not tab:
        raise SheetsError("기록할 탭 이름을 입력해 주세요. (예: 블로그)")
    if not rows:
        return 0
    if not is_write_configured():
        raise SheetsError(
            "시트에 기록하려면 구글 서비스 계정 설정이 필요합니다. "
            "GOOGLE_SERVICE_ACCOUNT_JSON 또는 GOOGLE_SERVICE_ACCOUNT_FILE 을 설정해 주세요."
        )

    a1_range = f"{_a1_tab(tab)}!A1"
    url = (
        f"{SHEETS_API}/{sheet_id}/values/{quote(a1_range, safe='')}:append"
        "?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS"
    )
    payload = {
        "majorDimension": "ROWS",
        "values": [["" if c is None else str(c) for c in row] for row in rows],
    }
    body = await _sheets_request("POST", url, tab, json=payload)
    updated = (body.get("updates") or {}).get("updatedRows")
    return int(updated) if updated is not None else len(rows)


# ---------------------------------------------------------------------------
# 공개 API: 읽기 + 키워드 조회
# ---------------------------------------------------------------------------

async def read_tab(sheet_url: str, tab: str) -> List[List[str]]:
    """
    탭 전체를 2차원 문자열 배열로 읽는다.

    먼저 공개 CSV 로 시도하고, 실패했는데 서비스 계정이 설정돼 있으면
    Sheets API 로 다시 시도한다. 둘 다 실패하면 SheetsError.
    """
    try:
        return await read_tab_public(sheet_url, tab)
    except SheetsError as public_err:
        if not is_write_configured():
            raise
        logger.info("public csv failed (%s); retrying with service account", public_err)
        try:
            return await read_tab_authenticated(sheet_url, tab)
        except SheetsError as auth_err:
            raise SheetsError(f"{auth_err} (공개 링크 읽기도 실패: {public_err})")


async def find_keywords(
    sheet_url: str, tab: str, keywords: List[str]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    키워드들이 탭 어딘가에 이미 있는지 확인한다.

    마케터마다 키워드를 적는 열이 달라서 모든 행의 모든 셀을 본다.
    양쪽 모두 공백 제거 + 소문자로 정규화해 비교한다(완전 일치).
    반환: {원본 키워드: {"row": 1-based 행, "col": 1-based 열, "cell": 원문} | None}
    같은 키워드가 여러 번 있으면 위쪽/왼쪽 첫 번째 셀을 돌려준다.
    """
    result: Dict[str, Optional[Dict[str, Any]]] = {kw: None for kw in keywords}
    wanted = {normalize_keyword(kw): kw for kw in keywords if normalize_keyword(kw)}
    if not wanted:
        return result

    rows = await read_tab(sheet_url, tab)
    remaining = dict(wanted)
    for r_idx, row in enumerate(rows, start=1):
        for c_idx, cell in enumerate(row, start=1):
            key = normalize_keyword(cell)
            if not key:
                continue
            original = remaining.pop(key, None)
            if original is not None:
                result[original] = {"row": r_idx, "col": c_idx, "cell": cell}
                if not remaining:
                    return result
    return result
