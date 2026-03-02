# AI-Augmented Common Data Environment

A multi-agent AI architecture for intelligent information management in openBIM projects, built on top of an ISO 19650-compliant CDE platform.

> **Paper:** *AI-Augmented Common Data Environment: A Multi-Agent Architecture for Intelligent Information Management in openBIM Projects* (EC3 2026)

## Architecture Overview

The system comprises two complementary layers:

1. **CDE Platform** (`src/cde/`): A FastAPI REST API implementing ISO 19650 governance (state machine, two-step approval, audit trail).
2. **Multi-Agent Layer** (`src/agents/`): A LangGraph-based Supervisor that routes natural language requests to three specialized agents.

```
User ──► Chainlit Chat UI ──► Supervisor (LangGraph)
                                  ├── IFC Agent ──► IfcOpenShell / IfcTester
                                  ├── RAG Agent ──► Qdrant Vector Store
                                  └── CDE Agent ──► CDE REST API
                                                       └── PostgreSQL
```

### Agent Inventory (27 tools)

| Agent | Tools | Description |
|---|---|---|
| **IFC Agent** | 12 | 5 compliance checks (schema, materials, quantities, spatial structure, classification) + 5 extraction tools (walls, slabs, beams/columns, doors/windows, pipes) + 2 IDS validation tools (`run_ids_check`, `get_ids_report`) |
| **RAG Agent** | 3 | Hybrid search (dense + BM25) over project documents via Qdrant (`search_documents`, `search_specs`, `search_specifications`) |
| **CDE Agent** | 12 | Project CRUD + list, member management, container CRUD + list, file upload/download, state transitions, approval, audit trail |

## Project Structure

```
.
├── app.py                     # Chainlit web chat frontend
├── chat.py                    # CLI chat (alternative to Chainlit)
├── docker-compose.yml         # PostgreSQL + Qdrant services
├── Makefile                   # Common commands
├── requirements.txt           # Python dependencies
├── data/
│   └── ubs-porte-1/           # Sample project data (PDFs, CSVs, chunks)
└── src/
    ├── agents/                # Multi-agent orchestration layer
    │   ├── orchestrator.py    # LangGraph Supervisor graph
    │   ├── ifc_tools.py       # 12 IfcOpenShell + IfcTester tools
    │   ├── rag_tools.py       # 3 Qdrant hybrid search tools
    │   ├── cde_agent.py       # 12 CDE governance tools + agent factory
    │   ├── cde_client.py      # HTTP client wrapping the CDE API
    │   └── llm.py             # LLM factory (OpenRouter)
    ├── cde/                   # CDE Platform (FastAPI)
    │   └── app/
    │       ├── main.py        # FastAPI app with lifespan
    │       ├── config.py      # Settings (DATABASE_URL, etc.)
    │       ├── database.py    # Async SQLAlchemy engine
    │       ├── models/        # ORM models (Project, Container, Transition, Audit)
    │       ├── schemas/       # Pydantic request/response schemas
    │       ├── routers/       # API endpoints (projects, containers, transitions, audit)
    │       └── services/      # Business logic layer
    ├── chunks/                # Document chunking pipeline
    │   ├── chunker.py         # PDF/CSV chunker using Docling
    │   └── seed_qdrant_specs.py  # Seeds chunks into Qdrant
    └── sinapi/                # Qdrant vector store utilities
        ├── qdrant_simple.py   # Hybrid search wrapper (dense + BM25)
        ├── embeddings_factory.py  # Embedding model factory (Ollama/OpenAI)
        └── seed_qdrant.py     # Collection seeding scripts
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- [Ollama](https://ollama.ai) with `qwen3-embedding:0.6b` model (for embeddings)

### 1. Clone and install

```bash
git clone https://github.com/rrdls/cde-ai-multi-agent.git
cd cde-ai-multi-agent
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys:
#   OPENROUTER_API_KEY=...   (for LLM access)
#   MODEL_NAME=...           (e.g., anthropic/claude-haiku-4.5)
```

### 3. Start infrastructure

```bash
docker compose up -d          # Starts PostgreSQL + Qdrant
```

### 4. Start the CDE API

```bash
make api
# or: cd src/cde && uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000` with interactive docs at `/docs`.

### 5. Seed document data (first time only)

```bash
# Pull the embedding model
ollama pull qwen3-embedding:0.6b

# Extract chunks from project PDFs
python -m src.chunks.chunker --project ubs-porte-1

# Seed chunks into Qdrant
make seed
```

### 6. Start the chat interface

