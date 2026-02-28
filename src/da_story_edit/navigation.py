from __future__ import annotations

from dataclasses import dataclass

TOP_START = "<!-- DA-STORY-EDIT:NAV:TOP:START -->"
TOP_END = "<!-- DA-STORY-EDIT:NAV:TOP:END -->"
BOTTOM_START = "<!-- DA-STORY-EDIT:NAV:BOTTOM:START -->"
BOTTOM_END = "<!-- DA-STORY-EDIT:NAV:BOTTOM:END -->"


@dataclass(frozen=True)
class NavTargets:
    first: str
    prev: str | None
    next: str | None
    last: str


def _link(label: str, url: str | None) -> str:
    if not url:
        return label
    return f'<a href="{url}">{label}</a>'


def render_nav_block(position: str, targets: NavTargets) -> str:
    if position not in {"top", "bottom"}:
        raise ValueError("position must be 'top' or 'bottom'")

    start = TOP_START if position == "top" else BOTTOM_START
    end = TOP_END if position == "top" else BOTTOM_END

    links = " | ".join(
        [
            _link("first", targets.first),
            _link("prev", targets.prev),
            _link("next", targets.next),
            _link("last", targets.last),
        ]
    )
    return f"{start}\n<p>{links}</p>\n{end}"


def _strip_block(body: str, start: str, end: str) -> str:
    current = body
    while True:
        start_idx = current.find(start)
        if start_idx == -1:
            break
        end_idx = current.find(end, start_idx)
        if end_idx == -1:
            # Malformed managed block: strip from start marker onward.
            current = current[:start_idx].rstrip()
            break
        end_idx += len(end)
        current = (current[:start_idx] + current[end_idx:]).strip()
    return current


def strip_managed_navigation(body: str) -> str:
    stripped = _strip_block(body, TOP_START, TOP_END)
    stripped = _strip_block(stripped, BOTTOM_START, BOTTOM_END)
    return stripped.strip()


def apply_navigation(body: str, targets: NavTargets) -> str:
    core = strip_managed_navigation(body)
    top = render_nav_block("top", targets)
    bottom = render_nav_block("bottom", targets)
    if core:
        return f"{top}\n\n{core}\n\n{bottom}\n"
    return f"{top}\n\n{bottom}\n"
