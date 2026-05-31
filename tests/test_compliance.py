from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from apache_trademark_mcp import compliance, web
from tests.html_fixtures import (
    COMPLIANT_PROJECT_HTML,
    COMPLIANT_THIRD_PARTY_HTML,
    FEATHER_LOGO_NO_TM_HTML,
    NONCOMPLIANT_PROJECT_HTML,
    NONCOMPLIANT_THIRD_PARTY_HTML,
    PODLING_COMPLIANT_HTML,
)


def _page(url: str, html: str) -> web.FetchedPage:
    title, headings, links, images, text = web.parse_html(html)
    return web.FetchedPage(
        url=url,
        final_url=url,
        status=200,
        html=html,
        text=text,
        title=title,
        headings=headings,
        links=links,
        images=images,
    )


def _statuses(report: compliance.ComplianceReport) -> dict[str, str]:
    return {f.rule: f.status for f in report.findings}


# ---------------------------------------------------------------------------
# Project website checker
# ---------------------------------------------------------------------------


class CheckProjectWebsiteTests(unittest.TestCase):
    def test_compliant_apache_page_passes(self) -> None:
        page = _page("https://foo.apache.org/", COMPLIANT_PROJECT_HTML)
        report = compliance.check_project_website(page, project_name="Foo")
        statuses = _statuses(report)
        self.assertEqual(statuses["apache_org_hosting"], "pass")
        self.assertEqual(statuses["apache_form_heading"], "pass")
        self.assertEqual(statuses["tm_symbol_on_first_use"], "pass")
        self.assertEqual(statuses["trademark_attribution"], "pass")
        self.assertEqual(statuses["nav_link_license"], "pass")
        self.assertEqual(statuses["nav_link_security"], "pass")
        self.assertEqual(statuses["nav_link_privacy"], "pass")
        self.assertEqual(statuses["link_back_to_apache_org"], "pass")
        self.assertEqual(report.verdict(), "PASS")

    def test_non_apache_host_fails(self) -> None:
        page = _page("https://foo.example.com/", COMPLIANT_PROJECT_HTML)
        report = compliance.check_project_website(page, project_name="Foo")
        statuses = _statuses(report)
        self.assertEqual(statuses["apache_org_hosting"], "fail")

    def test_noncompliant_page_fails_multiple_rules(self) -> None:
        page = _page("https://foo.apache.org/", NONCOMPLIANT_PROJECT_HTML)
        report = compliance.check_project_website(page, project_name="Foo")
        statuses = _statuses(report)
        self.assertEqual(statuses["apache_form_heading"], "fail")
        # tm_symbol_on_first_use is SHOULD in policy — warn even when no
        # prominent occurrence is found.
        self.assertEqual(statuses["tm_symbol_on_first_use"], "warn")
        self.assertEqual(statuses["trademark_attribution"], "fail")
        self.assertEqual(statuses["nav_link_license"], "fail")
        self.assertEqual(statuses["nav_link_privacy"], "fail")
        self.assertEqual(statuses["link_back_to_apache_org"], "fail")
        self.assertEqual(report.verdict(), "FAIL")

    def test_missing_tm_alone_is_a_warn_not_a_fail(self) -> None:
        # Compliant page with the TM stripped — should warn, not fail.
        html = COMPLIANT_PROJECT_HTML.replace("&trade;", "")
        page = _page("https://foo.apache.org/", html)
        report = compliance.check_project_website(page, project_name="Foo")
        statuses = _statuses(report)
        self.assertEqual(statuses["tm_symbol_on_first_use"], "warn")

    def test_podling_stage_runs_incubation_checks(self) -> None:
        page = _page("https://foo.apache.org/", PODLING_COMPLIANT_HTML)
        report = compliance.check_project_website(page, project_name="Foo", stage="podling")
        statuses = _statuses(report)
        self.assertEqual(statuses["incubation_disclaimer"], "pass")
        self.assertEqual(statuses["incubating_suffix"], "pass")

    def test_podling_stage_flags_missing_disclaimer(self) -> None:
        page = _page("https://foo.apache.org/", COMPLIANT_PROJECT_HTML)
        report = compliance.check_project_website(page, project_name="Foo", stage="podling")
        statuses = _statuses(report)
        self.assertEqual(statuses["incubation_disclaimer"], "fail")
        self.assertEqual(statuses["incubating_suffix"], "fail")

    def test_fetch_error_short_circuits(self) -> None:
        page = web.FetchedPage(
            url="https://foo.apache.org/",
            final_url="https://foo.apache.org/",
            status=0,
            html="",
            text="",
            title="",
            headings=[],
            links=[],
            images=[],
            error="boom",
        )
        report = compliance.check_project_website(page, project_name="Foo")
        self.assertEqual(report.findings, [])
        self.assertEqual(report.fetch_error, "boom")
        self.assertEqual(report.verdict(), "SKIP")

    def test_project_name_inferred_from_host(self) -> None:
        page = _page("https://foo.apache.org/", COMPLIANT_PROJECT_HTML)
        # No project_name passed — inference should pick "Foo" from the host
        report = compliance.check_project_website(page)
        statuses = _statuses(report)
        self.assertEqual(statuses["apache_form_heading"], "pass")

    def test_logo_attribution_passes_when_project_logo_named(self) -> None:
        page = _page("https://foo.apache.org/", COMPLIANT_PROJECT_HTML)
        report = compliance.check_project_website(page, project_name="Foo")
        statuses = _statuses(report)
        # COMPLIANT fixture's footer now names "the Apache Foo logo"
        self.assertEqual(statuses["logo_attribution"], "pass")

    def test_logo_attribution_warns_when_project_logo_not_named(self) -> None:
        page = _page("https://foo.apache.org/", FEATHER_LOGO_NO_TM_HTML)
        report = compliance.check_project_website(page, project_name="Foo")
        statuses = _statuses(report)
        # Footer omits any "Apache Foo logo" / "project logo" phrasing
        self.assertEqual(statuses["logo_attribution"], "warn")

    def test_feather_logo_without_tm_is_a_hard_fail(self) -> None:
        page = _page("https://foo.apache.org/", FEATHER_LOGO_NO_TM_HTML)
        report = compliance.check_project_website(page, project_name="Foo")
        statuses = _statuses(report)
        self.assertEqual(statuses["logo_tm"], "fail")

    def test_non_feather_logo_without_tm_is_a_warn(self) -> None:
        # Strip the TM from the compliant fixture so we can isolate the rule
        html = COMPLIANT_PROJECT_HTML.replace("&trade;", "")
        page = _page("https://foo.apache.org/", html)
        report = compliance.check_project_website(page, project_name="Foo")
        statuses = _statuses(report)
        self.assertEqual(statuses["logo_tm"], "warn")

    def test_logo_attribution_accepts_the_mark_logo_form(self) -> None:
        # Cassandra-style footer that says 'the {Mark} logo' rather than
        # 'the Apache {Mark} logo'. Should pass.
        html = """
        <html><body>
          <h1>Apache Foo</h1>
          <img src="/img/foo.png" alt="Foo logo" />
          <footer>
            Apache, the Apache feather logo, Apache Foo, Foo, and the Foo logo
            are either registered trademarks or trademarks of The Apache
            Software Foundation.
          </footer>
        </body></html>
        """
        page = _page("https://foo.apache.org/", html)
        report = compliance.check_project_website(page, project_name="Foo")
        statuses = _statuses(report)
        self.assertEqual(statuses["logo_attribution"], "pass")


