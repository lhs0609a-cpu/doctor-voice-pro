"""
google_sheets_service 단위 점검 스크립트 (네트워크 없음).

실행: python test_sheets_service.py  (backend 디렉터리에서)

- parse_sheet_id: URL 3가지 형태 + ID 단독 + 잘못된 입력
- find_keywords: read_tab 을 가짜 표로 monkeypatch 해 정규화/전체 셀 검색 확인
- make_jwt: 임시 RSA 키로 서명해 구조와 서명 검증 (토큰 서버 호출 없음)
"""
import asyncio
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.services import google_sheets_service as svc  # noqa: E402

SHEET_ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcdefg"
failures = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global failures
    status = "PASS" if cond else "FAIL"
    if not cond:
        failures += 1
    print(f"[{status}] {name}" + (f"  -- {detail}" if detail else ""))


# ---------------------------------------------------------------- parse_sheet_id
def test_parse_sheet_id() -> None:
    edit_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid=1234"
    share_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit?usp=sharing"
    user_url = f"https://docs.google.com/spreadsheets/u/1/d/{SHEET_ID}/htmlview"

    check("parse: edit URL with #gid", svc.parse_sheet_id(edit_url) == SHEET_ID)
    check("parse: share URL ?usp=sharing", svc.parse_sheet_id(share_url) == SHEET_ID)
    check("parse: /u/1/d/ URL", svc.parse_sheet_id(user_url) == SHEET_ID)
    check("parse: bare id", svc.parse_sheet_id(f"  {SHEET_ID}  ") == SHEET_ID)
    check("parse: empty -> None", svc.parse_sheet_id("") is None)
    check("parse: garbage -> None", svc.parse_sheet_id("https://naver.com/x") is None)
    check("parse: short token -> None", svc.parse_sheet_id("abc") is None)
    check("parse_gid: #gid", svc.parse_gid(edit_url) == "1234")
    check("parse_gid: none", svc.parse_gid(share_url) is None)
    check("a1 tab quoting", svc._a1_tab("It's") == "'It''s'")


# ---------------------------------------------------------------- find_keywords
FAKE_TABLE = [
    ["날짜", "병원", "키워드", "URL"],
    ["2026-08-01", "강남치과", "임플란트 가격", "https://blog.naver.com/a"],
    ["2026-08-02", "", "", ""],
    ["2026-08-03", "라미네이트 비용", "서초피부과", "https://blog.naver.com/b"],  # 키워드가 다른 열
    ["", "", "", "  치아교정   기간 "],  # 공백 뒤섞임, 4열
    ["2026-08-05", "Botox Price", "", ""],  # 대소문자
    ["", "", "", ""],
]


def test_find_keywords() -> None:
    calls = []

    async def fake_read_tab(sheet_url: str, tab: str):
        calls.append((sheet_url, tab))
        return [list(r) for r in FAKE_TABLE]

    original = svc.read_tab
    svc.read_tab = fake_read_tab
    try:
        result = asyncio.run(
            svc.find_keywords(
                "https://docs.google.com/spreadsheets/d/" + SHEET_ID + "/edit",
                "블로그",
                [
                    "임플란트가격",       # 원본엔 공백 있음
                    "라미네이트 비용",     # 2열에 있음
                    "치아교정 기간",       # 4열, 공백 뒤섞임
                    "botox price",         # 대소문자
                    "충치 치료",           # 없음
                    "   ",                 # 빈 키워드
                ],
            )
        )
    finally:
        svc.read_tab = original

    check("find: read_tab called once with tab", calls == [(
        "https://docs.google.com/spreadsheets/d/" + SHEET_ID + "/edit", "블로그")])
    check("find: whitespace-insensitive match",
          result["임플란트가격"] == {"row": 2, "col": 3, "cell": "임플란트 가격"},
          repr(result["임플란트가격"]))
    check("find: keyword in non-keyword column",
          result["라미네이트 비용"] == {"row": 4, "col": 2, "cell": "라미네이트 비용"},
          repr(result["라미네이트 비용"]))
    check("find: mixed inner/outer whitespace, col 4",
          result["치아교정 기간"] == {"row": 5, "col": 4, "cell": "  치아교정   기간 "},
          repr(result["치아교정 기간"]))
    check("find: case-insensitive",
          result["botox price"] == {"row": 6, "col": 2, "cell": "Botox Price"},
          repr(result["botox price"]))
    check("find: missing -> None", result["충치 치료"] is None)
    check("find: blank keyword -> None", result["   "] is None)
    check("find: all keys present", set(result) == {
        "임플란트가격", "라미네이트 비용", "치아교정 기간", "botox price", "충치 치료", "   "})

    check("normalize", svc.normalize_keyword(" A b\tC\n d ") == "abcd")
    check("strip trailing empty rows",
          len(svc._strip_trailing_empty([list(r) for r in FAKE_TABLE])) == 6)


