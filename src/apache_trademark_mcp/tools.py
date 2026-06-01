"""User-facing tool handlers, argument validation, and the ``TOOLS`` registry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from apache_trademark_mcp import compliance, policy, projects, schemas, search, web

# ---------------------------------------------------------------------------
# Startup-configurable defaults
# ---------------------------------------------------------------------------

_CONFIGURED_CACHE_DIR: Path | None = None


def configure_defaults(*, cache_dir: str | None = None) -> None:
    """Apply CLI-supplied defaults. Called from ``protocol.main``."""
    global _CONFIGURED_CACHE_DIR
    if cache_dir:
        _CONFIGURED_CACHE_DIR = projects.cache_dir_from_env(cache_dir)


def _cache_dir() -> Path:
    if _CONFIGURED_CACHE_DIR is not None:
        return _CONFIGURED_CACHE_DIR
    return projects.cache_dir_from_env(None)


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------


def _require_non_empty_string(value: Any, key: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"'{key}' must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"'{key}' must be a non-empty string")
    return stripped


def _optional_string(value: Any, key: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"'{key}' must be a string")
    return value


def _optional_number(value: Any, key: str, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"'{key}' must be a number")
    return float(value)


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


def _verdict_summary(verdict: str) -> str:
    return {
        "FAIL": (
            "FAIL — This name has at least one definitive policy violation listed in "
            "blocking_issues that must be resolved before filing an incubation proposal. "
            "Choose a different name or consult trademarks@apache.org."
        ),
        "WARN": (
            "WARN — No definitive policy violations found, but the name has advisory "
            "concerns listed in warnings. Review them before proceeding."
        ),
        "PASS": (
            "PASS (automated checks only) — No definitive policy violations detected "
            "against the ASF project list. This does NOT mean the name is approved. "
            "The full PODLINGNAMESEARCH process listed below is still required, including "
            "internet searches, USPTO search, and VP Brand Management approval."
        ),
    }[verdict]


def _podlingnamesearch_process(name: str) -> dict:
    return {
        "description": (
            "The PODLINGNAMESEARCH process is required for all podlings before the "
            "incubation proposal is accepted. VP Brand Management approval is mandatory — "
            "there is no lazy consensus."
        ),
        "required_steps": [
            {
                "step": 1,
                "action": "Search GitHub, SourceForge, and general web search engines",
                "detail": (
                    f"Search for '{name}' and 'Apache {name}' across GitHub, "
                    "SourceForge, and major search engines. Look specifically for software "
                    "projects in the same or adjacent technical spaces."
                ),
                "required": True,
            },
            {
                "step": 2,
                "action": "Search the USPTO trademark database (required)",
                "url": "https://tmsearch.uspto.gov",
                "detail": (
                    f"Search USPTO for: ({name})[BI,TI] and "
                    "(software or computer)[GS] and (live)[LD]. "
                    "Record the search results (number of hits, any matching "
                    "marks) in your JIRA ticket. Report facts only — do not "
                    "interpret or opine on likelihood of confusion."
                ),
                "required": True,
            },
            {
                "step": 3,
                "action": "File a PODLINGNAMESEARCH JIRA ticket",
                "url": "https://issues.apache.org/jira/projects/PODLINGNAMESEARCH",
                "detail": (
                    "Create a ticket summarising your search results. Include the name, "
                    "a short description of the project, and factual search results. "
                    "Report only facts — trademarks@ will assess likelihood of confusion. "
                    "Do not include your own opinion on whether it conflicts."
                ),
                "required": True,
            },
            {
                "step": 4,
                "action": "Notify trademarks@apache.org",
                "detail": (
                    "Send an email to trademarks@apache.org referencing your JIRA ticket. "
                    "The VP Brand Management must approve the name; approval is not assumed "
                    "if there is no response."
                ),
                "required": True,
            },
            {
                "step": 5,
                "action": "Await VP Brand Management approval",
                "detail": (
                    "Do not proceed with press releases, public announcements, or publicity "
                    "until approval is granted. There is no lazy consensus for name approval."
                ),
                "required": True,
            },
        ],
        "after_approval": [
            "Refer to the podling only as 'Apache Foo (Incubating)' in all external references.",
            "Include the incubation DISCLAIMER in all releases and in the README.",
            "Coordinate any publicity with the ASF PR Committee.",
        ],
    }


def validate_name(
    proposed_name: str,
    technical_description: str = "",
) -> dict[str, Any]:
    """Run all automated trademark-policy checks and return a structured verdict."""
    resolved_name = _require_non_empty_string(proposed_name, "proposed_name")
    resolved_description = _optional_string(technical_description, "technical_description")

    blocking: list[str] = []
    warnings: list[str] = []

    blocking.extend(policy.check_reserved(resolved_name))

    for flag in policy.check_native_american(resolved_name):
        blocking.append(
            f"'{flag}' is a Native American tribal or cultural name. "
            "ASF policy states: 'names with Native American connections will not be approved.' "
            "(https://www.apache.org/foundation/marks/pmcs#naming)"
        )

    format_blocking, format_warnings = policy.check_format(resolved_name)
    blocking.extend(format_blocking)
    warnings.extend(format_warnings)

    asf_projects = projects.fetch_projects(cache_dir=_cache_dir())
    asf_conflicts, nearby_asf_names = projects.find_name_conflicts(resolved_name, asf_projects)
    for m in asf_conflicts:
        if m["match_type"] == "exact":
            blocking.append(
                f"Exact name conflict with existing ASF project '{m['name']}'. "
                "The same name cannot be reused for a new podling."
            )
        else:
            blocking.append(
                f"Near-exact name match with existing ASF project '{m['name']}' "
                f"(similarity {m['similarity']:.0%}). This is very likely to be rejected "
                "by trademarks@ as the same or indistinguishably similar name."
            )

    verdict = "FAIL" if blocking else ("WARN" if warnings else "PASS")

    return {
        "proposed_name": resolved_name,
        "apache_form": f"Apache {resolved_name}",
        "technical_description": resolved_description or "(not provided)",
        "verdict": verdict,
        "verdict_summary": _verdict_summary(verdict),
        "blocking_issues": blocking,
        "warnings": warnings,
        "asf_name_conflicts": asf_conflicts,
        "nearby_asf_names": {
            "note": (
                "These ASF project names have some string similarity to the proposed name "
                "(0.70–0.90 range). They are listed for awareness only and do NOT constitute "
                "policy violations. Whether any of these names is 'confusingly similar' in the "
                "trademark sense depends on the technical space, consumer context, and other "
                "factors — this is assessed by trademarks@ through the PODLINGNAMESEARCH process."
            ),
            "names": nearby_asf_names,
        },
        "podlingnamesearch_process": _podlingnamesearch_process(resolved_name),
        "policy_citations": policy.policy_citations(),
    }


def search_asf_projects(query: str, min_similarity: float = 0.5) -> dict[str, Any]:
    """Fuzzy-search the ASF project list for names similar to ``query``."""
    resolved_query = _require_non_empty_string(query, "query")
    threshold = _optional_number(min_similarity, "min_similarity", 0.5)
    threshold = max(0.0, min(1.0, threshold))

    asf_projects = projects.fetch_projects(cache_dir=_cache_dir())
    similar = projects.find_similar(resolved_query, asf_projects, threshold=threshold)
    descriptions = projects.project_descriptions(asf_projects)

    enriched: list[dict] = []
    for m in similar:
        norm_key = policy.normalize(m["name"]).replace(" ", "-")
        enriched.append(
            {
                "name": m["name"],
                "similarity": m["similarity"],
                "url": m["url"],
                "description": descriptions.get(norm_key, ""),
            }
        )

    return {
        "query": resolved_query,
        "min_similarity": threshold,
        "total_found": len(enriched),
        "results": enriched,
        "cache_age_hours": projects.cache_age_hours(cache_dir=_cache_dir()),
        "tip": (
            "No ASF conflicts found."
            if not enriched
            else "Review each result to assess likelihood of confusion in your technical space."
        ),
    }


def get_naming_policy() -> dict[str, Any]:
    """Return the structured ASF naming-policy summary."""
    return policy.naming_policy()


def get_branding_checklist(stage: str = "podling") -> dict[str, Any]:
    """Return the branding checklist for a given lifecycle stage."""
    resolved_stage = _require_non_empty_string(stage, "stage").lower()
    return policy.branding_checklist(resolved_stage)


def get_policy_guidance(topic: str) -> dict[str, Any]:
    """Return focused ASF trademark policy guidance for a specific topic."""
    resolved = _require_non_empty_string(topic, "topic").lower().replace(" ", "_").replace("-", "_")
    return policy.policy_guidance(resolved)


def perform_name_search(proposed_name: str, technical_description: str = "") -> dict[str, Any]:
    """Run GitHub/PyPI/npm name searches and assemble a PODLINGNAMESEARCH JIRA body."""
    resolved_name = _require_non_empty_string(proposed_name, "proposed_name")
    resolved_description = _optional_string(technical_description, "technical_description")

    results = search.run_external_searches(resolved_name)
    github, pypi, npm = results["github"], results["pypi"], results["npm"]
    assessment = search.assess_findings(resolved_name, github, pypi, npm, resolved_description)

    return {
        "proposed_name": resolved_name,
        "apache_form": f"Apache {resolved_name}",
        "technical_description": resolved_description or "(not provided)",
        "suitability_assessment": assessment,
        "automated_search_results": {
            "github": github,
            "pypi": pypi,
            "npm": npm,
        },
        "trademark_search_urls": search.trademark_search_urls(resolved_name),
        "manual_searches_still_required": [
            "USPTO (required) — open the URL above, run the query, record exact results in JIRA",
            f"Google — search for '\"{resolved_name}\" software', note any products",
            f"SourceForge — search for '{resolved_name}', note any matching projects",
        ],
        "jira_ticket_template": search.jira_template(
            resolved_name, resolved_description, github, pypi, npm
        ),
        "jira_url": "https://issues.apache.org/jira/projects/PODLINGNAMESEARCH",
        "next_step": (
            "Complete the USPTO search, fill in any remaining blanks in the JIRA "
            "template above (facts only, no interpretation), then file at "
            "https://issues.apache.org/jira/projects/PODLINGNAMESEARCH and email "
            "trademarks@apache.org. VP Brand Management approval is mandatory — "
            "there is no lazy consensus."
        ),
    }


def refresh_project_cache() -> dict[str, Any]:
    """Force a fresh fetch of the ASF project list from projects.apache.org."""
    return projects.refresh_cache(cache_dir=_cache_dir())


def check_project_website(
    url: str,
    project_name: str = "",
    stage: str = "tlp",
) -> dict[str, Any]:
    """Fetch an Apache project page and check it against the branding policy."""
    resolved_url = _require_non_empty_string(url, "url")
    resolved_project = _optional_string(project_name, "project_name")
    resolved_stage = _optional_string(stage, "stage") or "tlp"
    if resolved_stage not in policy.VALID_BRANDING_STAGES:
        raise ValueError(f"'stage' must be one of: {', '.join(policy.VALID_BRANDING_STAGES)}")

    page = web.fetch_page(resolved_url)
    asf_projects = projects.fetch_projects(cache_dir=_cache_dir())
    known_marks = compliance.project_names_for_bare_scan(asf_projects)
    report = compliance.check_project_website(
        page,
        project_name=resolved_project or None,
        stage=resolved_stage,
        known_marks=known_marks,
    )

    return {
        **report.to_dict(),
        "project_name": resolved_project or compliance._infer_project_name(page),
        "stage": resolved_stage,
        "policy_references": {
            "branding_requirements": compliance.POLICY_URLS["branding"],
            "podling_branding_guide": compliance.POLICY_URLS["podling_branding"],
            "trademark_policy": compliance.POLICY_URLS["trademark_policy"],
            "tip": (
                "Pair this tool with the asf-policy MCP (key 'branding' or "
                "'podling_branding') for the full canonical policy text."
            ),
        },
    }


def check_third_party_use(
    url: str,
    mark: str = "",
) -> dict[str, Any]:
    """Fetch a third-party page and check it against ASF trademark policy."""
    resolved_url = _require_non_empty_string(url, "url")
    resolved_mark = _optional_string(mark, "mark")

    page = web.fetch_page(resolved_url)
    asf_projects = projects.fetch_projects(cache_dir=_cache_dir())
    known_marks = compliance.project_names_for_bare_scan(asf_projects)
    report = compliance.check_third_party_use(
        page, mark=resolved_mark or None, known_marks=known_marks
    )

    return {
        **report.to_dict(),
        "mark": resolved_mark,
        "policy_references": {
            "trademark_policy": compliance.POLICY_URLS["trademark_policy"],
            "domain_branding": compliance.POLICY_URLS["domain_branding"],
            "logos": compliance.POLICY_URLS["logos"],
            "tip": (
                "Pair this tool with the asf-policy MCP (keys 'trademark_policy' "
                "and 'domain_name_branding') for the full canonical policy text."
            ),
        },
    }


# ---------------------------------------------------------------------------
# TOOLS registry
# ---------------------------------------------------------------------------


TOOLS: dict[str, dict[str, Any]] = {
    "validate_name": schemas.tool_definition(
        description=(
            "Validate a proposed Apache project or podling name against ASF "
            "trademark policy (reserved marks, Native American names, format, "
            "and the live ASF committees+podlings list)."
        ),
        handler=validate_name,
        properties=schemas.validate_name_properties(),
        required=["proposed_name"],
    ),
    "search_asf_projects": schemas.tool_definition(
        description="Fuzzy-search the ASF project list for names similar to a query.",
        handler=search_asf_projects,
        properties=schemas.search_asf_projects_properties(),
        required=["query"],
    ),
    "get_naming_policy": schemas.tool_definition(
        description="Return the structured ASF naming-policy summary.",
        handler=get_naming_policy,
        properties={},
    ),
    "get_branding_checklist": schemas.tool_definition(
        description="Return the branding compliance checklist for a given stage.",
        handler=get_branding_checklist,
        properties=schemas.branding_checklist_properties(list(policy.VALID_BRANDING_STAGES)),
        required=["stage"],
    ),
    "get_policy_guidance": schemas.tool_definition(
        description="Return focused ASF trademark policy guidance for a specific topic.",
        handler=get_policy_guidance,
        properties=schemas.policy_guidance_properties(list(policy.VALID_GUIDANCE_TOPICS)),
        required=["topic"],
    ),
    "perform_name_search": schemas.tool_definition(
        description=(
            "Run the GitHub/PyPI/npm searches required by the PODLINGNAMESEARCH "
            "process and return a JIRA-ready ticket body plus USPTO search links."
        ),
        handler=perform_name_search,
        properties=schemas.perform_name_search_properties(),
        required=["proposed_name"],
    ),
    "refresh_project_cache": schemas.tool_definition(
        description="Force a fresh fetch of the ASF project list.",
        handler=refresh_project_cache,
        properties={},
    ),
    "check_project_website": schemas.tool_definition(
        description=(
            "Fetch an Apache project's homepage and report compliance with the ASF "
            "Project Branding Requirements (apache.org hosting, Apache-form heading, "
            "TM/(R) on first use, footer attribution, required navigation links, "
            "and incubation disclaimers for podlings)."
        ),
        handler=check_project_website,
        properties=schemas.check_project_website_properties(list(policy.VALID_BRANDING_STAGES)),
        required=["url"],
    ),
    "check_third_party_use": schemas.tool_definition(
        description=(
            "Fetch a third-party page and report whether it follows ASF Trademark "
            "Policy for using Apache marks: domain misuse, 'Powered By Apache Foo' "
            "branding form, non-affiliation disclaimer, logo misuse, and credit link."
        ),
        handler=check_third_party_use,
        properties=schemas.check_third_party_use_properties(),
        required=["url"],
    ),
}
