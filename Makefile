# =============================================================================
# CYRAXI Multimodal Phishing Intelligence Platform - Developer Automation
# =============================================================================

PYTHON ?= .venv/Scripts/python.exe
PYTEST ?= .venv/Scripts/pytest.exe
UVICORN ?= .venv/Scripts/uvicorn.exe

.PHONY: help test test-v start-infra stop-infra restart-infra pipeline pipeline-dry serve-backend serve-url lint clean

help:
	@echo "CYRAXI Platform Automation Commands:"
	@echo "  make test           - Run full test suite"
	@echo "  make test-v         - Run test suite with verbose output"
	@echo "  make start-infra    - Launch Neo4j and RustFS in docker"
	@echo "  make stop-infra     - Stop local infrastructure containers"
	@echo "  make pipeline       - Execute pipeline bridge (dataset -> URL -> Neo4j)"
	@echo "  make pipeline-dry   - Dry-run pipeline without Neo4j writes"
	@echo "  make serve-backend  - Start Investigation and Graph APIs"
	@echo "  make serve-url      - Start standalone URL Intelligence API"
	@echo "  make clean          - Remove temporary and cached files"

test:
	$(PYTEST) -q

test-v:
	$(PYTEST) -v

start-infra:
	docker compose up -d

stop-infra:
	docker compose down

restart-infra:
	docker compose down && docker compose up -d

pipeline:
	$(PYTHON) run_pipeline.py --limit 100

pipeline-dry:
	$(PYTHON) run_pipeline.py --dry-run --limit 10

serve-backend:
	$(PYTHON) backend_main.py

serve-url:
	$(UVICORN) modules.url_analyzer.api.server:app --host 127.0.0.1 --port 8000 --reload

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
