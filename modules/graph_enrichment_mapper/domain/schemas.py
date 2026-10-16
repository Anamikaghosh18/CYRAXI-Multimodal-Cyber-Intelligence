"""
Graph Enrichment Mapper — Domain Schemas
Pydantic models for graph ingestion request/response payloads.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GraphIngestRequest(BaseModel):
    """
    Payload to ingest one or more model output envelopes into the knowledge graph.

    - observation_meta: raw fields from info.txt (url, brand, ip, asn, asn_name,
      host, tld, country_code, country_name, family_id, isotime, sector)
    - model_outputs: list of canonical ModelOutputEnvelope dicts (one per modality)
    """
    observation_meta: Dict[str, Any] = Field(
        description="Raw observation metadata parsed from info.txt"
    )
    model_outputs: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of canonical ModelOutputEnvelope dicts from all modalities"
    )
    run_id: Optional[str] = "graph_ingest_run"


class NodeRef(BaseModel):
    label: str      # Neo4j node label e.g. "Observation"
    key: str        # property used as unique key e.g. "observation_id"
    value: str      # value of that key


class GraphIngestResult(BaseModel):
    nodes_merged: int
    relationships_merged: int
    observation_id: str
    warnings: List[str] = Field(default_factory=list)


class GraphIngestResponse(BaseModel):
    schema_version: str = "1.0.0"
    status: str  # "success" | "partial" | "error"
    result: Optional[GraphIngestResult] = None
    error: Optional[str] = None
