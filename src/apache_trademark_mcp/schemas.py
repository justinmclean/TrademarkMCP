"""Shared MCP input schema fragments for the trademark tools."""

from __future__ import annotations

from typing import Any

PROPOSED_NAME_PROPERTY = {
    "type": "string",
    "description": (
        "Proposed project name, WITHOUT the 'Apache' prefix (e.g. 'Kafka', not 'Apache Kafka')"
    ),
}
TECHNICAL_DESCRIPTION_PROPERTY = {
    "type": "string",
    "description": (
        "Brief description of what the project does; used to assess relevance of search hits"
    ),
}
QUERY_PROPERTY = {
    "type": "string",
    "description": "Search string — typically the proposed name or a related word",
}
MIN_SIMILARITY_PROPERTY = {
    "type": "number",
    "description": "Similarity threshold 0.0–1.0; values below 0.4 are noisy",
    "minimum": 0.0,
    "maximum": 1.0,
}


def input_schema(
    properties: dict[str, Any], *, required: list[str] | None = None
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def tool_definition(
    *,
    description: str,
    handler: Any,
    properties: dict[str, Any],
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "description": description,
        "inputSchema": input_schema(properties, required=required),
        "handler": handler,
    }


def validate_name_properties() -> dict[str, Any]:
    return {
        "proposed_name": PROPOSED_NAME_PROPERTY,
        "technical_description": TECHNICAL_DESCRIPTION_PROPERTY,
    }


def perform_name_search_properties() -> dict[str, Any]:
    return {
        "proposed_name": PROPOSED_NAME_PROPERTY,
        "technical_description": TECHNICAL_DESCRIPTION_PROPERTY,
    }


def search_asf_projects_properties() -> dict[str, Any]:
    return {
        "query": QUERY_PROPERTY,
        "min_similarity": MIN_SIMILARITY_PROPERTY,
    }


def branding_checklist_properties(stages: list[str]) -> dict[str, Any]:
    return {
        "stage": {
            "type": "string",
            "description": "Project lifecycle stage",
            "enum": stages,
        }
    }


def policy_guidance_properties(topics: list[str]) -> dict[str, Any]:
    return {
        "topic": {
            "type": "string",
            "description": "Focused trademark guidance topic",
            "enum": topics,
        }
    }


URL_PROPERTY = {
    "type": "string",
    "description": "Absolute http:// or https:// URL of the page to check",
}


def check_project_website_properties(stages: list[str]) -> dict[str, Any]:
    return {
        "url": URL_PROPERTY,
        "project_name": {
            "type": "string",
            "description": (
                "Project name without the 'Apache' prefix (e.g. 'Kafka'). "
                "If omitted, the server infers it from the host or page title."
            ),
        },
        "stage": {
            "type": "string",
            "description": "Project lifecycle stage; podling adds incubation-specific checks",
            "enum": stages,
        },
    }


def check_third_party_use_properties() -> dict[str, Any]:
    return {
        "url": URL_PROPERTY,
        "mark": {
            "type": "string",
            "description": (
                "Apache mark to check the page against (e.g. 'Kafka'). "
                "If omitted, the server infers it by scanning the page for "
                "'Apache <Name>' references."
            ),
        },
    }
