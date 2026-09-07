"""닥터보이스 서버(backend/app/api/campaign.py '발행 실행기 API') 동기 httpx 클라이언트."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger("server")


class ServerError(RuntimeError):
    def __init__(self, status: int, detail: str):
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


class ServerClient:
    """토큰은 login() 에서 받아 Authorization: Bearer 로 보낸다.
    401 이 오면 저장된 계정으로 한 번 재로그인 후 재시도한다."""

    def __init__(self, base_url: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.api = self.base_url + "/api/v1"
        self.token: Optional[str] = None
        self._email: Optional[str] = None
        self._password: Optional[str] = None
        self._http = httpx.Client(timeout=timeout)

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
        r = self._http.request(method, url, json=json, headers=self._headers())
        if r.status_code == 401 and _retry and self._email and self._password:
            log.warning("토큰 만료/무효(401) → 재로그인")
            self.login(self._email, self._password)
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
        self.token = token
        self._email, self._password = email, password
        return token

    def summary(self) -> List[Dict[str, Any]]:
        """[{blog_ref_id, naver_blog_id, label, status, status_reason, pending, next_at, login_id}]"""
        return self._request("GET", "/campaign/agent/summary") or []

    def credential(self, blog_ref_id: str) -> Dict[str, Any]:
        """{login_id, login_pw, naver_blog_id}"""
        return self._request("GET", f"/campaign/agent/blogs/{blog_ref_id}/credential") or {}

    def claim(self, blog_ref_id: str, limit: int = 5, include_images: bool = True) -> List[Dict[str, Any]]:
        """→ [ClaimedJob]. 서버가 20분 잠금을 건다(만료 후 재클레임 가능)."""
        body = {"blog_ref_id": blog_ref_id, "limit": limit, "include_images": include_images}
        return self._request("POST", "/campaign/agent/claim", json=body) or []

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
    ) -> Dict[str, Any]:
        body = {
            "lock_token": lock_token,
            "ok": bool(ok),
            "uncertain": bool(uncertain),
            "message": (message or None) and str(message)[:500],
            "url": url or None,
            "need_login": bool(need_login),
            "captcha": bool(captcha),
        }
        return self._request("POST", f"/campaign/agent/jobs/{job_id}/result", json=body) or {}

    def set_blog_status(self, blog_ref_id: str, status: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """status: active | login_required | captcha | paused ..."""
        return self._request("POST", f"/campaign/blogs/{blog_ref_id}/status", json={"status": status, "reason": reason}) or {}

    def close(self) -> None:
        self._http.close()
