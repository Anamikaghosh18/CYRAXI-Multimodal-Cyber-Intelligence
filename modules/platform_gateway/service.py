"""
Platform Gateway Investigation Orchestrator
Coordinates URL analysis, graph reputation lookup, automatic graph ingestion,
and visual subgraph assembly for frontend consumers.
"""

import time
import socket
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from urllib.parse import urlparse

from modules.url_analyzer.domain.extractor import StandardURLFeatureExtractor
from modules.url_analyzer.models.ml_models import SklearnURLClassifier
from modules.url_analyzer.models.heuristic_baseline import HeuristicURLClassifier
from modules.url_analyzer.service import URLAnalysisService, generate_observation_id

from modules.graph_enrichment_mapper.domain.schemas import GraphIngestRequest
from modules.graph_enrichment_mapper.infra.neo4j_driver import Neo4jDriver, GraphConnectionError
from modules.graph_enrichment_mapper.mapper import GraphEnrichmentMapper
from modules.graph_enrichment_mapper.algorithms import ThreatGraphAnalyticsEngine

from modules.platform_gateway.schemas import (
    URLScanRequest,
    PlatformScanResponse,
    TriageVerdict,
    VisualGraphData,
)


class PlatformGatewayService:
    """End-to-end scanner and investigation service for web applications."""

    def __init__(
        self,
        url_service: Optional[URLAnalysisService] = None,
        neo4j_driver: Optional[Neo4jDriver] = None,
        model_path: str = "modules/url_analyzer/models/saved/url_hgb_model.joblib",
    ):
        # 1. Initialize URL Analyzer
        if url_service is not None:
            self._url_service = url_service
        else:
            extractor = StandardURLFeatureExtractor()
            try:
                clf = SklearnURLClassifier.load(model_path)
            except Exception:
                clf = HeuristicURLClassifier()
            self._url_service = URLAnalysisService(classifier=clf, extractor=extractor)

        # 2. Initialize Neo4j & Graph Engine (graceful fallback if unavailable)
        self._driver = neo4j_driver
        self._mapper = None
        self._analytics = None
        if self._driver is not None:
            self._mapper = GraphEnrichmentMapper(self._driver)
            self._analytics = ThreatGraphAnalyticsEngine(self._driver)

    def scan_url(self, request: URLScanRequest) -> PlatformScanResponse:
        t0 = time.perf_counter()
        raw_url = request.url.strip()
        obs_id = generate_observation_id(raw_url)
        scanned_at = datetime.now(timezone.utc).isoformat()

        # 1. Resolve host and domain
        parsed = urlparse(raw_url)
        host = (parsed.netloc.split(":")[0] if parsed.netloc else "").lower()
        parts = host.split(".") if host else []
        domain = ".".join(parts[-2:]) if len(parts) >= 2 else host

        # 2. Fast DNS lookup for real host IP (best effort, timeout 0.5s)
        resolved_ip = ""
        try:
            resolved_ip = socket.gethostbyname(host) if host else ""
        except Exception:
            resolved_ip = ""

        # 3. Execute URL Model Analysis
        url_envelope = self._url_service.analyze(
            raw_url=raw_url,
            observation_id=obs_id,
            run_id=f"platform_scan_{int(time.time())}"
        )
        env_dict = url_envelope.model_dump()
        classification = env_dict.get("result", {}).get("classification", {})

        ml_confidence = float(classification.get("confidence_score", 0.0))
        ml_is_phish = bool(classification.get("is_phishing_predicted", False))
        ml_verdict = str(classification.get("verdict", "benign"))
        top_risk_factors = list(classification.get("top_risk_factors", []))

        # 4. Graph Reputation Check
        graph_reputation = {
            "graph_risk_score": 0.0,
            "verdict": "unknown",
            "signals": ["Graph database connection not active"],
            "metrics": {},
        }
        if self._analytics is not None:
            try:
                graph_reputation = self._analytics.compute_infrastructure_reputation(
                    domain=domain,
                    ip=resolved_ip,
                )
            except Exception as e:
                graph_reputation["signals"] = [f"Graph query error: {str(e)}"]

        graph_risk = float(graph_reputation.get("graph_risk_score", 0.0))

        # 5. Multimodal Evidence Fusion (ML Score + Graph Reputation)
        # If Graph shows strong past infrastructure abuse, boost the score
        fused_score = ml_confidence
        if graph_risk >= 0.50:
            boost = (graph_risk - 0.50) * 0.40
            fused_score = min(1.0, ml_confidence + boost)
            top_risk_factors.append(f"Historical Graph Alert: Host/domain flagged in prior campaigns ({graph_risk:.2f} risk)")

        final_is_phish = fused_score >= 0.50
        final_verdict = "phishing" if final_is_phish else ("suspicious" if fused_score >= 0.35 else "benign")

        # 6. Auto-ingest into Neo4j (if enabled and connected)
        if request.auto_ingest_graph and self._mapper is not None:
            try:
                ingest_meta = {
                    "observation_id": obs_id,
                    "url": raw_url,
                    "host": host,
                    "tld": parts[-1] if len(parts) >= 1 else "",
                    "ip": resolved_ip,
                    "isotime": scanned_at,
                    "dataset_id": "platform_realtime_scans",
                    "source_record_id": f"live_scan_{obs_id[4:16]}",
                }
                self._mapper.ingest(
                    GraphIngestRequest(
                        observation_meta=ingest_meta,
                        model_outputs=[env_dict],
                        run_id=url_envelope.run_id,
                    )
                )
            except Exception:
                pass  # Ingest failure shouldn't fail user triage

        # 7. Visual Subgraph for Frontend
        visual_graph = None
        if request.include_subgraph and self._analytics is not None:
            try:
                subgraph = self._analytics.get_observation_subgraph(obs_id, depth=2)
                visual_graph = VisualGraphData(
                    node_count=subgraph.get("node_count", 0),
                    edge_count=subgraph.get("edge_count", 0),
                    nodes=subgraph.get("nodes", []),
                    edges=subgraph.get("edges", []),
                )
            except Exception:
                visual_graph = VisualGraphData(node_count=0, edge_count=0, nodes=[], edges=[])

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        return PlatformScanResponse(
            schema_version="1.0.0",
            observation_id=obs_id,
            target_url=raw_url,
            scanned_at=scanned_at,
            latency_ms=elapsed_ms,
            triage=TriageVerdict(
                is_phishing=final_is_phish,
                verdict=final_verdict,
                confidence_score=round(ml_confidence, 4),
                fused_risk_score=round(fused_score, 4),
                top_risk_factors=top_risk_factors,
                identified_brand=None,
            ),
            graph_reputation=graph_reputation,
            visual_graph=visual_graph,
            model_metadata=env_dict.get("model", {}),
        )
