"""닥터보이스 서버(backend/app/api/campaign.py '발행 실행기 API') 동기 httpx 클라이언트."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

log = logging.getLogger("server")


class ServerError(RuntimeError):
    def __init__(self, status: int, detail: str):
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


# 서버 토큰은 30분이면 만료된다. 만료되고 나서 401 을 보고 다시 받으면 그 요청 하나가 실패하고
# 기록에도 "토큰 만료/무효" 가 계속 남는다. 남은 시간이 이만큼 밑으로 내려가면 미리 갈아끼운다.
RENEW_BEFORE_SECONDS = 300
DEFAULT_TOKEN_SECONDS = 1800


class ServerClient:
    """토큰은 login() 에서 받아 Authorization: Bearer 로 보낸다.

    만료 전에 스스로 새 토큰을 받아 두고, 그래도 401 이 오면 한 번 더 재인증한 뒤 재시도한다."""

    def __init__(self, base_url: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.api = self.base_url + "/api/v1"
        self.token: Optional[str] = None
        self.token_until: float = 0.0   # time.monotonic() 기준. 0 이면 만료 시각을 모른다.
        self._email: Optional[str] = None
        self._password: Optional[str] = None
        self._reauth = None          # 재인증(비밀번호 또는 기기 키)
        self._http = httpx.Client(timeout=timeout)

    def _keep_token(self, token: str, expires_in: Any = None) -> None:
        try:
            seconds = float(expires_in or DEFAULT_TOKEN_SECONDS)
        except (TypeError, ValueError):
            seconds = DEFAULT_TOKEN_SECONDS
        self.token = token
        self.token_until = time.monotonic() + max(60.0, seconds)

    def _renew_if_stale(self) -> None:
        """만료가 가까우면 조용히 새 토큰을 받는다. 실패해도 그냥 보내 본다 — 401 재시도가 받아 준다."""
        if not (self._reauth and self.token and self.token_until):
            return
        if time.monotonic() < self.token_until - RENEW_BEFORE_SECONDS:
            return
        try:
            self._reauth()
        except Exception as error:  # noqa: BLE001
            log.debug("토큰 미리 갱신 실패(그대로 진행): %s", error)

    # ------------------------------------------------------------ 내부
    def _headers(self) -> Dict[str, str]:
        h = {"Accept": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    @staticmethod
    def _detail(r: httpx.Response) -> str:
        try:
            j = r.json()
            if isinstance(j, dict):
                return str(j.get("detail") or j.get("message") or j)
            return str(j)
        except Exception:  # noqa: BLE001
            return r.text[:300]

    def _request(self, method: str, path: str, *, json: Any = None, _retry: bool = True) -> Any:
        url = self.api + path
        if _retry:
            self._renew_if_stale()
        r = self._http.request(method, url, json=json, headers=self._headers())
        if r.status_code == 401 and _retry and self._reauth:
            # 미리 갱신하므로 여기까지 오는 일은 드물다(서버 재시작·시계 차이 등).
            log.debug("토큰이 거절되어 다시 로그인합니다")
            self._reauth()
            return self._request(method, path, json=json, _retry=False)
        if r.status_code >= 400:
            raise ServerError(r.status_code, self._detail(r))
        if not r.content:
            return None
        return r.json()

    # ------------------------------------------------------------ 엔드포인트
    def login(self, email: str, password: str) -> str:
        r = self._http.post(self.api + "/auth/login", json={"email": email, "password": password}, headers={"Accept": "application/json"})
        if r.status_code >= 400:
            raise ServerError(r.status_code, self._detail(r))
        data = r.json()
        token = data.get("access_token") if isinstance(data, dict) else None
        if not token:
            raise ServerError(r.status_code, "응답에 access_token 이 없습니다")
        self._keep_token(token, data.get("expires_in"))
        self._email, self._password = email, password
        self._reauth = lambda: self.login(email, password)
        return token

    # ------------------------------------------------------- 홈페이지 자동 연결
    def pair_claim(self, code: str, device_id: str, label: str = "") -> Dict[str, Any]:
        """홈페이지가 건넨 1회용 코드로 이 기기 전용 키를 받는다. → {device_secret, email}"""
        r = self._http.post(self.api + "/campaign/agent/pair/claim",
                            json={"code": code, "device_id": device_id, "label": label or None},
                            headers={"Accept": "application/json"})
        if r.status_code >= 400:
            raise ServerError(r.status_code, self._detail(r))
        return r.json()

    def pair_request(self, device_id: str, label: str = "") -> Dict[str, Any]:
        """실행기가 먼저 손을 든다. → {request_id, expires_in}

        브라우저가 로컬 창구(127.0.0.1)에 닿지 못해도 연결되게 하는 반대 방향 길이다."""
        r = self._http.post(self.api + "/campaign/agent/pair/request",
                            json={"device_id": device_id, "label": label or None},
                            headers={"Accept": "application/json"})
        if r.status_code >= 400:
            raise ServerError(r.status_code, self._detail(r))
        return r.json()

    def pair_poll(self, request_id: str, device_id: str) -> Dict[str, Any]:
        """홈페이지가 승인했는지 묻는다. → {status: 'waiting'|'ok', device_secret?, email?}"""
        r = self._http.post(self.api + "/campaign/agent/pair/poll",
                            json={"request_id": request_id, "device_id": device_id},
                            headers={"Accept": "application/json"})
        if r.status_code >= 400:
            raise ServerError(r.status_code, self._detail(r))
        return r.json()

    def device_login(self, device_id: str, device_secret: str) -> Dict[str, Any]:
        """기기 키로 로그인 토큰을 받는다. 토큰이 만료되면 같은 키로 다시 받는다."""
        r = self._http.post(self.api + "/campaign/agent/device-token",
                            json={"device_id": device_id, "device_secret": device_secret},
                            headers={"Accept": "application/json"})
        if r.status_code >= 400:
            raise ServerError(r.status_code, self._detail(r))
        data = r.json()
        if not data.get("access_token"):
            raise ServerError(r.status_code, "응답에 access_token 이 없습니다")
        self._keep_token(data["access_token"], data.get("expires_in"))
        self._reauth = lambda: self.device_login(device_id, device_secret)
        return data

    def summary(self) -> List[Dict[str, Any]]:
        """[{blog_ref_id, naver_blog_id, label, status, status_reason, pending, next_at, login_id}]"""
        return self._request("GET", "/campaign/agent/summary") or []

    def proxy_for(self, blog_ref_id: str) -> Optional[str]:
        """이 블로그 전용 고정 프록시. 없으면 None — 그러면 PC 회선 그대로 나간다."""
        data = self._request("GET", f"/campaign/agent/blogs/{quote(str(blog_ref_id), safe='')}/proxy") or {}
        return data.get("proxy") or None

    def credential(self, blog_ref_id: str) -> Dict[str, Any]:
        """{login_id, login_pw, naver_blog_id}"""
        return self._request("GET", f"/campaign/agent/blogs/{blog_ref_id}/credential") or {}

    def claim(self, blog_ref_id: str, limit: int = 1, include_images: bool = True, mode: str = "live") -> List[Dict[str, Any]]:
        """→ [ClaimedJob]. 서버가 20분 잠금을 건다(만료 후 재클레임 가능)."""
        body = {"blog_ref_id": blog_ref_id, "limit": limit, "include_images": include_images, "mode": mode, "protocol_version": 2,
                "capabilities": ["landing_links_v1", "point_styles_v1"]}
        return self._request("POST", "/campaign/agent/claim", json=body) or []

    def checkpoint(self, job_id: str, lock_token: str, stage: str = "heartbeat"):
        return self._request("POST", f"/campaign/agent/jobs/{job_id}/checkpoint",
                             json={"lock_token": lock_token, "stage": stage})

    def report_result(
        self,
        job_id: str,
        lock_token: Optional[str],
        *,
        ok: bool,
        uncertain: bool = False,
        message: Optional[str] = None,
        url: Optional[str] = None,
        need_login: bool = False,
        captcha: bool = False,
        release: bool = False,
        receipt_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        body = {
            "lock_token": lock_token,
            "ok": bool(ok),
            "uncertain": bool(uncertain),
            "message": (message or None) and str(message)[:500],
            "url": url or None,
            "need_login": bool(need_login),
            "captcha": bool(captcha),
            "release": bool(release),
            "receipt_id": receipt_id,
        }
        return self._request("POST", f"/campaign/agent/jobs/{job_id}/result", json=body) or {}

    # ------------------------------------------------------- 신호등
    def heartbeat(self, *, device_id: str, version: str, running: bool,
                  label: str = "", note: str = "") -> Dict[str, Any]:
        """실행기가 살아 있음을 알린다. 웹의 연결 신호등이 이 값을 읽는다."""
        body = {"device_id": device_id, "version": version, "running": bool(running),
                "label": label or None, "note": note or None}
        return self._request("POST", "/campaign/agent/heartbeat", json=body) or {}

    # ------------------------------------------------------- 발행 큐(확장 대체)
    def queue_jobs(self, *, limit: int = 1, blog_ref_id: Optional[str] = None,
                   claim_unassigned: bool = False) -> List[Dict[str, Any]]:
        """대량 발행 큐에서 이 블로그 몫을 가져온다. 서버가 가져간 글을 registered 로 표시하므로
        받은 글은 반드시 queue_result 로 결과를 남겨야 한다(안 남기면 다시 나오지 않는다)."""
        path = f"/publish/queue/jobs?limit={int(limit)}"
        if blog_ref_id:
            path += f"&blog_ref_id={quote(str(blog_ref_id), safe='')}"
            path += f"&claim_unassigned={'true' if claim_unassigned else 'false'}"
        return self._request("GET", path) or []

    def queue_result(self, post_id: str, *, ok: bool, message: Optional[str] = None) -> Dict[str, Any]:
        body = {"ok": bool(ok), "message": (message or None) and str(message)[:500]}
        return self._request("POST", f"/publish/queue/{quote(str(post_id), safe='')}/result", json=body) or {}

    # ------------------------------------------------- 네이버에 이미 걸린 예약
    def put_reservations(self, blog_ref_id: str, *, ok: bool = True,
                         note: Optional[str] = None, items: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """이 블로그의 예약 목록 스냅샷을 서버 장부에 갈아 끼운다.

        ok=False 는 '못 읽었다'는 뜻이다 — 서버는 장부를 손대지 않고 완충만 넓힌다.
        못 읽은 것을 빈 목록으로 보내면 남의 예약 위에 겹쳐 잡히므로 절대 섞지 않는다."""
        rows = [{"at": r["at"].strftime("%Y-%m-%dT%H:%M") if hasattr(r["at"], "strftime") else str(r["at"]),
                 "title": (r.get("title") or None)} for r in (items or [])]
        body = {"ok": bool(ok), "note": (note or None) and str(note)[:300], "items": rows}
        return self._request("POST", f"/campaign/agent/blogs/{quote(str(blog_ref_id), safe='')}/reservations", json=body) or {}

    def reschedule(self, job_id: str, lock_token: str, *, reason: Optional[str] = None,
                   taken_at: Optional[List[Any]] = None) -> Dict[str, Any]:
        """그 시각에 이미 예약된 글이 있었다 → 올리지 말고 다음 빈 자리로 옮겨 달라."""
        body = {"lock_token": lock_token, "reason": (reason or None) and str(reason)[:500],
                "taken_at": [t.strftime("%Y-%m-%dT%H:%M") if hasattr(t, "strftime") else str(t) for t in (taken_at or [])]}
        return self._request("POST", f"/campaign/agent/jobs/{quote(str(job_id), safe='')}/reschedule", json=body) or {}

    def categories(self) -> Dict[str, Any]:
        return self._request("GET", "/publish/categories") or {}

    def put_categories(self, categories: List[Dict[str, str]]) -> Dict[str, Any]:
        return self._request("POST", "/publish/categories", json={"categories": categories}) or {}

    def adopt_blog_id(self, blog_ref_id: str, blog_id: str) -> Dict[str, Any]:
        """'로그인해 보니 블로그 주소가 이것' 이라고 알린다. 서버가 안전하다고 보면 맞춰 준다."""
        return self._request("POST", f"/campaign/agent/blogs/{quote(str(blog_ref_id), safe='')}/identity",
                             json={"blog_id": blog_id}) or {}

    def set_blog_status(self, blog_ref_id: str, status: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """status: active | login_required | captcha | paused ..."""
        return self._request("POST", f"/campaign/blogs/{blog_ref_id}/status", json={"status": status, "reason": reason}) or {}

    def close(self) -> None:
        self._http.close()
