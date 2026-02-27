# da-story-edit

`da-story-edit` is a Python application that processes a DeviantArt gallery and manages chapter-style navigation links for literature deviations.

Given a gallery URL, the tool will:

1. List deviations in that gallery.
2. Identify literature deviations and determine their deviation IDs.
3. Edit each literature deviation so it includes navigation links:
   - `first`
   - `prev`
   - `next`
   - `last`
4. Insert navigation at both the top and bottom of each literature deviation.
5. Stay idempotent: rerunning the tool removes/replaces previously managed navigation and writes the new correct navigation set.

## Project Status

This repository is in early setup phase. Core implementation is planned around the behavior above.

## Requirements

- Python `>=3.14` (as defined in `pyproject.toml`)
- [uv](https://docs.astral.sh/uv/)

## Installation

```bash
uv sync
```

## Planned CLI Usage

The package exposes a console entry point named `da-story-edit`.

Example target behavior:

```bash
uv run da-story-edit "https://www.deviantart.com/<user>/gallery/<id>/<name>"
```

Expected high-level output:

- Gallery summary (total deviations found)
- Literature deviations selected for editing
- Per-deviation edit result (updated/skipped/failed)
- Final summary

## Idempotency Contract

Navigation blocks created by this tool must be recognizable and fully replaceable. On repeated runs:

1. Existing tool-managed navigation blocks are detected and removed.
2. Current sequence order is recalculated from gallery content.
3. Fresh top/bottom navigation blocks are written.

This ensures safe reruns when deviations are added, removed, or reordered.

## Development

All commands must be run through `uv run`.

### Run tests

```bash
uv run pytest
```

### Type check

```bash
uv run ty check
```

### Lint and auto-fix

```bash
uv run ruff check --fix
```

### Format

```bash
uv run ruff format
```

### Suggested local cycle

```bash
uv run ruff format
uv run ruff check --fix
uv run ty check
uv run pytest
```

## License

TBD
