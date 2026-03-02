"""IfcOpenShell tools for compliance verification and quantity extraction.

All tools accept an IFC file path and return structured text output.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import ifcopenshell
from langchain_core.tools import tool


def _open_ifc(ifc_path: str) -> ifcopenshell.file:
    """Open an IFC file, raising clear errors."""
    path = Path(ifc_path)
    if not path.exists():
        raise FileNotFoundError(f"IFC file not found: {ifc_path}")
    return ifcopenshell.open(str(path))


# ============================================================================
# Compliance Verification Tools
# ============================================================================


@tool
def check_ifc_schema(ifc_path: str) -> str:
    """Check the IFC schema version of the model.

    Args:
        ifc_path: Absolute path to the IFC file.
    """
    ifc = _open_ifc(ifc_path)
    schema = ifc.schema
    return f"Schema: {schema}. Valid IFC file with {len(ifc.by_type('IfcProduct'))} products."


@tool
def check_material_assignment(ifc_path: str) -> str:
    """Check how many building elements have material assignments.

    Elements without materials cannot be mapped to cost compositions.

    Args:
        ifc_path: Absolute path to the IFC file.
    """
    ifc = _open_ifc(ifc_path)
    elements = ifc.by_type("IfcBuildingElement")
    with_material = 0
    without_material = []

    for elem in elements:
        has_mat = False
        for rel in getattr(elem, "HasAssociations", []):
            if rel.is_a("IfcRelAssociatesMaterial"):
                has_mat = True
                break
        if has_mat:
            with_material += 1
        else:
            without_material.append(
                f"{elem.is_a()} #{elem.id()} ({getattr(elem, 'Name', 'unnamed')})"
            )

    total = len(elements)
    pct = (with_material / total * 100) if total > 0 else 0
    result = (
        f"Material assignment: {with_material}/{total} elements ({pct:.1f}%)\n"
    )
    if without_material:
        result += f"Elements WITHOUT material ({len(without_material)}):\n"
        for item in without_material[:20]:
            result += f"  - {item}\n"
        if len(without_material) > 20:
            result += f"  ... and {len(without_material) - 20} more\n"

    return result


@tool
def check_quantity_sets(ifc_path: str) -> str:
    """Check if elements have quantity sets (BaseQuantities) defined.

    Elements need quantities (area, volume, length) for cost estimation.

    Args:
        ifc_path: Absolute path to the IFC file.
    """
    ifc = _open_ifc(ifc_path)
    elements = ifc.by_type("IfcBuildingElement")
    with_qsets = 0
    qset_names: Counter = Counter()

    for elem in elements:
        for rel in getattr(elem, "IsDefinedBy", []):
            if rel.is_a("IfcRelDefinesByProperties"):
                pset = rel.RelatingPropertyDefinition
                if pset.is_a("IfcElementQuantity"):
                    with_qsets += 1
                    qset_names[pset.Name or "unnamed"] += 1
                    break

    total = len(elements)
    pct = (with_qsets / total * 100) if total > 0 else 0
    result = f"Quantity sets: {with_qsets}/{total} elements ({pct:.1f}%)\n"
    if qset_names:
        result += "Quantity set types:\n"
        for name, count in qset_names.most_common(10):
            result += f"  - {name}: {count} elements\n"

    return result


@tool
def check_spatial_structure(ifc_path: str) -> str:
    """Check the spatial structure hierarchy (Site > Building > Storey).

    A proper hierarchy is needed for organized quantity takeoff.

    Args:
        ifc_path: Absolute path to the IFC file.
    """
    ifc = _open_ifc(ifc_path)
    sites = ifc.by_type("IfcSite")
    buildings = ifc.by_type("IfcBuilding")
    storeys = ifc.by_type("IfcBuildingStorey")

    lines = [
        f"Spatial structure:",
        f"  Sites: {len(sites)}",
        f"  Buildings: {len(buildings)}",
        f"  Storeys: {len(storeys)}",
    ]
    for storey in storeys:
        name = getattr(storey, "Name", "unnamed")
        elevation = getattr(storey, "Elevation", None)
        elev_str = f" (elevation: {elevation}m)" if elevation is not None else ""
        lines.append(f"    - {name}{elev_str}")

    return "\n".join(lines)


@tool
def check_classification(ifc_path: str) -> str:
    """Check if elements have classification references (e.g., Uniformat, OmniClass).

    Classifications help in mapping elements to cost database entries.

    Args:
        ifc_path: Absolute path to the IFC file.
    """
    model = _open_ifc(ifc_path)
    elems = model.by_type("IfcBuildingElement")
    total = len(elems)
    if total == 0:
        return "No BuildingElements found."

    classified = 0
    systems = Counter()

    for elem in elems:
        has_class = False
        if hasattr(elem, "HasAssociations"):
            for asc in elem.HasAssociations:
                if asc.is_a("IfcRelAssociatesClassification"):
                    ref = asc.RelatingClassification
                    if ref:
                        has_class = True
                        sys_name = getattr(ref, "Name", "Unknown")
                        item_ref = getattr(ref, "ItemReference", "N/A")
                        systems[f"{sys_name} ({item_ref})"] += 1
        if has_class:
            classified += 1

    lines = [
        f"Elements with classification: {classified}/{total} ({classified/total:.1%})",
    ]
    if systems:
        lines.append("Found classifications:")
        for k, v in systems.most_common(5):
            lines.append(f"  - {k}: {v} elements")
    return "\n".join(lines)


@tool
def run_ids_check(ifc_path: str, ids_path: str) -> str:
    """Run an Information Delivery Specification (IDS) validation using IfcTester.
    
    Validates an IFC model against an IDS XML specification and returns a JSON string
    containing the pass/fail results per requirement. The agent can save this JSON
    or use it to generate a report.
    
    Args:
        ifc_path: Absolute path to the IFC file.
        ids_path: Absolute path to the IDS XML file.
    """
    from ifctester import ids as ids_module
    import json
    
    try:
        my_ids = ids_module.open(ids_path)
        my_ifc = _open_ifc(ifc_path)
        my_ids.validate(my_ifc)
        
        # We extract a simplified dictionary of results
        info = getattr(my_ids, 'info', {}) or {}
        results = {
            "title": info.get('title', 'Untitled'),
            "version": info.get('version', 'N/A'),
            "specifications": []
        }
        
        for spec in my_ids.specifications:
            spec_data = {
                "name": spec.name,
                "description": spec.description,
                "status": "PASS" if spec.status else "FAIL",
                "requirements": []
            }
            results["specifications"].append(spec_data)
            
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error running IDS validation: {e}"


@tool
def get_ids_report(results_json: str) -> str:
    """Format raw JSON IDS results into a readable markdown report.
    
    Args:
        results_json: The JSON string output from run_ids_check.
    """
    import json
    try:
        data = json.loads(results_json)
        lines = [
            f"# IDS Validation Report: {data.get('title', 'Untitled')}",
            f"Version: {data.get('version', 'N/A')}",
            "",
            "## Specifications:"
        ]
        
        passed = 0
        total = 0
        for spec in data.get("specifications", []):
            total += 1
            status_icon = "✅" if spec.get("status") == "PASS" else "❌"
            if spec.get("status") == "PASS": passed += 1
            
            lines.append(f"- {status_icon} **{spec.get('name', 'N/A')}**: {spec.get('status')}")
            if spec.get("description"):
                lines.append(f"  > {spec.get('description')}")
                
        lines.insert(2, f"**Overall Summary**: {passed}/{total} specifications passed.")
        return "\n".join(lines)
    except Exception as e:
        return f"Error formatting IDS report: {e}"


# ============================================================================
# Extraction Tools (used by Extraction Agent)
# ============================================================================


def _get_material_name(elem: Any) -> str:
    """Extract material name from an IFC element."""
    for rel in getattr(elem, "HasAssociations", []):
        if rel.is_a("IfcRelAssociatesMaterial"):
            mat = rel.RelatingMaterial
            if mat.is_a("IfcMaterial"):
                return mat.Name or "unnamed"
            if mat.is_a("IfcMaterialLayerSetUsage"):
                layers = mat.ForLayerSet.MaterialLayers
                return ", ".join(
                    l.Material.Name for l in layers if l.Material
                )
            if mat.is_a("IfcMaterialLayerSet"):
                return ", ".join(
                    l.Material.Name for l in mat.MaterialLayers if l.Material
                )
    return "no material"


def _get_quantities(elem: Any) -> dict[str, float]:
    """Extract quantities from an element's quantity sets."""
    quantities = {}
    for rel in getattr(elem, "IsDefinedBy", []):
        if rel.is_a("IfcRelDefinesByProperties"):
            pset = rel.RelatingPropertyDefinition
            if pset.is_a("IfcElementQuantity"):
                for q in pset.Quantities:
                    if q.is_a("IfcQuantityArea"):
                        quantities[q.Name] = q.AreaValue
                    elif q.is_a("IfcQuantityVolume"):
                        quantities[q.Name] = q.VolumeValue
                    elif q.is_a("IfcQuantityLength"):
                        quantities[q.Name] = q.LengthValue
                    elif q.is_a("IfcQuantityCount"):
                        quantities[q.Name] = q.CountValue
    return quantities