# ---------------------------------------------------------------------------
# Third-party use checker
# ---------------------------------------------------------------------------


class CheckThirdPartyUseTests(unittest.TestCase):
    def test_compliant_third_party_passes(self) -> None:
        page = _page("https://yoyodyne.com/yoyostream", COMPLIANT_THIRD_PARTY_HTML)
        report = compliance.check_third_party_use(page, mark="Foo")
        statuses = _statuses(report)
        self.assertEqual(statuses["branding_form"], "pass")
        self.assertEqual(statuses["non_affiliation_disclaimer"], "pass")
        self.assertEqual(statuses["credit_link"], "pass")
        self.assertEqual(statuses["logo_misuse"], "pass")
        self.assertNotEqual(report.verdict(), "FAIL")

    def test_bare_mark_as_sld_fails(self) -> None:
        page = _page("https://foo.com/", NONCOMPLIANT_THIRD_PARTY_HTML)
        report = compliance.check_third_party_use(page, mark="Foo")
        statuses = _statuses(report)
        self.assertEqual(statuses["bare_mark_as_sld"], "fail")

    def test_domain_containing_apache_fails(self) -> None:
        page = _page("https://apache-foo.example.com/", NONCOMPLIANT_THIRD_PARTY_HTML)
        report = compliance.check_third_party_use(page, mark="Foo")
        statuses = _statuses(report)
        self.assertEqual(statuses["domain_uses_apache"], "fail")

    def test_feather_image_flagged(self) -> None:
        page = _page("https://example.com/", NONCOMPLIANT_THIRD_PARTY_HTML)
        report = compliance.check_third_party_use(page, mark="Foo")
        statuses = _statuses(report)
        self.assertEqual(statuses["logo_misuse"], "warn")

    def test_missing_disclaimer_warns(self) -> None:
        page = _page("https://example.com/", NONCOMPLIANT_THIRD_PARTY_HTML)
        report = compliance.check_third_party_use(page, mark="Foo")
        statuses = _statuses(report)
        self.assertEqual(statuses["non_affiliation_disclaimer"], "warn")
        self.assertEqual(statuses["credit_link"], "warn")

    def test_nominative_use_built_on_is_pass(self) -> None:
        # 'built on Apache Cassandra' — classic nominative use, should pass
        html = """
        <html><body>
          <p>Astra DB is built on Apache Cassandra and provides scale.</p>
          <p>Astra DB is not affiliated with the Apache Software Foundation.</p>
          <a href="https://cassandra.apache.org/">upstream</a>
        </body></html>
        """
        page = _page("https://example.com/", html)
        report = compliance.check_third_party_use(page, mark="Cassandra")
        statuses = _statuses(report)
        self.assertEqual(statuses["branding_form"], "pass")

    def test_nominative_use_compatible_with_is_pass(self) -> None:
        html = """
        <html><body>
          <p>YoyoStream is compatible with Apache Foo.</p>
        </body></html>
        """
        page = _page("https://example.com/", html)
        report = compliance.check_third_party_use(page, mark="Foo")
        statuses = _statuses(report)
        self.assertEqual(statuses["branding_form"], "pass")

    def test_apache_x_pro_branded_suffix_is_a_fail(self) -> None:
        # Vendor-branded suffix on the Apache mark is product-brand misuse
        html = "<html><body><h1>Apache Foo Pro</h1><p>The enterprise Foo.</p></body></html>"
        page = _page("https://example.com/", html)
        report = compliance.check_third_party_use(page, mark="Foo")
        statuses = _statuses(report)
        self.assertEqual(statuses["branding_form"], "fail")

    def test_apache_mark_without_nominative_phrase_is_a_warn(self) -> None:
        # 'Apache Foo' present but no nominative connector or approved form
        html = "<html><body><p>Welcome to Apache Foo land.</p></body></html>"
        page = _page("https://example.com/", html)
        report = compliance.check_third_party_use(page, mark="Foo")
        statuses = _statuses(report)
        self.assertEqual(statuses["branding_form"], "warn")

    def test_mark_inference(self) -> None:
        # Page mentions 'Apache Foo' — checker should infer 'Foo' and check
        # branding form.
        html = (
            "<html><body><p>YoyoStream is Powered By Apache Foo.</p>"
            '<a href="https://foo.apache.org/">upstream</a>'
            "<p>Not affiliated with Apache.</p>"
            "</body></html>"
        )
        page = _page("https://yoyodyne.com/yoyostream", html)
        report = compliance.check_third_party_use(page)
        statuses = _statuses(report)
        self.assertEqual(statuses["branding_form"], "pass")


