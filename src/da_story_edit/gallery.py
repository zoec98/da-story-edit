from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from urllib.parse import urlparse
import re

from da_story_edit.config import ConfigError


@dataclass(frozen=True)
class GalleryTarget:
    username: str
    folder_ref: str | None = None
    folder_slug: str | None = None


@dataclass(frozen=True)
class DeviationSummary:
    deviation_id: str
    title: str
    url: str
    kind: str

    @property
    def is_literature(self) -> bool:
        return self.kind == "literature"


def extract_gallery_deviation_urls(html: str, username: str) -> list[str]:
    pattern = re.compile(
        rf"https://www\.deviantart\.com/{re.escape(username)}/art/[^\"]+"
    )
    found = pattern.findall(html)
    ordered: list[str] = []
    seen: set[str] = set()
    for url in found:
        if url in seen:
            continue
        seen.add(url)
        ordered.append(url)
    return ordered


def parse_gallery_target(raw: str) -> GalleryTarget:
    value = raw.strip()
    if not value:
        raise ConfigError("Gallery input must not be empty.")

    if "://" not in value:
        return GalleryTarget(username=value)

    parsed = urlparse(value)
    parts = [part for part in parsed.path.split("/") if part]

    if parsed.netloc != "www.deviantart.com":
        raise ConfigError("Gallery URL must use host www.deviantart.com.")
    if len(parts) < 2 or parts[1] != "gallery":
        raise ConfigError("Gallery URL must look like /<user>/gallery/... .")

    username = parts[0]
    folder_ref: str | None = None
    folder_slug: str | None = None
    if len(parts) >= 3 and parts[2].isdigit():
        folder_ref = parts[2]
    if len(parts) >= 4:
        folder_slug = parts[3].strip().lower()
    return GalleryTarget(
        username=username, folder_ref=folder_ref, folder_slug=folder_slug
    )


def parse_gallery_results(payload: dict[str, object]) -> list[DeviationSummary]:
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        raise ConfigError("Gallery API response is missing a 'results' list.")

    items: list[DeviationSummary] = []
    for entry in raw_results:
        if not isinstance(entry, dict):
            continue
        entry_dict = cast(dict[str, object], entry)
        deviation_id = str(entry_dict.get("deviationid") or "").strip()
        title = str(entry_dict.get("title") or "").strip()
        url = str(entry_dict.get("url") or "").strip()
        kind = str(entry_dict.get("type") or "").strip().lower()
        if not kind and isinstance(entry_dict.get("text_content"), dict):
            kind = "literature"
        if not kind:
            kind = "unknown"
        if not deviation_id or not title or not url:
            continue
        items.append(
            DeviationSummary(
                deviation_id=deviation_id,
                title=title,
                url=url,
                kind=kind,
            )
        )
    return items