@tool
def extract_walls(ifc_path: str) -> str:
    """Extract all walls with their areas, materials, and types.

    Args:
        ifc_path: Absolute path to the IFC file.
    """
    ifc = _open_ifc(ifc_path)
    walls = ifc.by_type("IfcWall")

    lines = [f"Found {len(walls)} walls:"]
    for w in walls:
        name = getattr(w, "Name", "unnamed")
        material = _get_material_name(w)
        quantities = _get_quantities(w)
        area = quantities.get("NetSideArea") or quantities.get("GrossSideArea", "N/A")
        lines.append(
            f"  [{w.GlobalId[:8]}] {name} | Material: {material} | Area: {area}"
        )

    return "\n".join(lines)


@tool
def extract_slabs(ifc_path: str) -> str:
    """Extract all slabs with their areas, thicknesses, and materials.

    Args:
        ifc_path: Absolute path to the IFC file.
    """
    ifc = _open_ifc(ifc_path)
    slabs = ifc.by_type("IfcSlab")

    lines = [f"Found {len(slabs)} slabs:"]
    for s in slabs:
        name = getattr(s, "Name", "unnamed")
        material = _get_material_name(s)
        quantities = _get_quantities(s)
        area = quantities.get("NetArea") or quantities.get("GrossArea", "N/A")
        lines.append(
            f"  [{s.GlobalId[:8]}] {name} | Material: {material} | Area: {area}"
        )

    return "\n".join(lines)


