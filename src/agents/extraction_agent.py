"""Extraction Agent.

Extracts quantities from IFC models and enriches them with data from
project specifications via RAG search.
"""

from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from .llm import get_llm
from .ifc_tools import (
    extract_walls,
    extract_slabs,
    extract_beams_columns,
    extract_doors_windows,
    extract_pipes,
)
from .specs_tool import search_specifications

EXTRACTION_TOOLS = [
    extract_walls,
    extract_slabs,
    extract_beams_columns,
    extract_doors_windows,
    extract_pipes,
    search_specifications,
]

SYSTEM_PROMPT = """You are a Quantity Extraction Agent for Building Information Models (BIM).

Your task is to extract a complete Bill of Quantities from an IFC model for cost estimation. You work systematically through each element type.

## Workflow

1. Extract quantities for EACH element type using the IFC extraction tools:
   - Walls (areas)
   - Slabs (areas)
   - Beams and Columns (volumes)
   - Doors and Windows (counts and dimensions)
   - Pipes (lengths and diameters)

2. For each element type, use `search_specifications` to find relevant technical specifications from the project documents. This helps clarify materials, finishes, and standards referred to in the model.

3. Compile a structured Quantity Report.

## Output Format

Produce a Quantity Report in this exact JSON format:

```json
{
    "total_elements": 42,
    "categories": [
        {
            "category": "Walls",
            "count": 10,
            "items": [
                {
                    "element_id": "0abc1234",
                    "name": "Wall Type A",
                    "material": "Bloco ceramico 14x19x29",
                    "quantity": 25.5,
                    "unit": "m2",
                    "spec_notes": "Referenced in spec: alvenaria de vedacao e=14cm"
                }
            ]
        }
    ],
    "notes": "Any observations about the extraction"
}
```

Be thorough. Extract ALL elements, not just a sample. Use the specifications search to enrich the material descriptions when the IFC material names are generic.
"""


def create_extraction_agent():
    """Create an Extraction Agent."""
    return create_react_agent(
        model=get_llm(),
        tools=EXTRACTION_TOOLS,
        prompt=SYSTEM_PROMPT,
    )


def run_extraction(ifc_path: str) -> dict:
    """Run quantity extraction on an IFC file.

    Args:
        ifc_path: Absolute path to the IFC file.

    Returns:
        Agent response with quantity report.
    """
    agent = create_extraction_agent()
    result = agent.invoke({
        "messages": [
            {
                "role": "user",
                "content": f"Please extract all quantities from this IFC file: {ifc_path}",
            }
        ]
    })
    return result
