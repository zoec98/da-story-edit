# PLAN.md

## Goal

Build a Python CLI application that takes a DeviantArt gallery URL, determines the ordered list of literature deviations, and updates each literature deviation to include consistent `first | prev | next | last` links at both top and bottom.

The update flow must be idempotent:

1. Remove old tool-managed navigation blocks.
2. Recompute sequence from current gallery contents.
3. Insert updated navigation blocks.

## Status Update (2026-03-06)

The current codebase is beyond initial scaffolding. The source of truth is the implemented CLI and tests, not the earlier API assumptions in this document.

Current position in the plan:

- Delivery Phase 1 (`Foundation`): completed.
- Delivery Phase 2 (`Robust parsing`): completed for gallery listing and ordering behavior.
- Delivery Phase 3 (`Navigation engine`): completed.
- Delivery Phase 4 (`Edit client`): implemented at baseline.
- Delivery Phase 5 (`Hardening`): in progress.

What is implemented now:

- OAuth helper CLI:
  - `auth login-url`
  - `auth exchange`
  - `auth refresh`
  - `auth token-info`
- `.env` bootstrap/registry validation with non-destructive updates.
- Token handling:
  - normal commands use current access token
  - automatic one-time background refresh on token-expiry/invalid-token responses
  - clear fallback instruction to run `uv run da-story-edit auth refresh` on failure
- Gallery listing CLI:
  - `gallery list <gallery_url|username>`
  - `--ascending` keeps DA gallery order
  - `--descending` reverses order (default)
  - `--literature-only`
- Gallery workflow CLI:
  - `gallery download <gallery_url|username>`
  - `gallery link <workdir>`
  - `gallery upload <workdir>`
- UUID-safe behavior:
  - API operations use UUID `deviationid`
  - URL numeric suffixes are never used for API calls
- Folder URL handling:
  - try API folder resolution by folder slug first
  - then try the folder reference from the URL directly
  - otherwise fall back to `/gallery/all`
- Working-directory pipeline:
  - `gallery download` creates an empty gallery workdir, writes `manifest.json`, `*_meta.json`, and `*_original.html`
  - `gallery link` reads the manifest and originals, writes `*_updated.html` and `*.diff`
  - `gallery upload` reads the manifest and linked files, then uploads changed deviations
  - default workdirs live under `galleries/<slugified-gallery-name>`
- Deviation/edit API integration:
  - `GET /deviation/{uuid}?expand=deviation.fulltext` for metadata and fulltext blocks
  - `POST /deviation/literature/update/{uuid}` for writeback
- Failure handling now includes per-item `fetch_error`, `empty_content`, and missing-local-artifact reporting.

What is not implemented yet:

- Full write payload preservation hardening beyond `title`, `is_mature`, and rewritten `text`.
- A verified high-fidelity literature round-trip format for read-modify-write operations.
- Non-zero exit behavior when download/link/upload has per-item failures.
- Contract/integration tests that mock upload payload shape and retry behavior.
- Refactoring the sync orchestration out of `cli.py`.

## Documentation-Validated Constraints

This plan is aligned to DeviantArt Developer API `v1/20240701`.

Original plan assumptions:

- Gallery listing should use API endpoints (`/gallery/all` or `/gallery/{folderid}`), not HTML scraping as primary.
- Deviation identity in API is UUID `deviationid` (string UUID), not the numeric slug tail in web URLs.
- Literature updates are supported via `POST /deviation/literature/update/{deviationid}` (scope: `user.manage`).
- API clients must send a User-Agent and use HTTP compression.

Current code reality:

- Numeric IDs parsed from web URLs are useful as a temporary HTML fallback only, not canonical identifiers for API editing.
- Main implementation should be OAuth2 API-first.
- The current implementation does not call `GET /deviation/content`.
- Instead, it reads `text_content.body.markup.blocks` from `GET /deviation/{uuid}?expand=deviation.fulltext` and reconstructs simple HTML paragraphs locally before navigation insertion.
- This reconstruction path is the main open correctness question for the project.

## Configuration and Secrets Plan

Use `python-dotenv` and local `.env` (gitignored).

Startup behavior:

1. If `.env` is missing, create it.
2. Append any missing config keys from a registry, including short instruction comments.
3. Preserve all existing `.env` entries untouched.
4. Validate required values; if any are empty/missing, terminate with actionable instructions.

Initial required keys:

