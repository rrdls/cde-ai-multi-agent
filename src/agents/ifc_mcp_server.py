"""IFC MCP Tool Server — exposes IFC/IDS tools via FastMCP (stdio).

This server wraps the existing LangChain @tool functions from ifc_tools.py
and exposes them through the Model Context Protocol so that agents can
access them via MultiServerMCPClient.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is on path for imports
_SRC = Path(__file__).resolve().parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from fastmcp import FastMCP

# Import the underlying LangChain tools
from agents.ifc_tools import (
    check_ifc_schema,
    check_material_assignment,
    check_quantity_sets,
    check_spatial_structure,
    check_classification,
    extract_walls,
    extract_slabs,
    extract_beams_columns,
    extract_doors_windows,
    extract_pipes,
    run_ids_check,
    get_ids_report,
)

mcp = FastMCP("IFC / IfcOpenShell Server")


# ---------- Verification tools ----------

@mcp.tool
def check_schema(ifc_path: str) -> str:
    """Check the IFC schema version of a model file."""
    return check_ifc_schema.invoke({"ifc_path": ifc_path})


@mcp.tool
def check_materials(ifc_path: str) -> str:
    """Check material assignments in an IFC model."""
    return check_material_assignment.invoke({"ifc_path": ifc_path})


@mcp.tool
def check_quantities(ifc_path: str) -> str:
    """Check quantity sets (Qto) in an IFC model."""
    return check_quantity_sets.invoke({"ifc_path": ifc_path})


@mcp.tool
def check_spatial(ifc_path: str) -> str:
    """Check spatial structure (Site/Building/Storey) in an IFC model."""
    return check_spatial_structure.invoke({"ifc_path": ifc_path})


@mcp.tool
def check_class(ifc_path: str) -> str:
    """Check classification references in an IFC model."""
    return check_classification.invoke({"ifc_path": ifc_path})


# ---------- Extraction tools ----------

@mcp.tool
def get_walls(ifc_path: str) -> str:
    """Extract all walls from an IFC model with dimensions and materials."""
    return extract_walls.invoke({"ifc_path": ifc_path})


@mcp.tool
def get_slabs(ifc_path: str) -> str:
    """Extract all slabs from an IFC model with dimensions and materials."""
    return extract_slabs.invoke({"ifc_path": ifc_path})


@mcp.tool
def get_beams_columns(ifc_path: str) -> str:
    """Extract all beams and columns from an IFC model."""
    return extract_beams_columns.invoke({"ifc_path": ifc_path})


@mcp.tool
def get_doors_windows(ifc_path: str) -> str:
    """Extract all doors and windows from an IFC model."""
    return extract_doors_windows.invoke({"ifc_path": ifc_path})


@mcp.tool
def get_pipes(ifc_path: str) -> str:
    """Extract all pipes and pipe fittings from an IFC model."""
    return extract_pipes.invoke({"ifc_path": ifc_path})


# ---------- IDS validation tools ----------

@mcp.tool
def validate_ids(ifc_path: str, ids_path: str) -> str:
    """Run IDS validation of an IFC model against an IDS XML specification."""
    return run_ids_check.invoke({"ifc_path": ifc_path, "ids_path": ids_path})


@mcp.tool
def format_ids_report(results_json: str) -> str:
    """Format raw JSON IDS results into a readable markdown report."""
    return get_ids_report.invoke({"results_json": results_json})


if __name__ == "__main__":
    mcp.run()
