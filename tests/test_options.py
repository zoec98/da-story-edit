from da_story_edit.cli import _build_authorize_url
from da_story_edit.options import build_parser


def test_build_parser_parses_auth_login_url() -> None:
    parser = build_parser()
    args = parser.parse_args(["auth", "login-url", "--scopes", "browse user.manage"])

    assert args.command == "auth"
    assert args.auth_command == "login-url"
    assert args.scopes == "browse user.manage"


def test_build_parser_parses_exchange_code() -> None:
    parser = build_parser()
    args = parser.parse_args(["auth", "exchange", "--code", "abc123"])

    assert args.command == "auth"
    assert args.auth_command == "exchange"
    assert args.code == "abc123"


def test_build_authorize_url_contains_expected_parameters() -> None:
    url = _build_authorize_url(
        client_id="12345",
        redirect_uri="http://localhost:8765/callback",
        scopes="browse user.manage",
        state="fixed-state",
    )

    assert "https://www.deviantart.com/oauth2/authorize?" in url
    assert "response_type=code" in url
    assert "client_id=12345" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8765%2Fcallback" in url
    assert "scope=browse+user.manage" in url
    assert "state=fixed-state" in url


def test_build_parser_parses_token_info() -> None:
    parser = build_parser()
    args = parser.parse_args(["auth", "token-info"])

    assert args.command == "auth"
    assert args.auth_command == "token-info"


def test_build_parser_gallery_list_defaults_to_descending() -> None:
    parser = build_parser()
    args = parser.parse_args(["gallery", "list", "zoec98"])

    assert args.command == "gallery"
    assert args.gallery_command == "list"
    assert args.order == "descending"


def test_build_parser_gallery_list_accepts_ascending() -> None:
    parser = build_parser()
    args = parser.parse_args(["gallery", "list", "zoec98", "--ascending"])

    assert args.order == "ascending"


def test_build_parser_parses_sync_dry_run_short_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(["sync", "zoec98", "-n"])

    assert args.command == "sync"
    assert args.gallery == "zoec98"
    assert args.dry_run is True
    assert args.order == "descending"
