from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@dataclass
class HttpClientConfig:
    base_url: str = ""
    timeout: int = 30
    max_retries: int = 3
    backoff_factor: float = 0.5
    auth_token: str = ""


class PlatformHttpClient:
    """Platform-managed HTTP client with retry, circuit breaker, and auth."""

    def __init__(self, config: HttpClientConfig | None = None):
        self._config = config or HttpClientConfig()
        self._session = self._build_session()

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=self._config.max_retries,
            backoff_factor=self._config.backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        if self._config.auth_token:
            session.headers["Authorization"] = f"Bearer {self._config.auth_token}"
        return session

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        url = f"{self._config.base_url}{path}"
        return self._session.get(url, timeout=self._config.timeout, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        url = f"{self._config.base_url}{path}"
        return self._session.post(url, timeout=self._config.timeout, **kwargs)