def test_find_keywords_no_read_when_empty() -> None:
    async def boom(sheet_url, tab):
        raise AssertionError("read_tab should not be called")

    original = svc.read_tab
    svc.read_tab = boom
    try:
        result = asyncio.run(svc.find_keywords("x", "블로그", ["", "  "]))
    finally:
        svc.read_tab = original
    check("find: no network when all keywords blank", result == {"": None, "  ": None})


# ---------------------------------------------------------------- csv parsing
def test_csv_parse() -> None:
    raw = "﻿\"날짜\",\"키워드\"\r\n\"2026-08-01\",\"임플란트, 가격\"\r\n\"\",\"\"\r\n".encode("utf-8")
    rows = svc._parse_csv(raw)
    check("csv: BOM stripped + quoted comma + trailing blank removed",
          rows == [["날짜", "키워드"], ["2026-08-01", "임플란트, 가격"]], repr(rows))


# ---------------------------------------------------------------- JWT (offline)
def test_make_jwt() -> None:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    info = {"client_email": "bot@example.iam.gserviceaccount.com", "private_key": pem}

    token = svc.make_jwt(info, now=1_700_000_000)
    parts = token.split(".")
    check("jwt: three segments", len(parts) == 3)

    def dec(s: str) -> bytes:
        return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

    header = json.loads(dec(parts[0]))
    claims = json.loads(dec(parts[1]))
    check("jwt: header RS256", header == {"alg": "RS256", "typ": "JWT"}, repr(header))
    check("jwt: claims", claims == {
        "iss": "bot@example.iam.gserviceaccount.com",
        "scope": "https://www.googleapis.com/auth/spreadsheets",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": 1_700_000_000,
        "exp": 1_700_003_600,
    }, repr(claims))
    try:
        key.public_key().verify(
            dec(parts[2]), f"{parts[0]}.{parts[1]}".encode("ascii"),
            padding.PKCS1v15(), hashes.SHA256(),
        )
        ok = True
    except Exception:
        ok = False
    check("jwt: signature verifies with public key", ok)

    bad = {"client_email": "x@y", "private_key": "not a key"}
    try:
        svc.make_jwt(bad)
        check("jwt: bad key raises SheetsError", False)
    except svc.SheetsError as e:
        check("jwt: bad key raises SheetsError", "private_key" in str(e))


# ---------------------------------------------------------------- config wiring
def test_settings_fields() -> None:
    from app.core.config import Settings
    fields = Settings.model_fields
    check("settings: GOOGLE_SERVICE_ACCOUNT_JSON", "GOOGLE_SERVICE_ACCOUNT_JSON" in fields)
    check("settings: GOOGLE_SERVICE_ACCOUNT_FILE", "GOOGLE_SERVICE_ACCOUNT_FILE" in fields)
    # 기본값(둘 다 비어 있음)이면 쓰기 비활성.
    saved = (svc.settings.GOOGLE_SERVICE_ACCOUNT_JSON, svc.settings.GOOGLE_SERVICE_ACCOUNT_FILE)
    try:
        svc.settings.GOOGLE_SERVICE_ACCOUNT_JSON = ""
        svc.settings.GOOGLE_SERVICE_ACCOUNT_FILE = ""
        svc._sa_cache["key"] = None
        check("is_write_configured false when unset", svc.is_write_configured() is False)
        svc.settings.GOOGLE_SERVICE_ACCOUNT_JSON = json.dumps(
            {"client_email": "a@b", "private_key": "-----BEGIN PRIVATE KEY-----\nx\n-----END PRIVATE KEY-----\n"})
        check("is_write_configured true with json", svc.is_write_configured() is True)
        check("service_account_email", svc.service_account_email() == "a@b")
    finally:
        svc.settings.GOOGLE_SERVICE_ACCOUNT_JSON, svc.settings.GOOGLE_SERVICE_ACCOUNT_FILE = saved
        svc._sa_cache["key"] = None


if __name__ == "__main__":
    test_parse_sheet_id()
    test_find_keywords()
    test_find_keywords_no_read_when_empty()
    test_csv_parse()
    test_make_jwt()
    test_settings_fields()
    print()
    print("ALL PASSED" if failures == 0 else f"{failures} FAILED")
    sys.exit(1 if failures else 0)
