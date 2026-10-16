"""
Graph Enrichment Mapper & Platform Intelligence API Server
Exposes graph ingestion, algorithm queries, and unified platform scan endpoints.

Key Endpoints:
  POST /api/v1/platform/scan             — Unified end-to-end scan & triage (ML + Graph + Subgraph)
  GET  /api/v1/graph/subgraph/{obs_id}   — Visual ego-network for React Flow / Cytoscape.js
  GET  /api/v1/graph/reputation          — Infrastructure risk score (domain, ip, asn)
  GET  /api/v1/graph/campaigns/clusters  — Multi-brand campaign rings & infrastructure clusters
  GET  /api/v1/graph/analytics/overview  — Dashboard stats (top brands, abusive ASNs, countries)
  POST /api/v1/graph/ingest              — Ingest an observation + envelopes into Neo4j
  GET  /health                           — Liveness & Neo4j connectivity
"""

import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from modules.graph_enrichment_mapper.domain.schemas import (
    GraphIngestRequest,
    GraphIngestResponse,
)
from modules.graph_enrichment_mapper.infra.neo4j_driver import Neo4jDriver, GraphConnectionError
from modules.graph_enrichment_mapper.mapper import GraphEnrichmentMapper
from modules.graph_enrichment_mapper.algorithms import ThreatGraphAnalyticsEngine

from modules.platform_gateway.schemas import URLScanRequest, PlatformScanResponse
from modules.platform_gateway.service import PlatformGatewayService


