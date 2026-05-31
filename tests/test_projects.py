from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from apache_trademark_mcp import projects
from tests.fixtures import FAKE_PROJECTS


class ProjectNamesTests(unittest.TestCase):
    def test_includes_ids(self) -> None:
        names = projects.project_names(FAKE_PROJECTS)
        self.assertIn("kafka", names)
        self.assertIn("spark", names)

    def test_includes_human_name_when_it_differs_from_id(self) -> None:
        # Entry whose human-stripped name is different from the id should
        # contribute both forms.
        names = projects.project_names([{"id": "foo-podling", "name": "Apache Foo Pipelines"}])
        self.assertIn("foo-podling", names)
        self.assertIn("Foo Pipelines", names)

    def test_deduplicates_when_human_name_matches_id(self) -> None:
        # "Apache Kafka" -> "Kafka" lowercases to "kafka" which matches the id,
        # so the human form is intentionally dropped.
        names = projects.project_names([{"id": "kafka", "name": "Apache Kafka"}])
        self.assertEqual(names, ["kafka"])

    def test_ignores_non_dict_entries(self) -> None:
        # Deliberately pass garbage to exercise the runtime guard in
        # project_names; mypy correctly flags the bad types — silence it.
        names = projects.project_names(
            [{"id": "kafka"}, "garbage", None]  # type: ignore[list-item]
        )
        self.assertEqual(names, ["kafka"])


class MergeProjectsTests(unittest.TestCase):
    def test_drops_graduated_podling_in_favor_of_committee(self) -> None:
        committees = [
            {
                "id": "hugegraph",
                "name": "Apache HugeGraph",
                "shortdesc": "A large-scale graph database",
            },
        ]
        podlings = [
            {"id": "hugegraph", "name": "HugeGraph (Incubating)", "status": "graduated"},
            {"id": "polaris", "name": "Polaris (Incubating)", "status": "current"},
        ]
        merged = projects._merge_projects(committees, podlings)
        ids = [e["id"] for e in merged]
        names = [e["name"] for e in merged]
        self.assertEqual(ids.count("hugegraph"), 1)
        # Committee entry wins.
        self.assertIn("Apache HugeGraph", names)
        self.assertNotIn("HugeGraph (Incubating)", names)
        # Current podlings without a committee twin pass through.
        self.assertIn("polaris", ids)

    def test_skips_entries_without_id(self) -> None:
        merged = projects._merge_projects([{"name": "no id here"}], [{"id": "foo", "name": "Foo"}])
        self.assertEqual([e["id"] for e in merged], ["foo"])


class ProjectNamesIncubatingTests(unittest.TestCase):
    def test_strips_incubating_suffix(self) -> None:
        # A live podling: id=polaris, name="Polaris (Incubating)".
        # The cleaned name lowercases to "polaris" — matches id — so we should
        # NOT emit "Polaris (Incubating)" as a second name.
        names = projects.project_names([{"id": "polaris", "name": "Polaris (Incubating)"}])
        self.assertEqual(names, ["polaris"])


class FindNameConflictsTests(unittest.TestCase):
    def test_exact_match_is_conflict(self) -> None:
        conflicts, nearby = projects.find_name_conflicts("Kafka", FAKE_PROJECTS)
        self.assertTrue(any(c["match_type"] == "exact" for c in conflicts))
        self.assertEqual(nearby, [])

    def test_near_exact_match_is_conflict(self) -> None:
        # "Kafkaa" (typo) ~ 0.91 similarity to "kafka"
        conflicts, _nearby = projects.find_name_conflicts("Kafkaa", FAKE_PROJECTS)
        self.assertTrue(any(c["match_type"] in {"exact", "near_exact"} for c in conflicts))

    def test_nearby_match_is_not_a_conflict(self) -> None:
        # "Karka" should be similar enough to land in the nearby bucket but
        # not the conflict bucket against "kafka".
        conflicts, nearby = projects.find_name_conflicts("Karka", FAKE_PROJECTS)
        self.assertEqual(conflicts, [])
        self.assertTrue(any(n["name"].lower() == "kafka" for n in nearby))

    def test_completely_distinct_name_returns_nothing(self) -> None:
        conflicts, nearby = projects.find_name_conflicts("Zephyrium", FAKE_PROJECTS)
        self.assertEqual(conflicts, [])
        self.assertEqual(nearby, [])


class FindSimilarTests(unittest.TestCase):
    def test_threshold_filters_results(self) -> None:
        loose = projects.find_similar("kafka", FAKE_PROJECTS, threshold=0.0)
        strict = projects.find_similar("kafka", FAKE_PROJECTS, threshold=0.95)
        self.assertGreater(len(loose), len(strict))

    def test_results_are_sorted_descending(self) -> None:
        results = projects.find_similar("kafka", FAKE_PROJECTS, threshold=0.0)
        scores = [r["similarity"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))


class CacheTests(unittest.TestCase):
    def test_load_cache_fresh_returns_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = projects.cache_file(Path(tmp))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(FAKE_PROJECTS))
            data = projects._load_cache(path, ttl_seconds=3600)
            self.assertEqual(data, FAKE_PROJECTS)

    def test_load_cache_expired_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = projects.cache_file(Path(tmp))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(FAKE_PROJECTS))
            # Force the mtime well into the past.
            old = time.time() - 99999
            import os

            os.utime(path, (old, old))
            self.assertIsNone(projects._load_cache(path, ttl_seconds=3600))

    def test_load_cache_missing_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = projects.cache_file(Path(tmp))
            self.assertIsNone(projects._load_cache(path, ttl_seconds=3600))


class FetchProjectsTests(unittest.TestCase):
    def test_uses_cache_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = projects.cache_file(Path(tmp))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(FAKE_PROJECTS))
            data = projects.fetch_projects(cache_dir=Path(tmp))
            self.assertEqual(data, FAKE_PROJECTS)


if __name__ == "__main__":
    unittest.main()
