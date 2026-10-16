"""
Graph Enrichment Mapper — FastAPI Server
Exposes graph ingestion and query endpoints for backend team consumption.

Endpoints:
  GET  /health                          — liveness + Neo4j connectivity status
  POST /api/v1/graph/ingest             — ingest one observation into the graph
  POST /api/v1/graph/batch-ingest       — ingest multiple observations
  GET  /api/v1/graph/brand/{brand_name} — all observations targeting a brand
  GET  /api/v1/graph/ip/{ip_address}    — all observations sharing an IP
  GET  /api/v1/graph/campaign/{family_id} — all observations in a campaign cluster
"""

import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from modules.graph_enrichment_mapper.domain.schemas import (
    GraphIngestRequest,
    GraphIngestResponse,
    GraphIngestResult,
)
from modules.graph_enrichment_mapper.infra.neo4j_driver import Neo4jDriver, GraphConnectionError
from modules.graph_enrichment_mapper.mapper import GraphEnrichmentMapper


def create_app() -> FastAPI:
    """Application factory for the Graph Enrichment Mapper FastAPI service."""

    app = FastAPI(
        title="CYRAXI Knowledge Graph Enrichment API",
        version="1.0.0",
        description=(
            "Ingests multimodal ML model outputs into a Neo4j knowledge graph. "
            "Nodes: Observation, URL, Domain, IPAddress, AutonomousSystem, "
            "Brand, ModelRun, Prediction, CampaignCandidate. "
            "Call POST /api/v1/graph/ingest after each URL analysis pipeline run."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Shared Neo4j driver + mapper (lazy init on first request) ──────────
    _state: Dict[str, Any] = {"driver": None, "mapper": None, "error": None}

    def _get_mapper() -> GraphEnrichmentMapper:
        if _state["mapper"] is not None:
            return _state["mapper"]
        if _state["error"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Neo4j unavailable: {_state['error']}",
            )
        try:
            driver = Neo4jDriver()
            driver.apply_schema_constraints()
            _state["driver"] = driver
            _state["mapper"] = GraphEnrichmentMapper(driver)
        except GraphConnectionError as exc:
            _state["error"] = str(exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            )
        return _state["mapper"]

    # ── Health ─────────────────────────────────────────────────────────────
    @app.get("/health", tags=["Health"])
    def health():
        neo4j_ok = False
        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        detail = _state.get("error", "not yet connected")
        if _state.get("driver"):
            try:
                _state["driver"].run_query("RETURN 1 AS ping")
                neo4j_ok = True
                detail = "connected"
            except Exception as exc:
                detail = str(exc)
        return {
            "status":    "healthy" if neo4j_ok else "degraded",
            "module":    "graph_enrichment_mapper",
            "neo4j_uri": neo4j_uri,
            "neo4j":     "connected" if neo4j_ok else f"unavailable: {detail}",
        }

    # ── Ingest single observation ──────────────────────────────────────────
    @app.post(
        "/api/v1/graph/ingest",
        response_model=GraphIngestResponse,
        status_code=status.HTTP_200_OK,
        summary="Ingest one observation into the knowledge graph",
        description=(
            "Accepts observation metadata (from info.txt fields) and a list of "
            "ModelOutputEnvelope dicts. Writes nodes and relationships via MERGE "
            "(idempotent — safe to re-call for the same observation)."
        ),
        tags=["Graph Ingestion"],
    )
    def ingest_observation(request: GraphIngestRequest):
        mapper = _get_mapper()
        try:
            result = mapper.ingest(request)
            return GraphIngestResponse(status="success", result=result)
        except Exception as exc:
            return GraphIngestResponse(status="error", error=str(exc))

    # ── Batch ingest ───────────────────────────────────────────────────────
    @app.post(
        "/api/v1/graph/batch-ingest",
        status_code=status.HTTP_200_OK,
        summary="Batch ingest multiple observations",
        tags=["Graph Ingestion"],
    )
    def batch_ingest(requests: List[GraphIngestRequest]):
        mapper = _get_mapper()
        results = []
        for req in requests:
            try:
                r = mapper.ingest(req)
                results.append({"status": "success", "result": r.model_dump()})
            except Exception as exc:
                results.append({"status": "error", "error": str(exc)})
        return {
            "total": len(results),
            "results": results,
        }

    # ── Query: all observations for a brand ───────────────────────────────
    @app.get(
        "/api/v1/graph/brand/{brand_name}",
        status_code=status.HTTP_200_OK,
        summary="Observations targeting a brand",
        description="Returns all observations that TARGETS_BRAND the given brand name.",
        tags=["Graph Queries"],
    )
    def query_by_brand(brand_name: str, limit: int = 50):
        mapper = _get_mapper()
        rows = mapper._driver.run_query(
            """
            MATCH (o:Observation)-[:TARGETS_BRAND]->(b:Brand)
            WHERE toLower(b.name) CONTAINS toLower($brand_name)
               OR toLower(b.brand_id) CONTAINS toLower($brand_name)
            OPTIONAL MATCH (o)-[:CAPTURED_URL]->(u:URL)
            RETURN o.observation_id AS observation_id,
                   o.captured_at   AS captured_at,
                   b.name          AS brand,
                   u.raw_url       AS url
            ORDER BY o.captured_at DESC
            LIMIT $limit
            """,
            {"brand_name": brand_name, "limit": limit},
        )
        return {"brand": brand_name, "count": len(rows), "observations": rows}

    # ── Query: all observations on an IP ──────────────────────────────────
    @app.get(
        "/api/v1/graph/ip/{ip_address}",
        status_code=status.HTTP_200_OK,
        summary="Observations sharing an IP address",
        description="Returns all observations whose domain resolved to this IP at capture time.",
        tags=["Graph Queries"],
    )
    def query_by_ip(ip_address: str, limit: int = 50):
        mapper = _get_mapper()
        rows = mapper._driver.run_query(
            """
            MATCH (o:Observation)-[:CAPTURED_URL]->(u:URL)-[:HOSTED_ON]->(d:Domain)
                  -[:RESOLVED_TO]->(i:IPAddress {ip: $ip})
            OPTIONAL MATCH (o)-[:TARGETS_BRAND]->(b:Brand)
            RETURN o.observation_id AS observation_id,
                   o.captured_at   AS captured_at,
                   d.name          AS domain,
                   b.name          AS brand,
                   u.raw_url       AS url
            ORDER BY o.captured_at DESC
            LIMIT $limit
            """,
            {"ip": ip_address, "limit": limit},
        )
        return {"ip": ip_address, "count": len(rows), "observations": rows}

    # ── Query: all observations in a campaign cluster ─────────────────────
    @app.get(
        "/api/v1/graph/campaign/{family_id}",
        status_code=status.HTTP_200_OK,
        summary="Observations in a campaign cluster",
        description="Returns all observations linked to the given phishing kit family_id.",
        tags=["Graph Queries"],
    )
    def query_by_campaign(family_id: str, limit: int = 100):
        mapper = _get_mapper()
        rows = mapper._driver.run_query(
            """
            MATCH (o:Observation)-[:SUSPECTED_CAMPAIGN_MEMBER]->(c:CampaignCandidate)
            WHERE c.family_id = $family_id OR c.campaign_id CONTAINS $family_id
            OPTIONAL MATCH (o)-[:CAPTURED_URL]->(u:URL)
            OPTIONAL MATCH (o)-[:TARGETS_BRAND]->(b:Brand)
            RETURN o.observation_id AS observation_id,
                   o.captured_at   AS captured_at,
                   b.name          AS brand,
                   u.raw_url       AS url,
                   c.family_id     AS campaign_family_id
            ORDER BY o.captured_at
            LIMIT $limit
            """,
            {"family_id": family_id, "limit": limit},
        )
        return {"family_id": family_id, "count": len(rows), "observations": rows}

    return app


# Default app instance for ASGI servers
# uvicorn modules.graph_enrichment_mapper.api.server:app --port 8001
app = create_app()
