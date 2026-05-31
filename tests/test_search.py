from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from apache_trademark_mcp import search


class AssessFindingsTests(unittest.TestCase):
    def test_directly_named_repo_becomes_evidence(self) -> None:
        github = {
            "hits": [
                {
                    "name": "owner/Stratus",
                    "description": "A real project called Stratus",
                    "stars": 1234,
                    "language": "Go",
                    "url": "https://github.com/owner/Stratus",
                }
            ],
            "total_count": 1,
            "error": None,
        }
        pypi = {"found": False}
        npm = {"found": False}
        out = search.assess_findings("Stratus", github, pypi, npm, "a streaming engine")
        self.assertTrue(
            any("directly named 'Stratus'" in e for e in out["evidence_of_existing_use"])
        )

    def test_no_directly_named_repo_falls_to_notes(self) -> None:
        github = {"hits": [], "total_count": 0, "error": None}
        pypi = {"found": False}
        npm = {"found": False}
        out = search.assess_findings("ZzzUnlikelyName", github, pypi, npm, "")
        self.assertFalse(out["evidence_of_existing_use"])
        self.assertTrue(any("GitHub: no repositories" in n for n in out["notes"]))
        self.assertTrue(any("No technical_description" in n for n in out["notes"]))

    def test_pypi_hit_becomes_evidence(self) -> None:
        github = {"hits": [], "total_count": 0, "error": None}
        pypi = {
            "found": True,
            "version": "1.2.3",
            "summary": "A package called Stratus",
            "url": "https://pypi.org/project/Stratus/",
        }
        npm = {"found": False}
        out = search.assess_findings("Stratus", github, pypi, npm, "any description")
        self.assertTrue(
            any("PyPI package named 'Stratus'" in e for e in out["evidence_of_existing_use"])
        )


class JiraTemplateTests(unittest.TestCase):
    def test_template_includes_proposed_name(self) -> None:
        body = search.jira_template(
            "Stratus",
            "a streaming engine",
            github={"hits": [], "total_count": 0, "error": None},
            pypi={"found": False, "error": None},
            npm={"found": False, "error": None},
        )
        self.assertIn("Apache Stratus", body)
        self.assertIn("a streaming engine", body)
        self.assertIn("USPTO Trademark Search (REQUIRED)", body)

    def test_template_includes_uspto_query_with_name(self) -> None:
        body = search.jira_template(
            "Stratus",
            "",
            github={"hits": [], "total_count": 0, "error": None},
            pypi={"found": False, "error": None},
            npm={"found": False, "error": None},
        )
        self.assertIn("(Stratus)[BI,TI]", body)
        self.assertIn("REQUIRED: add a brief description", body)


class TrademarkSearchUrlsTests(unittest.TestCase):
    def test_includes_uspto_google_sourceforge(self) -> None:
        urls = search.trademark_search_urls("Foo Bar")
        self.assertEqual(set(urls), {"USPTO", "Google", "SourceForge"})
        self.assertIn("Foo%20Bar", urls["Google"]["url"])
        self.assertIn("Foo%20Bar", urls["SourceForge"]["url"])

    def test_uspto_query_includes_name(self) -> None:
        urls = search.trademark_search_urls("Stratus")
        self.assertIn("Stratus", urls["USPTO"]["recommended_query"])


if __name__ == "__main__":
    unittest.main()