@tool
def extract_beams_columns(ifc_path: str) -> str:
    """Extract all beams and columns with their volumes and materials.

    Args:
        ifc_path: Absolute path to the IFC file.
    """
    ifc = _open_ifc(ifc_path)
    beams = ifc.by_type("IfcBeam")
    columns = ifc.by_type("IfcColumn")
    elements = beams + columns

    lines = [f"Found {len(beams)} beams + {len(columns)} columns:"]
    for e in elements:
        name = getattr(e, "Name", "unnamed")
        etype = "Beam" if e.is_a("IfcBeam") else "Column"
        material = _get_material_name(e)
        quantities = _get_quantities(e)
        volume = quantities.get("NetVolume") or quantities.get("GrossVolume", "N/A")
        lines.append(
            f"  [{e.GlobalId[:8]}] {etype}: {name} | Material: {material} | Volume: {volume}"
        )

    return "\n".join(lines)


@tool
def extract_doors_windows(ifc_path: str) -> str:
    """Extract all doors and windows with their types, dimensions, and counts.

    Args:
        ifc_path: Absolute path to the IFC file.
    """
    ifc = _open_ifc(ifc_path)
    doors = ifc.by_type("IfcDoor")
    windows = ifc.by_type("IfcWindow")

    lines = [f"Found {len(doors)} doors + {len(windows)} windows:"]
    for d in doors:
        name = getattr(d, "Name", "unnamed")
        h = getattr(d, "OverallHeight", "N/A")
        w = getattr(d, "OverallWidth", "N/A")
        lines.append(f"  [Door] {name} | {w}x{h}mm | Material: {_get_material_name(d)}")

    for w_elem in windows:
        name = getattr(w_elem, "Name", "unnamed")
        h = getattr(w_elem, "OverallHeight", "N/A")
        w = getattr(w_elem, "OverallWidth", "N/A")
        lines.append(
            f"  [Window] {name} | {w}x{h}mm | Material: {_get_material_name(w_elem)}"
        )

    return "\n".join(lines)


@tool
def extract_pipes(ifc_path: str) -> str:
    """Extract all pipe segments with their lengths, diameters, and materials.

    Args:
        ifc_path: Absolute path to the IFC file.
    """
    ifc = _open_ifc(ifc_path)
    pipes = ifc.by_type("IfcPipeSegment")
    fittings = ifc.by_type("IfcPipeFitting")

    lines = [f"Found {len(pipes)} pipe segments + {len(fittings)} fittings:"]
    for p in pipes:
        name = getattr(p, "Name", "unnamed")
        material = _get_material_name(p)
        quantities = _get_quantities(p)
        length = quantities.get("Length") or quantities.get("GrossLength", "N/A")
        lines.append(
            f"  [Pipe] {name} | Material: {material} | Length: {length}"
        )

    type_counts: Counter = Counter()
    for f in fittings:
        name = getattr(f, "Name", "unnamed")
        type_counts[name] += 1

    if type_counts:
        lines.append(f"\nFitting summary:")
        for name, count in type_counts.most_common(20):
            lines.append(f"  - {name}: {count}x")

    return "\n".join(lines)
