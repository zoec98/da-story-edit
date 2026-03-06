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

This repository is in active implementation.

Implemented today:

- OAuth helper commands for login URL generation, code exchange, token refresh, and token validation.
- `.env` bootstrap and required-key validation.
- Gallery commands via DeviantArt API with folder resolution, ordering controls, and literature-only filtering.
- Split gallery workflow:
  - `gallery download` fetches literature deviations and stores local artifacts,
  - `gallery link` rewrites managed navigation blocks locally,
  - `gallery upload` uploads locally linked deviations.

Still in progress:

- hardening the literature read/write contract,
- preserving all write-sensitive fields on update,
- improving failure classification and sync summary behavior,
- broader integration-style tests for download/link/upload behavior.

## Requirements

- Python `>=3.14` (as defined in `pyproject.toml`)
- [uv](https://docs.astral.sh/uv/)

## Installation

```bash
uv sync
```

## Configuration

Configuration is loaded from `.env` using `python-dotenv`.

On startup, the app will:

1. Create `.env` if it does not exist.
2. Append any missing registry keys with instruction comments.
3. Preserve existing keys/values already in `.env`.
4. Exit with instructions if required values are still empty.

Current required keys:

- `DA_CLIENT_ID`
- `DA_CLIENT_SECRET`
- `DA_REDIRECT_URI`

OAuth helper commands:

```bash
uv run da-story-edit auth login-url
uv run da-story-edit auth exchange --code "<authorization-code>"
uv run da-story-edit auth refresh
uv run da-story-edit auth token-info
```

Gallery commands:

```bash
uv run da-story-edit gallery list "https://www.deviantart.com/<user>/gallery/<folderid>/<slug>" --descending
uv run da-story-edit gallery list "https://www.deviantart.com/<user>/gallery/<folderid>/<slug>" --ascending
uv run da-story-edit gallery download "https://www.deviantart.com/<user>/gallery/<folderid>/<slug>"
uv run da-story-edit gallery link galleries/<gallery-name>
uv run da-story-edit gallery upload galleries/<gallery-name>
```

Notes:

- `--descending` is the default.
- `--ascending` keeps the gallery order as shown on DeviantArt.
- `--descending` reverses that order.
- `--literature-only` filters `gallery list` output to literature deviations.
- `gallery download` defaults to `galleries/<gallery-name>` where the name is slugified for filesystem use.

Working directory layout:

```bash
galleries/
  horse-stories/
    manifest.json
    001_<uuid>_meta.json
    001_<uuid>_original.html
    001_<uuid>_updated.html
    001_<uuid>.diff
    ...
```

Notes:

- `gallery download` reads deviation metadata with `expand=deviation.fulltext`, reconstructs simple HTML from text blocks, and stores per-item metadata and original HTML.
- `gallery link` reads downloaded artifacts, applies navigation locally, and writes `*_updated.html` and `*.diff`.
- `gallery upload` uploads changed `*_updated.html` files via the literature update endpoint.
- Use `--workdir <path>` with `gallery download` to override the default `galleries/<gallery-name>` path.
- Current upload payload preservation is baseline only: `title`, `is_mature`, and rewritten `text`.

## CLI Usage

The package exposes a console entry point named `da-story-edit`.

Currently available commands:

```bash
uv run da-story-edit auth login-url
uv run da-story-edit auth exchange --code "<authorization-code>"
uv run da-story-edit auth refresh
uv run da-story-edit auth token-info
uv run da-story-edit gallery list "https://www.deviantart.com/<user>/gallery/<id>/<name>"
uv run da-story-edit gallery download "https://www.deviantart.com/<user>/gallery/<id>/<name>"
uv run da-story-edit gallery link galleries/<gallery-name>
uv run da-story-edit gallery upload galleries/<gallery-name>
```

Current high-level workflow output:

- Gallery summary (total deviations found)
- Literature deviations selected for editing
- Per-deviation download/link/upload result with `changed=yes|no` or `failed=...`
- Final summary counts for downloaded, changed, failed, or uploaded items depending on the command

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