class ThirdPartyImprovementsTests(unittest.TestCase):
    """Covers the post-Confluent-review improvements: trademark attribution,
    nominative trailers, explainer-page heuristic, domain_clean PASS,
    tiered verdict, and the looser logo_misuse rule."""

    def test_trademark_attribution_counts_as_disclaimer(self) -> None:
        html = (
            "<html><body>"
            "<h1>What is Apache Foo?</h1>"
            "<p>Apache Foo is great.</p>"
            "<footer>Apache Foo is a trademark of the Apache Software "
            "Foundation.</footer>"
            "</body></html>"
        )
        page = _page("https://example.com/what-is-apache-foo/", html)
        report = compliance.check_third_party_use(page, mark="Foo")
        statuses = _statuses(report)
        self.assertEqual(statuses["non_affiliation_disclaimer"], "pass")

    def test_apache_x_project_trailer_is_nominative(self) -> None:
        html = "<html><body><p>The Apache Foo project handles streams.</p></body></html>"
        page = _page("https://example.com/", html)
        report = compliance.check_third_party_use(page, mark="Foo")
        statuses = _statuses(report)
        self.assertEqual(statuses["branding_form"], "pass")

    def test_explainer_url_downgrades_branding_warn_to_info(self) -> None:
        html = "<html><body><p>Welcome to Apache Foo land.</p></body></html>"
        page = _page("https://example.com/what-is-apache-foo/", html)
        report = compliance.check_third_party_use(page, mark="Foo")
        statuses = _statuses(report)
        # Same body that previously WARNed (test above) now INFOs because the
        # URL slug indicates an explainer page.
        self.assertEqual(statuses["branding_form"], "info")

    def test_explainer_url_slash_form_is_recognised(self) -> None:
        # AWS-style /what-is/<topic> concept hub URL.
        html = "<html><body><p>Welcome to Apache Foo land.</p></body></html>"
        page = _page("https://aws.example.com/what-is/apache-foo", html)
        report = compliance.check_third_party_use(page, mark="Foo")
        statuses = _statuses(report)
        self.assertEqual(statuses["branding_form"], "info")

    def test_explainer_title_downgrades_branding_warn_to_info(self) -> None:
        html = (
            "<html><head><title>What Is Apache Foo</title></head>"
            "<body><p>Welcome to Apache Foo land.</p></body></html>"
        )
        page = _page("https://example.com/random-page", html)
        report = compliance.check_third_party_use(page, mark="Foo")
        statuses = _statuses(report)
        self.assertEqual(statuses["branding_form"], "info")

    def test_domain_clean_pass_emitted(self) -> None:
        html = "<html><body><p>Compatible with Apache Foo.</p></body></html>"
        page = _page("https://example.com/", html)
        report = compliance.check_third_party_use(page, mark="Foo")
        statuses = _statuses(report)
        self.assertEqual(statuses["domain_clean"], "pass")

    def test_apache_logo_image_with_powered_by_in_page_text_does_not_warn(
        self,
    ) -> None:
        # apache-foo-logo.png with no "powered" in filename or alt, BUT the
        # page text says "Powered By Apache Foo" — should not WARN.
        html = (
            "<html><body>"
            "<p>YoyoStream is Powered By Apache Foo.</p>"
            '<img src="https://cdn.example.com/apache-foo-logo.svg" '
            'alt="Apache Foo logo">'
            "</body></html>"
        )
        page = _page("https://example.com/", html)
        report = compliance.check_third_party_use(page, mark="Foo")
        statuses = _statuses(report)
        # With the old rule this would WARN. Now: PASS (no apache-logo hits)
        # because the page has a Powered-By context.
        self.assertEqual(statuses["logo_misuse"], "pass")

    def test_tiered_verdict_only_advisory_problems_is_pass(self) -> None:
        # A page that's clean except for missing apache.org credit link.
        # credit_link is ADVISORY — should not pull the verdict down to WARN.
        html = (
            "<html><body>"
            "<p>Compatible with Apache Foo.</p>"
            "<p>Apache Foo is a trademark of the Apache Software Foundation.</p>"
            "</body></html>"
        )
        page = _page("https://example.com/", html)
        report = compliance.check_third_party_use(page, mark="Foo")
        # credit_link warns (advisory); domain_clean passes; branding_form
        # passes (nominative); non_affiliation_disclaimer passes (attribution).
        statuses = _statuses(report)
        self.assertEqual(statuses["credit_link"], "warn")
        self.assertEqual(report.verdict(), "PASS")

    def test_tiered_verdict_critical_fail_is_fail(self) -> None:
        # A page on an apache-spoofing domain still goes straight to FAIL.
        html = "<html><body><p>Hello.</p></body></html>"
        page = _page("https://apache-foo.example.com/", html)
        report = compliance.check_third_party_use(page, mark="Foo")
        self.assertEqual(report.verdict(), "FAIL")

    def test_severity_included_in_finding_dict(self) -> None:
        html = "<html><body><p>Compatible with Apache Foo.</p></body></html>"
        page = _page("https://example.com/", html)
        report = compliance.check_third_party_use(page, mark="Foo")
        for f in report.to_dict()["findings"]:
            self.assertIn("severity", f)
            self.assertIn(f["severity"], {"critical", "important", "advisory"})


if __name__ == "__main__":
    unittest.main()
