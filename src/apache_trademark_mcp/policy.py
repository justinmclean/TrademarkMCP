"""Static ASF trademark policy data and policy-check functions.

This module is intentionally pure Python (no I/O) so it is trivially testable.
The data here is sourced from:

  https://www.apache.org/foundation/marks/
  https://www.apache.org/foundation/marks/pmcs
  https://incubator.apache.org/guides/names.html
  https://incubator.apache.org/guides/branding.html
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Policy data
# ---------------------------------------------------------------------------

# Native American tribal / cultural names.
# ASF policy: "names with Native American connections will not be approved."
NATIVE_AMERICAN_TERMS: set[str] = {
    "abenaki",
    "abnaki",
    "acoma",
    "algonquin",
    "algonkin",
    "apache",
    "arapaho",
    "assiniboine",
    "athabascan",
    "bannock",
    "blackfoot",
    "blackfeet",
    "blood",
    "brule",
    "caddo",
    "catawba",
    "cayuga",
    "cayuse",
    "cherokee",
    "cheyenne",
    "chickasaw",
    "chinook",
    "chippewa",
    "chiricahua",
    "choctaw",
    "chumash",
    "cochiti",
    "comanche",
    "cree",
    "creek",
    "crow",
    "dakota",
    "delaware",
    "erie",
    "flathead",
    "havasupai",
    "hidatsa",
    "ho-chunk",
    "hopi",
    "huron",
    "illinois",
    "iowa",
    "iroquois",
    "isleta",
    "jemez",
    "jicarilla",
    "kansa",
    "kaw",
    "kickapoo",
    "kiowa",
    "kootenai",
    "laguna",
    "lakota",
    "lenape",
    "lumbee",
    "mahican",
    "mandan",
    "maricopa",
    "maliseet",
    "mashantucket",
    "mdewakanton",
    "menominee",
    "mescalero",
    "miami",
    "micmac",
    "mikmaq",
    "miniconjou",
    "miwok",
    "mohawk",
    "mohegan",
    "mohican",
    "muscogee",
    "nakoda",
    "nakota",
    "nanticoke",
    "narragansett",
    "navaho",
    "navajo",
    "nez-perce",
    "niantic",
    "nipmuc",
    "oglala",
    "ojibwe",
    "ojibwa",
    "omaha",
    "oneida",
    "onondaga",
    "osage",
    "ottawa",
    "paiute",
    "pamunkey",
    "passamaquoddy",
    "pawnee",
    "peigan",
    "penobscot",
    "pequot",
    "piegan",
    "pima",
    "piscataway",
    "ponca",
    "potawatomi",
    "powhatan",
    "pueblo",
    "quapaw",
    "rappahannock",
    "sahnish",
    "salish",
    "san-carlos",
    "santa-clara",
    "sauk",
    "seminole",
    "seneca",
    "shawnee",
    "shinnecock",
    "shoshone",
    "shoshoni",
    "sioux",
    "sisseton",
    "spokane",
    "stoney",
    "susquehannock",
    "taos",
    "tesuque",
    "tohono",
    "tonkawa",
    "tonto",
    "tsalagi",
    "tuscarora",
    "tutelo",
    "ute",
    "wahpeton",
    "wampanoag",
    "washoe",
    "wea",
    "wichita",
    "winnebago",
    "wyandot",
    "yakama",
    "yanktonai",
    "yaqui",
    "yavapai",
    "yokuts",
    "yuma",
    "zuni",
    "lipan",
    "white-mountain",
    "fort-sill",
    "yavapai-apache",
}

# ASF-reserved marks that cannot appear in new project names.
RESERVED_ASF_MARKS: set[str] = {
    "apachecon",
    "asf",
    "community over code",
    "the apache way",
    "apache software foundation",
}

# Terms that are generic / purely descriptive — weak trademarks.
GENERIC_TERMS: set[str] = {
    "data",
    "cloud",
    "stream",
    "flow",
    "pipe",
    "queue",
    "store",
    "cache",
    "index",
    "search",
    "query",
    "compute",
    "service",
    "platform",
    "framework",
    "engine",
    "server",
    "client",
    "tool",
    "kit",
    "lib",
    "core",
    "base",
    "hub",
    "net",
    "web",
    "api",
    "sdk",
    "db",
    "sql",
    "ml",
    "ai",
    "open",
    "free",
}

VALID_BRANDING_STAGES = ("podling", "graduation", "tlp")

VALID_GUIDANCE_TOPICS = (
    "domain_names",
    "third_party_use",
    "powered_by",
    "nominative_use",
    "confusion_test",
    "podling_naming",
    "event_naming",
    "logo_use",
    "books_articles",
)


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def normalize(name: str) -> str:
    """Lowercase, strip 'Apache ' prefix, remove non-alphanumeric."""
    name = re.sub(r"^apache\s+", "", name, flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()


# ---------------------------------------------------------------------------
# Rule checks
# ---------------------------------------------------------------------------


def check_reserved(name: str) -> list[str]:
    """Return issues for reserved marks or the 'Apache' prefix."""
    issues: list[str] = []
    lower = name.lower().strip()
    if re.match(r"^apache\b", lower):
        issues.append(
            "Name begins with 'Apache'. The 'Apache' house-mark prefix is added "
            "by the ASF — the proposed name should be just 'Foo', not 'Apache Foo'."
        )
    for mark in RESERVED_ASF_MARKS:
        if mark in lower:
            issues.append(f"Contains reserved ASF mark: '{mark}'.")
    return issues


def check_native_american(name: str) -> list[str]:
    """Return the Native American terms found in the proposed name."""
    flags: list[str] = []
    norm = normalize(name)
    candidates = {norm} | set(re.split(r"[\s\-_]+", norm))
    for word in candidates:
        if word and word in NATIVE_AMERICAN_TERMS:
            flags.append(word)
    return sorted(set(flags))


def check_format(name: str) -> tuple[list[str], list[str]]:
    """Return (blocking_issues, warnings) from formatting rules."""
    issues: list[str] = []
    warnings: list[str] = []
    stripped = name.strip()

    if len(stripped) < 2:
        issues.append("Name is too short (minimum 2 characters).")
    if not re.match(r"^[a-zA-Z]", stripped):
        issues.append("Name must start with a letter.")
    if len(stripped) > 35:
        warnings.append(
            f"Name is quite long ({len(stripped)} chars). "
            "Shorter names are easier to remember and search."
        )
    if re.search(r"\d", stripped):
        warnings.append("Name contains digits, which can complicate trademark registration.")
    if normalize(stripped) in GENERIC_TERMS:
        warnings.append(
            f"'{stripped}' is a generic/descriptive term. Generic names are weak "
            "trademarks and may be confusingly similar to many existing products."
        )
    return issues, warnings


# ---------------------------------------------------------------------------
# Policy documents
# ---------------------------------------------------------------------------


def naming_policy() -> dict:
    """Return the structured ASF naming-policy summary."""
    return {
        "title": "ASF Project and Podling Naming Requirements",
        "sources": [
            "https://www.apache.org/foundation/marks/pmcs#naming",
            "https://incubator.apache.org/guides/names.html",
            "https://www.apache.org/foundation/marks/",
        ],
        "required_rules": [
            {
                "id": "no_confusing_similarity",
                "rule": "No confusingly similar names to existing ASF or third-party products",
                "detail": (
                    "Use internet search to verify there is no similar product in the "
                    "same technical space. Apply the 'likelihood of confusion' test: "
                    "would a relevant consumer mistake the source? Be good citizens — "
                    "do not try a twist close to the name of a similar product."
                ),
            },
            {
                "id": "no_native_american",
                "rule": "No Native American cultural or tribal names",
                "detail": (
                    "ASF policy: 'Be culturally sensitive and avoid names that might "
                    "offend. In particular, names with Native American connections "
                    "will not be approved.'"
                ),
            },
            {
                "id": "no_apache_prefix",
                "rule": "Do not include 'Apache' in the proposed name",
                "detail": (
                    "The 'Apache' house-mark prefix is added by the ASF. Propose just "
                    "'Foo', not 'Apache Foo'. The full form 'Apache Foo' is used in "
                    "all formal branding after acceptance."
                ),
            },
            {
                "id": "no_reserved_marks",
                "rule": "No ASF reserved marks",
                "detail": (
                    "Names must not include 'ApacheCon', 'ASF', "
                    "'Community Over Code', or 'The Apache Way'."
                ),
            },
            {
                "id": "no_bare_third_party_trademarks",
                "rule": "No bare third-party trademarks embedded in the name",
                "detail": (
                    "Use a qualifier if referencing another trademark. "
                    "'Apache Xerces for Perl' is acceptable; "
                    "'Apache Xerces Perl' is not — 'Perl' is a trademark of "
                    "the Perl Foundation."
                ),
            },
            {
                "id": "podlingnamesearch_jira",
                "rule": "Podlings must file a PODLINGNAMESEARCH JIRA ticket",
                "detail": (
                    "Before the proposal vote, file a ticket at "
                    "https://issues.apache.org/jira/projects/PODLINGNAMESEARCH "
                    "and obtain VP Brand Management approval."
                ),
                "url": "https://issues.apache.org/jira/projects/PODLINGNAMESEARCH",
            },
        ],
        "strong_recommendations": [
            "Choose a name that is easy to remember, not too long, not difficult to spell.",
            "Prefer unique coined words over common dictionary terms.",
            "Verify the ProjectName.apache.org subdomain is not already taken.",
            "Consider functional names for sub-products (e.g. 'Apache Foo Pipelines').",
            "Pick a name early — renaming later is expensive (mailing lists, packages, logos).",
            "See this as a marketing opportunity, not a bother.",
        ],
        "process_for_podlings": [
            "1. Propose a name during the incubation proposal discussion.",
            "2. Run validate_name to check against ASF projects.",
            "3. Search the internet for similar products in the same technical space.",
            "4. Check USPTO (https://tmsearch.uspto.gov) trademark database.",
            "5. File a JIRA ticket in PODLINGNAMESEARCH with search results.",
            "6. Await VP Brand Management approval.",
            "7. After approval, refer to the podling only as 'Apache Foo (Incubating)'.",
            "8. Do not issue press releases or seek publicity before approval.",
        ],
    }


def _base_branding_checklist() -> list[dict]:
    return [
        {
            "item": "Homepage hosted at ProjectName.apache.org",
            "required": True,
            "detail": "All official project web content must be on an apache.org domain.",
            "url": "https://www.apache.org/foundation/marks/pmcs#websites",
        },
        {
            "item": "Primary branding uses 'Apache ProjectName' form",
            "required": True,
            "detail": (
                "First and most prominent references on every page use 'Apache ProjectName'. "
                "Other references may use just 'ProjectName'."
            ),
        },
        {
            "item": "Homepage includes one-sentence software product description",
            "required": True,
            "detail": (
                "Must describe what the software does as a product — e.g. "
                "'Apache Foo software provides X functionality.' "
                "Calling it a 'project' or 'community' alone is insufficient for trademark purposes."
            ),
        },
        {
            "item": "TM or R symbol on first prominent occurrence of project name",
            "required": True,
            "detail": (
                "Include TM or R next to the first main occurrence of 'Apache ProjectName' "
                "in page headers and in running text on the homepage."
            ),
        },
        {
            "item": "Trademark attribution in page footer",
            "required": True,
            "detail": (
                "Footer must include: 'Apache Foo, Foo, Apache, the Apache feather logo, "
                "and the Apache Foo logo are trademarks or registered trademarks of "
                "The Apache Software Foundation.'"
            ),
        },
        {
            "item": "Navigation links to License, Sponsorship, Thanks, Security, Privacy",
            "required": True,
            "detail": (
                "Required links: apache.org/licenses/, apache.org/foundation/sponsorship.html, "
                "apache.org/foundation/thanks.html, security page, privacy.apache.org page."
            ),
            "url": "https://www.apache.org/foundation/marks/pmcs#navigation",
        },
        {
            "item": "Prominent link back to www.apache.org",
            "required": True,
            "detail": "All projects must feature a prominent link back to the main ASF homepage.",
        },
        {
            "item": "Third-party trademarks attributed in footer",
            "required": True,
            "detail": (
                "Any non-ASF trademarks referenced on the site must be attributed, "
                "either specifically or with a generic 'all other marks are trademarks "
                "of their respective owners' statement."
            ),
        },
        {
            "item": "DOAP file registered with projects.apache.org",
            "required": True,
            "detail": "All projects must provide a DOAP file or equivalent structured metadata.",
            "url": "https://www.apache.org/foundation/marks/pmcs#metadata",
        },
        {
            "item": "Logo includes TM symbol (if project has a logo)",
            "required": False,
            "detail": "Project logos should include a small TM symbol adjacent to the graphic.",
        },
    ]


def _podling_branding_extras() -> list[dict]:
    return [
        {
            "item": "Incubation disclaimer on website and all documentation",
            "required": True,
            "detail": (
                "Required text: 'Apache [Name] is an effort undergoing incubation at "
                "The Apache Software Foundation (ASF), sponsored by [TLP sponsor]. "
                "Incubation is required of all newly accepted projects until a further "
                "review indicates that the infrastructure, communications, and decision "
                "making process have stabilized in a manner consistent with other "
                "successful ASF projects. While incubation status is not necessarily a "
                "reflection of the completeness or stability of the code, it does indicate "
                "that the project has yet to be fully endorsed by the ASF.'"
            ),
            "url": "https://incubator.apache.org/guides/branding.html",
        },
        {
            "item": "README files in all repositories include incubation statement",
            "required": True,
            "detail": (
                "Each repository README must include the incubation statement and a link "
                "to the full disclaimer. May also reference podling as 'Apache Foo (Incubating)'."
            ),
        },
        {
            "item": "Refer to project as 'Apache Foo (Incubating)' in all external references",
            "required": True,
            "detail": (
                "All external references must use 'Apache Foo (Incubating)' or include a "
                "statement that the project is undergoing incubation at the ASF."
            ),
        },
        {
            "item": "DISCLAIMER file included in release artifacts",
            "required": True,
            "detail": (
                "Release artifacts must include a DISCLAIMER file alongside NOTICE and "
                "LICENSE files, containing the full incubation disclaimer text."
            ),
        },
        {
            "item": "PODLINGNAMESEARCH JIRA ticket filed and approved",
            "required": True,
            "detail": "VP Brand Management must have approved the name. Required before graduation.",
            "url": "https://issues.apache.org/jira/projects/PODLINGNAMESEARCH",
        },
        {
            "item": "Publicity activities coordinated with ASF PR Committee",
            "required": True,
            "detail": (
                "Podlings must coordinate with the Apache Public Relations Committee on "
                "all publicity activities. The ASF Press Team must review any releases "
                "by affiliated organizations."
            ),
        },
    ]


def _graduation_branding_extras() -> list[dict]:
    return [
        {
            "item": "All TLP checklist items complete",
            "required": True,
            "detail": "Every item from the base TLP branding checklist must be in place.",
        },
        {
            "item": "Non-apache.org domains transferred to ASF (if applicable)",
            "required": True,
            "detail": (
                "Any domain names previously used by the project must be transferred "
                "to the ASF as a donation. Retention for limited uses requires Brand "
                "Management approval."
            ),
        },
        {
            "item": "Primary development homepage migrated to ProjectName.apache.org",
            "required": True,
            "detail": (
                "The primary development homepage — contributor info, downloads, mailing "
                "lists — must be at ProjectName.apache.org before graduation."
            ),
        },
        {
            "item": "Incubation disclaimers and '(Incubating)' suffixes removed",
            "required": True,
            "detail": "After graduation, all incubation references must be removed from the site and docs.",
        },
        {
            "item": "VP Brand Management confirms name approval is on record",
            "required": True,
            "detail": "Confirm the PODLINGNAMESEARCH ticket is resolved and approval is documented.",
        },
    ]


def branding_checklist(stage: str) -> dict:
    """Return the branding checklist for a given lifecycle stage."""
    if stage not in VALID_BRANDING_STAGES:
        raise ValueError(
            f"Unknown stage '{stage}'. Valid stages: " + ", ".join(VALID_BRANDING_STAGES)
        )

    if stage == "podling":
        checklist = _base_branding_checklist() + _podling_branding_extras()
        title = "Podling Branding Compliance Checklist (During Incubation)"
        notes = [
            "All 'required: true' items must be completed before graduation.",
            "Contact trademarks@apache.org with questions.",
            "Full requirements: https://www.apache.org/foundation/marks/pmcs",
            "Incubator branding guide: https://incubator.apache.org/guides/branding.html",
        ]
    elif stage == "graduation":
        checklist = _base_branding_checklist() + _graduation_branding_extras()
        title = "Pre-Graduation Branding Checklist"
        notes = [
            "All items must be in place at the time of the graduation vote.",
            "Confirm with trademarks@apache.org before the resolution goes to the IPMC.",
        ]
    else:  # tlp
        checklist = _base_branding_checklist()
        title = "Top-Level Project (TLP) Ongoing Branding Checklist"
        notes = [
            "Non-compliant projects must work with trademarks@ to achieve compliance.",
            "Branding questions: trademarks@apache.org",
            "Full policy: https://www.apache.org/foundation/marks/pmcs",
        ]

    return {
        "title": title,
        "stage": stage,
        "total_items": len(checklist),
        "required_items": sum(1 for c in checklist if c["required"]),
        "checklist": checklist,
        "notes": notes,
        "policy_url": "https://www.apache.org/foundation/marks/pmcs",
    }


# ---------------------------------------------------------------------------
# Focused guidance
# ---------------------------------------------------------------------------

_GUIDANCE: dict[str, dict] = {
    "domain_names": {
        "title": "Domain Name Branding Policy",
        "url": "https://www.apache.org/foundation/marks/domains",
        "summary": (
            "Third parties generally may NOT use Apache marks in domain names "
            "if it would likely confuse consumers about the source of software. "
            "Using a bare Apache product name as a second-level domain "
            "(e.g. tomcat.com) is not allowed. Written permission from VP Brand "
            "Management is required for any approved use."
        ),
        "key_rules": [
            "No bare Apache product names as second-level domains.",
            "Must clearly display non-affiliation with the ASF.",
            "Must credit the Apache project community.",
            "Must link to Apache project mailing lists and resources.",
            "No use of 'Apache' or 'Community Over Code' in domain names.",
            "Only top-level project VPs (not podling PPMCs) may grant third-party domain permissions.",
        ],
    },
    "third_party_use": {
        "title": "Third-Party Use of Apache Marks in Software Products",
        "url": "https://www.apache.org/foundation/marks/",
        "summary": (
            "In general, third parties may NOT use ASF trademarks in software product "
            "branding. The 'Powered By Apache Foo' naming form is the primary approved "
            "exception. Company names must not be confusingly similar to ASF project names."
        ),
        "key_rules": [
            "No ASF marks in software product branding without written permission.",
            "'Powered By Apache Foo' or 'Apache Foo Inside' forms are permitted.",
            "Books and articles may reference Apache marks without permission.",
            "Merchandise requires a separate Non-Software Merchandise Branding Policy review.",
            "Company names confusingly similar to ASF project names are not allowed.",
        ],
    },
    "powered_by": {
        "title": "Powered By Apache — Naming Policy",
        "url": "https://www.apache.org/foundation/marks/faq/#poweredby",
        "summary": (
            "'Powered By Apache Foo' is the approved way for third parties to reference "
            "Apache software in their own product names or branding. Your own brand must "
            "be the primary identity; the Apache mark is secondary."
        ),
        "key_rules": [
            "Use 'Powered By Apache Foo' or 'Apache Foo Inside' form.",
            "Your brand is primary; Apache mark is secondary.",
            "Must not create confusion that your product IS the Apache product.",
            "Powered By logos are available from individual Apache projects.",
            "Do not modify the Apache product logo when using it.",
        ],
    },
    "nominative_use": {
        "title": "Nominative Fair Use of Apache Marks",
        "url": "https://www.apache.org/foundation/marks/#nominative",
        "summary": (
            "Anyone may use ASF trademarks to refer to the actual Apache product "
            "(nominative fair use). This does NOT allow branding your own products "
            "with Apache marks."
        ),
        "three_requirements": [
            "The product/service must not be readily identifiable without using the mark.",
            "Only use as much of the mark as necessary to identify the product.",
            "Nothing in the use may suggest ASF sponsorship or endorsement.",
        ],
        "allowed_examples": [
            "'Support services for Apache Kafka are available at my site.'",
            "'Apache Spark is faster than X for batch workloads.'",
            "'I recommend Apache Flink for streaming pipelines.'",
        ],
        "not_allowed_examples": [
            "Branding your own software product with an Apache mark.",
            "A company name confusingly similar to an Apache project.",
            "A domain name that implies ASF affiliation or endorsement.",
        ],
    },
    "confusion_test": {
        "title": "Likelihood-of-Confusion Test",
        "url": "https://www.apache.org/foundation/marks/#confusion",
        "summary": (
            "A name infringes when relevant consumers would likely be confused or "
            "mistaken about the source of a product or service. This is the primary "
            "test for whether a proposed name conflicts with an Apache mark."
        ),
        "key_factors": [
            "Similarity of the marks: sound, appearance, and meaning.",
            "Similarity of the goods or services.",
            "Channels of trade and marketing.",
            "Sophistication of typical consumers.",
            "Evidence of actual confusion in the marketplace.",
            "Intent of the party adopting the mark.",
        ],
        "practical_guidance": (
            "If an average developer searching for the Apache product might "
            "find your product instead — or vice versa — that is likely confusion."
        ),
    },
    "podling_naming": {
        "title": "Podling Name Search Process",
        "url": "https://incubator.apache.org/guides/names.html",
        "summary": (
            "Podlings must perform a thorough name search and obtain VP Brand "
            "Management approval before the name is used publicly. A JIRA ticket "
            "in PODLINGNAMESEARCH is required before the proposal is accepted."
        ),
        "process": [
            "1. Check proposed name against existing ASF projects (use validate_name).",
            "2. Search the internet for similar software products in the same technical space.",
            "3. Search USPTO (https://tmsearch.uspto.gov) trademark database.",
            "4. File a PODLINGNAMESEARCH JIRA ticket with your search results.",
            "5. Await VP Brand Management approval.",
            "6. After approval: always refer to the podling as 'Apache Foo (Incubating)'.",
        ],
        "jira_url": "https://issues.apache.org/jira/projects/PODLINGNAMESEARCH",
        "contact": "trademarks@apache.org",
    },
    "event_naming": {
        "title": "Third-Party Event Branding Policy",
        "url": "https://www.apache.org/foundation/marks/events",
        "summary": (
            "Any use of ASF trademarks in relation to conferences or events must be "
            "approved in writing by VP Brand Management. 'Community Over Code' is "
            "reserved exclusively for official ASF conferences."
        ),
        "key_rules": [
            "Written approval from VP Brand Management required for events using Apache marks.",
            "'Community Over Code' is exclusively reserved for ASF conferences.",
            "Request approvals well in advance — there are Community Over Code blackout dates.",
            "Individual Apache project conferences require VP of that project's approval.",
        ],
    },
    "logo_use": {
        "title": "Logo and Graphics Usage Policy",
        "url": "https://www.apache.org/foundation/marks/pmcs#logos",
        "summary": (
            "Apache project logos may be used as hyperlinks to ASF project websites "
            "without permission. All other uses require written approval from VP Brand "
            "Management, a Brand Management Committee member, or the relevant project VP."
        ),
        "key_rules": [
            "May use logos solely as hyperlinks to ASF project sites — no approval needed.",
            "All other logo uses need written approval.",
            "Third-party websites may not use Apache logos as their own brand elements.",
            "Do not modify the appearance of any Apache logo.",
            "Do not use the ASF feather graphic mark in your own logo.",
            "Derivative logos are permitted under the Apache License but must not be confusingly similar.",
            "Project logos must include a small TM symbol.",
        ],
    },
    "books_articles": {
        "title": "Using Apache Marks in Books and Articles",
        "url": "https://www.apache.org/foundation/marks/#books",
        "summary": (
            "You may write about Apache software and use Apache marks in titles "
            "without permission. ASF prefers you use the full 'Apache Foo' name "
            "and include a trademark attribution in your acknowledgments."
        ),
        "key_rules": [
            "No permission required to reference Apache marks in books or articles.",
            "May use marks in book titles: 'Foo for Dummies', 'Learning Apache Foo'.",
            "Prefer 'Apache Foo' over just 'Foo' in the title when it fits.",
            "Include trademark attribution in acknowledgments: 'Apache, Apache Foo, and Foo are trademarks of the Apache Software Foundation.'",
        ],
    },
}


def policy_guidance(topic: str) -> dict:
    """Return the guidance entry for the given topic, raising on unknown topic."""
    if topic not in _GUIDANCE:
        raise ValueError(f"Unknown topic '{topic}'. Available: " + ", ".join(sorted(_GUIDANCE)))
    return _GUIDANCE[topic]


def policy_citations() -> list[dict]:
    """Standard citation set returned alongside validation verdicts."""
    return [
        {
            "rule": "Podling Name Search — required process",
            "url": "https://www.apache.org/foundation/marks/naming.html#namesearch",
            "excerpt": (
                "Before entering incubation, a podling must perform a name search and "
                "ensure that the VP, Apache Brand Management approves its name. "
                "VP Brand Management approval is required; there is no lazy consensus."
            ),
        },
        {
            "rule": "Incubator Names Guide",
            "url": "https://incubator.apache.org/guides/names.html",
            "excerpt": (
                "File a PODLINGNAMESEARCH JIRA with search results (facts only). "
                "Searches must include USPTO (required)."
            ),
        },
        {
            "rule": "Native American names prohibited",
            "url": "https://www.apache.org/foundation/marks/pmcs#naming",
            "excerpt": (
                "Be culturally sensitive and avoid names that might offend. "
                "In particular, names with Native American connections will not be approved."
            ),
        },
        {
            "rule": "Confusing Similarity — applies to all trademarks",
            "url": "https://www.apache.org/foundation/marks/pmcs#naming",
            "excerpt": (
                "Use internet search tools to be sure there is no 'similar' product in the "
                "same technical space. 'Confusingly similar' applies to all existing trademarks, "
                "not only ASF project names. Even if a product name cannot be found via search, "
                "if you are aware that it, or one very like it, is in use for a similar product "
                "then we cannot use it."
            ),
        },
    ]
