"""CDE MCP Tool Server — exposes CDE governance tools via FastMCP (stdio).

Wraps the existing LangChain @tool functions from cde_agent.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from fastmcp import FastMCP

from agents.cde_agent import (
    create_project,
    list_projects,
    add_project_member,
    list_members,
    create_container,
    list_containers,
    upload_file,
    download_file,
    get_container_info,
    request_state_transition,
    approve_transition,
    list_project_audit,
)

mcp = FastMCP("CDE / ISO 19650 Governance Server")


# ---------- Project tools ----------

@mcp.tool
def new_project(name: str, description: str = "") -> str:
    """Create a new project in the CDE."""
    return create_project.invoke({"name": name, "description": description})


@mcp.tool
def get_projects() -> str:
    """List all projects in the CDE."""
    return list_projects.invoke({})


@mcp.tool
def add_member(project_id: str, name: str, role: str, organization: str = "") -> str:
    """Add a member to a CDE project."""
    return add_project_member.invoke({
        "project_id": project_id, "name": name,
        "role": role, "organization": organization,
    })


@mcp.tool
def get_members(project_id: str) -> str:
    """List all members of a CDE project."""
    return list_members.invoke({"project_id": project_id})


# ---------- Container tools ----------

@mcp.tool
def new_container(
    project_id: str, name: str, container_type: str, created_by: str = "Agent"
) -> str:
    """Create a new information container in a CDE project."""
    return create_container.invoke({
        "project_id": project_id, "name": name,
        "container_type": container_type, "created_by": created_by,
    })


@mcp.tool
def get_containers(project_id: str) -> str:
    """List all containers in a CDE project."""
    return list_containers.invoke({"project_id": project_id})


@mcp.tool
def upload(container_id: str, file_path: str) -> str:
    """Upload a file as a new revision to a container."""
    return upload_file.invoke({"container_id": container_id, "file_path": file_path})


@mcp.tool
def download(container_id: str, revision_number: int = 1) -> str:
    """Download a file from a CDE container revision."""
    return download_file.invoke({
        "container_id": container_id, "revision_number": revision_number,
    })


@mcp.tool
def container_info(container_id: str) -> str:
    """Get details about a container (state, type, revisions)."""
    return get_container_info.invoke({"container_id": container_id})


# ---------- Governance tools ----------

@mcp.tool
def request_transition(
    container_id: str,
    to_state: str,
    requester_name: str,
    justification: str = "",
    suitability_code: str | None = None,
) -> str:
    """Request a state transition for a container (ISO 19650)."""
    args: dict = {
        "container_id": container_id,
        "to_state": to_state,
        "requester_name": requester_name,
        "justification": justification,
    }
    if suitability_code:
        args["suitability_code"] = suitability_code
    return request_state_transition.invoke(args)


@mcp.tool
def approve(transition_id: str, approver_name: str) -> str:
    """Approve a pending state transition."""
    return approve_transition.invoke({
        "transition_id": transition_id, "approver_name": approver_name,
    })


@mcp.tool
def audit_trail(project_id: str) -> str:
    """List the audit trail for a project (all actions logged)."""
    return list_project_audit.invoke({"project_id": project_id})


if __name__ == "__main__":
    mcp.run()
