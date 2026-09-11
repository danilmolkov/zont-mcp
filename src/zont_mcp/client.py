"""Тонкий HTTP-клиент для API ZONT (https://zont-online.ru/api/docs/)."""

from __future__ import annotations

import base64
import os
from typing import Any

import httpx

API_BASE = "https://my.zont.online/api/"


class ZontApiError(Exception):
    """Ошибка, возвращённая API ZONT (поле "ok": false), либо HTTP-ошибка транспорта."""

    def __init__(self, error: str | None, error_ui: str | list[str] | None, status: int):
        self.error = error
        self.error_ui = error_ui
        self.status = status
        if isinstance(error_ui, list):
            message = "; ".join(error_ui)
        elif error_ui:
            message = error_ui
        else:
            message = f"HTTP {status}"
        suffix = f" ({error})" if error else ""
        super().__init__(f"ZONT API error{suffix}: {message}")


class ZontClient:
    def __init__(
        self,
        client: str,
        login: str | None = None,
        password: str | None = None,
        token: str | None = None,
    ):
        if not token and not (login and password):
            raise RuntimeError(
                "ZONT credentials are missing: set ZONT_TOKEN, or both ZONT_LOGIN and ZONT_PASSWORD"
            )
        self.client = client
        self.login = login
        self.password = password
        self.token = token
        self._http = httpx.AsyncClient(base_url=API_BASE, timeout=30.0)

    def _auth_headers(self) -> dict[str, str]:
        if self.token:
            return {"X-ZONT-Token": self.token}
        raw = f"{self.login}:{self.password}".encode()
        return {"Authorization": f"Basic {base64.b64encode(raw).decode()}"}

    async def post(self, method: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        res = await self._http.post(
            method,
            headers={
                "Content-Type": "application/json",
                "X-ZONT-Client": self.client,
                **self._auth_headers(),
            },
            json=body or {},
        )
        return self._parse_json(res)

    async def get_raw(self, method: str, params: dict[str, str] | None = None) -> httpx.Response:
        res = await self._http.get(
            method,
            headers={"X-ZONT-Client": self.client, **self._auth_headers()},
            params=params or {},
        )
        if res.status_code >= 400:
            content_type = res.headers.get("content-type", "")
            if "application/json" in content_type:
                self._parse_json(res)  # raises ZontApiError with server-provided details
            raise ZontApiError(None, f"HTTP {res.status_code}", res.status_code)
        return res

    def _parse_json(self, res: httpx.Response) -> dict[str, Any]:
        try:
            data = res.json() if res.content else {}
        except ValueError as exc:
            raise ZontApiError(
                None, f"Invalid JSON response (HTTP {res.status_code}): {res.text[:500]}", res.status_code
            ) from exc
        if isinstance(data, dict) and data.get("ok") is False:
            raise ZontApiError(data.get("error"), data.get("error_ui"), res.status_code)
        if res.status_code >= 400:
            raise ZontApiError(
                data.get("error") if isinstance(data, dict) else None,
                (data.get("error_ui") if isinstance(data, dict) else None) or f"HTTP {res.status_code}",
                res.status_code,
            )
        return data

    async def aclose(self) -> None:
        await self._http.aclose()


def client_from_env() -> ZontClient:
    client = os.environ.get("ZONT_CLIENT")
    if not client:
        raise RuntimeError(
            "ZONT_CLIENT environment variable is required (contact e-mail sent as X-ZONT-Client header)"
        )
    return ZontClient(
        client=client,
        login=os.environ.get("ZONT_LOGIN"),
        password=os.environ.get("ZONT_PASSWORD"),
        token=os.environ.get("ZONT_TOKEN"),
    )
