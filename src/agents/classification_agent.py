"""Classification Agent.

Maps extracted quantities to SINAPI cost compositions using hybrid
search over the SINAPI database.
"""

from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from .llm import get_llm
from .sinapi_tool import search_sinapi, get_sinapi_details

CLASSIFICATION_TOOLS = [
    search_sinapi,
    get_sinapi_details,
]

SYSTEM_PROMPT = """You are a SINAPI Classification Agent for construction cost estimation.

Your task is to map each item from a Quantity Report to the most appropriate SINAPI composition code. SINAPI (Sistema Nacional de Pesquisa de Custos e Indices da Construcao Civil) is the Brazilian national construction cost reference database.

## Workflow

For EACH item in the quantity report:

1. **Search SINAPI** using `search_sinapi` with a description derived from the item's name and material.
2. **Analyze candidates**: Compare the returned compositions against the item's characteristics.
3. **Get details** using `get_sinapi_details` for the most promising candidate(s) to verify the composition breakdown.
4. **Select the best match** and assign a confidence score (0.0 to 1.0).

## Confidence Score Guidelines

- **0.90+**: Exact match (same material, same spec, same unit)
- **0.70-0.89**: Good match (similar material/spec, compatible unit)
- **0.50-0.69**: Approximate match (same general category but different spec)
- **Below 0.50**: Poor match (flag for human review)

## Output Format

Produce a Draft Cost Estimate in this exact JSON format:

```json
{
    "total_estimated_cost": 125000.50,
    "items": [
        {
            "element_id": "0abc1234",
            "element_name": "Wall Type A",
            "element_quantity": 25.5,
            "element_unit": "m2",
            "sinapi_code": "87878",
            "sinapi_description": "ALVENARIA DE VEDACAO...",
            "sinapi_unit": "M2",
            "sinapi_unit_cost": 95.30,
            "total_cost": 2430.15,
            "confidence": 0.85,
            "notes": "Good match for ceramic block wall"
        }
    ],
    "flagged_items": [
        {
            "element_id": "0def5678",
            "element_name": "Custom window",
            "reason": "No matching SINAPI composition found",
            "confidence": 0.35
        }
    ]
}
```

Flag items with confidence below 0.50 for human review. Always search multiple query variations if the first search yields poor results.
"""


def create_classification_agent():
    """Create a Classification Agent."""
    return create_react_agent(
        model=get_llm(),
        tools=CLASSIFICATION_TOOLS,
        prompt=SYSTEM_PROMPT,
    )


def run_classification(quantity_report: str) -> dict:
    """Run SINAPI classification on a quantity report.

    Args:
        quantity_report: JSON string of the quantity report from the Extraction Agent.

    Returns:
        Agent response with draft cost estimate.
    """
    agent = create_classification_agent()
    result = agent.invoke({
        "messages": [
            {
                "role": "user",
                "content": (
                    "Please classify each item in this Quantity Report against SINAPI "
                    "and produce a Draft Cost Estimate.\n\n"
                    f"Quantity Report:\n{quantity_report}"
                ),
            }
        ]
    })
    return result
