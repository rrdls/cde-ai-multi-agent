"""CLI runner for the CDE cost estimation pipeline.

Usage:
    python run_pipeline.py --ifc path/to/model.ifc [--project ubs-porte-1]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add src/ to path
_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "src"))

load_dotenv(_ROOT / ".env")

from agents.cde_client import CDEClient  # noqa: E402
from agents.orchestrator import run_pipeline  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_pipeline")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the CDE cost estimation agent pipeline"
    )
    parser.add_argument(
        "--ifc",
        type=Path,
        required=True,
        help="Path to the IFC model file",
    )
    parser.add_argument(
        "--project-name",
        type=str,
        default="UBS Porte 1",
        help="Name for the CDE project",
    )
    parser.add_argument(
        "--cde-url",
        type=str,
        default="http://localhost:8000",
        help="CDE API base URL",
    )
    args = parser.parse_args()

    ifc_path = args.ifc.resolve()
    if not ifc_path.exists():
        logger.error(f"IFC file not found: {ifc_path}")
        sys.exit(1)

    logger.info(f"IFC file: {ifc_path}")
    logger.info(f"CDE API: {args.cde_url}")

    # ----------------------------------------------------------
    # Step 1: Setup CDE project
    # ----------------------------------------------------------
    logger.info("Setting up CDE project...")
    cde = CDEClient(args.cde_url)

    try:
        # Create project
        project = cde.create_project(
            name=args.project_name,
            description="Automated cost estimation pipeline",
        )
        project_id = project["id"]
        logger.info(f"Project created: {project_id}")

        # Add members
        cde.add_member(project_id, "Orchestrator", "lead_appointed", "AI Pipeline")
        cde.add_member(project_id, "Human Reviewer", "appointing_party", "Client")
        logger.info("Members added")

        # Create IFC container and upload
        container = cde.create_container(
            project_id=project_id,
            name=ifc_path.stem,
            container_type="ifc_model",
            description=f"IFC model: {ifc_path.name}",
        )
        container_id = container["id"]
        cde.upload_revision(container_id, ifc_path, "Task Team")
        logger.info(f"IFC container created: {container_id}")

    finally:
        cde.close()

    # ----------------------------------------------------------
    # Step 2: Run pipeline
    # ----------------------------------------------------------
    logger.info("Starting agent pipeline...")
    result = run_pipeline(
        project_id=project_id,
        ifc_container_id=container_id,
        ifc_path=str(ifc_path),
        cde_base_url=args.cde_url,
    )

    # ----------------------------------------------------------
    # Step 3: Print results
    # ----------------------------------------------------------
    print("\n" + "=" * 60)
    print("PIPELINE RESULTS")
    print("=" * 60)

    print(f"\nPhase: {result.get('current_phase', 'unknown')}")

    if result.get("error"):
        print(f"Error: {result['error']}")

    if result.get("loin_report"):
        report = result["loin_report"]
        status = "PASSED" if report.get("passed") else "FAILED"
        print(f"\n--- LOIN Verification: {status} ---")
        for rule in report.get("rules", []):
            print(f"  [{rule.get('status', '?')}] {rule.get('name', '?')}: {rule.get('message', '')}")
        print(f"  Recommendation: {report.get('recommendation', 'N/A')}")

    if result.get("quantity_report"):
        report = result["quantity_report"]
        print(f"\n--- Quantity Report ---")
        print(f"  Total elements: {report.get('total_elements', 0)}")
        for cat in report.get("categories", []):
            print(f"  {cat.get('category', '?')}: {cat.get('count', 0)} items")

    if result.get("draft_estimate"):
        estimate = result["draft_estimate"]
        total = estimate.get("total_estimated_cost", 0)
        items = estimate.get("items", [])
        flagged = estimate.get("flagged_items", [])
        print(f"\n--- Draft Cost Estimate ---")
        print(f"  Total estimated cost: R$ {total:,.2f}")
        print(f"  Classified items: {len(items)}")
        print(f"  Flagged for review: {len(flagged)}")

    # Print audit trail
    print(f"\n--- Audit Trail ---")
    cde = CDEClient(args.cde_url)
    try:
        audit = cde.list_audit(project_id)
        for entry in audit:
            print(f"  [{entry.get('action', '?')}] {entry.get('actor_name', '?')}: {entry.get('details', '')[:80]}")
    finally:
        cde.close()

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
