from da_story_edit.cli import _html_from_fulltext_markup


def test_html_from_fulltext_markup_renders_blocks() -> None:
    payload: dict[str, object] = {
        "text_content": {
            "body": {
                "markup": {
                    "blocks": [
                        {"text": "Line one", "type": "unstyled"},
                        {"text": "Line two\ncontinued", "type": "unstyled"},
                    ]
                }
            }
        }
    }

    html = _html_from_fulltext_markup(payload)

    assert "<p>Line one</p>" in html
    assert "<p>Line two<br>continued</p>" in html


def test_html_from_fulltext_markup_returns_empty_without_blocks() -> None:
    payload: dict[str, object] = {
        "text_content": {
            "body": {
                "type": "draft",
                "features": "[]",
            }
        }
    }

    html = _html_from_fulltext_markup(payload)

    assert html == ""
