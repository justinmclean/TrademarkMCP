"""Rule logic for the two web-compliance checkers.

These functions are pure: they take a :class:`~apache_trademark_mcp.web.FetchedPage`
and known project metadata, and return structured ``findings`` describing what
passed, what failed, what is advisory, and the policy URL backing each rule.

The actual HTTP fetch belongs in :mod:`apache_trademark_mcp.web`; the tool
handlers in :mod:`apache_trademark_mcp.tools` glue the two together.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from apache_trademark_mcp import policy, web

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

PASS = "pass"
FAIL = "fail"
WARN = "warn"
INFO = "info"
SKIP = "skip"  # rule could not be evaluated (e.g. fetch failed)

# Severity tiers for findings. They let the verdict distinguish active policy
# violations from missing positive evidence — important for third-party pages,
# where "no apache.org credit link" and "domain spoofs apache.org" should not
# carry the same weight.
CRITICAL = "critical"  # active policy violation; one of these forces FAIL
IMPORTANT = "important"  # warrants a human look (default for branding/disclaimer)
ADVISORY = "advisory"  # nice-to-have (e.g. missing credit link)

_RANK = {FAIL: 3, WARN: 2, INFO: 1, PASS: 0, SKIP: 0}

# Per-rule severity. Anything not listed defaults to IMPORTANT.
_RULE_SEVERITY = {
    # Third-party use rules
    "domain_uses_apache": CRITICAL,
    "bare_mark_as_sld": CRITICAL,
    "domain_clean": ADVISORY,
    "branding_form": IMPORTANT,
    "non_affiliation_disclaimer": IMPORTANT,
    "logo_misuse": IMPORTANT,
    "credit_link": ADVISORY,
    "third_party_host": ADVISORY,
    # Project-website rules (check_project_website) — MUST rules from
    # https://www.apache.org/foundation/marks/pmcs are CRITICAL; SHOULD rules
    # are IMPORTANT; navigation links / logo attribution are CRITICAL because
    # the branding policy requires them.
    "apache_org_hosting": CRITICAL,
    "apache_form_heading": CRITICAL,
    "trademark_attribution": CRITICAL,
    "link_back_to_apache_org": CRITICAL,
    "incubation_disclaimer": CRITICAL,
    "incubating_suffix": CRITICAL,
    "logo_tm": IMPORTANT,
    "logo_attribution": IMPORTANT,
    "tm_symbol_on_first_use": IMPORTANT,
    "third_party_trademark_note": ADVISORY,
    "bare_other_asf_marks": IMPORTANT,
}


def rule_severity(rule: str) -> str:
    # Nav-link rules are generated as nav_link_{license|privacy|...}. The
    # branding policy lists these as MUST, so treat any nav_link_* as CRITICAL.
    if rule.startswith("nav_link_"):
        return CRITICAL
    return _RULE_SEVERITY.get(rule, IMPORTANT)


@dataclass
class Finding:
    rule: str
    status: str
    detail: str
    policy_url: str
    evidence: str = ""
    severity: str = ""  # filled in from _RULE_SEVERITY in to_dict if blank

    def effective_severity(self) -> str:
        return self.severity or rule_severity(self.rule)

    def to_dict(self) -> dict:
        out = {
            "rule": self.rule,
            "status": self.status,
            "severity": self.effective_severity(),
            "detail": self.detail,
            "policy_url": self.policy_url,
        }
        if self.evidence:
            out["evidence"] = self.evidence
        return out


@dataclass
class ComplianceReport:
    target_url: str
    final_url: str
    findings: list[Finding] = field(default_factory=list)
    fetch_error: str | None = None

    def verdict(self) -> str:
        """Tiered verdict.

        FAIL  → any CRITICAL FAIL.
        WARN  → any IMPORTANT FAIL/WARN, or CRITICAL WARN.
        PASS  → only PASS/INFO findings, or all WARNs are ADVISORY-tier.
        SKIP  → the fetch never produced a page to evaluate.
        """
        if self.fetch_error:
            return "SKIP"
        if not self.findings:
            return "PASS"

        has_critical_fail = any(
            f.status == FAIL and f.effective_severity() == CRITICAL for f in self.findings
        )
        if has_critical_fail:
            return "FAIL"

        has_important_problem = any(
            f.status in (FAIL, WARN) and f.effective_severity() in (CRITICAL, IMPORTANT)
            for f in self.findings
        )
        if has_important_problem:
            return "WARN"

        return "PASS"

    def to_dict(self) -> dict:
        counts: dict[str, int] = {}
        severity_counts: dict[str, dict[str, int]] = {}
        for f in self.findings:
            counts[f.status] = counts.get(f.status, 0) + 1
            sev = f.effective_severity()
            severity_counts.setdefault(sev, {})[f.status] = (
                severity_counts.setdefault(sev, {}).get(f.status, 0) + 1
            )
        return {
            "target_url": self.target_url,
            "final_url": self.final_url,
            "verdict": self.verdict(),
            "counts": counts,
            "severity_counts": severity_counts,
            "fetch_error": self.fetch_error,
            "findings": [f.to_dict() for f in self.findings],
        }


# ---------------------------------------------------------------------------
# Policy URLs (cited inline with every finding)
# ---------------------------------------------------------------------------

POLICY_URLS = {
    "branding": "https://www.apache.org/foundation/marks/pmcs",
    "podling_branding": "https://incubator.apache.org/guides/branding.html",
    "trademark_policy": "https://www.apache.org/foundation/marks/",
    "domain_branding": "https://www.apache.org/foundation/marks/domains",
    "logos": "https://www.apache.org/foundation/marks/pmcs#logos",
    "navigation": "https://www.apache.org/foundation/marks/pmcs#navigation",
    "attribution": "https://www.apache.org/foundation/marks/pmcs#attributions",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _infer_project_name(page: web.FetchedPage) -> str:
    """Best-guess the project name from the host (foo.apache.org -> Foo)."""
    host = page.host
    if web.is_apache_host(host) and host != "apache.org":
        first = host.split(".")[0]
        if first and first != "www":
            return first.capitalize()
    # Fall back to title prefix: "Apache Foo — ..." -> "Foo"
    m = re.search(r"\bApache\s+([A-Z][A-Za-z0-9]+)", page.title or "")
    if m:
        return m.group(1)
    return ""


def _find_first_occurrence(text: str, project_name: str) -> tuple[int, str]:
    """Return ``(index, surrounding_window)`` for the first 'Apache <Name>'."""
    if not project_name:
        return -1, ""
    pattern = re.compile(rf"\bApache\s+{re.escape(project_name)}\b", flags=re.IGNORECASE)
    m = pattern.search(text)
    if not m:
        return -1, ""
    start = max(0, m.start() - 20)
    end = min(len(text), m.end() + 30)
    return m.start(), text[start:end]


def _has_tm_or_r_near(window: str) -> bool:
    """Return True if a TM/(R) marker appears within ``window``."""
    return bool(re.search(r"™|®|\(\s*TM\s*\)|\(\s*R\s*\)", window, flags=re.IGNORECASE))


def _link_to_path_present(
    links: Iterable[web.Link], host_substring: str, path_substring: str = ""
) -> web.Link | None:
    """Find a link whose href contains ``host_substring`` (and optional path)."""
    for link in links:
        href = (link.href or "").lower()
        if host_substring in href and (not path_substring or path_substring in href):
            return link
    return None


# ---------------------------------------------------------------------------
# Bare-mark detection for other ASF projects
# ---------------------------------------------------------------------------

# Project names that overlap with common English words and would generate
# excessive false positives if scanned bare. The list is intentionally short:
# if you're going to err, err on the side of fewer flags rather than more.
# The mark list itself is sourced from the live ASF project feed (see
# ``project_names_for_bare_scan`` below) — this is purely a stoplist applied
# *after* fetching, so new podlings whose names happen to collide with
# English words don't immediately start spraying false positives.
AMBIGUOUS_ENGLISH_PROJECT_NAMES: frozenset[str] = frozenset(
    {
        "Ant",
        "Any23",
        "Bee",
        "Bigtop",
        "Bloodhound",
        "Camel",
        "Crail",
        "Etch",
        "Falcon",
        "Felix",
        "Forrest",
        "Fortress",
        "Helix",
        "Heron",
        "Hive",
        "Hop",
        "James",
        "Lens",
        "Logging",
        "Marvin",
        "Nemo",
        "Pig",
        "Pony",
        "Portals",
        "Roller",
        "Sentry",
        "Spot",
        "Storm",
        "Traffic",
        "Training",
        "Wave",
        "Whimsy",
        "Zest",
        "Zeta",
    }
)


def project_names_for_bare_scan(
    projects: Iterable[dict] | None,
    *,
    stoplist: Iterable[str] = AMBIGUOUS_ENGLISH_PROJECT_NAMES,
    min_length: int = 4,
) -> list[str]:
    """Return capitalized ASF project names suitable for a bare-mark scan.

    Takes the parsed ASF projects feed (committees + podlings) and extracts
    project names in the form most useful for case-sensitive matching:
    capitalized human names like ``Spark`` and ``Flink`` (not the lowercase
    ids like ``spark``).

    Filters out:
      * empty / whitespace-only names
      * names shorter than ``min_length`` (avoids 3-letter acronyms that
        match too eagerly in body text)
      * names that don't start with an uppercase letter (lowercase ids would
        match common English words on a case-sensitive scan)
      * names in ``stoplist`` (common-English-word overlaps)
    """
    if not projects:
        return []
    stop_lc = {s.strip().lower() for s in stoplist if s}
    seen: set[str] = set()
    out: list[str] = []
    for entry in projects:
        if not isinstance(entry, dict):
            continue
        # Skip retired podlings — they're no longer active ASF marks and
        # shouldn't trigger branding-policy violations on third-party or
        # sibling-project pages. Graduated podlings reach this loop via
        # their committee entry (no status field), so this filter only
        # drops genuinely retired projects.
        if str(entry.get("status", "")).strip().lower() == "retired":
            continue
        candidates = (
            str(entry.get("name", "")),
            # Some podlings only carry the id; capitalise the first letter
            # so it survives the case-sensitive scan.
            str(entry.get("id", "")).capitalize(),
        )
        for raw in candidates:
            name = re.sub(r"^[Aa]pache\s+", "", raw).strip()
            name = re.sub(r"\s*\(\s*incubating\s*\)\s*$", "", name, flags=re.IGNORECASE)
            if len(name) < min_length:
                continue
            if not name[:1].isupper():
                continue
            if name.lower() in stop_lc:
                continue
            if name in seen:
                continue
            seen.add(name)
            out.append(name)
    return out


def _scan_bare_other_asf_marks(
    text: str,
    *,
    marks: Iterable[str],
    project: str = "",
    excluded_marks: Iterable[str] = (),
) -> list[dict]:
    """Return a list of bare ASF mark mentions found in ``text``.

    A mark is considered "bare" if a capitalized, word-bounded occurrence of
    the mark appears in ``text`` while the ``Apache <Mark>`` form never does.
    The check is case-sensitive on the mark itself ("Spark" matches, "spark"
    does not) to avoid noise from common-English-word lowercase usage.

    Each result dict carries: ``mark`` (the ASF project name), ``count``
    (number of bare occurrences), and ``evidence`` (short surrounding snippet
    of the first bare occurrence).

    ``project`` is excluded from the scan so the page's own name is not
    flagged. ``excluded_marks`` removes marks the caller knows are safe to
    skip on this page (e.g. a podling that has explicitly negotiated a
    naming exception).
    """
    if not text:
        return []

    own_lc = (project or "").strip().lower()
    excl_lc = {m.strip().lower() for m in excluded_marks if m}

    findings: list[dict] = []
    for mark in sorted({m for m in marks if m}):
        mark_lc = mark.lower()
        if mark_lc == own_lc or mark_lc in excl_lc:
            continue

        # Case-sensitive search for any "Apache <Mark>" mention anywhere on
        # the page. If present, the page has already established the brand
        # form and bare follow-on uses are acceptable.
        apache_form_re = re.compile(
            rf"\bApache\s+{re.escape(mark)}\b", flags=re.IGNORECASE
        )
        if apache_form_re.search(text):
            continue

        # Case-sensitive scan for bare occurrences. Word-bounded so 'Spark'
        # doesn't match 'sparking' or 'Sparkling'.
        bare_re = re.compile(rf"\b{re.escape(mark)}\b")
        matches = list(bare_re.finditer(text))
        if not matches:
            continue

        first = matches[0]
        start = max(0, first.start() - 30)
        end = min(len(text), first.end() + 30)
        snippet = text[start:end].strip()
        findings.append(
            {
                "mark": mark,
                "count": len(matches),
                "evidence": snippet[:200],
            }
        )

    return findings


def _check_bare_other_asf_marks(
    page: web.FetchedPage,
    project: str,
    report: ComplianceReport,
    *,
    marks: Iterable[str] | None,
    fail_status: str = FAIL,
    no_match_status: str = PASS,
) -> None:
    """Add a finding for any ASF marks used bare on the page.

    ``marks`` is the candidate mark list, normally derived from the live
    ASF projects feed via :func:`project_names_for_bare_scan`. If ``None``
    or empty, the check is reported as SKIP — the caller could not supply
    a project list (e.g. the network is offline and there is no cache).

    ``fail_status`` lets callers downgrade the finding to WARN for pages
    where nominative use is plausible (third-party sites).
    """
    mark_list = list(marks) if marks else []
    if not mark_list:
        report.findings.append(
            Finding(
                rule="bare_other_asf_marks",
                status=SKIP,
                detail=(
                    "No ASF project list available to scan against. The "
                    "bare-mark check needs the cached projects.apache.org "
                    "feed; run refresh_project_cache or check network access."
                ),
                policy_url=POLICY_URLS["trademark_policy"],
            )
        )
        return

    bare = _scan_bare_other_asf_marks(page.text, marks=mark_list, project=project)
    if not bare:
        report.findings.append(
            Finding(
                rule="bare_other_asf_marks",
                status=no_match_status,
                detail=(
                    "No other ASF project marks were found used without the "
                    "'Apache' prefix."
                ),
                policy_url=POLICY_URLS["trademark_policy"],
            )
        )
        return

    names = ", ".join(b["mark"] for b in bare[:10])
    evidence_lines = "; ".join(
        f"{b['mark']} (×{b['count']}): {b['evidence']}" for b in bare[:5]
    )
    report.findings.append(
        Finding(
            rule="bare_other_asf_marks",
            status=fail_status,
            detail=(
                "Page mentions other ASF project mark(s) without ever using "
                f"the 'Apache <Name>' form: {names}. ASF branding policy "
                "requires the full 'Apache <ProjectName>' form on first use "
                "of any ASF mark, including marks of sibling projects."
            ),
            policy_url=POLICY_URLS["trademark_policy"],
            evidence=evidence_lines,
        )
    )


# ---------------------------------------------------------------------------
# ASF project website checks
# ---------------------------------------------------------------------------


def check_project_website(
    page: web.FetchedPage,
    *,
    project_name: str | None = None,
    stage: str = "tlp",
    known_marks: Iterable[str] | None = None,
) -> ComplianceReport:
    """Return a :class:`ComplianceReport` for an Apache project's homepage.

    ``known_marks`` is the list of capitalised ASF project names to scan for
    bare usage (e.g. ``["Spark", "Flink", ...]``). Callers normally derive
    this from the live ASF project feed via
    :func:`project_names_for_bare_scan`; tests pass an explicit list.
    """
    report = ComplianceReport(target_url=page.url, final_url=page.final_url)

    if page.error:
        report.fetch_error = page.error
        return report

    project = (project_name or _infer_project_name(page)).strip()
    stage_lc = (stage or "tlp").strip().lower()
    if stage_lc not in policy.VALID_BRANDING_STAGES:
        stage_lc = "tlp"

    _check_apache_host(page, report)
    _check_apache_form_heading(page, project, report)
    _check_tm_symbol_on_first_use(page, project, report)
    _check_trademark_attribution(page, report)
    _check_third_party_trademark_note(page, report)
    _check_required_nav_links(page, report)
    _check_apache_org_link(page, report)
    _check_logo_has_tm(page, report)
    _check_logo_attribution(page, project, report)
    # ASF project pages have no nominative-use exception — bare references to
    # sibling ASF projects are a policy violation.
    _check_bare_other_asf_marks(
        page, project, report, marks=known_marks, fail_status=FAIL
    )

    if stage_lc == "podling":
        _check_incubation_disclaimer(page, report)
        _check_incubating_suffix(page, project, report)

    return report


def _check_apache_host(page: web.FetchedPage, report: ComplianceReport) -> None:
    host = page.host
    if web.is_apache_host(host):
        report.findings.append(
            Finding(
                rule="apache_org_hosting",
                status=PASS,
                detail=f"Site is hosted on '{host}' (apache.org domain).",
                policy_url=POLICY_URLS["branding"],
            )
        )
    else:
        report.findings.append(
            Finding(
                rule="apache_org_hosting",
                status=FAIL,
                detail=(
                    f"Site is hosted on '{host}', not an apache.org domain. ASF policy "
                    "requires official project content to live on ProjectName.apache.org."
                ),
                policy_url=POLICY_URLS["branding"],
            )
        )


def _check_apache_form_heading(
    page: web.FetchedPage, project: str, report: ComplianceReport
) -> None:
    if not project:
        report.findings.append(
            Finding(
                rule="apache_form_heading",
                status=SKIP,
                detail=(
                    "Could not infer the project name from the host or title. "
                    "Pass project_name explicitly to enable this check."
                ),
                policy_url=POLICY_URLS["branding"],
            )
        )
        return

    expected = f"Apache {project}"
    heading_blob = " | ".join(page.headings[:5])
    in_title = expected.lower() in (page.title or "").lower()
    in_heading = expected.lower() in heading_blob.lower()
    if in_heading or in_title:
        report.findings.append(
            Finding(
                rule="apache_form_heading",
                status=PASS,
                detail=(
                    f"'{expected}' appears in a top heading or page title — primary "
                    "branding is in the required form."
                ),
                policy_url=POLICY_URLS["branding"],
                evidence=heading_blob[:200] or page.title,
            )
        )
    else:
        report.findings.append(
            Finding(
                rule="apache_form_heading",
                status=FAIL,
                detail=(
                    f"Primary heading / title does not include '{expected}'. The first "
                    "and most prominent reference on every page must use the "
                    "'Apache ProjectName' form."
                ),
                policy_url=POLICY_URLS["branding"],
                evidence=heading_blob[:200] or page.title,
            )
        )


def _check_tm_symbol_on_first_use(
    page: web.FetchedPage, project: str, report: ComplianceReport
) -> None:
    if not project:
        return

    pattern = re.compile(rf"\bApache\s+{re.escape(project)}\b", flags=re.IGNORECASE)

    # Per policy, the TM/(R) must appear at the first prominent occurrence
    # "both in header/title text and at the name's first appearance in
    # running text." We treat any of (title, a heading containing the mark,
    # first running-text occurrence) as a valid carrier — if at least one
    # prominent location has the symbol we pass; if none do we fail.
    candidates: list[str] = []
    if page.title and pattern.search(page.title):
        candidates.append(page.title)
    for heading in page.headings:
        if pattern.search(heading):
            candidates.append(heading)
    _idx, window = _find_first_occurrence(page.text, project)
    if window:
        candidates.append(window)

    if not candidates:
        report.findings.append(
            Finding(
                rule="tm_symbol_on_first_use",
                status=WARN,
                detail=(
                    f"Could not locate any 'Apache {project}' reference on the page to "
                    "check for a TM or (R) symbol."
                ),
                policy_url=POLICY_URLS["branding"],
            )
        )
        return

    if any(_has_tm_or_r_near(c) for c in candidates):
        report.findings.append(
            Finding(
                rule="tm_symbol_on_first_use",
                status=PASS,
                detail=(
                    f"A TM or (R) symbol appears next to a prominent 'Apache {project}' "
                    "reference (title, heading, or first running-text occurrence)."
                ),
                policy_url=POLICY_URLS["branding"],
                evidence=next(c for c in candidates if _has_tm_or_r_near(c))[:200],
            )
        )
    else:
        report.findings.append(
            Finding(
                rule="tm_symbol_on_first_use",
                status=WARN,
                detail=(
                    f"No TM or (R) symbol next to any prominent 'Apache {project}' "
                    "reference. Policy: 'you SHOULD include the appropriate TM or (R) "
                    "symbol next to the first main occurrence of the Apache "
                    f"{project} project name, both in header/title text and at the "
                    "name's first appearance in running text.' (Soft requirement — "
                    "'should' rather than 'must' in policy.)"
                ),
                policy_url=POLICY_URLS["branding"],
                evidence=candidates[0][:200],
            )
        )


def _check_trademark_attribution(page: web.FetchedPage, report: ComplianceReport) -> None:
    blob = page.text_lower
    asf_phrase = "apache software foundation"
    trademark_phrases = (
        "trademarks of the apache software foundation",
        "registered trademarks of the apache software foundation",
        "trademarks or registered trademarks of the apache software foundation",
    )
    if any(p in blob for p in trademark_phrases) or ("trademark" in blob and asf_phrase in blob):
        report.findings.append(
            Finding(
                rule="trademark_attribution",
                status=PASS,
                detail=(
                    "Page mentions an Apache Software Foundation trademark attribution string."
                ),
                policy_url=POLICY_URLS["attribution"],
            )
        )
    else:
        report.findings.append(
            Finding(
                rule="trademark_attribution",
                status=FAIL,
                detail=(
                    "No 'trademarks of The Apache Software Foundation' attribution "
                    "found in the visible page text. Required in the page footer."
                ),
                policy_url=POLICY_URLS["attribution"],
            )
        )


def _check_third_party_trademark_note(page: web.FetchedPage, report: ComplianceReport) -> None:
    blob = page.text_lower
    if ("other marks" in blob and "respective owners" in blob) or "all other marks" in blob:
        report.findings.append(
            Finding(
                rule="third_party_trademark_note",
                status=PASS,
                detail=(
                    "Page includes a generic third-party trademark acknowledgement "
                    "(e.g. 'all other marks are trademarks of their respective owners')."
                ),
                policy_url=POLICY_URLS["attribution"],
            )
        )
    else:
        report.findings.append(
            Finding(
                rule="third_party_trademark_note",
                status=WARN,
                detail=(
                    "No generic third-party trademark acknowledgement found. If the "
                    "site mentions any non-ASF marks, they must be attributed to "
                    "their owners (e.g. 'All other marks ... respective owners')."
                ),
                policy_url=POLICY_URLS["attribution"],
            )
        )


_NAV_REQUIREMENTS: list[tuple[str, str, str]] = [
    ("license", "apache.org/licenses", "License → apache.org/licenses/"),
    (
        "sponsorship_or_donate",
        "apache.org/foundation/sponsorship",
        "Sponsorship / Donate → apache.org/foundation/sponsorship.html",
    ),
    (
        "thanks_or_sponsors",
        "apache.org/foundation/thanks",
        "Thanks / Sponsors → apache.org/foundation/thanks.html",
    ),
    ("security", "apache.org/security", "Security → apache.org/security/"),
    (
        "privacy",
        "privacy.apache.org",
        "Privacy → privacy.apache.org/policies/privacy-policy-public.html",
    ),
]


def _check_required_nav_links(page: web.FetchedPage, report: ComplianceReport) -> None:
    for rule, host_substring, label in _NAV_REQUIREMENTS:
        # Allow project-specific security pages: any /security/ link on the
        # same apache.org host also counts for the security rule.
        link = _link_to_path_present(page.links, host_substring)
        if link is None and rule == "security":
            link = _link_to_path_present(page.links, "/security")
        if rule == "thanks_or_sponsors" and link is None:
            link = _link_to_path_present(page.links, "apache.org/foundation/sponsors")

        if link is not None:
            report.findings.append(
                Finding(
                    rule=f"nav_link_{rule}",
                    status=PASS,
                    detail=f"Required navigation link present: {label}.",
                    policy_url=POLICY_URLS["navigation"],
                    evidence=link.href,
                )
            )
        else:
            report.findings.append(
                Finding(
                    rule=f"nav_link_{rule}",
                    status=FAIL,
                    detail=(
                        f"Required navigation link missing: {label}. "
                        "Must appear in the main navigation on all top-level pages."
                    ),
                    policy_url=POLICY_URLS["navigation"],
                )
            )


def _check_apache_org_link(page: web.FetchedPage, report: ComplianceReport) -> None:
    link = _link_to_path_present(page.links, "www.apache.org") or _link_to_path_present(
        page.links, "apache.org"
    )
    if link is not None:
        report.findings.append(
            Finding(
                rule="link_back_to_apache_org",
                status=PASS,
                detail="Page links back to the main ASF homepage at www.apache.org.",
                policy_url=POLICY_URLS["navigation"],
                evidence=link.href,
            )
        )
    else:
        report.findings.append(
            Finding(
                rule="link_back_to_apache_org",
                status=FAIL,
                detail=(
                    "No prominent link back to www.apache.org found. All projects "
                    "must feature a prominent link to the main ASF homepage."
                ),
                policy_url=POLICY_URLS["navigation"],
            )
        )


_FEATHER_HINTS = ("feather", "asf-logo", "apache-logo", "asf_logo", "apache_logo")


def _logo_uses_asf_feather(page: web.FetchedPage) -> tuple[bool, str]:
    """Return ``(uses_feather, evidence)`` for any project-logo image.

    The hint is purely textual (src/alt). A clean SVG that bakes the feather
    in without a hinted filename cannot be detected here — those land in the
    softer WARN bucket below.
    """
    for img in page.images:
        blob = f"{img.src or ''} {img.alt or ''}".lower()
        if "logo" not in blob:
            continue
        if any(hint in blob for hint in _FEATHER_HINTS):
            return True, img.src or img.alt
    return False, ""


def _check_logo_has_tm(page: web.FetchedPage, report: ComplianceReport) -> None:
    has_logo_image = any(
        "logo" in (img.src or "").lower() or "logo" in (img.alt or "").lower()
        for img in page.images
    )
    if not has_logo_image:
        report.findings.append(
            Finding(
                rule="logo_tm",
                status=INFO,
                detail="No project-logo image detected on this page; logo TM check skipped.",
                policy_url=POLICY_URLS["logos"],
            )
        )
        return

    uses_feather, feather_evidence = _logo_uses_asf_feather(page)
    has_tm_in_page = _has_tm_or_r_near(page.text)

    # Policy ("Logos and Graphics Policy") uses softer "ensure" language for
    # project logos generally, but tightens to "especially if it uses the ASF
    # graphic mark" when the logo incorporates the feather. So:
    #   - feather-based logo + no TM in page text  -> FAIL
    #   - any project logo + TM somewhere in page text -> PASS
    #     (may be baked into the bitmap; confirm visually)
    #   - other project logo + no TM in page text  -> WARN
    if has_tm_in_page:
        report.findings.append(
            Finding(
                rule="logo_tm",
                status=PASS,
                detail=(
                    "A logo image is present and a TM or (R) symbol appears somewhere on "
                    "the page. The TM/(R) may instead live inside the logo bitmap; "
                    "confirm visually."
                ),
                policy_url=POLICY_URLS["logos"],
            )
        )
        return

    if uses_feather:
        report.findings.append(
            Finding(
                rule="logo_tm",
                status=FAIL,
                detail=(
                    "Logo appears to use the ASF feather / Apache graphic mark and no "
                    "TM or (R) symbol was found in the page text. Policy is stronger "
                    "for logos that incorporate the ASF graphic mark: TM must be in "
                    "the graphic or immediately adjacent to it."
                ),
                policy_url=POLICY_URLS["logos"],
                evidence=feather_evidence,
            )
        )
    else:
        report.findings.append(
            Finding(
                rule="logo_tm",
                status=WARN,
                detail=(
                    "A logo image is present but no TM or (R) symbol was found in the "
                    "page text. Project logos should include a small TM in the graphic "
                    "or immediately adjacent to it. (Soft requirement — 'ensure' rather "
                    "than 'must' in policy.)"
                ),
                policy_url=POLICY_URLS["logos"],
            )
        )


def _check_logo_attribution(page: web.FetchedPage, project: str, report: ComplianceReport) -> None:
    """Attribution must mention the project logo when one is shown on the page."""
    has_logo_image = any(
        "logo" in (img.src or "").lower() or "logo" in (img.alt or "").lower()
        for img in page.images
    )
    if not has_logo_image:
        return  # Nothing to check; the broader trademark_attribution rule already ran.

    blob = page.text_lower
    project_lc = project.lower() if project else ""

    # Accept any of:
    #   - "the Apache {Project} logo ... trademark"  (most explicit)
    #   - "the {Project} logo ... trademark"         (Cassandra-style footer)
    #   - "the Project logo ... trademark"           (generic placeholder text)
    # Each must co-occur with a trademark/ASF context in the same blob so we
    # don't match unrelated mentions like "the feather logo".
    has_trademark_context = "trademark" in blob and "apache software foundation" in blob
    project_logo_phrases: list[str] = []
    if project_lc:
        project_logo_phrases.append(f"apache {project_lc} logo")
        project_logo_phrases.append(f"the {project_lc} logo")
    project_logo_phrases.append("project logo")
    matched_phrase = next(
        (p for p in project_logo_phrases if p in blob),
        None,
    )

    if matched_phrase and has_trademark_context:
        report.findings.append(
            Finding(
                rule="logo_attribution",
                status=PASS,
                detail=(
                    f"Trademark attribution names the project logo (matched '{matched_phrase}')."
                ),
                policy_url=POLICY_URLS["attribution"],
            )
        )
    else:
        report.findings.append(
            Finding(
                rule="logo_attribution",
                status=WARN,
                detail=(
                    "Page shows a project logo but the trademark attribution does not "
                    "name it. Policy: 'For pages that include the project logo on them, "
                    'ensure you mention "... and the Project logo are trademarks ..." '
                    "in the attribution.' Accepted phrasings include 'and the Apache "
                    f"{project or '<Name>'} logo' or 'and the {project or '<Name>'} logo'."
                ),
                policy_url=POLICY_URLS["attribution"],
            )
        )


def _check_incubation_disclaimer(page: web.FetchedPage, report: ComplianceReport) -> None:
    blob = page.text_lower
    if "undergoing incubation" in blob and "apache software foundation" in blob:
        report.findings.append(
            Finding(
                rule="incubation_disclaimer",
                status=PASS,
                detail=(
                    "Page contains the incubation disclaimer "
                    "('undergoing incubation at The Apache Software Foundation...')."
                ),
                policy_url=POLICY_URLS["podling_branding"],
            )
        )
    else:
        report.findings.append(
            Finding(
                rule="incubation_disclaimer",
                status=FAIL,
                detail=(
                    "Required incubation disclaimer text not found. Podling pages must "
                    "include the full DISCLAIMER text noting that the project is "
                    "undergoing incubation at the Apache Software Foundation."
                ),
                policy_url=POLICY_URLS["podling_branding"],
            )
        )


def _check_incubating_suffix(page: web.FetchedPage, project: str, report: ComplianceReport) -> None:
    blob = page.text
    if "Incubating" in blob or "(incubating)" in blob.lower():
        report.findings.append(
            Finding(
                rule="incubating_suffix",
                status=PASS,
                detail="Page references the project as '(Incubating)' as required for podlings.",
                policy_url=POLICY_URLS["podling_branding"],
            )
        )
    else:
        report.findings.append(
            Finding(
                rule="incubating_suffix",
                status=FAIL,
                detail=(
                    f"No '(Incubating)' suffix found. Podlings must refer to themselves as "
                    f"'Apache {project or '<Name>'} (Incubating)' in all external references."
                ),
                policy_url=POLICY_URLS["podling_branding"],
            )
        )


# ---------------------------------------------------------------------------
# Third-party use checks
# ---------------------------------------------------------------------------


def check_third_party_use(
    page: web.FetchedPage,
    *,
    mark: str | None = None,
    known_marks: Iterable[str] | None = None,
) -> ComplianceReport:
    """Return a :class:`ComplianceReport` for a third-party page using ASF marks.

    ``known_marks`` is the list of capitalised ASF project names to scan for
    bare usage; see :func:`check_project_website` for details.
    """
    report = ComplianceReport(target_url=page.url, final_url=page.final_url)

    if page.error:
        report.fetch_error = page.error
        return report

    resolved_mark = (mark or "").strip()
    if not resolved_mark:
        # Try to infer the mark by scanning page text for "Apache <Word>" pairs.
        m = re.search(r"\bApache\s+([A-Z][A-Za-z0-9]+)", page.text)
        if m:
            resolved_mark = m.group(1)

    _check_not_apache_host(page, report)
    _check_domain_misuse(page, resolved_mark, report)
    _check_branding_form(page, resolved_mark, report)
    _check_non_affiliation_disclaimer(page, report)
    _check_logo_misuse(page, report)
    _check_credit_link(page, resolved_mark, report)
    # On third-party pages bare nominative use is more often defensible, so
    # surface bare sibling-mark references as a WARN rather than a FAIL.
    _check_bare_other_asf_marks(
        page, resolved_mark, report, marks=known_marks, fail_status=WARN
    )

    return report


def _check_not_apache_host(page: web.FetchedPage, report: ComplianceReport) -> None:
    if web.is_apache_host(page.host):
        report.findings.append(
            Finding(
                rule="third_party_host",
                status=INFO,
                detail=(
                    f"Host '{page.host}' is on the apache.org domain. This checker is "
                    "for third-party sites; results may not be meaningful for ASF pages."
                ),
                policy_url=POLICY_URLS["trademark_policy"],
            )
        )


def _check_domain_misuse(page: web.FetchedPage, mark: str, report: ComplianceReport) -> None:
    host = page.host
    sld = web.second_level_domain(host)
    fired = False

    if "apache" in host and not web.is_apache_host(host):
        fired = True
        report.findings.append(
            Finding(
                rule="domain_uses_apache",
                status=FAIL,
                detail=(
                    f"Domain '{host}' contains 'apache'. ASF policy: 'No use of Apache "
                    "or Community Over Code in domain names.' Use of Apache marks in "
                    "third-party domain names requires written permission from VP "
                    "Brand Management."
                ),
                policy_url=POLICY_URLS["domain_branding"],
                evidence=host,
            )
        )

    if mark and sld.lower() == mark.lower():
        fired = True
        report.findings.append(
            Finding(
                rule="bare_mark_as_sld",
                status=FAIL,
                detail=(
                    f"Bare Apache product name '{mark}' used as a second-level domain "
                    f"('{host}'). ASF policy prohibits using a bare Apache product "
                    "name as a second-level domain (e.g. tomcat.com)."
                ),
                policy_url=POLICY_URLS["domain_branding"],
                evidence=host,
            )
        )

    if not fired and host:
        report.findings.append(
            Finding(
                rule="domain_clean",
                status=PASS,
                detail=(
                    f"Domain '{host}' does not contain 'apache' and is not the bare "
                    f"'{mark}' name. No domain-policy issues detected."
                    if mark
                    else f"Domain '{host}' does not contain 'apache'. No domain-policy "
                    "issues detected."
                ),
                policy_url=POLICY_URLS["domain_branding"],
                evidence=host,
            )
        )


# Phrases that, when they precede "Apache {Mark}", strongly suggest the page is
# referring to the actual Apache product (nominative fair use) rather than
# branding the page's own product with the mark.
_NOMINATIVE_CONNECTORS = (
    "built on",
    "built upon",
    "based on",
    "compatible with",
    "support for",
    "supports",
    "runs on",
    "running on",
    "works with",
    "uses",
    "using",
    "leverages",
    "leveraging",
    "powered by",
    "integrates with",
    "integration with",
    "implementation of",
    "implementation for",
    "deployed on",
    "on top of",
    "wrapper around",
    "wrapper for",
    "client for",
    "driver for",
    "connector for",
    "extension for",
    "plugin for",
    "extends",
    # Educational / descriptive — explainer pages, encyclopedia entries.
    # Note: deliberately NOT including plain "the" — it would match anything.
    # Use trailers (Apache X "project"/"community"/...) for that case.
    "what is",
    "what's",
    "what are",
    "about",
    "contributing to",
    "contribute to",
    "donated to",
    "donation to",
    "maintained by",
    "developed by",
    "developed at",
    "originally developed at",
    "created by",
    "created at",
    "managed by",
    "stewarded by",
    "release of",
    "version of",
    "distribution of",
)

# Phrases that follow "Apache {Mark}" and signal descriptive / nominative use
# (e.g. "Apache Kafka project", "Apache Kafka community").
_NOMINATIVE_TRAILERS = (
    "project",
    "projects",
    "community",
    "committers",
    "contributors",
    "documentation",
    "docs",
    "website",
    "homepage",
    "trademark",
    "trademarks",
    "logo",
)


def _find_nominative_use(blob: str, mark: str) -> str | None:
    """Return the connector phrase if 'Apache {mark}' appears after one,
    or a trailer-based match like 'Apache Mark project'."""
    # Leading connectors:  (built on|based on|...)\s+Apache\s+Mark\b
    connector_alt = "|".join(re.escape(c) for c in _NOMINATIVE_CONNECTORS)
    pattern = re.compile(
        rf"\b({connector_alt})\s+Apache\s+{re.escape(mark)}\b",
        flags=re.IGNORECASE,
    )
    m = pattern.search(blob)
    if m:
        return m.group(1).lower()

    # Trailers:  \bApache Mark (project|community|...)\b
    trailer_alt = "|".join(re.escape(t) for t in _NOMINATIVE_TRAILERS)
    trailer_pattern = re.compile(
        rf"\bApache\s+{re.escape(mark)}\s+({trailer_alt})\b",
        flags=re.IGNORECASE,
    )
    tm = trailer_pattern.search(blob)
    if tm:
        return f"Apache {mark} {tm.group(1).lower()}"

    return None


_EXPLAINER_URL_TOKENS = (
    # Hyphen-style: /what-is-apache-kafka/
    "/what-is-",
    "/what-are-",
    # Slash-style: /what-is/apache-kafka (AWS, IBM cloud docs, Cloudflare,
    # Snowflake, etc. all use this layout for concept hubs)
    "/what-is/",
    "/what-are/",
    "/concepts/",
    "/topics/",
    "/learn/",
    "/learn-",
    "/glossary/",
    "/wiki/",
    "/wikipedia/",
    "/guide/",
    "/guides/",
    "/tutorial/",
    "/tutorials/",
    "/intro-to-",
    "/introduction-to-",
    "/explained",
    "/blog/",
)

_EXPLAINER_TITLE_PREFIXES = (
    "what is ",
    "what are ",
    "what's ",
    "how does ",
    "how to ",
    "introduction to ",
    "intro to ",
    "guide to ",
    "a guide to ",
    "the guide to ",
    "understanding ",
    "explaining ",
)


def is_explainer_page(page: web.FetchedPage) -> bool:
    """True if URL or title suggests this is an encyclopedia/explainer page.

    Explainer pages (``what-is-X``, ``/learn/X``, ``/glossary/X``) are
    fundamentally nominative use: the page is *about* the mark, not branding
    a product with it. A missing "Powered By" form on such a page is not a
    policy concern.
    """
    url = (page.final_url or page.url or "").lower()
    if any(tok in url for tok in _EXPLAINER_URL_TOKENS):
        return True
    title = (page.title or "").strip().lower()
    return any(title.startswith(prefix) for prefix in _EXPLAINER_TITLE_PREFIXES)


def _check_branding_form(page: web.FetchedPage, mark: str, report: ComplianceReport) -> None:
    if not mark:
        report.findings.append(
            Finding(
                rule="branding_form",
                status=SKIP,
                detail=(
                    "No Apache mark provided and none could be inferred from the page. "
                    "Pass 'mark' to enable the branding-form check."
                ),
                policy_url=POLICY_URLS["trademark_policy"],
            )
        )
        return

    blob = page.text
    approved_forms = (
        f"Powered By Apache {mark}",
        f"Powered by Apache {mark}",
        f"Apache {mark} Inside",
    )
    has_approved_brand_form = any(form in blob for form in approved_forms)
    apache_mark_present = re.search(rf"\bApache\s+{re.escape(mark)}\b", blob, flags=re.IGNORECASE)
    bare_mark_present = re.search(rf"\b{re.escape(mark)}\b", blob)
    nominative_connector = _find_nominative_use(blob, mark)

    # Heuristic for product-branding misuse: the mark appears immediately
    # adjacent to a vendor-style suffix like 'Pro', 'Plus', 'Enterprise', etc.
    branded_suffix = re.search(
        rf"\bApache\s+{re.escape(mark)}\s+(Pro|Plus|Enterprise|Cloud|Premium|Lite|Ultimate)\b",
        blob,
        flags=re.IGNORECASE,
    )

    if branded_suffix:
        report.findings.append(
            Finding(
                rule="branding_form",
                status=FAIL,
                detail=(
                    f"Page uses '{branded_suffix.group(0)}' — adding a vendor suffix "
                    f"to 'Apache {mark}' brands your own product with the Apache "
                    "mark, which is not permitted. Use the 'Powered By Apache "
                    f"{mark}' form instead."
                ),
                policy_url=POLICY_URLS["trademark_policy"],
                evidence=branded_suffix.group(0),
            )
        )
        return

    if has_approved_brand_form:
        report.findings.append(
            Finding(
                rule="branding_form",
                status=PASS,
                detail=(
                    f"Page uses an approved branding form: 'Powered By Apache "
                    f"{mark}' or 'Apache {mark} Inside'."
                ),
                policy_url=POLICY_URLS["trademark_policy"],
            )
        )
        return

    if nominative_connector and apache_mark_present:
        report.findings.append(
            Finding(
                rule="branding_form",
                status=PASS,
                detail=(
                    f"Page refers to 'Apache {mark}' with a nominative phrasing "
                    f"('{nominative_connector} Apache {mark}'). Nominative use is "
                    "permitted under ASF Trademark Policy provided the mark is "
                    "only used as much as necessary and nothing suggests ASF "
                    "sponsorship or endorsement."
                ),
                policy_url=POLICY_URLS["trademark_policy"],
                evidence=f"{nominative_connector} Apache {mark}",
            )
        )
        return

    explainer = is_explainer_page(page)

    if apache_mark_present:
        if explainer:
            report.findings.append(
                Finding(
                    rule="branding_form",
                    status=INFO,
                    detail=(
                        f"Page refers to 'Apache {mark}' on what looks like an "
                        "encyclopedia/explainer page (URL or title suggests it is "
                        "*about* the mark). This is nominative use by default; the "
                        "absence of a 'Powered By' branding form is expected."
                    ),
                    policy_url=POLICY_URLS["trademark_policy"],
                )
            )
            return
        report.findings.append(
            Finding(
                rule="branding_form",
                status=WARN,
                detail=(
                    f"Page refers to 'Apache {mark}' but does not use an approved "
                    f"branding form ('Powered By Apache {mark}' / 'Apache {mark} "
                    "Inside') or a recognised nominative phrase ('built on Apache "
                    f"{mark}', 'compatible with Apache {mark}', etc.). Check whether "
                    "the reference is purely nominative or whether it is being used "
                    "as your own product brand."
                ),
                policy_url=POLICY_URLS["trademark_policy"],
            )
        )
        return

    if bare_mark_present:
        if explainer:
            report.findings.append(
                Finding(
                    rule="branding_form",
                    status=INFO,
                    detail=(
                        f"Page mentions '{mark}' without the 'Apache' prefix on "
                        "what looks like an explainer page. Encyclopedia/glossary "
                        "pages commonly use the short form after first reference."
                    ),
                    policy_url=POLICY_URLS["trademark_policy"],
                )
            )
            return
        report.findings.append(
            Finding(
                rule="branding_form",
                status=WARN,
                detail=(
                    f"Page mentions '{mark}' without the 'Apache' prefix. ASF prefers "
                    f"the full 'Apache {mark}' form in references; bare-mark usage "
                    "may suggest the mark is your own product name."
                ),
                policy_url=POLICY_URLS["trademark_policy"],
            )
        )
        return

    report.findings.append(
        Finding(
            rule="branding_form",
            status=INFO,
            detail=f"No '{mark}' references found in the page text.",
            policy_url=POLICY_URLS["trademark_policy"],
        )
    )


_TRADEMARK_ATTRIBUTION_RE = re.compile(
    r"(?:are|is|a)\s+(?:registered\s+)?trademark[s]?\s+of\s+"
    r"(?:the\s+)?apache\s+software\s+foundation",
    re.IGNORECASE,
)


def _check_non_affiliation_disclaimer(page: web.FetchedPage, report: ComplianceReport) -> None:
    blob = page.text_lower
    phrases = (
        "not affiliated with",
        "not associated with",
        "no affiliation with",
        "independent",
    )
    has_disclaimer = any(p in blob for p in phrases) and "apache" in blob
    attribution_match = _TRADEMARK_ATTRIBUTION_RE.search(page.text)

    if has_disclaimer:
        report.findings.append(
            Finding(
                rule="non_affiliation_disclaimer",
                status=PASS,
                detail=(
                    "Page includes language signalling non-affiliation with the ASF "
                    "(e.g. 'not affiliated with' / 'independent')."
                ),
                policy_url=POLICY_URLS["trademark_policy"],
            )
        )
        return

    if attribution_match:
        report.findings.append(
            Finding(
                rule="non_affiliation_disclaimer",
                status=PASS,
                detail=(
                    "Page includes a standard trademark attribution to the Apache "
                    "Software Foundation. This is the recommended pattern for "
                    "nominative third-party use and serves the same purpose as an "
                    "explicit non-affiliation disclaimer."
                ),
                policy_url=POLICY_URLS["trademark_policy"],
                evidence=attribution_match.group(0),
            )
        )
        return

    report.findings.append(
        Finding(
            rule="non_affiliation_disclaimer",
            status=WARN,
            detail=(
                "No clear non-affiliation disclaimer or trademark attribution to "
                "the ASF found. Third-party uses of Apache marks should either "
                "say 'not affiliated with the ASF' or include the standard "
                "'<Mark> is a trademark of the Apache Software Foundation' "
                "attribution."
            ),
            policy_url=POLICY_URLS["trademark_policy"],
        )
    )


def _check_logo_misuse(page: web.FetchedPage, report: ComplianceReport) -> None:
    feather_hits: list[str] = []
    apache_logo_hits: list[str] = []
    # If the page text *anywhere* uses "Powered By Apache ..." we treat Apache
    # logo images on the page as likely the official Powered-By badge rather
    # than misuse — even when the filename itself doesn't contain "powered".
    page_text_lower = page.text_lower
    page_has_powered_by = bool(re.search(r"powered\s+by\s+apache\b", page_text_lower))

    for img in page.images:
        src = (img.src or "").lower()
        alt = (img.alt or "").lower()
        combined = src + " " + alt

        if "feather" in src or "feather" in alt:
            feather_hits.append(img.src or img.alt)
            continue
        if "apache" not in src and "apache" not in alt:
            continue
        # An apache-referencing image. Don't flag if the image, its alt text,
        # or the surrounding page indicates it's the Powered-By badge.
        if "powered" in combined or page_has_powered_by:
            continue
        apache_logo_hits.append(img.src or img.alt)

    if feather_hits:
        report.findings.append(
            Finding(
                rule="logo_misuse",
                status=WARN,
                detail=(
                    "Found image(s) referencing the ASF feather graphic. Third "
                    "parties may not use the ASF feather mark as a brand element. "
                    "Verify visually."
                ),
                policy_url=POLICY_URLS["logos"],
                evidence="; ".join(feather_hits[:3]),
            )
        )
        return

    if apache_logo_hits:
        report.findings.append(
            Finding(
                rule="logo_misuse",
                status=INFO,
                detail=(
                    "Found image(s) whose filename or alt text references an Apache "
                    "mark, and the page does not contain a 'Powered By Apache' "
                    "phrase. May be a legitimate Powered-By badge — verify visually."
                ),
                policy_url=POLICY_URLS["logos"],
                evidence="; ".join(apache_logo_hits[:3]),
            )
        )
        return

    report.findings.append(
        Finding(
            rule="logo_misuse",
            status=PASS,
            detail="No obviously misused Apache logo or feather mark images detected.",
            policy_url=POLICY_URLS["logos"],
        )
    )


def _check_credit_link(page: web.FetchedPage, mark: str, report: ComplianceReport) -> None:
    link = _link_to_path_present(page.links, "apache.org")
    if link is None:
        report.findings.append(
            Finding(
                rule="credit_link",
                status=WARN,
                detail=(
                    "Page does not link back to any apache.org page. Third-party use "
                    "should credit the upstream Apache project and link to its "
                    "official ProjectName.apache.org page."
                ),
                policy_url=POLICY_URLS["trademark_policy"],
            )
        )
    else:
        report.findings.append(
            Finding(
                rule="credit_link",
                status=PASS,
                detail="Page links to an apache.org resource — credit link present.",
                policy_url=POLICY_URLS["trademark_policy"],
                evidence=link.href,
            )
        )