- `DA_CLIENT_ID`
- `DA_CLIENT_SECRET`
- `DA_REDIRECT_URI`

## Current Inputs

- Test gallery: `https://www.deviantart.com/zoec98/gallery/100193480/testgallery`
- Cached locally in `tmp/`:
  - `tmp/gallery_url.txt`
  - `tmp/000_gallery.html`
  - `tmp/url.txt` (ordered deviation URLs)
  - `tmp/001_deviation.html`
  - `tmp/002_deviation.html`
  - `tmp/003_deviation.html`

Observed ordered URLs:

1. `https://www.deviantart.com/zoec98/art/Ignore-Me-1-Test-Deviation-1303905935`
2. `https://www.deviantart.com/zoec98/art/Ignore-Me-2-Test-Deviation-1303906302`
3. `https://www.deviantart.com/zoec98/art/Ignore-Me-3-Final-Test-Deviation-1303906477`

Observed notes:

- Gallery HTML marks these as `literature` in the anchor `aria-label`.
- URL suffix numeric IDs are not the same as API UUID `deviationid`; API UUIDs must be resolved via API responses.

## Scope Boundaries

In scope:

- Gallery fetch + parse.
- Literature deviation filtering.
- Ordered navigation computation.
- Deviation edit operation with idempotent replace behavior.
- Logging and summary output.

Out of scope (initially):

- GUI/web frontend.
- Multi-account orchestration.
- Parallel edit workers.

## Architecture Plan

Proposed module layout:

- `src/da_story_edit/cli.py`:
  - CLI arg parsing, orchestration, output formatting.
- `src/da_story_edit/models.py`:
  - Typed models (`DeviationRef`, `NavigationTargets`, `EditResult`).
- `src/da_story_edit/gallery.py`:
  - API-first gallery discovery (`/gallery/all` and optional folder-targeting).
  - Resolve target folder from input gallery URL where possible.
  - Extract ordered literature entries with API UUIDs.
  - Optional HTML fallback parser for dev/debug only.
- `src/da_story_edit/deviation.py`:
  - Fetch deviation metadata and full content (`/deviation/{id}`, `/deviation/content`).
  - Normalize/validate literature vs non-literature.
  - Prepare update payload from existing fields + rewritten body.
- `src/da_story_edit/navigation.py`:
  - Build first/prev/next/last mapping.
  - Render nav block markup (top and bottom).
  - Idempotent strip/replace functions.
- `src/da_story_edit/client.py`:
  - OAuth2 token handling.
  - Typed wrappers for required DA endpoints.
  - Retry/error handling.

## API Contract Plan

Primary endpoints:

1. `GET /gallery/all` or `GET /gallery/{folderid}` to enumerate deviations in order.
2. `GET /deviation/content?deviationid=<uuid>` to fetch full literature HTML.
3. `POST /deviation/literature/update/{deviationid}` to write updated literature body.

Auth/scopes:

- Read flow: `browse` scope (client credentials or user grant where applicable).
- Write flow: user OAuth grant with `user.manage` scope.

HTTP requirements:

- Always send explicit User-Agent.
- Enable compression (httpx default supports compressed responses).

## Idempotency Design

Use explicit markers around managed blocks:

- Top block markers:
  - `<!-- DA-STORY-EDIT:NAV:TOP:START -->`
  - `<!-- DA-STORY-EDIT:NAV:TOP:END -->`
- Bottom block markers:
  - `<!-- DA-STORY-EDIT:NAV:BOTTOM:START -->`
  - `<!-- DA-STORY-EDIT:NAV:BOTTOM:END -->`

Update algorithm per deviation:

1. Load current literature content.
2. Remove any existing marked top/bottom blocks.
3. Generate fresh top/bottom blocks for current sequence position.
4. Insert top block at content start and bottom block at content end.
5. Submit literature update request with required preserved fields (title, maturity settings, etc.) plus new body.

Safety rule: if markers are malformed (start without end), fail that deviation explicitly and continue with others.

## Data Extraction Strategy

### Gallery parsing

Implemented strategy:

- Parse API response objects from `/gallery/all` or `/gallery/{folderid}`.
- Preserve API response order across pagination.
- Keep only entries where API type indicates literature.
- Use returned `deviationid` UUID directly.

### Deviation ID resolution

Implemented:

- Use API-provided `deviationid` UUID from gallery response.
- Do not use numeric ID suffixes from public web URLs for API reads or writes.

## Editing Strategy

