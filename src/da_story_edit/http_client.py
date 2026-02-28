from __future__ import annotations

import random
import time
from dataclasses import dataclass

import httpx


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:148.0) "
    "Gecko/20100101 Firefox/148.0"
)

DEFAULT_BROWSER_ACCEPT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
)
DEFAULT_API_ACCEPT = "application/json"
DEFAULT_ACCEPT_LANGUAGE = "en-US,en;q=0.9"
DEFAULT_ACCEPT_ENCODING = "gzip, deflate"


@dataclass(frozen=True)
class RequestProfile:
    accept: str
    include_accept_language: bool


API_PROFILE = RequestProfile(accept=DEFAULT_API_ACCEPT, include_accept_language=False)
BROWSER_PROFILE = RequestProfile(
    accept=DEFAULT_BROWSER_ACCEPT, include_accept_language=True
)


class ThrottledHttpClient:
    """httpx wrapper with randomized pre-request delay and shared headers."""

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        min_delay_seconds: float = 0.2,
        max_delay_seconds: float = 1.2,
    ) -> None:
        self.user_agent = user_agent
        self.min_delay_seconds = min_delay_seconds
        self.max_delay_seconds = max_delay_seconds

    def _delay(self) -> None:
        pause = random.uniform(self.min_delay_seconds, self.max_delay_seconds)
        time.sleep(pause)

    def _build_headers(
        self,
        profile: RequestProfile,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": profile.accept,
            "Accept-Encoding": DEFAULT_ACCEPT_ENCODING,
        }
        if profile.include_accept_language:
            headers["Accept-Language"] = DEFAULT_ACCEPT_LANGUAGE
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def _normalize_values(
        self, values: dict[str, object] | None
    ) -> dict[str, str | int | float | None] | None:
        if values is None:
            return None
        normalized: dict[str, str | int | float | None] = {}
        for key, value in values.items():
            if value is None:
                normalized[key] = None
            elif isinstance(value, bool):
                normalized[key] = "true" if value else "false"
            elif isinstance(value, (str, int, float)):
                normalized[key] = value
            else:
                normalized[key] = str(value)
        return normalized

    def get(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        profile: RequestProfile = API_PROFILE,
        follow_redirects: bool = False,
        timeout: float = 30.0,
    ) -> httpx.Response:
        self._delay()
        headers = self._build_headers(profile)
        return httpx.get(
            url,
            params=self._normalize_values(params),
            headers=headers,
            follow_redirects=follow_redirects,
            timeout=timeout,
        )

    def post(
        self,
        url: str,
        *,
        data: dict[str, object] | None = None,
        profile: RequestProfile = API_PROFILE,
        follow_redirects: bool = False,
        timeout: float = 30.0,
    ) -> httpx.Response:
        self._delay()
        headers = self._build_headers(profile)
        return httpx.post(
            url,
            data=self._normalize_values(data),
            headers=headers,
            follow_redirects=follow_redirects,
            timeout=timeout,
        )
