# AGENTS

## Purpose

This repository contains a small dependency-free MCP server covering the three main ASF trademark jobs:

1. **Naming new projects** — validate proposed Apache project / podling names against policy.
2. **Auditing project websites** — check Apache project pages against the Project Branding Requirements.
3. **Auditing third-party use** — check external pages against ASF Trademark Policy.

For naming, the server automates the parts of the PODLINGNAMESEARCH process that can be automated — reserved-mark checks, Native American name detection, ASF project-list conflict checks, and software-source name lookups (GitHub, PyPI, npm) — and assembles a ready-to-paste JIRA ticket body. It reports facts only; the final "confusingly similar" judgement belongs to `trademarks@apache.org`.

## Project Layout

- `src/apache_trademark_mcp/policy.py`
  - Static policy data (reserved marks, Native American terms, generic terms), normalization, and pure-Python rule checks. Also produces the structured naming-policy document, branding checklists, and focused guidance entries.
- `src/apache_trademark_mcp/projects.py`
  - Fetches and caches the live ASF committees + podlings list from `projects.apache.org`, and runs string-similarity name conflict checks against it. Uses only `urllib`.
- `src/apache_trademark_mcp/search.py`
  - Software-source name lookups against GitHub, PyPI, and npm, run concurrently with `concurrent.futures`. Builds the PODLINGNAMESEARCH JIRA ticket body and USPTO search URLs.
- `src/apache_trademark_mcp/web.py`
  - Stdlib-only HTML fetcher (`urllib`) and parser (`html.parser`), plus URL helpers (`is_apache_host`, `second_level_domain`).
- `src/apache_trademark_mcp/compliance.py`
  - Pure rule logic for the two web-compliance checkers (`check_project_website`, `check_third_party_use`). Each finding carries the policy URL backing it.
- `src/apache_trademark_mcp/schemas.py`
  - Shared MCP input schema fragments and schema-builder helpers.
- `src/apache_trademark_mcp/tools.py`
  - User-facing tool handlers, argument validation, and the `TOOLS` registry.
- `src/apache_trademark_mcp/protocol.py`
  - JSON-RPC/MCP stdio protocol handling.
- `server.py`
  - Thin entrypoint.
- `tests/`
  - Unit and integration tests.
- `docs/architecture.md`
  - High-level module and runtime structure.

## Key Defaults And Concepts

- `--cache-dir` controls where the ASF project list is cached. Defaults to `~/.cache/apache-trademark-mcp`.
- The project list cache TTL is 24 hours. Use `refresh_project_cache` to force a fetch.
- All HTTP calls go through `urllib`; there are no runtime dependencies beyond the standard library.
- `find_name_conflicts` flags exact and ≥0.90 string-similarity matches as conflicts and returns 0.70–0.90 matches as "nearby" awareness data only — the final "confusingly similar" judgement is for `trademarks@`.
- `perform_name_search` runs three external HTTP lookups in parallel. Failures are caught per-source so a partial result is always returned.

## Developer Workflow

Use these commands before finishing changes:

- `make check-format`
- `make lint`
- `make typecheck`
- `make test`

Coverage is available via:

- `make coverage`

## Contribution Guidelines

- Keep static policy data and pure rule checks in `src/apache_trademark_mcp/policy.py`.
- Keep ASF project-list I/O and similarity helpers in `src/apache_trademark_mcp/projects.py`.
- Keep external HTTP name lookups (GitHub/PyPI/npm) and JIRA template generation in `src/apache_trademark_mcp/search.py`.
- Keep HTML fetching and parsing in `src/apache_trademark_mcp/web.py` — never re-implement HTTP/HTML handling in other modules.
- Keep pure web-compliance rule logic in `src/apache_trademark_mcp/compliance.py`. Every finding must carry a `policy_url`. Rules that cannot be evaluated should return `SKIP`, not raise.
- Keep user-facing tool handlers in `src/apache_trademark_mcp/tools.py`.
- Keep MCP/JSON-RPC protocol wiring in `src/apache_trademark_mcp/protocol.py`.
- Keep `server.py` minimal.
- Add tests for any new tool, policy rule, or search source.
- Update `README.md` and `docs/architecture.md` when changing public tools or runtime structure.

## Testing Notes

- Policy-rule behavior belongs in `tests/test_policy.py`.
- Project-list parsing and similarity behavior belongs in `tests/test_projects.py`.
- External-search adapters and JIRA template generation belong in `tests/test_search.py`.
- HTML parsing and URL helpers belong in `tests/test_web.py`.
- Web compliance rule logic belongs in `tests/test_compliance.py`, exercised against fixtures in `tests/html_fixtures.py`.
- Tool handler argument validation and dispatch belong in `tests/test_tools.py`.
- JSON-RPC envelope handling belongs in `tests/test_protocol.py`.
- End-to-end stdio behavior belongs in `tests/test_mcp_integration.py`.
- External HTTP must always be patched in tests — never reach out to the network from the test suite.
