from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from apache_trademark_mcp import policy


class NormalizeTests(unittest.TestCase):
    def test_lowercases_and_strips_apache_prefix(self) -> None:
        self.assertEqual(policy.normalize("Apache Kafka"), "kafka")

    def test_drops_non_alphanumerics(self) -> None:
        self.assertEqual(policy.normalize("Foo-Bar!"), "foobar")

    def test_collapses_to_lower_alpha_spaces(self) -> None:
        # ``normalize`` only strips the 'Apache' prefix when it is at the very
        # start of the string (no leading whitespace), matching the original
        # behaviour intended for IDs like 'Apache Foo'.
        self.assertEqual(policy.normalize("APACHE  Some Name 99"), "some name 99")


class CheckReservedTests(unittest.TestCase):
    def test_apache_prefix_is_blocking(self) -> None:
        issues = policy.check_reserved("Apache Foo")
        self.assertTrue(any("Apache" in i and "house-mark" in i for i in issues))

    def test_reserved_apachecon_is_blocking(self) -> None:
        issues = policy.check_reserved("apachecon-stream")
        self.assertTrue(any("apachecon" in i for i in issues))

    def test_neutral_name_passes(self) -> None:
        self.assertEqual(policy.check_reserved("Stratus"), [])


class CheckNativeAmericanTests(unittest.TestCase):
    def test_flags_exact_tribal_name(self) -> None:
        self.assertEqual(policy.check_native_american("Cherokee"), ["cherokee"])

    def test_flags_token_within_compound(self) -> None:
        self.assertIn("cherokee", policy.check_native_american("Cherokee Streams"))

    def test_neutral_name_returns_empty(self) -> None:
        self.assertEqual(policy.check_native_american("Stratus"), [])


class CheckFormatTests(unittest.TestCase):
    def test_short_name_blocks(self) -> None:
        blocking, _warnings = policy.check_format("A")
        self.assertTrue(any("too short" in i for i in blocking))

    def test_must_start_with_letter(self) -> None:
        blocking, _warnings = policy.check_format("9Lives")
        self.assertTrue(any("must start with a letter" in i for i in blocking))

    def test_long_name_warns(self) -> None:
        _blocking, warnings = policy.check_format("A" * 40)
        self.assertTrue(any("quite long" in w for w in warnings))

    def test_generic_term_warns(self) -> None:
        _blocking, warnings = policy.check_format("Cloud")
        self.assertTrue(any("generic" in w.lower() for w in warnings))

    def test_digits_warn(self) -> None:
        _blocking, warnings = policy.check_format("Foo2")
        self.assertTrue(any("digits" in w for w in warnings))


class NamingPolicyTests(unittest.TestCase):
    def test_contains_required_rules(self) -> None:
        doc = policy.naming_policy()
        rule_ids = [r["id"] for r in doc["required_rules"]]
        self.assertIn("no_native_american", rule_ids)
        self.assertIn("no_apache_prefix", rule_ids)
        self.assertIn("podlingnamesearch_jira", rule_ids)


class BrandingChecklistTests(unittest.TestCase):
    def test_podling_includes_incubation_disclaimer(self) -> None:
        doc = policy.branding_checklist("podling")
        items = [c["item"] for c in doc["checklist"]]
        self.assertTrue(any("Incubation disclaimer" in i for i in items))

    def test_graduation_includes_domain_transfer(self) -> None:
        doc = policy.branding_checklist("graduation")
        items = [c["item"] for c in doc["checklist"]]
        self.assertTrue(any("Non-apache.org domains transferred" in i for i in items))

    def test_tlp_is_base_only(self) -> None:
        tlp = policy.branding_checklist("tlp")
        # TLP should not have the incubation-specific items
        items = [c["item"] for c in tlp["checklist"]]
        self.assertFalse(any("Incubation disclaimer" in i for i in items))

    def test_unknown_stage_raises(self) -> None:
        with self.assertRaises(ValueError):
            policy.branding_checklist("unknown")


class PolicyGuidanceTests(unittest.TestCase):
    def test_known_topic_returns_guidance(self) -> None:
        guidance = policy.policy_guidance("nominative_use")
        self.assertIn("title", guidance)
        self.assertIn("three_requirements", guidance)

    def test_unknown_topic_raises(self) -> None:
        with self.assertRaises(ValueError):
            policy.policy_guidance("not_a_topic")


if __name__ == "__main__":
    unittest.main()
