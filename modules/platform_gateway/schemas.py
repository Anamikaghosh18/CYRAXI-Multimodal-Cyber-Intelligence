"""
Schemas for Platform Gateway & Web Integration
Structured responses tailored for web frontends, threat triage dashboards, and SIEM connectors.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class URLScanRequest(BaseModel):
    """Payload sent by the website search bar / API."""
    url: str = Field(..., description="Target URL to inspect and triage")
    include_subgraph: bool = Field(default=True, description="Whether to include visual nodes and edges")
    auto_ingest_graph: bool = Field(default=True, description="Whether to store this observation in Neo4j")


class TriageVerdict(BaseModel):
    is_phishing: bool
    verdict: str  # "phishing" | "suspicious" | "benign"
    confidence_score: float
    fused_risk_score: float  # Blends ML confidence + Graph historical reputation
    top_risk_factors: List[str]
    identified_brand: Optional[str] = None


class VisualGraphData(BaseModel):
    node_count: int
    edge_count: int
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


class PlatformScanResponse(BaseModel):
    schema_version: str = "1.0.0"
    observation_id: str
    target_url: str
    scanned_at: str
    latency_ms: float
    triage: TriageVerdict
    graph_reputation: Dict[str, Any]
    visual_graph: Optional[VisualGraphData] = None
    model_metadata: Dict[str, Any]
