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

    auth_subparsers.add_parser(
        "token-info",
        help="Validate current access token and show known scope information.",
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

    sync = subparsers.add_parser(
        "sync",
        help="Download literature deviations, edit navigation locally, and optionally upload.",
    )
    sync.add_argument(
        "gallery",
        help="Gallery URL (preferred) or DeviantArt username.",
    )
    sync.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Do not upload; show planned changes only.",
    )
    sync.add_argument(
        "--workdir",
        default=None,
        help="Working directory for downloaded/edited files (must be empty if existing).",
    )
    sync_order = sync.add_mutually_exclusive_group()
    sync_order.add_argument(
        "--ascending",
        action="store_const",
        const="ascending",
        dest="order",
        help="Keep gallery order as shown on DeviantArt (manual order).",
    )
    sync_order.add_argument(
        "--descending",
        action="store_const",
        const="descending",
        dest="order",
        help="Reverse gallery order (useful when chapters were posted over time).",
    )
    sync.set_defaults(order="descending")

    return parser
