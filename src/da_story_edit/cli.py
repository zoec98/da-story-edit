from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path
from urllib.parse import urlencode

import httpx

from da_story_edit.da_api import DeviantArtApiClient, slugify_name
from da_story_edit.config import ConfigError, load_required_config, upsert_env_values
from da_story_edit.gallery import (
    DeviationSummary,
    extract_gallery_deviation_urls,
    parse_gallery_target,
)
from da_story_edit.options import build_parser

AUTHORIZE_ENDPOINT = "https://www.deviantart.com/oauth2/authorize"
TOKEN_ENDPOINT = "https://www.deviantart.com/oauth2/token"
PLACEBO_ENDPOINT = "https://www.deviantart.com/api/v1/oauth2/placebo"
USER_AGENT = "da-story-edit/0.1.0 (+https://github.com/zoec98/da-story-edit)"


def _build_authorize_url(
    client_id: str, redirect_uri: str, scopes: str, state: str
) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scopes,
            "state": state,
        }
    )
    return f"{AUTHORIZE_ENDPOINT}?{query}"


def _token_request(form_data: dict[str, str]) -> dict[str, object]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    try:
        response = httpx.post(
            TOKEN_ENDPOINT, data=form_data, headers=headers, timeout=30.0
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        body = ""
        if isinstance(exc, httpx.HTTPStatusError):
            snippet = exc.response.text[:300].replace("\n", " ")
            body = f" Response body: {snippet}"
        raise ConfigError(f"OAuth token request failed.{body}") from exc

    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise ConfigError("OAuth token response was not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise ConfigError("OAuth token response had unexpected shape.")
    return payload


def _ensure_token_fields(payload: dict[str, object]) -> tuple[str, str]:
    access_token = str(payload.get("access_token") or "").strip()
    refresh_token = str(payload.get("refresh_token") or "").strip()
    if not access_token or not refresh_token:
        raise ConfigError(
            "OAuth token response was missing access_token or refresh_token."
        )
    return access_token, refresh_token


def _scope_from_payload(payload: dict[str, object]) -> str:
    return str(payload.get("scope") or "").strip()


def _refresh_tokens(
    cfg: dict[str, str], refresh_token: str, env_path: Path
) -> tuple[str, str, str]:
    payload = _token_request(
        {
            "grant_type": "refresh_token",
            "client_id": cfg["DA_CLIENT_ID"],
            "client_secret": cfg["DA_CLIENT_SECRET"],
            "refresh_token": refresh_token,
        }
    )
    access_token, new_refresh_token = _ensure_token_fields(payload)
    scope = _scope_from_payload(payload)
    updates = {
        "DA_ACCESS_TOKEN": access_token,
        "DA_REFRESH_TOKEN": new_refresh_token,
    }
    if scope:
        updates["DA_OAUTH_SCOPE"] = scope
    upsert_env_values(env_path, updates)
    return access_token, new_refresh_token, scope


def _validate_access_token(access_token: str) -> None:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    try:
        response = httpx.get(
            PLACEBO_ENDPOINT,
            params={"access_token": access_token},
            headers=headers,
            timeout=30.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        body = ""
        if isinstance(exc, httpx.HTTPStatusError):
            snippet = exc.response.text[:300].replace("\n", " ")
            body = f" Response body: {snippet}"
        raise ConfigError(f"Access token validation failed.{body}") from exc


def _fetch_gallery_page_urls(gallery_url: str, username: str) -> list[str]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html",
    }
    try:
        response = httpx.get(gallery_url, headers=headers, timeout=30.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ConfigError(
            "Failed to fetch gallery HTML fallback for URL parsing."
        ) from exc

    urls = extract_gallery_deviation_urls(response.text, username)
    if not urls:
        raise ConfigError(
            "Gallery HTML fallback could not find deviation URLs for this user."
        )
    return urls


def _normalize_url(url: str) -> str:
    return url.rstrip("/")


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    env_path = Path(".env")

    if args.command is None:
        load_required_config(
            ["DA_CLIENT_ID", "DA_CLIENT_SECRET", "DA_REDIRECT_URI"], env_path
        )
        print("Configuration looks good. Next: implement gallery processing pipeline.")
        return 0

    if args.command == "auth" and args.auth_command == "login-url":
        cfg = load_required_config(["DA_CLIENT_ID", "DA_REDIRECT_URI"], env_path)
        state = args.state or secrets.token_urlsafe(24)
        url = _build_authorize_url(
            cfg["DA_CLIENT_ID"], cfg["DA_REDIRECT_URI"], args.scopes, state
        )
        print(url)
        print(f"\nstate={state}")
        return 0

    if args.command == "auth" and args.auth_command == "exchange":
        cfg = load_required_config(
            ["DA_CLIENT_ID", "DA_CLIENT_SECRET", "DA_REDIRECT_URI"], env_path
        )
        payload = _token_request(
            {
                "grant_type": "authorization_code",
                "client_id": cfg["DA_CLIENT_ID"],
                "client_secret": cfg["DA_CLIENT_SECRET"],
                "redirect_uri": cfg["DA_REDIRECT_URI"],
                "code": args.code,
            }
        )
        access_token, refresh_token = _ensure_token_fields(payload)
        scope = _scope_from_payload(payload)
        updates = {
            "DA_ACCESS_TOKEN": access_token,
            "DA_REFRESH_TOKEN": refresh_token,
        }
        if scope:
            updates["DA_OAUTH_SCOPE"] = scope
        upsert_env_values(env_path, updates)
        print("OAuth code exchange succeeded. Updated token values in .env.")
        if scope:
            print(f"Scope: {scope}")
        return 0

    if args.command == "auth" and args.auth_command == "refresh":
        required = ["DA_CLIENT_ID", "DA_CLIENT_SECRET"]
        if args.refresh_token is None:
            required.append("DA_REFRESH_TOKEN")
        cfg = load_required_config(required, env_path)
        refresh_token = args.refresh_token or cfg["DA_REFRESH_TOKEN"]
        _, _, scope = _refresh_tokens(cfg, refresh_token, env_path)
        print("OAuth refresh succeeded. Updated token values in .env.")
        if scope:
            print(f"Scope: {scope}")
        return 0

    if args.command == "auth" and args.auth_command == "token-info":
        if args.refresh_first:
            cfg = load_required_config(
                ["DA_CLIENT_ID", "DA_CLIENT_SECRET", "DA_REFRESH_TOKEN"], env_path
            )
            access_token, _, scope = _refresh_tokens(
                cfg, cfg["DA_REFRESH_TOKEN"], env_path
            )
            cfg["DA_ACCESS_TOKEN"] = access_token
            if scope:
                cfg["DA_OAUTH_SCOPE"] = scope
        else:
            cfg = load_required_config(["DA_ACCESS_TOKEN"], env_path)

        _validate_access_token(cfg["DA_ACCESS_TOKEN"])

        known_scope = (cfg.get("DA_OAUTH_SCOPE") or "").strip()
        scope_tokens = {token for token in known_scope.split() if token}
        has_browse = "browse" in scope_tokens
        has_user_manage = "user.manage" in scope_tokens

        print("Access token is valid.")
        if known_scope:
            print(f"Known scope: {known_scope}")
            print(f"Has browse: {'yes' if has_browse else 'no'}")
            print(f"Has user.manage: {'yes' if has_user_manage else 'no'}")
            if has_browse and has_user_manage:
                print("Scope check: OK for planned read/write operations.")
            else:
                print("Scope check: missing required scopes for full workflow.")
        else:
            print("Known scope: unavailable")
            print(
                "Run `uv run da-story-edit auth refresh` once to capture scope into DA_OAUTH_SCOPE."
            )
        return 0

    if args.command == "gallery" and args.gallery_command == "list":
        if args.refresh_first:
            cfg = load_required_config(
                ["DA_CLIENT_ID", "DA_CLIENT_SECRET", "DA_REFRESH_TOKEN"], env_path
            )
            access_token, _, _ = _refresh_tokens(cfg, cfg["DA_REFRESH_TOKEN"], env_path)
            cfg["DA_ACCESS_TOKEN"] = access_token
        else:
            cfg = load_required_config(["DA_ACCESS_TOKEN"], env_path)

        target = parse_gallery_target(args.gallery)
        client = DeviantArtApiClient(
            access_token=cfg["DA_ACCESS_TOKEN"], user_agent=USER_AGENT
        )
        deviations: list[DeviationSummary] = []
        resolved_folder_id: str | None = None
        if target.folder_ref:
            if "-" in target.folder_ref:
                resolved_folder_id = target.folder_ref
            else:
                folders = client.list_folders(target.username)
                if target.folder_slug:
                    folder_map = {
                        slugify_name(folder.name): folder for folder in folders
                    }
                    match = folder_map.get(slugify_name(target.folder_slug))
                    if match:
                        resolved_folder_id = match.folder_id

        if resolved_folder_id is not None:
            deviations = client.list_gallery(
                username=target.username,
                folder_id=resolved_folder_id,
            )
        elif target.folder_ref and "://" in args.gallery:
            ordered_urls = _fetch_gallery_page_urls(args.gallery, target.username)
            all_gallery = client.list_gallery(username=target.username, folder_id=None)
            by_url = {_normalize_url(item.url): item for item in all_gallery}
            deviations = [
                by_url[url]
                for url in (_normalize_url(u) for u in ordered_urls)
                if url in by_url
            ]
            if not deviations:
                raise ConfigError(
                    "Could not map folder URLs from gallery HTML to API UUID entries."
                )
        else:
            deviations = client.list_gallery(username=target.username, folder_id=None)

        if args.order == "descending":
            deviations = list(reversed(deviations))

        if args.literature_only:
            deviations = [item for item in deviations if item.is_literature]

        print(
            f"Gallery list for {target.username}"
            f"{f' folder {resolved_folder_id}' if resolved_folder_id else ' (all)'}"
        )
        print(f"Order: {args.order}")
        print(f"Total entries: {len(deviations)}")

        for idx, item in enumerate(deviations, start=1):
            print(
                f"{idx:03d} | {item.kind:10} | {item.deviation_id} | {item.title} | {item.url}"
            )

        literature_count = sum(1 for item in deviations if item.is_literature)
        print(f"Literature entries: {literature_count}")
        return 0

    parser.print_help()
    return 2


def main() -> None:
    try:
        raise SystemExit(run())
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2) from exc
