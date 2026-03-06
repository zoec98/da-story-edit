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

    gallery_download = gallery_subparsers.add_parser(
        "download",
        help="Download literature deviations and store gallery artifacts locally.",
    )
    gallery_download.add_argument(
        "gallery",
        help="Gallery URL (preferred) or DeviantArt username.",
    )
    gallery_download.add_argument(
        "--workdir",
        default=None,
        help="Working directory for downloaded files (must be empty if existing).",
    )
    download_order = gallery_download.add_mutually_exclusive_group()
    download_order.add_argument(
        "--ascending",
        action="store_const",
        const="ascending",
        dest="order",
        help="Keep gallery order as shown on DeviantArt (manual order).",
    )
    download_order.add_argument(
        "--descending",
        action="store_const",
        const="descending",
        dest="order",
        help="Reverse gallery order (useful when chapters were posted over time).",
    )
    gallery_download.set_defaults(order="descending")

    gallery_link = gallery_subparsers.add_parser(
        "link",
        help="Apply local first/prev/next/last navigation to downloaded gallery artifacts.",
    )
    gallery_link.add_argument(
        "workdir",
        help="Gallery working directory created by `gallery download`.",
    )

    gallery_upload = gallery_subparsers.add_parser(
        "upload",
        help="Upload locally linked literature deviations from a gallery working directory.",
    )
    gallery_upload.add_argument(
        "workdir",
        help="Gallery working directory created by `gallery download` and updated by `gallery link`.",
    )

    return parser
