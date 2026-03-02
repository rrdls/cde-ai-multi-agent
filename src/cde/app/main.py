"""CDE PoC FastAPI Application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_db
from app.routers import projects, containers, transitions, audit


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on startup."""
    await init_db()
    yield


app = FastAPI(
    title="CDE PoC API",
    description=(
        "Simplified Common Data Environment proof-of-concept implementing "
        "ISO 19650 governance concepts: Information Containers, Governance "
        "States (WIP/Shared/Published/Archived), State Transitions with "
        "human-in-the-loop approval, and immutable Audit Trails."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(projects.router)
app.include_router(containers.router)
app.include_router(transitions.router)
app.include_router(audit.router)


@app.get("/", tags=["Health"])
async def root():
    """Health check."""
    return {"status": "ok", "service": "CDE PoC API", "version": "0.1.0"}