def create_app() -> FastAPI:
    """Application factory for the Graph & Platform Intelligence API."""

    app = FastAPI(
        title="CYRAXI Threat Intelligence & Knowledge Graph API",
        version="2.0.0",
        description=(
            "Central API for the CYRAXI Threat Platform. Provides real-time URL triage, "
            "graph-assisted threat reputation scoring, campaign clustering, "
            "and visual subgraph generation for web frontends."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── State holding singletons (lazily initialized) ──────────────────────
    _state: Dict[str, Any] = {
        "driver": None,
        "mapper": None,
        "analytics": None,
        "gateway": None,
        "error": None,
    }

    def _init_components():
        if _state["gateway"] is not None:
            return
        # Try connecting to Neo4j
        try:
            driver = Neo4jDriver()
            driver.apply_schema_constraints()
            _state["driver"] = driver
            _state["mapper"] = GraphEnrichmentMapper(driver)
            _state["analytics"] = ThreatGraphAnalyticsEngine(driver)
        except Exception as exc:
            _state["error"] = str(exc)

        # Gateway can work even if driver is None (gracefully falls back to pure ML)
        _state["gateway"] = PlatformGatewayService(
            neo4j_driver=_state["driver"],
        )

    # ── Health ─────────────────────────────────────────────────────────────
    @app.get("/health", tags=["System"])
    def health():
        _init_components()
        neo4j_ok = False
        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        detail = _state.get("error", "not connected")
        if _state.get("driver"):
            try:
                _state["driver"].run_query("RETURN 1 AS ping")
                neo4j_ok = True
                detail = "connected"
            except Exception as exc:
                detail = str(exc)

        return {
            "status": "healthy" if neo4j_ok else "degraded",
            "module": "cyraxi_platform_api",
            "neo4j_uri": neo4j_uri,
            "neo4j_status": "connected" if neo4j_ok else f"unavailable ({detail})",
            "features_active": [
                "url_hgb_model",
                "explainability_engine",
                "graph_algorithms" if neo4j_ok else "graph_fallback_mode",
            ],
        }

    # ── 1. UNIFIED PLATFORM SCAN (Primary Web Hook) ────────────────────────
    @app.post(
        "/api/v1/platform/scan",
        response_model=PlatformScanResponse,
        status_code=status.HTTP_200_OK,
        summary="Unified URL Scan & Threat Triage",
        description=(
            "The primary endpoint for web applications. Takes a URL, analyzes it with ML models, "
            "checks graph infrastructure reputation, auto-ingests into Neo4j, "
            "and returns a visual graph canvas ready for Cytoscape.js/React Flow."
        ),
        tags=["Platform Triage"],
    )
    def platform_scan(request: URLScanRequest):
        _init_components()
        gateway: PlatformGatewayService = _state["gateway"]
        return gateway.scan_url(request)

    # ── 2. VISUAL SUBGRAPH EXPORTER (For Web Graph View) ───────────────────
    @app.get(
        "/api/v1/graph/subgraph/{observation_id}",
        status_code=status.HTTP_200_OK,
        summary="Visual Subgraph for an Observation",
        description="Returns nodes & edges formatted directly for Cytoscape.js / React Flow canvas.",
        tags=["Graph Intelligence"],
    )
    def get_subgraph(observation_id: str, depth: int = Query(default=2, ge=1, le=3)):
        _init_components()
        if not _state["analytics"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Neo4j is not connected: {_state['error']}",
            )
        return _state["analytics"].get_observation_subgraph(observation_id, depth=depth)

    # ── 3. THREAT REPUTATION SCORING ───────────────────────────────────────
    @app.get(
        "/api/v1/graph/reputation",
        status_code=status.HTTP_200_OK,
        summary="Infrastructure Threat Reputation Check",
        description="Calculates empirical graph risk score (0.0 to 1.0) based on historical connectivity.",
        tags=["Graph Intelligence"],
    )
    def check_reputation(
        domain: Optional[str] = None,
        ip: Optional[str] = None,
        asn: Optional[str] = None,
    ):
        _init_components()
        if not _state["analytics"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Neo4j is not connected: {_state['error']}",
            )
        return _state["analytics"].compute_infrastructure_reputation(domain=domain, ip=ip, asn=asn)

    # ── 4. CAMPAIGN CLUSTER DISCOVERY ──────────────────────────────────────
    @app.get(
        "/api/v1/graph/campaigns/clusters",
        status_code=status.HTTP_200_OK,
        summary="Discover Infrastructure Campaign Clusters",
        description="Groups observations into clusters sharing IPs, ASNs, or kits targeting multiple brands.",
        tags=["Threat Intelligence"],
    )
    def discover_clusters(min_size: int = Query(default=2, ge=1), limit: int = Query(default=20, le=100)):
        _init_components()
        if not _state["analytics"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Neo4j is not connected: {_state['error']}",
            )
        clusters = _state["analytics"].discover_campaign_clusters(min_size=min_size, limit=limit)
        return {"total_clusters": len(clusters), "clusters": clusters}

    # ── 5. DASHBOARD OVERVIEW METRICS ──────────────────────────────────────
    @app.get(
        "/api/v1/graph/analytics/overview",
        status_code=status.HTTP_200_OK,
        summary="Threat Dashboard Analytics Overview",
        description="Aggregated statistics for landing dashboards: top brands, abusive ASNs, countries.",
        tags=["Threat Intelligence"],
    )
    def analytics_overview():
        _init_components()
        if not _state["analytics"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Neo4j is not connected: {_state['error']}",
            )
        return _state["analytics"].get_dashboard_analytics_overview()

    # ── 6. GRAPH INGESTION ─────────────────────────────────────────────────
    @app.post(
        "/api/v1/graph/ingest",
        response_model=GraphIngestResponse,
        status_code=status.HTTP_200_OK,
        summary="Ingest observation & envelopes into graph",
        tags=["Graph Ingestion"],
    )
    def ingest_observation(request: GraphIngestRequest):
        _init_components()
        if not _state["mapper"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Neo4j is not connected: {_state['error']}",
            )
        try:
            result = _state["mapper"].ingest(request)
            return GraphIngestResponse(status="success", result=result)
        except Exception as exc:
            return GraphIngestResponse(status="error", error=str(exc))

    # ── 7. ENTITY LOOKUP QUERIES ───────────────────────────────────────────
    @app.get("/api/v1/graph/brand/{brand_name}", tags=["Graph Queries"])
    def query_by_brand(brand_name: str, limit: int = 50):
        _init_components()
        if not _state["driver"]:
            raise HTTPException(status_code=503, detail="Neo4j not connected")
        rows = _state["driver"].run_query(
            """
            MATCH (o:Observation)-[:TARGETS_BRAND]->(b:Brand)
            WHERE toLower(b.name) CONTAINS toLower($brand_name)
               OR toLower(b.brand_id) CONTAINS toLower($brand_name)
            OPTIONAL MATCH (o)-[:CAPTURED_URL]->(u:URL)
            RETURN o.observation_id AS observation_id, o.captured_at AS captured_at,
                   b.name AS brand, u.raw_url AS url
            ORDER BY o.captured_at DESC LIMIT $limit
            """,
            {"brand_name": brand_name, "limit": limit},
        )
        return {"brand": brand_name, "count": len(rows), "observations": rows}

    @app.get("/api/v1/graph/ip/{ip_address}", tags=["Graph Queries"])
    def query_by_ip(ip_address: str, limit: int = 50):
        _init_components()
        if not _state["driver"]:
            raise HTTPException(status_code=503, detail="Neo4j not connected")
        rows = _state["driver"].run_query(
            """
            MATCH (o:Observation)-[:CAPTURED_URL]->(u:URL)-[:HOSTED_ON]->(d:Domain)-[:RESOLVED_TO]->(i:IPAddress {ip: $ip})
            OPTIONAL MATCH (o)-[:TARGETS_BRAND]->(b:Brand)
            RETURN o.observation_id AS observation_id, o.captured_at AS captured_at,
                   d.name AS domain, b.name AS brand, u.raw_url AS url
            ORDER BY o.captured_at DESC LIMIT $limit
            """,
            {"ip": ip_address, "limit": limit},
        )
        return {"ip": ip_address, "count": len(rows), "observations": rows}

    return app


# Default app instance for ASGI servers
app = create_app()
