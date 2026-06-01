# Apache Trademark MCP

This repo contains a small dependency-free MCP server for the three main ASF trademark jobs:

1. **Naming new projects** — validate proposed Apache project / podling names against trademark policy.
2. **Auditing project websites** — check that an ASF project page follows the Project Branding Requirements.
3. **Auditing third-party use** — check that an external site using Apache marks follows ASF Trademark Policy.

For naming, it automates the parts of the [PODLINGNAMESEARCH](https://incubator.apache.org/guides/names.html) process that can be automated and produces a ready-to-paste JIRA ticket body for the parts that cannot.

It reports facts only — the final "confusingly similar" judgement is made by `trademarks@apache.org` and the VP, Brand Management.

The server exposes MCP tools for:

- validating a proposed name against reserved ASF marks, Native American name restrictions, format rules, and the live ASF committees + podlings list
- fuzzy-searching the ASF project list
- returning the structured ASF naming policy
- returning the branding compliance checklist for podling, graduation, or TLP stages
- returning focused guidance on specific trademark topics (domain names, nominative use, powered-by, etc.)
- running the GitHub / PyPI / npm searches required by the PODLINGNAMESEARCH process and producing a pre-filled JIRA ticket body
- forcing a fresh fetch of the ASF project list
- **auditing an Apache project's homepage** for compliance with the Project Branding Requirements (apache.org hosting, Apache-form heading, TM/(R) on first use, footer attribution, required navigation links, and incubation disclaimers for podlings)
- **auditing a third-party page** for ASF trademark policy compliance (domain misuse, branding form, non-affiliation disclaimer, logo misuse, and credit link)

## Pairing with the ASF Policy MCP

This server is self-contained — it fetches the live policy pages from `apache.org` and bakes the rule checks into structured findings. For the **full canonical policy text** (the actual paragraphs from `apache.org/foundation/marks/`), pair it with the [asf-policy MCP](https://github.com/justinmclean/PolicyMCP). The compliance tools include `policy_references.tip` pointing to the relevant Policy MCP keys (`branding`, `podling_branding`, `trademark_policy`, `domain_name_branding`).

## Install

    python3 -m venv .venv
    source .venv/bin/activate
    python3 -m pip install .

For local development:

    make install-dev

## Run

    trademark-mcp --cache-dir /path/to/cache

The server uses `stdio`, so it is intended to be launched by an MCP client. The `--cache-dir` flag is optional — it defaults to `~/.cache/apache-trademark-mcp`.

For local development without installing first, you can still launch the stdio server directly:

    python3 server.py

The package also keeps `apache-trademark-mcp` as a backwards-compatible command alias.

## Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` and add:

    {
      "mcpServers": {
        "apache-trademark": {
          "command": "trademark-mcp"
        }
      }
    }

Then restart Claude Desktop. If you installed into a virtual environment that is not on your `PATH`, use the absolute path to that environment's `trademark-mcp` command.

## MCP tools

`validate_name` Validates a proposed name against the reserved ASF marks, Native American restrictions, format rules, and the live ASF committees + podlings list, and returns a structured `PASS` / `WARN` / `FAIL` verdict along with the full PODLINGNAMESEARCH process the proposer still needs to complete.

`search_asf_projects` Fuzzy-searches the ASF project list for names similar to a query string, with a tunable similarity threshold.

`get_naming_policy` Returns the structured ASF naming-policy summary, including required rules, strong recommendations, and the podling name-search process.

`get_branding_checklist` Returns the branding compliance checklist for a given lifecycle stage (`podling`, `graduation`, or `tlp`).

`get_policy_guidance` Returns focused ASF trademark policy guidance for a specific topic (`domain_names`, `third_party_use`, `powered_by`, `nominative_use`, `confusion_test`, `podling_naming`, `event_naming`, `logo_use`, `books_articles`).

`perform_name_search` Runs the GitHub / PyPI / npm name lookups required by the PODLINGNAMESEARCH process, in parallel, and returns a pre-filled JIRA ticket body plus the USPTO search URL ready to open in a browser.

`refresh_project_cache` Forces a fresh fetch of the ASF project list from `projects.apache.org`.

`check_project_website` Fetches an Apache project homepage and reports compliance with the Project Branding Requirements: apache.org hosting, Apache-form heading, TM/(R) on first prominent occurrence, footer trademark attribution, required navigation links (License, Sponsorship, Thanks, Security, Privacy), prominent link back to www.apache.org, third-party trademark acknowledgement, logo TM, and — when `stage="podling"` — the incubation DISCLAIMER text and `(Incubating)` suffix. Each finding cites the relevant policy URL.

`check_third_party_use` Fetches a third-party page and reports whether it follows ASF Trademark Policy for using Apache marks: domain misuse (bare Apache names as second-level domains, `apache` in the domain), approved branding form (`Powered By Apache Foo` / `Apache Foo Inside`), non-affiliation disclaimer, logo misuse (feather mark or unmodified project logos as primary brand), and credit link back to the upstream project. Each finding cites the relevant policy URL.

## Usage Examples

These examples show the kinds of questions a user can ask an MCP client connected to this server.

### Checking A Proposed Name

- "Validate the proposed Apache podling name 'Stratus'."
- "Is 'Cherokee' a valid podling name?"
- "Check whether 'Apache Foo' would pass the policy checks for a new podling."
- "I want to propose a streaming database project called 'Cascade'. Run validation."

### Exploring Conflicts

- "Search the ASF project list for names similar to 'arrow'."
- "Are there any existing ASF projects whose name is similar to 'spark'?"
- "Show me ASF projects whose names look anything like 'kafka' with a similarity threshold of 0.4."

### Reading The Policy

- "Summarize ASF naming policy for a podling."
- "What does ASF policy say about Native American names?"
- "What is the 'Powered By Apache' naming convention?"
- "Explain ASF's nominative-use rules."
- "What's the likelihood-of-confusion test in trademark law as applied by the ASF?"

### Branding Compliance

- "Give me the branding checklist for a podling preparing to graduate."
- "What does a top-level Apache project need on its homepage for trademark compliance?"
- "What incubation disclaimers does a podling need in release artifacts?"

### Running The Name Search

- "Run the PODLINGNAMESEARCH searches for 'Stratus' and give me a JIRA ticket I can paste."
- "I'm proposing a metadata catalog called 'Atlas'. Run the name search."
- "Search GitHub, PyPI, and npm for 'Foo' and give me the USPTO link."

### Auditing An ASF Project Website

- "Audit https://kafka.apache.org/ for trademark compliance."
- "Check whether https://foo.apache.org/ has the required navigation links and trademark attribution."
- "Run the podling-stage branding audit on https://newpodling.apache.org/."
- "Does my project homepage include TM next to the first 'Apache Foo' reference?"

### Auditing Third-Party Use

- "Is https://yoyodyne.com/yoyostream using Apache Foo marks correctly?"
- "Check whether https://kafka.com/ violates ASF trademark policy."
- "Does this vendor page have a non-affiliation disclaimer and the right 'Powered By' form?"
- "Audit https://example.com/ for misuse of the Apache feather logo."

## Development

Common tasks are available through `make`:

    make format
    make lint
    make typecheck
    make test
    make coverage
    make check

## Notes

- This server reports facts only. It does not opine on whether a name is "confusingly similar" — that is a legal judgement made by `trademarks@apache.org` and the VP, Brand Management.
- A `PASS` verdict from `validate_name` does **not** mean the name is approved. The full PODLINGNAMESEARCH process — internet search, USPTO search, JIRA ticket, VP Brand Management approval — is still required.
- All HTTP calls are made through the Python standard library; the package has no runtime dependencies.

TrademarkMCP is an independent tool and is not a project of the Apache Software Foundation. Apache and related marks are trademarks of The Apache Software Foundation.
