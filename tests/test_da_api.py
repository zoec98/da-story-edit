from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import httpx

from da_story_edit.da_api import DeviantArtApiClient
from da_story_edit.http_client import ThrottledHttpClient


@dataclass
class _FakeResponse:
    payload: dict[str, object]
    status_code: int = 200

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://example.com")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                "error",
                request=request,
                response=response,
            )

    def json(self) -> dict[str, object]:
        return self.payload

    @property
    def text(self) -> str:
        return str(self.payload)


class _FakeHttpClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def get(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        profile: object = None,
        follow_redirects: bool = False,
        timeout: float = 30.0,
    ) -> _FakeResponse:
        del profile, follow_redirects, timeout
        self.calls.append((url, params))
        assert params is not None
        if url.endswith("/gallery/folders"):
            raw_offset = params.get("offset", 0)
            if isinstance(raw_offset, int):
                offset = raw_offset
            elif isinstance(raw_offset, str):
                offset = int(raw_offset)
            else:
                raise AssertionError(f"Unexpected offset type: {type(raw_offset)}")
            if offset == 0:
                return _FakeResponse(
                    {
                        "results": [{"folderid": "A", "name": "Alpha"}],
                        "has_more": True,
                        "next_offset": 1,
                    }
                )
            return _FakeResponse(
                {
                    "results": [{"folderid": "B", "name": "Beta"}],
                    "has_more": False,
                    "next_offset": None,
                }
            )
        if "/gallery/" in url:
            return _FakeResponse(
                {"results": [], "has_more": False, "next_offset": None}
            )
        raise AssertionError(f"Unexpected URL: {url}")

    def post(
        self,
        url: str,
        *,
        data: dict[str, object] | None = None,
        profile: object = None,
        follow_redirects: bool = False,
        timeout: float = 30.0,
    ) -> _FakeResponse:
        del url, data, profile, follow_redirects, timeout
        raise AssertionError("post() should not be called in this test")


def test_list_folders_paginates_all_pages() -> None:
    fake = _FakeHttpClient()
    client = DeviantArtApiClient(
        access_token="token",
        user_agent="ua",
        http_client=cast(ThrottledHttpClient, fake),
    )

    folders = client.list_folders("zoec98")

    assert [folder.folder_id for folder in folders] == ["A", "B"]
    folder_calls = [call for call in fake.calls if call[0].endswith("/gallery/folders")]
    assert len(folder_calls) == 2


def test_list_gallery_includes_mode_newest_parameter() -> None:
    fake = _FakeHttpClient()
    client = DeviantArtApiClient(
        access_token="token",
        user_agent="ua",
        http_client=cast(ThrottledHttpClient, fake),
    )

    client.list_gallery("zoec98", folder_id="FOLDER-UUID", mode="newest")

    gallery_calls = [
        call for call in fake.calls if call[0].endswith("/gallery/FOLDER-UUID")
    ]
    assert len(gallery_calls) == 1
    _, params = gallery_calls[0]
    assert params is not None
    assert params["mode"] == "newest"
