"""Orchestrator: Multi-Agent Supervisor for CDE Chat.

Routes user messages to specialized agents:
- IFC Agent: model checks + quantity extraction (via IFC MCP Server)
- RAG Agent: document retrieval and project specifications (via RAG MCP Server)
- CDE Agent: project governance + state transitions (via CDE MCP Server)

Tools are loaded from FastMCP servers via langchain-mcp-adapters
(MultiServerMCPClient) using stdio transport.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Annotated, Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from typing_extensions import TypedDict

from .llm import get_llm

logger = logging.getLogger(__name__)

# ============================================================================
# MCP Tool Loading
# ============================================================================

_AGENTS_DIR = Path(__file__).resolve().parent

# MCP server definitions (stdio transport)
MCP_SERVERS = {
    "ifc": {
        "command": "python",
        "args": [str(_AGENTS_DIR / "ifc_mcp_server.py")],
        "transport": "stdio",
    },
    "rag": {
        "command": "python",
        "args": [str(_AGENTS_DIR / "rag_mcp_server.py")],
        "transport": "stdio",
    },
    "cde": {
        "command": "python",
        "args": [str(_AGENTS_DIR / "cde_mcp_server.py")],
        "transport": "stdio",
    },
}

# Tools loaded from MCP servers at startup
_mcp_tools: dict[str, list] = {}


async def _load_mcp_tools() -> dict[str, list]:
    """Connect to all MCP servers and load their tools."""
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(MCP_SERVERS)
    all_tools = await client.get_tools()

    # Partition tools by server name prefix
    ifc_names = {
        "check_schema", "check_materials", "check_quantities",
        "check_spatial", "check_class", "get_walls", "get_slabs",
        "get_beams_columns", "get_doors_windows", "get_pipes",
        "validate_ids", "format_ids_report",
    }
    rag_names = {"query_documents", "query_specs", "query_specifications"}
    cde_names = {
        "new_project", "get_projects", "add_member", "get_members",
        "new_container", "get_containers", "upload", "download",
        "container_info", "request_transition", "approve", "audit_trail",
    }

    tools_by_server: dict[str, list] = {"ifc": [], "rag": [], "cde": []}
    for tool in all_tools:
        if tool.name in ifc_names:
            tools_by_server["ifc"].append(tool)
        elif tool.name in rag_names:
            tools_by_server["rag"].append(tool)
        elif tool.name in cde_names:
            tools_by_server["cde"].append(tool)

    logger.info(
        "MCP tools loaded: IFC=%d, RAG=%d, CDE=%d",
        len(tools_by_server["ifc"]),
        len(tools_by_server["rag"]),
        len(tools_by_server["cde"]),
    )
    return tools_by_server


def _ensure_mcp_tools() -> dict[str, list]:
    """Load MCP tools (cached after first call).
    
    Handles both standalone scripts (no event loop) and Chainlit
    (existing event loop) by using a background thread when needed.
    """
    global _mcp_tools
    if not _mcp_tools:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Inside an existing event loop (e.g. Chainlit) — run in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                _mcp_tools = pool.submit(asyncio.run, _load_mcp_tools()).result()
        else:
            _mcp_tools = asyncio.run(_load_mcp_tools())
    return _mcp_tools


# ============================================================================
# Shared State
# ============================================================================


class SupervisorState(TypedDict):
    """Shared conversation state across all agents."""

    messages: Annotated[list[BaseMessage], add_messages]


# ============================================================================
# Sub-agent definitions
# ============================================================================

IFC_PROMPT = """You are an IFC (Industry Foundation Classes) specialist agent.

You have tools to:
1. **Verify** an IFC model (compliance checks): schema, materials, quantities, spatial structure, classification
2. **Extract** quantities: walls, slabs, beams/columns, doors/windows, pipes
3. **IDS Validation**: Validate IFC against an IDS XML using validate_ids and format it with format_ids_report.
4. **CDE File Access**: Use get_projects, get_containers, and download to retrieve files from the CDE.

## Important Workflow for IDS Validation
1. First use **get_projects** to find the project ID
2. Then use **get_containers** to find the IFC model and IDS specification container IDs
3. Use **download** to download both the IFC and IDS files to local paths
4. Run **validate_ids** with the downloaded file paths
5. Format results with **format_ids_report**

When verifying, run ALL 5 checks and produce a summary.
When extracting, be thorough and extract ALL elements of the requested type.
Always report results clearly with counts and details."""

RAG_PROMPT = """You are a Document Retrieval (RAG) specialist agent.

You have tools to:
1. Search general project documents
2. Search technical specs
3. Search design specifications

Use these tools to retrieve information from the project's vector store.
Always base your answers on the retrieved text and cite the source."""

CDE_PROMPT = """You are a CDE (Common Data Environment) Agent that manages project governance following ISO 19650.

You can create projects, manage team members, create information containers, upload/download files, and handle state transitions through the governance workflow.

