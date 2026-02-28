from da_story_edit.navigation import (
    BOTTOM_END,
    BOTTOM_START,
    TOP_END,
    TOP_START,
    NavTargets,
    apply_navigation,
    strip_managed_navigation,
)


def test_apply_navigation_inserts_top_and_bottom_blocks() -> None:
    body = "<p>Hello world</p>"
    updated = apply_navigation(
        body,
        NavTargets(
            first="https://example.com/1",
            prev=None,
            next="https://example.com/2",
            last="https://example.com/9",
        ),
    )
    assert TOP_START in updated
    assert TOP_END in updated
    assert BOTTOM_START in updated
    assert BOTTOM_END in updated
    assert "<p>Hello world</p>" in updated


def test_strip_managed_navigation_removes_existing_blocks() -> None:
    body = (
        f"{TOP_START}\n<p>old</p>\n{TOP_END}\n\n"
        "<p>content</p>\n\n"
        f"{BOTTOM_START}\n<p>old</p>\n{BOTTOM_END}\n"
    )
    stripped = strip_managed_navigation(body)
    assert stripped == "<p>content</p>"