Current implementation:

1. `sync` supports dry-run and live upload modes.
2. Only literature entries from gallery listing are processed.
3. For each literature deviation:
   - fetch metadata with `expand=deviation.fulltext`
   - reconstruct HTML from text blocks
   - strip existing managed nav blocks
   - insert fresh top and bottom nav blocks
   - write local artifacts and diffs
   - upload changed items in live mode
4. Current upload preserves only baseline fields:
   - `title`
   - `is_mature`
   - rewritten `text`

## CLI Plan

Initial command:

`uv run da-story-edit <gallery_url> [--dry-run] [--cache-dir tmp] [--verbose]`

Behavior:

- Resolve `username` and target gallery/folder context from URL.
- Fetch ordered deviations via API.
- Print ordered literature list with UUID deviation IDs.
- Compute navigation mapping.
- Dry-run: print diffs/summary only.
- Live mode: apply edits and print per-item results.

## Caching Plan (`tmp/`)

Purpose: reduce repeated network fetches during development.

Conventions:

- `tmp/gallery_url.txt`: test gallery source URL.
- `tmp/000_gallery.html`: cached gallery HTML.
- `tmp/url.txt`: ordered deviation URLs (one per line).
- `tmp/001_deviation.html`, `002_...`, ...: cached deviation pages in order.
- `tmp/gallery_all_page_<n>.json`: cached API list pages.
- `tmp/deviation_content_<uuid>.json`: cached API content payloads.

Cache policy:

- Reuse existing files by default.
- Refresh only with explicit `--refresh-cache`.

## Testing Plan

Framework/tools:

- `uv run pytest`
- `uv run ty check`
- `uv run ruff check --fix`
- `uv run ruff format`

Test phases:

1. Unit tests for parsing:
   - gallery URL parsing (`username`, folder slug/id hints)
   - API response parsing for literature detection and UUID extraction
2. Unit tests for navigation mapping:
   - first/middle/last edge cases
3. Unit tests for idempotent replacement:
   - no marker, existing marker, malformed marker
4. Integration-style tests using cached API JSON fixtures and optional HTML fallback fixtures.
5. CLI tests:
   - dry-run output
   - summary counts
6. Contract tests (mocked client):
   - update payload includes required preserved fields
   - update uses `/deviation/literature/update/{uuid}`

## Delivery Phases

1. Foundation
   - create modules, models, and CLI skeleton
   - implement API client with OAuth token plumbing
   - implement `.env` bootstrap + validation (registry-driven)
2. Robust parsing
   - gallery URL resolution + API listing/pagination + tests
3. Navigation engine
   - block rendering and idempotent replacement logic
4. Edit client
   - `GET /deviation/{uuid}?expand=deviation.fulltext` read + `/deviation/literature/update/{uuid}` write
5. Hardening
   - logging, error reporting, edge cases, docs refresh

Progress notes:

- Phase 1: done
- Phase 2: done (with URL-folder HTML fallback)
- Phase 3: done
- Phase 4: done (baseline)
- Phase 5: in progress

## Risks and Mitigations

- DeviantArt markup changes:
  - keep HTML parsing as fallback only; main path uses API.
- Authentication/session fragility:
  - isolate OAuth/token refresh in `client.py`, add retries and explicit failure messages.
- Partial update failures:
  - continue processing, report failures, non-zero exit on any failure.
- Content collision with user text:
  - unique marker strings and strict replacement logic.
- Parameter clearing risk on update endpoint:
  - always fetch/preserve required existing fields before posting updates.
- Content fidelity risk:
  - current fulltext-block-to-HTML reconstruction may lose formatting or semantics needed for safe round-trip uploads.

## Immediate Next Actions

1. Validate the literature body round-trip:
   - confirm whether `deviation.fulltext` block reconstruction is sufficient for upload
   - otherwise restore or replace with a safer content-read path
2. Harden literature update payload preservation:
   - confirm and preserve all required or behavior-sensitive fields beyond `title` and `is_mature`
3. Improve download/link/upload reporting and failure modes:
   - keep explicit changed/failed/uploaded counts
   - return non-zero when a command has failures
4. Add end-to-end and contract tests for:
   - download then link then upload workflow
   - rerun idempotency
   - partial failure reporting
   - token-expiry auto-refresh during upload
   - upload payload shape
5. Move current mixed orchestration out of `cli.py` into dedicated modules (`sync.py` / `deviation.py`) for maintainability
