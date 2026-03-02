"""Interactive chat CLI for the CDE multi-agent system.

Usage:
    python chat.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add src/ to path
_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "src"))

load_dotenv(_ROOT / ".env")

from agents.orchestrator import build_supervisor  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("chat")


def main() -> None:
    print("=" * 60)
    print("  CDE Multi-Agent Chat")
    print("  Agents: IFC | SINAPI | CDE")
    print("  Type 'quit' or 'exit' to end")
    print("=" * 60)
    print()

    graph = build_supervisor()
    messages = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "sair"):
            print("Bye!")
            break

        messages.append({"role": "user", "content": user_input})

        try:
            result = graph.invoke({"messages": messages})

            # Extract the last AI message
            response_messages = result.get("messages", [])
            assistant_reply = None
            for msg in reversed(response_messages):
                content = getattr(msg, "content", None)
                if content and not getattr(msg, "tool_calls", None):
                    assistant_reply = content
                    break

            if assistant_reply:
                print(f"\nAssistant: {assistant_reply}\n")
                messages.append({"role": "assistant", "content": assistant_reply})
            else:
                print("\nAssistant: (no response)\n")

        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    main()
