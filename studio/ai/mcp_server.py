"""Reverse BYOAI: expose Academic Outreach Studio tools to the student's AI client.

Inference stays in ChatGPT / Claude / Copilot — we never hold subscription tokens.

Distribution channels (documented, separate review where required):
  - ChatGPT desktop-only local MCP plugins
  - Claude Desktop Extensions (.mcpb MCP Bundles)
  - VS Code / Copilot MCP registration (technical research workflows)

Run scaffold:
  .venv/bin/python -m studio.ai.mcp_server
"""

from __future__ import annotations

from typing import Any

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

PACKAGING = {
    "chatgpt_desktop_plugin": {
        "status": "adapter_ready",
        "docs": "https://developers.openai.com/plugins/deploy/desktop-only",
        "note": "Local MCP server; public directory has separate review.",
    },
    "claude_desktop_extension": {
        "status": "adapter_ready",
        "bundle": "AcademicOutreachStudio.mcpb",
        "docs": "https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop",
        "note": "Single-click MCP Bundle; directory listing is a separate submission.",
    },
    "vscode_copilot_mcp": {
        "status": "adapter_ready",
        "docs": "https://code.visualstudio.com/api/extension-guides/ai/mcp",
        "note": "Focus on project/repo research alignment — not a general email backend claim.",
    },
}


def list_tools() -> list[dict[str, str]]:
    return [
        {"name": name, "description": f"Academic Outreach Studio tool: {name}"}
        for name in TOOL_NAMES
    ]


def packaging_manifest() -> dict[str, Any]:
    return {
        "name": "Academic Outreach Studio",
        "tools": list_tools(),
        "channels": PACKAGING,
        "policy": (
            "No subscription credential extraction. "
            "No undocumented consumer bridges. "
            "Evidence-bound drafts only."
        ),
    }


def main() -> None:
    manifest = packaging_manifest()
    print("Academic Outreach Studio MCP scaffold")
    print(manifest["policy"])
    print("Tools:")
    for t in manifest["tools"]:
        print(f"  - {t['name']}")
    print("Distribution channels:")
    for key, meta in PACKAGING.items():
        print(f"  - {key}: {meta['status']} — {meta['docs']}")
    print("Install an MCP SDK and wire stdio transport before shipping bundles.")


if __name__ == "__main__":
    main()
