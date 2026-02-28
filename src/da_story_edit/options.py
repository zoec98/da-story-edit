from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="da-story-edit",
        description="DeviantArt literature navigation editor.",
    )
    subparsers = parser.add_subparsers(dest="command")

    auth = subparsers.add_parser("auth", help="OAuth helper commands.")
    auth_subparsers = auth.add_subparsers(dest="auth_command", required=True)

    login_url = auth_subparsers.add_parser(
        "login-url", help="Print the DeviantArt OAuth authorize URL."
    )
    login_url.add_argument(
        "--scopes",
        default="browse user.manage",
        help="Space-separated OAuth scopes (default: browse user.manage).",
    )
    login_url.add_argument(
        "--state",
        default=None,
        help="Optional OAuth state value. Auto-generated if omitted.",
    )

    exchange = auth_subparsers.add_parser(
        "exchange",
        help="Exchange an OAuth authorization code for tokens and store them in .env.",
    )
    exchange.add_argument(
        "--code", required=True, help="Authorization code from redirect."
    )

    refresh = auth_subparsers.add_parser(
        "refresh",
        help="Refresh OAuth access token using refresh token from .env.",
    )
    refresh.add_argument(
        "--refresh-token",
        default=None,
        help="Optional refresh token override (defaults to DA_REFRESH_TOKEN).",
    )

    return parser
