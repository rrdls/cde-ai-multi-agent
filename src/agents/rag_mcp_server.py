"""RAG MCP Tool Server — exposes document retrieval tools via FastMCP (stdio).

Wraps the existing LangChain @tool functions from rag_tools.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from fastmcp import FastMCP

from agents.rag_tools import search_documents, search_specs, search_specifications

mcp = FastMCP("RAG / Document Retrieval Server")


@mcp.tool
def query_documents(query: str, k: int = 5) -> str:
    """Search project documents and general text files via RAG."""
    return search_documents.invoke({"query": query, "k": k})


@mcp.tool
def query_specs(query: str, k: int = 5) -> str:
    """Search project technical specifications."""
    return search_specs.invoke({"query": query, "k": k})


@mcp.tool
def query_specifications(query: str, k: int = 5) -> str:
    """Search project technical specifications and design details."""
    return search_specifications.invoke({"query": query, "k": k})


if __name__ == "__main__":
    mcp.run()
