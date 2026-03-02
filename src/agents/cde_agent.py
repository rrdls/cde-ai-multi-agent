"""CDE Agent — manages project lifecycle and governance in the CDE API.

Tools for creating projects, containers, uploading files, and managing
ISO 19650 state transitions.
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from .cde_client import CDEClient
from .llm import get_llm

CDE_BASE_URL = "http://localhost:8000"

# Singleton client
_client: CDEClient | None = None


def _get_client() -> CDEClient:
    global _client
    if _client is None:
        _client = CDEClient(CDE_BASE_URL)
    return _client


# ============================================================================
# Project Tools
# ============================================================================


@tool
def create_project(name: str, description: str = "") -> str:
    """Create a new project in the CDE.

    Args:
        name: Project name (e.g., "UBS Porte 1").
        description: Optional project description.
    """
    result = _get_client().create_project(name, description)
    return f"Project created: ID={result['id']}, Name={result['name']}"


@tool
def list_projects() -> str:
    """List all projects in the CDE.

    Returns a list of all projects with their IDs and names.
    Use this to find the project ID before creating containers or other operations.
    """
    projects = _get_client().list_projects()
    if not projects:
        return "No projects found. Create one with create_project."
    lines = [f"Found {len(projects)} project(s):"]
    for p in projects:
        lines.append(
            f"  - ID={p['id']} | Name={p['name']} | "
            f"Description={p.get('description', '')}"
        )
    return "\n".join(lines)


@tool
def add_project_member(
    project_id: str, name: str, role: str, organization: str = ""
) -> str:
    """Add a member to a CDE project.

    Args:
        project_id: The project ID.
        name: Member name.
        role: Role (lead_appointed, task_team, appointing_party).
        organization: Member's organization.
    """
    result = _get_client().add_member(project_id, name, role, organization)
    return f"Member added: {result['name']} as {result['role']}"


@tool
def list_members(project_id: str) -> str:
    """List all members of a CDE project.

    Args:
        project_id: The project ID.
    """
    members = _get_client().list_members(project_id)
    if not members:
        return "No members found in this project."
    lines = [f"Found {len(members)} member(s):"]
    for m in members:
        lines.append(
            f"  - {m['name']} | Role: {m['role']} | ID: {m['id']}"
        )
    return "\n".join(lines)


# ============================================================================
# Container Tools
# ============================================================================


@tool
def create_container(
    project_id: str,
    name: str,
    container_type: str,
    created_by: str = "Agent",
) -> str:
    """Create a new information container in a CDE project.

    Args:
        project_id: The project ID.
        name: Container name (e.g., "IFC Model ARQ").
        container_type: Type (ifc_model, drawing, specification, report, cost_estimate).
        created_by: Who is creating the container.
    """
    result = _get_client().create_container(
        project_id, name, container_type, created_by=created_by
    )
    return (
        f"Container created: ID={result['id']}, "
        f"Name={result['name']}, State={result['current_state']}"
    )


@tool
def list_containers(project_id: str) -> str:
    """List all containers in a CDE project.

    Use this to find container IDs for upload, download, or governance operations.

    Args:
        project_id: The project ID.
    """
    containers = _get_client().list_containers(project_id)
    if not containers:
        return "No containers found in this project."
    lines = [f"Found {len(containers)} container(s):"]
    for c in containers:
        lines.append(
            f"  - ID={c['id']} | Name={c['name']} | "
            f"Type={c['container_type']} | State={c['current_state']}"
        )
    return "\n".join(lines)


@tool
def upload_file(container_id: str, file_path: str) -> str:
    """Upload a file as a new revision to a container.

    Args:
        container_id: The container ID.
        file_path: Absolute path to the file to upload.
    """
    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"
    result = _get_client().upload_revision(container_id, path)
    return f"File uploaded: revision {result.get('revision_number', '?')} of {path.name}"


@tool
def download_file(container_id: str, revision_number: int = 1) -> str:
    """Download a file from a CDE container revision to a local path.

    Use this to retrieve files (IFC models, IDS specs, reports) stored
    in the CDE so that other agents can process them.

    Args:
        container_id: The container ID.
        revision_number: The revision number to download (default: 1, the first).
    """
    try:
        local_path = _get_client().download_revision(container_id, revision_number)
        return (
            f"File downloaded to: {local_path}\n"
            f"This absolute path can be used by IFC tools or other agents."
        )
    except Exception as e:
        return f"Error downloading file: {e}"


@tool
def get_container_info(container_id: str) -> str:
    """Get details about a container (state, type, revisions).

    Args:
        container_id: The container ID.
    """
    result = _get_client().get_container(container_id)
    lines = [
        f"Container: {result['name']}",
        f"Type: {result['container_type']}",
        f"State: {result['current_state']}",
    ]
    revisions = result.get("revisions", [])
    lines.append(f"Revisions: {len(revisions)}")
    for rev in revisions:
        lines.append(
            f"  - Rev {rev['revision_number']}: {rev.get('original_filename', '?')} "
            f"({rev.get('file_size_bytes', '?')} bytes)"
        )
    return "\n".join(lines)


# ============================================================================
# Governance Tools
# ============================================================================


@tool
def request_state_transition(
    container_id: str,
    to_state: str,
    requester_name: str,
    justification: str = "",
    suitability_code: str | None = None,
) -> str:
    """Request a state transition for a container (ISO 19650 governance).

    Valid transitions: WIP→SHARED, SHARED→PUBLISHED, PUBLISHED→ARCHIVED.

    Args:
        container_id: The container ID.
        to_state: Target state (shared, published, archived).
        requester_name: Who is requesting the transition.
        justification: Reason for the transition.
        suitability_code: Required when transitioning to SHARED.
    """
    result = _get_client().request_transition(
        container_id, to_state, requester_name, justification, suitability_code
    )
    return f"Transition requested: ID={result['id']}, Status={result['status']}"


@tool
def approve_transition(transition_id: str, approver_name: str) -> str:
    """Approve a pending state transition.

    Args:
        transition_id: The transition ID.
        approver_name: Who is approving.
    """
    result = _get_client().approve_transition(transition_id, approver_name)
    return f"Transition approved: container is now '{result.get('to_state', '?')}'"


@tool
def list_project_audit(project_id: str) -> str:
    """List the audit trail for a project (all actions logged).

    Args:
        project_id: The project ID.
    """
    entries = _get_client().list_audit(project_id)
    if not entries:
        return "No audit entries found."
    lines = []
    for e in entries[:20]:
        lines.append(
            f"[{e.get('action', '?')}] {e.get('actor_name', '?')}: "
            f"{e.get('details', '')[:80]}"
        )
    return "\n".join(lines)


CDE_TOOLS = [
    # Project management
    create_project,
    list_projects,
    add_project_member,
    list_members,
    # Container management
    create_container,
    list_containers,
    upload_file,
    download_file,
    get_container_info,
    # Governance
    request_state_transition,
    approve_transition,
    list_project_audit,
]

SYSTEM_PROMPT = """You are a CDE (Common Data Environment) Agent that manages project governance following ISO 19650.

You can create projects, manage team members, create information containers, upload/download files, and handle state transitions through the governance workflow.

## Important Workflow
- Before creating a container, use **list_projects** to find the project ID.
- Before uploading or downloading, use **list_containers** to find the container ID.
- When asked to download a file, use **download_file** and return the local path so other agents can use it.

## ISO 19650 Container States
- **WIP** (Work in Progress): Initial state for new containers
- **SHARED**: Approved content shared with the team (requires suitability code)
- **PUBLISHED**: Officially published content
- **ARCHIVED**: Archived content (immutable)

## Suitability Codes (required when sharing)
- S0: Work in Progress
- S1: Coordination
- S2: Information
- S3: Review and Comment
- S4: Stage Approval
- S6: PIM Authorization
- S7: AIM Authorization

Always report the outcome of each action clearly.
"""


def create_cde_agent():
    """Create a CDE management agent."""
    return create_react_agent(
        model=get_llm(),
        tools=CDE_TOOLS,
        prompt=SYSTEM_PROMPT,
    )
