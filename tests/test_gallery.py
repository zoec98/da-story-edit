import pytest

from da_story_edit.config import ConfigError
from da_story_edit.da_api import slugify_name
from da_story_edit.gallery import (
    extract_gallery_deviation_urls,
    parse_gallery_results,
    parse_gallery_target,
)


def test_parse_gallery_target_from_test_url() -> None:
    target = parse_gallery_target(
        "https://www.deviantart.com/zoec98/gallery/100193480/testgallery"
    )
    assert target.username == "zoec98"
    assert target.folder_ref == "100193480"
    assert target.folder_slug == "testgallery"


def test_parse_gallery_target_from_username() -> None:
    target = parse_gallery_target("zoec98")
    assert target.username == "zoec98"
    assert target.folder_ref is None


def test_parse_gallery_target_rejects_non_deviantart_host() -> None:
    with pytest.raises(ConfigError):
        parse_gallery_target("https://example.com/zoec98/gallery/100193480/testgallery")


def test_parse_gallery_results_extracts_valid_entries() -> None:
    payload: dict[str, object] = {
        "results": [
            {
                "deviationid": "uuid-1",
                "title": "Title 1",
                "url": "https://www.deviantart.com/a/art/x",
                "type": "literature",
            },
            {
                "deviationid": "",
                "title": "missing id",
                "url": "https://www.deviantart.com/a/art/y",
                "type": "literature",
            },
        ]
    }

    results = parse_gallery_results(payload)
    assert len(results) == 1
    assert results[0].deviation_id == "uuid-1"
    assert results[0].is_literature is True


def test_slugify_name_matches_gallery_slug_style() -> None:
    assert slugify_name("Test Gallery") == "testgallery"


def test_extract_gallery_deviation_urls_preserves_order_and_deduplicates() -> None:
    html = """
    <a href="https://www.deviantart.com/zoec98/art/A-1"></a>
    <a href="https://www.deviantart.com/zoec98/art/B-2"></a>
    <a href="https://www.deviantart.com/zoec98/art/A-1"></a>
    """
    urls = extract_gallery_deviation_urls(html, "zoec98")
    assert urls == [
        "https://www.deviantart.com/zoec98/art/A-1",
        "https://www.deviantart.com/zoec98/art/B-2",
    ]
