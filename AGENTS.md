# AGENTS.md

This file defines how humans and coding agents should work in this repository.

## Mission

Build a Python application that:

1. Accepts a DeviantArt gallery URL.
2. Lists deviations in that gallery.
3. Identifies literature deviations and resolves their deviation IDs.
4. Edits each literature deviation to add `first`, `prev`, `next`, `last` navigation links at:
   - the top
   - the bottom
5. Is idempotent: reruns replace old tool-managed navigation with fresh correct navigation.

## Audience Split

- `README.md`: user-facing behavior and usage.
- `AGENTS.md` (this file): contributor and agent implementation/process rules.

## Tech Stack

- Language: Python
- Package/runtime manager: `uv`
- Configuration/secrets: `python-dotenv` with local `.env` (never committed)
- Tests: `pytest`
- Type checking: `ty` (Astral, via `ty check`)
- Linting: `ruff check --fix`
- Formatting: `ruff format`

## Non-Negotiable Command Policy

Run project tooling with `uv run ...` only.

- Allowed:
  - `uv run pytest`
  - `uv run ty check`
  - `uv run ruff check --fix`
  - `uv run ruff format`
- Not allowed:
  - `pytest`
  - `ty`
  - `ruff ...`

If a command needs project context, execute it from the repository root.

## Configuration Contract

- Use `.env` for local config and secrets.
- On startup, bootstrap `.env` from a central config registry:
  - create `.env` if missing
  - append only missing keys with instruction comments
  - never overwrite existing key/value pairs
- If required values remain empty, terminate with clear user instructions.

## Implementation Guidance

### Idempotent navigation editing

- Use clearly delimited markers for tool-managed navigation blocks so they can be replaced safely.
- On each run:
  1. Strip existing managed blocks from target deviations.
  2. Recompute sequence order from current gallery state.
  3. Write new blocks at top and bottom.

### Ordering assumptions

- Define one canonical ordering rule and keep it stable.
- If ordering cannot be determined reliably, fail explicitly instead of producing ambiguous links.

### Data model expectations

Keep a structured representation for literature entries, e.g.:

- deviation ID
- title
- URL
- sequence index
- navigation targets (`first`, `prev`, `next`, `last`)

### Error handling

- Continue processing other deviations when one edit fails.
- Emit a clear per-item result and a final summary.
- Distinguish between:
  - fetch/parsing failures
  - permission/auth failures
  - edit/update failures

## Suggested Repository Layout

As implementation grows, prefer:

- `src/da_story_edit/cli.py`
- `src/da_story_edit/gallery.py`
- `src/da_story_edit/literature.py`
- `src/da_story_edit/navigation.py`
- `src/da_story_edit/client.py`
- `tests/`

Adjust as needed, but keep responsibilities separated.

## Testing Expectations

Minimum target test coverage areas:

1. Gallery parsing and literature filtering.
2. Deviation ID extraction.
3. Navigation mapping for first/prev/next/last.
4. Idempotent replace behavior (existing managed blocks are replaced, not duplicated).
5. Error path behavior and summary reporting.

## Contributor Workflow

Recommended local cycle:

```bash
uv run ruff format
uv run ruff check --fix
uv run ty check
uv run pytest
```

Before opening a PR:

1. Ensure all four commands above pass.
2. Add/update tests for behavior changes.
3. Update `README.md` and this file when user-facing behavior or process changes.

## Agent Guardrails

Agents working in this repository must follow these constraints:

1. Respect scope
   - Do not implement unrelated features.
2. Preserve idempotency
   - Never append navigation blindly.
   - Always replace tool-managed blocks deterministically.
3. Keep edits traceable
   - Use explicit block markers for managed content.
4. Do not bypass toolchain policy
   - Use `uv run ...` for pytest, ty, and ruff commands.
5. Favor small, reviewable changes
   - Keep diffs focused; avoid broad refactors unless requested.
6. Maintain tests with behavior
   - Behavior changes require tests.
7. Fail safely
   - Prefer explicit errors and partial progress reporting over silent corruption.
8. Avoid destructive git/file operations unless explicitly requested.

## Open Questions (Track Here)

- Authentication/session strategy for editing deviations.
- Official API vs browser-automation/scraping boundaries.
- Canonical ordering source in gallery views.
- Navigation marker format to minimize user-content collision risk.