```bash
# Web UI (Chainlit)
chainlit run app.py -w

# or CLI
make chat
```

## CDE API Endpoints

The CDE platform exposes 19 REST endpoints:

| Group | Endpoints | Description |
|---|---|---|
| **Projects** | `POST /projects`, `GET /projects`, `GET /projects/{id}`, `GET /projects/{id}/dashboard`, `POST /projects/{id}/members`, `GET /projects/{id}/members`, `DELETE /projects/{id}/members/{mid}` | Project and team management |
| **Containers** | `POST /projects/{id}/containers`, `GET /projects/{id}/containers`, `GET /containers/{id}`, `GET /containers/{id}/revisions`, `POST /containers/{id}/revisions`, `GET /containers/{id}/revisions/{rev}/download` | Information container lifecycle |
| **Transitions** | `POST /containers/{id}/transitions`, `GET /containers/{id}/transitions`, `POST /transitions/{id}/approve`, `POST /transitions/{id}/reject`, `GET /projects/{id}/transitions/pending` | ISO 19650 state machine (WIP → Shared → Published → Archived) |
| **Audit** | `GET /projects/{id}/audit` | Immutable audit trail |

### ISO 19650 Governance Model

Containers follow a strict state machine:

```
WIP ──(requires suitability code)──► SHARED ──► PUBLISHED ──► ARCHIVED
          ↑                              ↑
     two-step approval             two-step approval
```

Every state transition requires:
- A **suitability code** (S0..S7) when moving to Shared
- **Two-step approval**: one actor requests, a different actor approves
- All actions are **immutably logged** in the audit trail

## Demo Walkthrough

This walkthrough reproduces the functional demonstration described in the paper (Section 5). It assumes a project with team members and IFC/IDS files has already been set up. The demo exercises five governance requirements: state machine, suitability codes, two-step approval, audit trail, and agent integration.

### Step 0: Start the services

You need **three terminals** running simultaneously:

```bash
# Terminal 1: Infrastructure (PostgreSQL + Qdrant)
docker compose up -d

# Terminal 2: CDE API (port 8000)
cd src/cde && python -m uvicorn app.main:app --reload --port 8000

# Terminal 3: Chat interface (port 8001)
chainlit run app.py -w --port 8001
```

Open `http://localhost:8001` in your browser.

### Step 1: Explore the project

Start by querying the existing project data:

> List all projects

> List the members of the UBS Porte 1 project

> List all containers in the project

The CDE Agent uses `list_projects`, `list_members`, and `list_containers` to return the project's current state, team composition, and uploaded files.

### Step 2: Run IDS validation (agent integration ✅)

> Validate the IFC model against the IDS specification

The Supervisor routes this to the **IFC Agent**, which downloads the IFC and IDS files from the CDE, runs IfcTester, and returns structured results:
- ✅ Walls must have material → PASS
- ❌ Doors must have material → FAIL
- ✅ Slabs must have material → PASS

### Step 3: Share without suitability code (suitability codes ✅)

> Share the IFC Model container with the team

The CDE Agent attempts a WIP → Shared transition. The platform **rejects** it because no suitability code was provided.

### Step 4: Share with code S2 (state machine ✅ + two-step approval ✅)

> Share the IFC Model container with suitability code S2

The transition is created as **pending**, requiring a second actor to approve it.

### Step 5: Approve transition

> Approve the pending transition as Diego Calvetti

The container state changes from WIP to Shared.

### Step 6: Audit trail (audit trail ✅)

> Show the audit trail for the project

All actions (creates, uploads, transitions, approvals) are listed chronologically.

## Technology Stack

| Component | Technology |
|---|---|
| CDE Backend | FastAPI, SQLAlchemy (async), PostgreSQL |
| Agent Framework | LangGraph, LangChain |
| LLM Access | OpenRouter (any model) |
| IFC Processing | IfcOpenShell, IfcTester (IDS validation) |
| Vector Store | Qdrant (hybrid: dense + BM25 sparse) |
| Embeddings | Ollama (`qwen3-embedding:0.6b`, 1024-dim) |
| Document Chunking | Docling |
| Chat Frontend | Chainlit |
| Infrastructure | Docker Compose |

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `OPENROUTER_API_KEY` | API key for OpenRouter LLM access | (required) |
| `MODEL_NAME` | LLM model identifier | `anthropic/claude-haiku-4.5` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://cde:cde@localhost:5432/cde` |
| `CDE_API_URL` | CDE backend URL | `http://localhost:8000` |
| `OLLAMA_BASE_URL` | Ollama API URL | `http://localhost:11434` |

## License

MIT
