# PLAN.md

## Goal

Build a Python CLI application that takes a DeviantArt gallery URL, determines the ordered list of literature deviations, and updates each literature deviation to include consistent `first | prev | next | last` links at both top and bottom.

The update flow must be idempotent:

1. Remove old tool-managed navigation blocks.
2. Recompute sequence from current gallery contents.
3. Insert updated navigation blocks.

## Documentation-Validated Constraints

This plan is aligned to DeviantArt Developer API `v1/20240701`.

Confirmed from docs:

- Gallery listing should use API endpoints (`/gallery/all` or `/gallery/{folderid}`), not HTML scraping as primary.
- Deviation identity in API is UUID `deviationid` (string UUID), not the numeric slug tail in web URLs.
- Full literature/journal HTML is available via `GET /deviation/content` (scope: `browse`).
- Literature updates are supported via `POST /deviation/literature/update/{deviationid}` (scope: `user.manage`).
- API clients must send a User-Agent and use HTTP compression.

Implication:

- Numeric IDs parsed from web URLs are useful as a temporary HTML fallback only, not canonical identifiers for API editing.
- Main implementation should be OAuth2 API-first.

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

Primary strategy:

- Parse API response objects from `/gallery/all` or `/gallery/{folderid}`.
- Preserve API response order (including pagination order).
- Keep only entries where API type indicates literature.
- Use returned `deviationid` UUID directly.

Fallback strategy:

- Parse cached/public HTML only when API access is unavailable (development fallback).
- Mark fallback mode as read-only until UUID resolution is available.

### Deviation ID resolution

Primary:

- Use API-provided `deviationid` UUID from gallery response.

Fallback:

- If starting from URL list, resolve IDs through API metadata/deviation lookup before any write attempt.

## Editing Strategy

Confirmed: official update endpoint exists for literature updates.

Plan:

1. Start with dry-run mode:
   - compute and print intended changes only.
2. Implement real update mode after auth flow is verified.
3. Add strict checks:
   - only edit entries confirmed as literature in API response.
   - skip with warning if content is non-editable.
4. Preserve required fields on update:
   - title, is_mature, and any required maturity metadata must be sent to avoid unintended clearing.

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
2. Robust parsing
   - gallery URL resolution + API listing/pagination + tests
3. Navigation engine
   - block rendering and idempotent replacement logic
4. Edit client
   - `/deviation/content` read + `/deviation/literature/update/{uuid}` write + retries
5. Hardening
   - logging, error reporting, edge cases, docs refresh

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

## Immediate Next Actions

1. Implement API client (`httpx`) with User-Agent, OAuth token support, and endpoint wrappers.
2. Implement gallery URL resolver and API-based literature listing with UUID IDs.
3. Implement dry-run navigation generation from `/deviation/content`.
4. Implement marker-based idempotent replace engine + tests.
5. Implement literature update submission with preserved required fields + mocked contract tests.
