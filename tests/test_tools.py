from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from apache_trademark_mcp import projects, tools
from tests.fixtures import FAKE_PROJECTS


class CacheFixture:
    """Context manager that points the tools module at a tempdir cache prepopulated with FAKE_PROJECTS."""

    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()

    def __enter__(self) -> Path:
        path = Path(self._tmp.name)
        cache = projects.cache_file(path)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(FAKE_PROJECTS))
        tools.configure_defaults(cache_dir=str(path))
        return path

    def __exit__(self, *exc: object) -> None:
        tools._CONFIGURED_CACHE_DIR = None
        self._tmp.cleanup()


class ValidateNameTests(unittest.TestCase):
    def test_pass_for_neutral_name(self) -> None:
        with CacheFixture():
            out = tools.validate_name("Stratusnova")
        self.assertEqual(out["verdict"], "PASS")
        self.assertEqual(out["apache_form"], "Apache Stratusnova")
        self.assertEqual(out["blocking_issues"], [])

    def test_fail_for_native_american_name(self) -> None:
        with CacheFixture():
            out = tools.validate_name("Cherokee")
        self.assertEqual(out["verdict"], "FAIL")
        self.assertTrue(any("Native American" in i for i in out["blocking_issues"]))

    def test_fail_for_apache_prefix(self) -> None:
        with CacheFixture():
            out = tools.validate_name("Apache Foo")
        self.assertEqual(out["verdict"], "FAIL")
        self.assertTrue(any("house-mark" in i for i in out["blocking_issues"]))

    def test_fail_for_exact_existing_project(self) -> None:
        with CacheFixture():
            out = tools.validate_name("Kafka")
        self.assertEqual(out["verdict"], "FAIL")
        self.assertTrue(
            any("Exact name conflict" in i for i in out["blocking_issues"]),
            f"expected exact-conflict blocking issue, got: {out['blocking_issues']}",
        )

    def test_empty_name_raises_value_error(self) -> None:
        with CacheFixture():
            with self.assertRaises(ValueError):
                tools.validate_name("")


class SearchAsfProjectsTests(unittest.TestCase):
    def test_returns_hits_for_known_project(self) -> None:
        with CacheFixture():
            out = tools.search_asf_projects("kafka", min_similarity=0.0)
        names = [r["name"].lower() for r in out["results"]]
        self.assertIn("kafka", names)

    def test_threshold_is_clamped(self) -> None:
        with CacheFixture():
            out = tools.search_asf_projects("kafka", min_similarity=5.0)
        # Clamped to 1.0 — only exact matches survive.
        scores = [r["similarity"] for r in out["results"]]
        for s in scores:
            self.assertGreaterEqual(s, 1.0)


class BrandingAndPolicyTests(unittest.TestCase):
    def test_get_branding_checklist_dispatches(self) -> None:
        out = tools.get_branding_checklist("podling")
        self.assertEqual(out["stage"], "podling")

    def test_get_policy_guidance_dispatches(self) -> None:
        out = tools.get_policy_guidance("nominative_use")
        self.assertIn("title", out)

    def test_get_naming_policy_returns_doc(self) -> None:
        out = tools.get_naming_policy()
        self.assertIn("required_rules", out)


class CheckProjectWebsiteTests(unittest.TestCase):
    def test_passes_when_fetch_returns_compliant_html(self) -> None:
        from tests.html_fixtures import COMPLIANT_PROJECT_HTML
        from apache_trademark_mcp import web

        def fake_fetch(url: str, timeout: float = 15.0) -> web.FetchedPage:
            title, headings, links, images, text = web.parse_html(COMPLIANT_PROJECT_HTML)
            return web.FetchedPage(
                url=url,
                final_url=url,
                status=200,
                html=COMPLIANT_PROJECT_HTML,
                text=text,
                title=title,
                headings=headings,
                links=links,
                images=images,
            )

        with mock.patch("apache_trademark_mcp.tools.web.fetch_page", side_effect=fake_fetch):
            out = tools.check_project_website("https://foo.apache.org/", "Foo", "tlp")
        self.assertEqual(out["verdict"], "PASS")
        self.assertIn("policy_references", out)

    def test_rejects_invalid_stage(self) -> None:
        with self.assertRaises(ValueError):
            tools.check_project_website("https://foo.apache.org/", "Foo", "bogus")


class CheckThirdPartyUseTests(unittest.TestCase):
    def test_flags_bare_mark_as_sld(self) -> None:
        from tests.html_fixtures import NONCOMPLIANT_THIRD_PARTY_HTML
        from apache_trademark_mcp import web

        def fake_fetch(url: str, timeout: float = 15.0) -> web.FetchedPage:
            title, headings, links, images, text = web.parse_html(NONCOMPLIANT_THIRD_PARTY_HTML)
            return web.FetchedPage(
                url=url,
                final_url=url,
                status=200,
                html=NONCOMPLIANT_THIRD_PARTY_HTML,
                text=text,
                title=title,
                headings=headings,
                links=links,
                images=images,
            )

        with mock.patch("apache_trademark_mcp.tools.web.fetch_page", side_effect=fake_fetch):
            out = tools.check_third_party_use("https://foo.com/", "Foo")
        rules = {f["rule"]: f["status"] for f in out["findings"]}
        self.assertEqual(rules["bare_mark_as_sld"], "fail")


class PerformNameSearchTests(unittest.TestCase):
    def test_patches_external_calls(self) -> None:
        fake_results = {
            "github": {"hits": [], "total_count": 0, "error": None},
            "pypi": {"found": False, "error": None},
            "npm": {"found": False, "error": None},
        }
        with CacheFixture():
            with mock.patch(
                "apache_trademark_mcp.tools.search.run_external_searches",
                return_value=fake_results,
            ):
                out = tools.perform_name_search("Stratus", "a streaming engine")
        self.assertEqual(out["proposed_name"], "Stratus")
        self.assertIn("jira_ticket_template", out)
        self.assertIn("USPTO Trademark Search", out["jira_ticket_template"])


class ToolsRegistryTests(unittest.TestCase):
    def test_registry_has_expected_tools(self) -> None:
        self.assertEqual(
            set(tools.TOOLS),
            {
                "validate_name",
                "search_asf_projects",
                "get_naming_policy",
                "get_branding_checklist",
                "get_policy_guidance",
                "perform_name_search",
                "refresh_project_cache",
                "check_project_website",
                "check_third_party_use",
            },
        )

    def test_each_tool_has_handler_and_schema(self) -> None:
        for name, meta in tools.TOOLS.items():
            self.assertIn("description", meta, name)
            self.assertIn("handler", meta, name)
            self.assertIn("inputSchema", meta, name)
            self.assertFalse(meta["inputSchema"]["additionalProperties"], name)


if __name__ == "__main__":
    unittest.main()
