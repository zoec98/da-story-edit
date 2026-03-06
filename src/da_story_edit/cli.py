from __future__ import annotations

import json
import secrets
import sys
from datetime import UTC, datetime
from difflib import unified_diff
from html import escape
from pathlib import Path
import re
from typing import Callable, TypeVar, cast
import unicodedata
from urllib.parse import urlencode

import httpx

from da_story_edit.da_api import DeviantArtApiClient, slugify_name
from da_story_edit.config import (
    AuthTokenExpiredError,
    ConfigError,
    load_config,
    load_required_config,
    upsert_env_values,
)
from da_story_edit.gallery import (
    DeviationSummary,
    GalleryTarget,
    parse_gallery_target,
)
from da_story_edit.http_client import API_PROFILE, ThrottledHttpClient
from da_story_edit.navigation import NavTargets, apply_navigation
from da_story_edit.options import build_parser

AUTHORIZE_ENDPOINT = "https://www.deviantart.com/oauth2/authorize"
TOKEN_ENDPOINT = "https://www.deviantart.com/oauth2/token"
PLACEBO_ENDPOINT = "https://www.deviantart.com/api/v1/oauth2/placebo"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:148.0) "
    "Gecko/20100101 Firefox/148.0"
)
T = TypeVar("T")


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


def _token_request(
    form_data: dict[str, str], http_client: ThrottledHttpClient
) -> dict[str, object]:
    try:
        response = http_client.post(
            TOKEN_ENDPOINT,
            data={k: v for k, v in form_data.items()},
            profile=API_PROFILE,
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
    cfg: dict[str, str],
    refresh_token: str,
    env_path: Path,
    http_client: ThrottledHttpClient,
) -> tuple[str, str, str]:
    payload = _token_request(
        {
            "grant_type": "refresh_token",
            "client_id": cfg["DA_CLIENT_ID"],
            "client_secret": cfg["DA_CLIENT_SECRET"],
            "refresh_token": refresh_token,
        },
        http_client,
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


def _validate_access_token(access_token: str, http_client: ThrottledHttpClient) -> None:
    try:
        response = http_client.get(
            PLACEBO_ENDPOINT,
            params={"access_token": access_token},
            profile=API_PROFILE,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        if isinstance(exc, httpx.HTTPStatusError):
            if _looks_like_invalid_token(exc.response):
                raise AuthTokenExpiredError(
                    "Access token is invalid or expired."
                ) from exc
        body = ""
        if isinstance(exc, httpx.HTTPStatusError):
            snippet = exc.response.text[:300].replace("\n", " ")
            body = f" Response body: {snippet}"
        raise ConfigError(f"Access token validation failed.{body}") from exc


def _resolve_gallery_deviations(
    access_token: str,
    gallery_input: str,
    http_client: ThrottledHttpClient,
) -> tuple[GalleryTarget, list[DeviationSummary], str | None, str]:
    target = parse_gallery_target(gallery_input)
    client = DeviantArtApiClient(
        access_token=access_token,
        user_agent=USER_AGENT,
        http_client=http_client,
    )

    deviations: list[DeviationSummary] = []
    resolved_folder_id: str | None = None
    workspace_label = target.username
    folders = client.list_folders(target.username) if target.folder_slug else []
    if target.folder_slug:
        folder_map = {slugify_name(folder.name): folder for folder in folders}
        match = folder_map.get(slugify_name(target.folder_slug))
        if match:
            candidate = client.list_gallery(
                username=target.username,
                folder_id=match.folder_id,
                mode="newest",
            )
            if candidate:
                deviations = candidate
                resolved_folder_id = match.folder_id
                workspace_label = match.name

    if not deviations and target.folder_ref:
        if not folders:
            folders = client.list_folders(target.username)
        folder_by_id = {folder.folder_id: folder for folder in folders}
        candidate = client.list_gallery(
            username=target.username,
            folder_id=target.folder_ref,
            mode="newest",
        )
        if candidate:
            deviations = candidate
            resolved_folder_id = target.folder_ref
            matched_folder = folder_by_id.get(target.folder_ref)
            if matched_folder:
                workspace_label = matched_folder.name
            elif target.folder_slug:
                workspace_label = target.folder_slug

    if not deviations:
        deviations = client.list_gallery(
            username=target.username,
            folder_id=None,
            mode="newest",
        )
        resolved_folder_id = None

    return target, deviations, resolved_folder_id, workspace_label


def _ensure_empty_workdir(path: Path) -> Path:
    if path.exists():
        if not path.is_dir():
            raise ConfigError(f"Workdir path exists and is not a directory: {path}")
        if any(path.iterdir()):
            raise ConfigError(f"Workdir must be empty: {path}")
    else:
        path.mkdir(parents=True, exist_ok=False)
    return path


def _slugify_path_name(value: str) -> str:
    normalized = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    )
    lowered = normalized.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "gallery"


def _default_gallery_workdir(label: str) -> Path:
    return Path("galleries") / _slugify_path_name(label)


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


def _html_from_fulltext_markup(payload: dict[str, object]) -> str:
    text_content = payload.get("text_content")
    if not isinstance(text_content, dict):
        return ""
    text_content_dict = cast(dict[str, object], text_content)
    body = text_content_dict.get("body")
    if not isinstance(body, dict):
        return ""
    body_dict = cast(dict[str, object], body)
    markup = body_dict.get("markup")
    if not isinstance(markup, dict):
        return ""
    markup_dict = cast(dict[str, object], markup)
    blocks = markup_dict.get("blocks")
    if not isinstance(blocks, list):
        return ""

    lines: list[str] = []
    for raw_block in blocks:
        if not isinstance(raw_block, dict):
            continue
        block = cast(dict[str, object], raw_block)
        text = str(block.get("text") or "")
        if not text.strip():
            continue
        escaped = escape(text).replace("\n", "<br>")
        lines.append(f"<p>{escaped}</p>")
    return "\n".join(lines)


def _manifest_path(workdir: Path) -> Path:
    return workdir / "manifest.json"


def _read_manifest(workdir: Path) -> dict[str, object]:
    manifest_path = _manifest_path(workdir)
    if not manifest_path.exists():
        raise ConfigError(f"Manifest not found: {manifest_path}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Manifest is not valid JSON: {manifest_path}") from exc
    if not isinstance(payload, dict):
        raise ConfigError(f"Manifest has unexpected shape: {manifest_path}")
    return payload


def _write_manifest(workdir: Path, manifest: dict[str, object]) -> None:
    _manifest_path(workdir).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _manifest_items(manifest: dict[str, object]) -> list[dict[str, object]]:
    raw_items = manifest.get("items")
    if not isinstance(raw_items, list):
        raise ConfigError("Manifest is missing an 'items' list.")
    items: list[dict[str, object]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            raise ConfigError("Manifest item has unexpected shape.")
        items.append(cast(dict[str, object], raw_item))
    return items


def _item_base_name(idx: int, deviation_id: str) -> str:
    safe_id = deviation_id.replace("/", "_")
    return f"{idx:03d}_{safe_id}"


def _run_with_optional_refresh(
    env_path: Path,
    operation: Callable[[str], T],
    http_client: ThrottledHttpClient,
) -> tuple[T, bool]:
    cfg = load_required_config(["DA_ACCESS_TOKEN"], env_path)
    access_token = cfg["DA_ACCESS_TOKEN"]
    refreshed = False
    try:
        _validate_access_token(access_token, http_client)
    except AuthTokenExpiredError:
        raw = load_config(env_path)
        has_refresh_setup = all(
            (raw.get(name) or "").strip()
            for name in ["DA_CLIENT_ID", "DA_CLIENT_SECRET", "DA_REFRESH_TOKEN"]
        )
        if not has_refresh_setup:
            raise ConfigError(
                "Access token is invalid or expired and automatic refresh is not configured.\n"
                "Set DA_CLIENT_ID, DA_CLIENT_SECRET, and DA_REFRESH_TOKEN in .env,\n"
                "then run `uv run da-story-edit auth refresh`."
            )

        refresh_cfg = load_required_config(
            ["DA_CLIENT_ID", "DA_CLIENT_SECRET", "DA_REFRESH_TOKEN"], env_path
        )
        access_token, _, _ = _refresh_tokens(
            refresh_cfg,
            refresh_cfg["DA_REFRESH_TOKEN"],
            env_path,
            http_client,
        )
        refreshed = True
        try:
            _validate_access_token(access_token, http_client)
        except AuthTokenExpiredError as exc:
            raise ConfigError(
                "Automatic token refresh was attempted once but the refreshed token is still rejected.\n"
                "Run `uv run da-story-edit auth refresh` manually and retry the command."
            ) from exc

    try:
        return operation(access_token), refreshed
    except AuthTokenExpiredError:
        if refreshed:
            raise ConfigError(
                "API rejected the refreshed access token during operation.\n"
                "Run `uv run da-story-edit auth refresh` manually and retry the command."
            ) from None

        raw = load_config(env_path)
        has_refresh_setup = all(
            (raw.get(name) or "").strip()
            for name in ["DA_CLIENT_ID", "DA_CLIENT_SECRET", "DA_REFRESH_TOKEN"]
        )
        if not has_refresh_setup:
            raise ConfigError(
                "Access token is invalid or expired and automatic refresh is not configured.\n"
                "Set DA_CLIENT_ID, DA_CLIENT_SECRET, and DA_REFRESH_TOKEN in .env,\n"
                "then run `uv run da-story-edit auth refresh`."
            ) from None
        refresh_cfg = load_required_config(
            ["DA_CLIENT_ID", "DA_CLIENT_SECRET", "DA_REFRESH_TOKEN"], env_path
        )
        access_token, _, _ = _refresh_tokens(
            refresh_cfg,
            refresh_cfg["DA_REFRESH_TOKEN"],
            env_path,
            http_client,
        )
        try:
            _validate_access_token(access_token, http_client)
            return operation(access_token), True
        except AuthTokenExpiredError as exc:
            raise ConfigError(
                "Automatic token refresh was attempted once but the token is still rejected.\n"
                "Run `uv run da-story-edit auth refresh` manually and retry the command."
            ) from exc


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    env_path = Path(".env")
    http_client = ThrottledHttpClient(user_agent=USER_AGENT)

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
            },
            http_client,
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
        _, _, scope = _refresh_tokens(cfg, refresh_token, env_path, http_client)
        print("OAuth refresh succeeded. Updated token values in .env.")
        if scope:
            print(f"Scope: {scope}")
        return 0

    if args.command == "auth" and args.auth_command == "token-info":
        _run_with_optional_refresh(
            env_path,
            lambda access_token: _validate_access_token(access_token, http_client),
            http_client,
        )
        cfg = load_config(env_path)

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
        result, _ = _run_with_optional_refresh(
            env_path,
            lambda access_token: _resolve_gallery_deviations(
                access_token, args.gallery, http_client
            ),
            http_client,
        )
        target, deviations, resolved_folder_id, _ = result

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

    if args.command == "gallery" and args.gallery_command == "download":
        result, refreshed = _run_with_optional_refresh(
            env_path,
            lambda access_token: _resolve_gallery_deviations(
                access_token, args.gallery, http_client
            ),
            http_client,
        )
        target, deviations, resolved_folder_id, workspace_label = result
        if args.order == "descending":
            deviations = list(reversed(deviations))
        literature = [item for item in deviations if item.is_literature]
        if not literature:
            raise ConfigError(
                "No literature deviations found in selected gallery scope."
            )

        if args.workdir:
            workdir = _ensure_empty_workdir(Path(args.workdir))
        else:
            workdir = _ensure_empty_workdir(_default_gallery_workdir(workspace_label))

        cfg = load_config(env_path)
        access_token = cfg.get("DA_ACCESS_TOKEN") or ""
        if refreshed:
            access_token = load_required_config(["DA_ACCESS_TOKEN"], env_path)[
                "DA_ACCESS_TOKEN"
            ]
        client = DeviantArtApiClient(
            access_token=access_token,
            user_agent=USER_AGENT,
            http_client=http_client,
        )

        failed_count = 0
        downloaded_count = 0
        print(f"Gallery workdir: {workdir}")
        print(f"Gallery: {target.username}")
        if resolved_folder_id:
            print(f"Folder: {resolved_folder_id}")
        print(f"Order: {args.order}")
        print(f"Literature items: {len(literature)}")
        print("Mode: download")

        manifest_items: list[dict[str, object]] = []

        for idx, item in enumerate(literature, start=1):
            try:
                metadata = client.get_deviation(
                    item.deviation_id, expand="deviation.fulltext"
                )
            except ConfigError as exc:
                failed_count += 1
                print(
                    f"{idx:03d} {item.title} [{item.deviation_id}] failed=fetch_error details={exc}"
                )
                continue

            html = _html_from_fulltext_markup(metadata)
            if not html.strip():
                failed_count += 1
                print(
                    f"{idx:03d} {item.title} [{item.deviation_id}] failed=empty_content "
                    "details=no body markup in /deviation/{uuid}?expand=deviation.fulltext"
                )
                continue

            base = _item_base_name(idx, item.deviation_id)
            (workdir / f"{base}_meta.json").write_text(
                json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
            )
            (workdir / f"{base}_original.html").write_text(html, encoding="utf-8")
            manifest_items.append(
                {
                    "index": idx,
                    "deviation_id": item.deviation_id,
                    "title": item.title,
                    "url": item.url,
                    "kind": item.kind,
                    "base_name": base,
                }
            )
            downloaded_count += 1
            print(
                f"{idx:03d} {item.title} [{item.deviation_id}] downloaded=yes"
            )

        manifest = {
            "schema_version": 1,
            "downloaded_at": datetime.now(UTC).isoformat(),
            "gallery_input": args.gallery,
            "gallery_username": target.username,
            "resolved_folder_id": resolved_folder_id,
            "workspace_label": workspace_label,
            "order": args.order,
            "items": manifest_items,
        }
        _write_manifest(workdir, manifest)

        print(f"Downloaded items: {downloaded_count}")
        print(f"Failed items: {failed_count}")
        print(f"Manifest: {_manifest_path(workdir)}")
        return 0

    if args.command == "gallery" and args.gallery_command == "link":
        workdir = Path(args.workdir)
        manifest = _read_manifest(workdir)
        items = _manifest_items(manifest)
        if not items:
            raise ConfigError("Manifest contains no items to link.")

        changed_count = 0
        failed_count = 0
        print(f"Gallery workdir: {workdir}")
        print("Mode: link")
        print(f"Literature items: {len(items)}")

        urls = [str(item.get("url") or "").strip() for item in items]
        if any(not url for url in urls):
            raise ConfigError("Manifest contains an item with a missing URL.")

        for idx, item in enumerate(items, start=1):
            deviation_id = str(item.get("deviation_id") or "").strip()
            title = str(item.get("title") or "").strip() or deviation_id
            base = str(item.get("base_name") or "").strip()
            if not deviation_id or not base:
                raise ConfigError("Manifest contains an item with missing identifiers.")

            original_path = workdir / f"{base}_original.html"
            if not original_path.exists():
                failed_count += 1
                print(f"{idx:03d} {title} [{deviation_id}] failed=missing_original")
                continue

            html = original_path.read_text(encoding="utf-8")
            targets = NavTargets(
                first=urls[0],
                prev=urls[idx - 2] if idx > 1 else None,
                next=urls[idx] if idx < len(urls) else None,
                last=urls[-1],
            )
            updated = apply_navigation(html, targets)
            changed = updated != (html if html.endswith("\n") else f"{html}\n")

            (workdir / f"{base}_updated.html").write_text(updated, encoding="utf-8")
            diff = "\n".join(
                unified_diff(
                    (html or "").splitlines(),
                    updated.splitlines(),
                    fromfile=f"{base}_original.html",
                    tofile=f"{base}_updated.html",
                    lineterm="",
                )
            )
            (workdir / f"{base}.diff").write_text(
                diff + ("\n" if diff else ""), encoding="utf-8"
            )

            print(f"{idx:03d} {title} [{deviation_id}] changed={'yes' if changed else 'no'}")
            if changed:
                changed_count += 1

        manifest["linked_at"] = datetime.now(UTC).isoformat()
        _write_manifest(workdir, manifest)
        print(f"Changed items: {changed_count}")
        print(f"Failed items: {failed_count}")
        return 0

    if args.command == "gallery" and args.gallery_command == "upload":
        workdir = Path(args.workdir)
        manifest = _read_manifest(workdir)
        items = _manifest_items(manifest)
        if not items:
            raise ConfigError("Manifest contains no items to upload.")

        def _upload_operation(access_token: str) -> tuple[int, int]:
            client = DeviantArtApiClient(
                access_token=access_token,
                user_agent=USER_AGENT,
                http_client=http_client,
            )
            uploaded_count = 0
            failed_count = 0

            print(f"Gallery workdir: {workdir}")
            print("Mode: upload")
            print(f"Literature items: {len(items)}")

            for idx, item in enumerate(items, start=1):
                deviation_id = str(item.get("deviation_id") or "").strip()
                title = str(item.get("title") or "").strip() or deviation_id
                base = str(item.get("base_name") or "").strip()
                if not deviation_id or not base:
                    raise ConfigError(
                        "Manifest contains an item with missing identifiers."
                    )

                meta_path = workdir / f"{base}_meta.json"
                original_path = workdir / f"{base}_original.html"
                updated_path = workdir / f"{base}_updated.html"
                if not meta_path.exists():
                    failed_count += 1
                    print(f"{idx:03d} {title} [{deviation_id}] failed=missing_meta")
                    continue
                if not original_path.exists():
                    failed_count += 1
                    print(f"{idx:03d} {title} [{deviation_id}] failed=missing_original")
                    continue
                if not updated_path.exists():
                    failed_count += 1
                    print(f"{idx:03d} {title} [{deviation_id}] failed=missing_updated")
                    continue

                try:
                    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    raise ConfigError(f"Metadata is not valid JSON: {meta_path}") from exc
                if not isinstance(metadata, dict):
                    raise ConfigError(f"Metadata has unexpected shape: {meta_path}")

                original_html = original_path.read_text(encoding="utf-8")
                updated_html = updated_path.read_text(encoding="utf-8")
                changed = updated_html != (
                    original_html
                    if original_html.endswith("\n")
                    else f"{original_html}\n"
                )
                print(f"{idx:03d} {title} [{deviation_id}] changed={'yes' if changed else 'no'}")
                if not changed:
                    continue

                client.update_literature(
                    deviation_id=deviation_id,
                    title=str(metadata.get("title") or title),
                    body_html=updated_html,
                    is_mature=bool(metadata.get("is_mature")),
                )
                uploaded_count += 1

            return uploaded_count, failed_count

        (uploaded_count, failed_count), _ = _run_with_optional_refresh(
            env_path,
            _upload_operation,
            http_client,
        )
        manifest["uploaded_at"] = datetime.now(UTC).isoformat()
        _write_manifest(workdir, manifest)
        print(f"Uploaded items: {uploaded_count}")
        print(f"Failed items: {failed_count}")
        return 0

    parser.print_help()
    return 2


def main() -> None:
    try:
        raise SystemExit(run())
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2) from exc
