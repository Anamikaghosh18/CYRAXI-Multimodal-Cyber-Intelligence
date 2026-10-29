"""
Investigation API Server
Exposes investigation workflow endpoints for the frontend.
"""

import os
from typing import List, Literal
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from modules.investigation.service import InvestigationService
from modules.investigation.persistence import InvestigationPersistence
from modules.graph_enrichment_mapper.infra.neo4j_driver import Neo4jDriver, GraphConnectionError
from modules.dataset_adapter.s3_artifacts import load_project_env


class ArchiveExperimentRequest(BaseModel):
    mode: Literal["random", "selected"] = "selected"
    observation_ids: List[str] = Field(default_factory=list, max_length=20)
    count: int = Field(default=3, ge=1, le=20)
    limit_related: int = Field(default=10, ge=1, le=50)


def create_app() -> FastAPI:
    """Application factory for the Investigation API service."""

    app = FastAPI(
        title="CYRAXI Investigation API",
        version="1.0.0",
        description="End-to-end cybercrime investigation workflow API",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Lazy initialization
    _state = {"service": None, "persistence": None, "error": None}

    def _get_service():
        load_project_env()
        if _state["service"] is not None:
            return _state["service"]
        if _state["error"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Service unavailable: {_state['error']}",
            )
        try:
            neo4j_driver = Neo4jDriver()
            neo4j_driver.connect()
            service = InvestigationService(
                archive_path=os.getenv("PHISHPEDIA_ARCHIVE_PATH", "data/phish_sample_30k.zip"),
                neo4j_driver=neo4j_driver,
            )
            persistence = InvestigationPersistence(
                neo4j_driver=neo4j_driver,
                output_dir="output/investigations",
            )
            _state["service"] = service
            _state["persistence"] = persistence
        except GraphConnectionError as exc:
            _state["error"] = str(exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            )
        return _state["service"]

    @app.on_event("shutdown")
    def close_services():
        if _state.get("service") is not None:
            if _state["service"]._artifact_archive is not None:
                _state["service"]._artifact_archive.close()
            artifact_source = _state["service"]._artifact_source
            storage_client = getattr(artifact_source, "client", None)
            if storage_client is not None:
                storage_client.close()
            _state["service"].neo4j_driver.close()

    @app.get("/health", tags=["Health"])
    def health():
        return {
            "status": "healthy" if _state["service"] else "degraded",
            "module": "investigation_api",
            "detail": _state.get("error", "ready"),
        }

    @app.post(
        "/api/v1/investigation/analyze",
        tags=["Investigation"],
    )
    def investigate(
        input_value: str,
        input_type: str = "observation_id",
        limit_related: int = 10,
    ):
        """Run investigation on observation ID or URL."""
        service = _get_service()

        report = service.investigate(
            input_value=input_value,
            input_type=input_type,
            limit_related=limit_related,
        )

        # Persist to filesystem
        if _state["persistence"]:
            _state["persistence"].persist(report, neo4j=False, filesystem=True)

        return report

    @app.get("/api/v1/investigation/archive/observations", tags=["Archive Experiments"])
    def list_archive_observations(
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        search: str = Query(default="", max_length=200),
    ):
        """Browse the indexed attack records stored in Neo4j."""
        try:
            service = _get_service()
            return service.list_database_observations(limit=limit, offset=offset, search=search)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Attack database unavailable: {type(exc).__name__}: {exc}",
            )

    @app.post("/api/v1/investigation/archive/run", tags=["Archive Experiments"])
    def run_archive_experiment(request: ArchiveExperimentRequest):
        """Run analysis for a random archive sample or explicitly selected records."""
        service = _get_service()
        if request.mode == "random":
            observations = service.sample_database_observations(request.count)
            requested_ids = [obs.get("observation_id") for obs in observations]
        else:
            requested_ids = list(dict.fromkeys(request.observation_ids))
            if not requested_ids:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Select at least one archive record or choose random sampling.",
                )
            if len(requested_ids) > 20:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="A single archive experiment can include at most 20 records.",
                )
            found = service.get_database_observations(requested_ids)
            observations = [found[obs_id] for obs_id in requested_ids if obs_id in found]

        reports = []
        found_ids = {observation["observation_id"] for observation in observations}
        persistence = _state["persistence"]
        for observation in observations:
            observation_id = observation["observation_id"]
            try:
                report = service.investigate(
                    input_value=observation_id,
                    input_type="observation_id",
                    limit_related=request.limit_related,
                    observation_data=observation,
                )
                if persistence:
                    persistence.persist(report, neo4j=False, filesystem=True)
                reports.append({
                    "investigation_id": report["investigation_id"],
                    "observation_id": observation_id,
                    "input_value": report["input_value"],
                    "status": report["status"],
                    "created_at": report["created_at"],
                    "runtime_ms": report.get("execution_metadata", {}).get("total_runtime_ms"),
                    "target_brand": (observation.get("label") or {}).get("ground_truth", {}).get("target_brand"),
                    "domain": (observation.get("url") or {}).get("domain"),
                    "related_count": len(report.get("related_observations", [])),
                    "module_statuses": {
                        name: (result or {}).get("status")
                        for name, result in report.get("module_results", {}).items()
                        if name != "graph_persistence"
                    },
                    "graph_status": (report.get("module_results", {}).get("graph_persistence") or {}).get("status"),
                    "warning_count": len(report.get("warnings", [])),
                })
            except Exception as exc:
                reports.append({
                    "observation_id": observation_id,
                    "target_brand": (observation.get("label") or {}).get("ground_truth", {}).get("target_brand"),
                    "domain": (observation.get("url") or {}).get("domain"),
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "module_statuses": {},
                    "warning_count": 1,
                })

        missing_ids = [obs_id for obs_id in requested_ids if obs_id not in found_ids]
        return {
            "mode": request.mode,
            "requested_count": request.count if request.mode == "random" else len(requested_ids),
            "completed_count": sum(result.get("status") != "error" for result in reports),
            "failed_count": sum(result.get("status") == "error" for result in reports),
            "limit_related": request.limit_related,
            "results": reports,
            "missing_observation_ids": missing_ids,
        }

    @app.get(
        "/api/v1/investigation/{investigation_id}",
        tags=["Investigation"],
    )
    def get_investigation(investigation_id: str):
        """Retrieve a saved investigation report."""
        from pathlib import Path
        import json

        report_path = Path("output/investigations") / f"{investigation_id}.json"

        if not report_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation {investigation_id} not found",
            )

        with open(report_path, "r") as f:
            return json.load(f)

    @app.get(
        "/api/v1/investigation",
        tags=["Investigation"],
    )
    def list_investigations(limit: int = 50):
        """List recent investigations."""
        from pathlib import Path
        import json

        output_dir = Path("output/investigations")
        if not output_dir.exists():
            return {"investigations": []}

        investigations = []
        for filepath in sorted(output_dir.glob("*.json"), reverse=True)[:limit]:
            try:
                with open(filepath, "r") as f:
                    report = json.load(f)
                    investigations.append({
                        "investigation_id": report["investigation_id"],
                        "observation_id": report["observation_id"],
                        "input_type": report["input_type"],
                        "input_value": report["input_value"],
                        "status": report["status"],
                        "created_at": report["created_at"],
                        "related_count": len(report.get("related_observations", [])),
                        "runtime_ms": report.get("execution_metadata", {}).get("total_runtime_ms"),
                    })
            except Exception:
                continue

        return {"investigations": investigations}

    return app


app = create_app()
