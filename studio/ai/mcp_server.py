"""Experimental MCP server exposing academic tools to the student's AI client.

Run (when MCP SDK is installed):
  .venv/bin/python -m studio.ai.mcp_server

This is reverse BYOAI: inference stays in their client; we expose data + draft tools.
"""

from __future__ import annotations

TOOL_NAMES = [
    "search_professors",
    "get_professor_profile",
    "find_research_openings",
    "get_research_papers",
    "get_student_profile",
    "generate_evidence_bound_draft",
    "validate_draft",
    "save_draft",
]


def list_tools() -> list[dict[str, str]]:
    return [
        {
            "name": name,
            "description": f"Academic Outreach Studio tool: {name}",
        }
        for name in TOOL_NAMES
    ]


def main() -> None:
    print("Academic Outreach Studio MCP scaffold")
    print("Tools:")
    for t in list_tools():
        print(f"  - {t['name']}")
    print("Install an MCP SDK and wire stdio transport before shipping to clients.")


if __name__ == "__main__":
    main()
