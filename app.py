"""Chainlit frontend for the CDE Multi-Agent system."""

import sys
from pathlib import Path

# Add src/ to path
_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "src"))

import chainlit as cl
from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")

from agents.orchestrator import build_supervisor
from langchain_core.messages import HumanMessage, AIMessage


@cl.on_chat_start
async def on_chat_start():
    # Build the multi-agent graph (Supervisor)
    graph = build_supervisor()
    cl.user_session.set("graph", graph)
    cl.user_session.set("messages", [])

    await cl.Message(
        content="Welcome to the CDE Multi-Agent Chat!\n\nI am the Supervisor. I can help you with:\n"
        "- **IFC Verification & Extraction** (IDS validation, compliance checks, quantities)\n"
        "- **Document Retrieval** (project specifications, technical documents)\n"
        "- **CDE Governance** (ISO 19650 state transitions, audits)\n\n"
        "How can I help you today?"
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    graph = cl.user_session.get("graph")
    messages = cl.user_session.get("messages")

    # Add the user's message to the state
    messages.append(HumanMessage(content=message.content))

    # Create an empty message to stream or update the response
    msg = cl.Message(content="Thinking...")
    await msg.send()

    try:
        # Use ainvoke since agent nodes are async (MCP tools are async-only)
        result = await graph.ainvoke({"messages": messages})

        # Extract the last AI message
        response_messages = result.get("messages", [])
        assistant_reply = None
        
        # Traverse backwards to find the last AI message that is not a tool call
        for r_msg in reversed(response_messages):
            if isinstance(r_msg, AIMessage):
                content = getattr(r_msg, "content", None)
                if content and not getattr(r_msg, "tool_calls", None):
                    assistant_reply = content
                    break

        if assistant_reply:
            msg.content = assistant_reply
            await msg.update()
            # Save the assistant's reply in the session history
            messages.append(AIMessage(content=assistant_reply))
        else:
            msg.content = "(no response)"
            await msg.update()

    except Exception as e:
        msg.content = f"Error: {e}"
        await msg.update()
