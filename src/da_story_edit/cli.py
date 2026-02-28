from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path
from urllib.parse import urlencode

import httpx

from da_story_edit.config import ConfigError, load_required_config, upsert_env_values
from da_story_edit.options import build_parser

AUTHORIZE_ENDPOINT = "https://www.deviantart.com/oauth2/authorize"
TOKEN_ENDPOINT = "https://www.deviantart.com/oauth2/token"
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
        upsert_env_values(
            env_path,
            {
                "DA_ACCESS_TOKEN": access_token,
                "DA_REFRESH_TOKEN": refresh_token,
            },
        )
        print(
            "OAuth code exchange succeeded. Updated DA_ACCESS_TOKEN and DA_REFRESH_TOKEN in .env."
        )
        return 0

    if args.command == "auth" and args.auth_command == "refresh":
        required = ["DA_CLIENT_ID", "DA_CLIENT_SECRET"]
        if args.refresh_token is None:
            required.append("DA_REFRESH_TOKEN")
        cfg = load_required_config(required, env_path)
        refresh_token = args.refresh_token or cfg["DA_REFRESH_TOKEN"]
        payload = _token_request(
            {
                "grant_type": "refresh_token",
                "client_id": cfg["DA_CLIENT_ID"],
                "client_secret": cfg["DA_CLIENT_SECRET"],
                "refresh_token": refresh_token,
            }
        )
        access_token, new_refresh_token = _ensure_token_fields(payload)
        upsert_env_values(
            env_path,
            {
                "DA_ACCESS_TOKEN": access_token,
                "DA_REFRESH_TOKEN": new_refresh_token,
            },
        )
        print(
            "OAuth refresh succeeded. Updated DA_ACCESS_TOKEN and DA_REFRESH_TOKEN in .env."
        )
        return 0

    parser.print_help()
    return 2


def main() -> None:
    try:
        raise SystemExit(run())
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2) from exc
