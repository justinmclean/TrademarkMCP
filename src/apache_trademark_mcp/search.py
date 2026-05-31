"""External name-search helpers for the PODLINGNAMESEARCH process.

Performs lookups against GitHub, PyPI, and npm using only stdlib HTTP, and
formats the results into a ready-to-paste JIRA ticket body.
"""

from __future__ import annotations

import concurrent.futures
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_TIMEOUT_SECONDS = 12.0


def _http_get_json(url: str, timeout: float, headers: dict[str, str] | None = None) -> Any:
    final_headers = {"User-Agent": "apache-trademark-mcp/0.1"}
    if headers:
        final_headers.update(headers)
    req = urllib.request.Request(url, headers=final_headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        status = resp.status
        body = resp.read().decode("utf-8")
        return status, json.loads(body) if body else None


def github_search(name: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> dict:
    """Search GitHub repositories by name, sorted by stars."""
    out: dict[str, Any] = {"hits": [], "total_count": 0, "error": None}
    qs = urllib.parse.urlencode({"q": name, "sort": "stars", "per_page": 5})
    url = f"https://api.github.com/search/repositories?{qs}"
    try:
        status, data = _http_get_json(
            url,
            timeout=timeout,
            headers={"Accept": "application/vnd.github+json"},
        )
        if status == 200 and isinstance(data, dict):
            out["total_count"] = data.get("total_count", 0)
            for repo in data.get("items", [])[:5]:
                out["hits"].append(
                    {
                        "name": repo.get("full_name"),
                        "description": repo.get("description") or "",
                        "stars": repo.get("stargazers_count", 0),
                        "url": repo.get("html_url"),
                        "language": repo.get("language"),
                    }
                )
        elif status == 403:
            out["error"] = "GitHub rate limit — search manually at https://github.com/search"
        else:
            out["error"] = f"GitHub returned HTTP {status}"
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            out["error"] = "GitHub rate limit — search manually at https://github.com/search"
        else:
            out["error"] = f"GitHub returned HTTP {exc.code}"
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        out["error"] = str(exc)
    return out


def pypi_search(name: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> dict:
    """Look up a package on PyPI by exact name."""
    out: dict[str, Any] = {
        "found": False,
        "url": None,
        "summary": None,
        "version": None,
        "error": None,
    }
    url = f"https://pypi.org/pypi/{urllib.parse.quote(name)}/json"
    try:
        status, data = _http_get_json(url, timeout=timeout)
        if status == 200 and isinstance(data, dict):
            info = data.get("info", {}) if isinstance(data.get("info"), dict) else {}
            out["found"] = True
            out["url"] = f"https://pypi.org/project/{name}/"
            out["summary"] = info.get("summary", "")
            out["version"] = info.get("version", "")
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            out["error"] = f"PyPI returned HTTP {exc.code}"
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        out["error"] = str(exc)
    return out


def npm_search(name: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> dict:
    """Look up a package on the npm registry by exact name (lowercased)."""
    lower = name.lower()
    out: dict[str, Any] = {
        "found": False,
        "url": None,
        "description": None,
        "latest_version": None,
        "error": None,
    }
    url = f"https://registry.npmjs.org/{urllib.parse.quote(lower)}"
    try:
        status, data = _http_get_json(url, timeout=timeout)
        if status == 200 and isinstance(data, dict):
            out["found"] = True
            out["url"] = f"https://www.npmjs.com/package/{lower}"
            out["description"] = data.get("description", "")
            out["latest_version"] = data.get("dist-tags", {}).get("latest", "")
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            out["error"] = f"npm returned HTTP {exc.code}"
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
        out["error"] = str(exc)
    return out


def run_external_searches(name: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> dict[str, dict]:
    """Run GitHub, PyPI, and npm lookups concurrently."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            "github": pool.submit(github_search, name, timeout),
            "pypi": pool.submit(pypi_search, name, timeout),
            "npm": pool.submit(npm_search, name, timeout),
        }
        return {key: future.result() for key, future in futures.items()}


# ---------------------------------------------------------------------------
# JIRA template + USPTO links
# ---------------------------------------------------------------------------


def uspto_search_links(name: str) -> dict:
    """Return USPTO TESS search URLs and a recommended query string."""
    recommended_query = f"({name})[BI,TI] and (software or computer)[GS] and (live)[LD]"
    return {
        "url": "https://tmsearch.uspto.gov/search/search-information",
        "direct_search": (
            f"https://tmsearch.uspto.gov/search/search-information#search/{name}/words"
        ),
        "recommended_query": recommended_query,
        "instructions": (
            "Go to https://tmsearch.uspto.gov → Basic Word Mark Search. "
            f"Enter '{name}' in the Search Term field. Select 'Live' status. "
            "Record the number of results and any matching marks."
        ),
        "required": True,
    }


def trademark_search_urls(name: str) -> dict[str, dict]:
    """Return URLs for the trademark/search engines a proposer should consult."""
    return {
        "USPTO": uspto_search_links(name),
        "Google": {
            "url": f"https://www.google.com/search?q=%22{urllib.parse.quote(name)}%22+software",
            "instructions": (
                f"Search Google for '\"{name}\" software' and note any software "
                "products using this name."
            ),
            "required": True,
        },
        "SourceForge": {
            "url": f"https://sourceforge.net/directory/?q={urllib.parse.quote(name)}",
            "instructions": (f"Search SourceForge for '{name}' and note any matching projects."),
            "required": True,
        },
    }


def assess_findings(
    name: str,
    github: dict,
    pypi: dict,
    npm: dict,
    technical_description: str,
) -> dict:
    """Summarise factual evidence found by the searches."""
    evidence: list[str] = []
    notes: list[str] = []

    name_lower = name.lower()
    gh_hits = github.get("hits", [])
    gh_total = github.get("total_count", 0)

    directly_named = [
        h for h in gh_hits if name_lower in (h.get("name", "") or "").lower().split("/")[-1]
    ]

    if directly_named:
        for r in directly_named:
            stars = r.get("stars", 0)
            desc = (r.get("description") or "no description")[:120]
            evidence.append(
                f"GitHub project directly named '{name}': {r['name']} "
                f"({stars:,} stars, {r.get('language') or 'unknown language'}) — {desc}"
            )
    else:
        if gh_total > 0:
            notes.append(
                f"GitHub: {gh_total:,} repositories mention '{name}' but none of the "
                "top results use it as their primary project name."
            )
        else:
            notes.append(f"GitHub: no repositories found mentioning '{name}'.")

    if pypi.get("found"):
        ver = pypi.get("version") or "0.0.0"
        summary = pypi.get("summary") or "no description"
        evidence.append(
            f"PyPI package named '{name}' exists (v{ver}): {summary} — {pypi.get('url', '')}"
        )
    else:
        notes.append(f"PyPI: no package named '{name}' found.")

    if npm.get("found"):
        ver = npm.get("latest_version") or "0.0.0"
        desc = npm.get("description") or "no description"
        evidence.append(
            f"npm package named '{name_lower}' exists (v{ver}): {desc} — {npm.get('url', '')}"
        )
    else:
        notes.append(f"npm: no package named '{name_lower}' found.")

    if not technical_description:
        notes.append(
            "IMPORTANT: No technical_description was provided. The relevance of any "
            f"found '{name}' projects depends entirely on whether they are in the same "
            "technical space as the proposed project. Re-run with technical_description "
            "set to get a more targeted assessment."
        )

    if evidence:
        summary = (
            f"Evidence of existing software named '{name}' was found (see evidence list). "
            "Include these findings in the PODLINGNAMESEARCH JIRA ticket as factual records. "
            "trademarks@ will determine whether any represent a conflict — do not interpret "
            "or judge this yourself in the public JIRA."
        )
        if technical_description:
            summary += (
                f" When writing up the JIRA, note which (if any) of these projects operate "
                f"in a similar technical space to: '{technical_description}'."
            )
    else:
        summary = (
            f"No software projects directly named '{name}' were found in the automated "
            "searches (GitHub, PyPI, npm). Note this in the JIRA ticket as a factual finding. "
            "A USPTO search is still required — an absence of open source usage "
            "does not mean there are no registered trademarks."
        )

    return {
        "evidence_of_existing_use": evidence,
        "notes": notes,
        "summary": summary,
        "reminder": (
            "Per ASF policy: record facts only in the JIRA ticket. Do not speculate, "
            "interpret, or offer legal opinions. Suitability is determined privately "
            "by trademarks@ and approved by the VP, Brand Management."
        ),
    }


def jira_template(
    name: str, technical_description: str, github: dict, pypi: dict, npm: dict
) -> str:
    """Return the PODLINGNAMESEARCH JIRA body, pre-populated with search results."""
    name_lower = name.lower()

    def gh_line() -> str:
        if github.get("error"):
            return (
                f"GitHub search error: {github['error']}. "
                f"Perform manually at https://github.com/search?q={urllib.parse.quote(name)}"
            )
        total = github.get("total_count", 0)
        hits = github.get("hits", [])
        if total == 0:
            return "GitHub: 0 repositories found with this name."
        lines = [f"GitHub: {total:,} total repositories. Top results:"]
        for h in hits[:5]:
            desc = (h.get("description") or "no description")[:120]
            lines.append(
                f"  - {h['name']} ({h['stars']:,} stars, "
                f"{h.get('language') or 'unknown language'}): {desc}"
            )
        return "\n".join(lines)

    def pypi_line() -> str:
        if pypi.get("error"):
            return (
                f"PyPI: lookup error — check manually at "
                f"https://pypi.org/search/?q={urllib.parse.quote(name)}"
            )
        if pypi.get("found"):
            return (
                f"PyPI: package '{name}' exists at {pypi['url']}\n"
                f"  Version: {pypi.get('version') or '?'}\n"
                f"  Description: {pypi.get('summary') or 'none'}"
            )
        return f"PyPI: no package named '{name}' found."

    def npm_line() -> str:
        if npm.get("error"):
            return (
                f"npm: lookup error — check manually at "
                f"https://www.npmjs.com/search?q={urllib.parse.quote(name)}"
            )
        if npm.get("found"):
            return (
                f"npm: package '{name_lower}' exists at {npm['url']}\n"
                f"  Version: {npm.get('latest_version') or '?'}\n"
                f"  Description: {npm.get('description') or 'none'}"
            )
        return f"npm: no package named '{name_lower}' found."

    uspto_query = f"(({name})[BI,TI] AND (software or computer)[GS] AND (live)[LD])"

    return f"""h2. Proposed Name
Apache {name}

h2. Project Description
{technical_description or "(REQUIRED: add a brief description of what the project does and its technical space)"}

h2. GitHub Search Results
{gh_line()}

h2. Package Registry Search Results
{pypi_line()}

{npm_line()}

h2. SourceForge Search Results
See: https://sourceforge.net/directory/?q={urllib.parse.quote(name)}
(add results here)

h2. Web / Search Engine Results
Search: https://www.google.com/search?q=%22{urllib.parse.quote(name)}%22+software
(add notable results here)

h2. USPTO Trademark Search (REQUIRED)
Query: {uspto_query}
Search at: https://tmsearch.uspto.gov
Results: (add number of hits and any matching live marks here)

h2. Summary of Findings
(Report facts only. Do not interpret or give opinions on likelihood of confusion — that assessment is made by trademarks@apache.org and the VP Brand Management.)
"""
