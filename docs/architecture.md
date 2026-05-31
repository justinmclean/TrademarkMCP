# Architecture

## Overview

`TrademarkMCP` exposes ASF trademark policy checks and the PODLINGNAMESEARCH automation through a small MCP-compatible interface.

The project follows the same broad shape as `HealthMCP` and `ReportMCP`:

- `server.py`
  A tiny top-level entrypoint for MCP clients.
- `src/apache_trademark_mcp/protocol.py`
  The JSON-RPC/MCP protocol loop over stdio.
- `src/apache_trademark_mcp/tools.py`
  Dependency-light tool handlers, argument validation, and the `TOOLS` registry.
- `src/apache_trademark_mcp/schemas.py`
  Shared MCP input schema fragments and schema-builder helpers.
- `src/apache_trademark_mcp/policy.py`
  Static ASF policy data and pure-Python rule checks.
- `src/apache_trademark_mcp/projects.py`
  Live ASF project-list fetch, cache, and similarity search.
- `src/apache_trademark_mcp/search.py`
  External name lookups (GitHub, PyPI, npm) and the PODLINGNAMESEARCH JIRA template.
- `src/apache_trademark_mcp/web.py`
  Stdlib HTML fetcher + parser, used by both compliance checkers.
- `src/apache_trademark_mcp/compliance.py`
  Pure rule logic for the two web-compliance checkers (`check_project_website` and `check_third_party_use`).

## Modules

### `src/apache_trademark_mcp/policy.py`

This module is responsible for:

- holding the canonical lists of reserved ASF marks, Native American tribal/cultural terms, and generic descriptive terms
- normalizing proposed names for comparison (lowercasing, stripping `Apache ` prefix, dropping non-alphanumerics)
- the pure rule checks: reserved marks, Native American detection, basic format rules
- producing the structured naming-policy document
- producing the branding compliance checklists for `podling`, `graduation`, and `tlp` stages
- producing the focused policy guidance entries for specific topics

The module performs no I/O and has no dependencies beyond `re`, making it trivially unit-testable.

### `src/apache_trademark_mcp/projects.py`

This module is responsible for:

- fetching the live ASF committees + podlings list from `projects.apache.org`
- caching the result on disk with a 24-hour TTL
- normalising committee + podling entries into a flat list of project names
- string-similarity comparisons between a proposed name and the existing project list
- separating "conflict" matches (≥0.90) from "nearby" matches (0.70–0.90)

All HTTP calls use `urllib`. If the network is unavailable, the module falls back to a stale cache rather than failing.

### `src/apache_trademark_mcp/search.py`

This module is responsible for:

- searching GitHub repositories by name
- looking up packages by exact name on PyPI and npm
- running the three lookups concurrently with `concurrent.futures.ThreadPoolExecutor`
- summarising the findings as evidence + notes
- assembling the PODLINGNAMESEARCH JIRA ticket body, including the USPTO search URL pre-filled with the proposed name

Each adapter catches its own network failures so a partial result is always returned.

### `src/apache_trademark_mcp/web.py`

This module is responsible for:

- fetching arbitrary URLs over HTTP/HTTPS with a 15-second timeout and a 2 MB read cap
- parsing the response body with `html.parser` and producing a structured `FetchedPage` (title, headings, links, images, normalised visible text)
- helpers for URL classification: `is_apache_host`, `host_of`, `second_level_domain`, `absolutise`

It uses only the standard library, captures errors into `FetchedPage.error` rather than raising, and rejects non-`http(s)` URLs up front.

### `src/apache_trademark_mcp/compliance.py`

This module provides the pure rule logic for the two web-compliance checkers. Every rule emits a `Finding` with a status (`pass` / `fail` / `warn` / `info` / `skip`) and the URL of the policy section backing it. A `ComplianceReport` aggregates findings and computes an overall verdict (`PASS` / `WARN` / `FAIL` / `SKIP`).

The project website checker covers:

