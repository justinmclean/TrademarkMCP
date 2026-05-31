"""Shared test fixtures for the trademark MCP tests."""

from __future__ import annotations

# A small fake ASF project list — committee + podling entries normalised to
# the same shape ``projects.fetch_projects`` returns. The "Apache " prefix is
# stripped from the human name field.
FAKE_PROJECTS: list[dict] = [
    {"id": "kafka", "name": "Apache Kafka", "shortdesc": "Distributed event streaming platform"},
    {"id": "spark", "name": "Apache Spark", "shortdesc": "Unified analytics engine"},
    {"id": "arrow", "name": "Apache Arrow", "shortdesc": "Cross-language columnar memory format"},
    {"id": "flink", "name": "Apache Flink", "shortdesc": "Stateful stream processing"},
    {"id": "airflow", "name": "Apache Airflow", "shortdesc": "Workflow scheduling"},
    {"id": "iceberg", "name": "Apache Iceberg", "shortdesc": "Open table format"},
    # Podling-shaped entry
    {"id": "stratus", "name": "Apache Stratus", "shortdesc": "Imaginary podling for tests"},
]