## Important Workflow
- Before creating a container, use **get_projects** to find the project ID.
- Before uploading or downloading, use **get_containers** to find the container ID.
- When asked to download a file, use **download** and return the local path so other agents can use it.

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

Always report the outcome of each action clearly."""


def _make_ifc_agent():
    tools = _ensure_mcp_tools()
    # IFC agent gets IFC tools + CDE file access tools (download, list)
    ifc_tools = tools["ifc"] + [
        t for t in tools["cde"]
        if t.name in ("get_projects", "get_containers", "download")
    ]
    return create_react_agent(
        model=get_llm(),
        tools=ifc_tools,
        prompt=IFC_PROMPT,
    )


def _make_rag_agent():
    tools = _ensure_mcp_tools()
    return create_react_agent(
        model=get_llm(),
        tools=tools["rag"],
        prompt=RAG_PROMPT,
    )


def _make_cde_agent():
    tools = _ensure_mcp_tools()
    return create_react_agent(
        model=get_llm(),
        tools=tools["cde"],
        prompt=CDE_PROMPT,
    )


# ============================================================================
# Supervisor (router)
# ============================================================================

SUPERVISOR_PROMPT = """You are a Supervisor that routes user requests to specialized agents.

You have 3 agents available:
- **ifc_agent**: For anything related to IFC models (verification, quantity extraction, IDS validation, checks)
- **rag_agent**: For searching documents, guidelines, specs, and textual information retrieval
- **cde_agent**: For CDE project management (create projects, containers, upload files, state transitions, audit)

Based on the user's message, decide which agent should handle it.
If the request doesn't clearly fit any agent, respond directly with helpful guidance.

Respond with ONLY the agent name (ifc_agent, rag_agent, cde_agent) or "direct" if you should respond yourself."""


def supervisor_route(state: SupervisorState) -> str:
    """Use LLM to decide which agent handles the user message."""
    llm = get_llm()

    messages = state["messages"]
    last_human = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_human = msg.content
            break

    if not last_human:
        return "direct"

    response = llm.invoke([
        {"role": "system", "content": SUPERVISOR_PROMPT},
        {"role": "user", "content": last_human},
    ])

    route = response.content.strip().lower()

    if "ifc" in route or "model" in route or "check" in route:
        return "ifc_agent"
    elif "document" in route or "spec" in route or "rag" in route or "search" in route:
        return "rag_agent"
    elif "cde" in route or "project" in route or "container" in route or "transition" in route:
        return "cde_agent"
    else:
        return "direct"


# ============================================================================
# Graph nodes
# ============================================================================

async def run_ifc_agent(state: SupervisorState) -> dict:
    """Invoke the IFC agent."""
    logger.info(">>> Delegating to IFC Agent")
    agent = _make_ifc_agent()
    result = await agent.ainvoke({"messages": state["messages"]})
    return {"messages": result["messages"]}


async def run_rag_agent(state: SupervisorState) -> dict:
    """Invoke the RAG agent."""
    logger.info(">>> Delegating to RAG Agent")
    agent = _make_rag_agent()
    result = await agent.ainvoke({"messages": state["messages"]})
    return {"messages": result["messages"]}


async def run_cde_agent(state: SupervisorState) -> dict:
    """Invoke the CDE agent."""
    logger.info(">>> Delegating to CDE Agent")
    agent = _make_cde_agent()
    result = await agent.ainvoke({"messages": state["messages"]})
    return {"messages": result["messages"]}


def respond_direct(state: SupervisorState) -> dict:
    """Supervisor responds directly (no delegation)."""
    logger.info(">>> Supervisor responding directly")
    llm = get_llm()
    response = llm.invoke([
        {
            "role": "system",
            "content": (
                "You are a helpful assistant for a CDE (Common Data Environment) "
                "platform that manages BIM models and construction information. "
                "You coordinate IFC validation, document retrieval via RAG, and "
                "ISO 19650 governance. Answer the user's question directly."
            ),
        },
        *[
            {"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content}
            for m in state["messages"]
            if hasattr(m, "content") and m.content
        ],
    ])
    return {"messages": [response]}


# ============================================================================
# Build graph
# ============================================================================


def build_supervisor() -> StateGraph:
    """Build the multi-agent supervisor graph.

    Structure:
        START → supervisor_route → ifc_agent / rag_agent / cde_agent / direct → END
    """
    builder = StateGraph(SupervisorState)

    # Nodes
    builder.add_node("ifc_agent", run_ifc_agent)
    builder.add_node("rag_agent", run_rag_agent)
    builder.add_node("cde_agent", run_cde_agent)
    builder.add_node("direct", respond_direct)

    # Routing
    builder.add_conditional_edges(
        START,
        supervisor_route,
        {
            "ifc_agent": "ifc_agent",
            "rag_agent": "rag_agent",
            "cde_agent": "cde_agent",
            "direct": "direct",
        },
    )

    # All agents return to END
    builder.add_edge("ifc_agent", END)
    builder.add_edge("rag_agent", END)
    builder.add_edge("cde_agent", END)
    builder.add_edge("direct", END)

    return builder.compile()
