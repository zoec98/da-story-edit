from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import cast

import httpx

from da_story_edit.config import AuthTokenExpiredError, ConfigError
from da_story_edit.gallery import DeviationSummary, parse_gallery_results

API_BASE = "https://www.deviantart.com/api/v1/oauth2"


@dataclass(frozen=True)
class GalleryFolder:
    folder_id: str
    name: str


def slugify_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    lowered = normalized.lower()
    return re.sub(r"[^a-z0-9]+", "", lowered)


class DeviantArtApiClient:
    def __init__(self, access_token: str, user_agent: str) -> None:
        self.access_token = access_token
        self.headers = {
            "User-Agent": user_agent,
            "Accept": "application/json",
        }

    def _get(self, path: str, params: dict[str, object]) -> dict[str, object]:
        merged = {"access_token": self.access_token}
        merged.update(params)
        url = f"{API_BASE}{path}"
        try:
            response = httpx.get(url, params=merged, headers=self.headers, timeout=30.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            body = ""
            if isinstance(exc, httpx.HTTPStatusError):
                if _looks_like_invalid_token(exc.response):
                    raise AuthTokenExpiredError(
                        "Access token is invalid or expired."
                    ) from exc
            if isinstance(exc, httpx.HTTPStatusError):
                snippet = exc.response.text[:300].replace("\n", " ")
                body = f" Response body: {snippet}"
            raise ConfigError(f"API request failed for {path}.{body}") from exc

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise ConfigError(f"API response for {path} was not valid JSON.") from exc
        if not isinstance(payload, dict):
            raise ConfigError(f"API response for {path} had unexpected shape.")
        return payload

    def list_gallery(
        self, username: str, folder_id: str | None = None
    ) -> list[DeviationSummary]:
        path = "/gallery/all" if folder_id is None else f"/gallery/{folder_id}"
        offset = 0
        limit = 24
        all_items: list[DeviationSummary] = []

        while True:
            payload = self._get(
                path,
                {
                    "username": username,
                    "offset": offset,
                    "limit": limit,
                    "mature_content": "true",
                },
            )
            page_items = parse_gallery_results(payload)
            all_items.extend(page_items)

            has_more = bool(payload.get("has_more"))
            next_offset = payload.get("next_offset")
            if not has_more:
                break
            if not isinstance(next_offset, int):
                if not page_items:
                    break
                offset += len(page_items)
            else:
                offset = next_offset
        return all_items

    def list_folders(self, username: str) -> list[GalleryFolder]:
        payload = self._get(
            "/gallery/folders",
            {
                "username": username,
            },
        )
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            raise ConfigError(
                "Gallery folders API response is missing a 'results' list."
            )

        folders: list[GalleryFolder] = []
        for entry in raw_results:
            if not isinstance(entry, dict):
                continue
            entry_dict = cast(dict[str, object], entry)
            folder_id = str(entry_dict.get("folderid") or "").strip()
            name = str(entry_dict.get("name") or "").strip()
            if not folder_id or not name:
                continue
            folders.append(GalleryFolder(folder_id=folder_id, name=name))
        return folders


def _looks_like_invalid_token(response: httpx.Response) -> bool:
    if response.status_code in {401, 403}:
        text = response.text.lower()
        if "invalid_token" in text or "expired" in text:
            return True
        try:
            payload = response.json()
        except Exception:
            return False
        if isinstance(payload, dict):
            err = str(payload.get("error") or "").lower()
            desc = str(payload.get("error_description") or "").lower()
            return "invalid_token" in err or "expired" in desc
    return False
