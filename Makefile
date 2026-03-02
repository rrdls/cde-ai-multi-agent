.PHONY: up down api seed pipeline install

# -------------------------------------------------------
# Infrastructure
# -------------------------------------------------------

up: ## Start Qdrant (Docker)
	docker compose up -d
	@echo "Qdrant running on http://localhost:6333"

down: ## Stop Qdrant
	docker compose down

# -------------------------------------------------------
# Python environment
# -------------------------------------------------------

install: ## Install all dependencies in venv
	pip install -r requirements.txt
	@echo "Dependencies installed"

# -------------------------------------------------------
# CDE API
# -------------------------------------------------------

api: ## Start CDE API (FastAPI)
	cd src/cde && uvicorn app.main:app --reload --port 8000

# -------------------------------------------------------
# Data seeding (run once)
# -------------------------------------------------------

seed: ## Seed PDF specs into Qdrant (skips if collection exists)
	python src/chunks/seed_qdrant_specs.py --project ubs-porte-1

seed-force: ## Force re-seed (recreates collection)
	python src/chunks/seed_qdrant_specs.py --project ubs-porte-1 --overwrite

# -------------------------------------------------------
# Agent pipeline
# -------------------------------------------------------

chat: ## Start interactive multi-agent chat
	python chat.py

pipeline: ## Run the full agent pipeline (batch mode)
	python run_pipeline.py --ifc $(IFC)

# Usage: make pipeline IFC=data/ubs-porte-1/ifc/model.ifc