- apache.org hosting
- 'Apache ProjectName' form in title or headings
- TM/(R) symbol on first prominent occurrence (title, heading, or running text)
- footer trademark attribution
- third-party trademark acknowledgement
- required navigation links (License, Sponsorship, Thanks, Security, Privacy)
- prominent link back to www.apache.org
- logo TM heuristic
- (for podlings) the incubation DISCLAIMER text and `(Incubating)` suffix

The third-party-use checker covers:

- domain misuse (bare Apache product names as second-level domains, `apache` in the domain)
- approved branding form (`Powered By Apache Foo` / `Apache Foo Inside`)
- non-affiliation disclaimer language
- logo misuse (feather mark, unmodified Apache product logos)
- credit link back to the upstream project's apache.org page

### `src/apache_trademark_mcp/tools.py`

This module provides the user-facing tool handlers:

- `validate_name`
- `search_asf_projects`
- `get_naming_policy`
- `get_branding_checklist`
- `get_policy_guidance`
- `perform_name_search`
- `refresh_project_cache`
- `check_project_website`
- `check_third_party_use`

It also resolves the project-list cache directory from either:

- the `--cache-dir` startup argument
- the `APACHE_TRADEMARK_MCP_CACHE_DIR` environment variable
- the default `~/.cache/apache-trademark-mcp`

Tool handlers return native structured payloads (dicts). The protocol layer wraps them with both MCP `structuredContent` and a JSON text fallback in `content`.

### `src/apache_trademark_mcp/schemas.py`

This module contains shared MCP input schema fragments and schema-builder helpers. New tool schema definitions should be added here rather than inline in `protocol.py`.

### `src/apache_trademark_mcp/protocol.py`

This module implements the stdio MCP/JSON-RPC behavior. It supports:

- `initialize`
- `tools/list`
- `tools/call`

Requests can be sent as single JSON-RPC objects or as JSON-RPC batches. Batch responses omit notification-only messages and preserve per-request success or error payloads for the remaining messages. The protocol layer validates the JSON-RPC envelope before dispatching, returning structured `error.data` details for parse errors, invalid requests, invalid params, and unknown methods.

### `server.py`

This file is intentionally tiny. It just imports `main` from `apache_trademark_mcp.protocol` and exits with that return code.

## Testing

The test suite is layered:

- `tests/test_policy.py`
  Unit tests for normalization, rule checks, and the policy documents (naming policy, branding checklists, focused guidance).
- `tests/test_projects.py`
  Tests for project-list normalization, similarity helpers, and conflict / similar search behaviour.
- `tests/test_search.py`
  Tests for the JIRA template assembler and the findings summary (HTTP adapters are exercised with patched `urllib`).
- `tests/test_web.py`
  Tests for HTML parsing and URL helpers (`is_apache_host`, `second_level_domain`).
- `tests/test_compliance.py`
  Tests for the pure rule logic in `compliance.py`, exercised against compliant / non-compliant HTML fixtures in `tests/html_fixtures.py`.
- `tests/test_tools.py`
  Tests for argument validation and the `TOOLS` registry, with patched HTTP boundaries.
- `tests/test_protocol.py`
  Unit tests for the JSON-RPC envelope helpers and dispatch.
- `tests/test_mcp_integration.py`
  End-to-end tests that spawn `server.py` as a subprocess and exercise MCP-style JSON-RPC requests over stdio. Network access is suppressed by pointing the cache directory at a tempdir that already contains a fixture cache file.

## Design Notes

- The policy module is intentionally pure-Python with no I/O, so rule changes are testable without touching the HTTP layer.
- The top-level `server.py` is intentionally minimal so the real behavior stays in testable package modules.
- The `tools` module is dependency-light on purpose, which makes unit testing straightforward.
- Conflict thresholds (≥0.90) and "nearby" thresholds (0.70–0.90) are kept conservative on purpose. String similarity is a starting point for the manual searches required by `trademarks@`, not a substitute for them.
