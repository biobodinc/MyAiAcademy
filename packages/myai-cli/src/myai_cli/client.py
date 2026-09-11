"""Thin HTTP client for the local service.

Discovery: read ``local-api.json`` (host/port) and ``local-api.token`` from the app data
directory. Both are written by ``myai-core`` on the same machine and are owner-readable
only, so a CLI run by the same user can reach the API and nothing else can.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from myai_core.paths import AppPaths, resolve_app_paths


class ServiceNotRunningError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LocalService:
    api_base: str
    token: str

    @classmethod
    def discover(cls, data_dir: Path | None = None) -> LocalService:
        paths: AppPaths = resolve_app_paths(data_dir)
        try:
            discovery = json.loads(paths.discovery_file.read_text(encoding="utf-8"))
            token = paths.token_file.read_text(encoding="utf-8").strip()
        except FileNotFoundError as exc:
            raise ServiceNotRunningError(
                "The MyAI local service is not running. Start it with `myai serve` "
                "or open the MyAI Academy desktop app."
            ) from exc
        api_base = str(discovery["api_base"])
        if not api_base.startswith(("http://127.0.0.1:", "http://localhost:", "http://[::1]:")):
            raise ServiceNotRunningError("Refusing to use a non-loopback service address.")
        return cls(api_base=api_base, token=token)

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.api_base,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=httpx.Timeout(30.0, connect=2.0),
        )

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            with self._client() as client:
                response = client.request(method, path, **kwargs)
        except httpx.ConnectError as exc:
            raise ServiceNotRunningError(
                "Could not connect to the MyAI local service. Is it running? (`myai serve`)"
            ) from exc
        if response.status_code >= 400:
            detail = (
                response.json().get("detail", response.text)
                if _is_json(response)
                else (response.text)
            )
            raise ApiError(response.status_code, str(detail))
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def get(self, endpoint: str, **params: Any) -> Any:
        query = {k: v for k, v in params.items() if v is not None}
        return self.request("GET", endpoint, params=query)

    def post(self, path: str, body: dict[str, Any]) -> Any:
        return self.request("POST", path, json=body)

    def put(self, path: str, body: dict[str, Any]) -> Any:
        return self.request("PUT", path, json=body)

    def patch(self, path: str, body: dict[str, Any]) -> Any:
        return self.request("PATCH", path, json=body)


class ApiError(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"{status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


def _is_json(response: httpx.Response) -> bool:
    content_type: str = response.headers.get("content-type", "")
    return content_type.startswith("application/json")
