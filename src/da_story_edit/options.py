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

    token_info = auth_subparsers.add_parser(
        "token-info",
        help="Validate current access token and show known scope information.",
    )
    token_info.add_argument(
        "--refresh-first",
        action="store_true",
        help="Refresh access token before validating it.",
    )

    gallery = subparsers.add_parser("gallery", help="Gallery operations.")
    gallery_subparsers = gallery.add_subparsers(dest="gallery_command", required=True)

    gallery_list = gallery_subparsers.add_parser(
        "list",
        help="List deviations for a gallery URL or username.",
    )
    gallery_list.add_argument(
        "gallery",
        help="Gallery URL (preferred) or DeviantArt username.",
    )
    gallery_list.add_argument(
        "--literature-only",
        action="store_true",
        help="Show only literature deviations.",
    )
    gallery_list.add_argument(
        "--refresh-first",
        action="store_true",
        help="Refresh access token before listing.",
    )
    order_group = gallery_list.add_mutually_exclusive_group()
    order_group.add_argument(
        "--ascending",
        action="store_const",
        const="ascending",
        dest="order",
        help="Keep gallery order as shown on DeviantArt (manual order).",
    )
    order_group.add_argument(
        "--descending",
        action="store_const",
        const="descending",
        dest="order",
        help="Reverse gallery order (useful when chapters were posted over time).",
    )
    gallery_list.set_defaults(order="descending")

    return parser
