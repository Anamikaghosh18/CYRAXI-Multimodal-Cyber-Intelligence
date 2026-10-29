"""
Graph Enrichment Mapper - Core Mapper Service
Translates a canonical observation + model outputs into Neo4j Cypher MERGE statements.

Node types written per call:
  Observation, URL, Domain, IPAddress, AutonomousSystem,
  Brand, WebPageCapture, ModelRun, Prediction, CampaignCandidate

Relationships written per call:
  CAPTURED_URL, HOSTED_ON, RESOLVED_TO, ANNOUNCED_BY,
  STORED_AS, TARGETS_BRAND, SUSPECTED_CAMPAIGN_MEMBER,
  EVALUATED, PRODUCED, APPLIES_TO, SUPPORTED_BY
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from modules.graph_enrichment_mapper.domain.schemas import (
    GraphIngestRequest,
    GraphIngestResult,
)
from modules.graph_enrichment_mapper.infra.neo4j_driver import Neo4jDriver


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _slug(text: str) -> str:
    """Make a graph-safe ID slug from arbitrary text."""
    return text.lower().replace(" ", "_").replace("/", "_").replace(".", "_")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_registered_domain(host: str) -> str:
    parts = [p for p in host.split(".") if p]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


class GraphEnrichmentMapper:
    """
    Core service that translates observation + model output envelopes
    into Neo4j graph nodes and relationships via Cypher MERGE statements.
    """

    def __init__(self, driver: Neo4jDriver):
        self._driver = driver

    def ingest(self, request: GraphIngestRequest) -> GraphIngestResult:
        """
        Main entry point. Ingests one observation and all its model outputs.
        Returns counts of nodes and relationships merged.
        """
        meta    = request.observation_meta
        outputs = request.model_outputs
        run_id  = request.run_id or f"graph_ingest_{uuid.uuid4().hex[:8]}"

        nodes_merged = 0
        rels_merged  = 0
        warnings: List[str] = []

        # ── 1. Derive identifiers ──────────────────────────────────────────
        obs_id   = meta.get("observation_id") or self._derive_obs_id(meta)
        raw_url  = meta.get("url", "")
        url_hash = _sha256(raw_url) if raw_url else ""
        host     = meta.get("host", "")
        domain   = _extract_registered_domain(host) if host else ""
        ip       = meta.get("ip", "")
        asn      = meta.get("asn", "")
        asn_name = meta.get("asn_name", "")
        brand    = meta.get("brand", "")
        sector   = meta.get("sector", "")
        family_id = meta.get("family_id", "")
        tld      = meta.get("tld", "")
        isotime  = meta.get("isotime", _now_iso())
        country_code = meta.get("country_code", "")
        country_name = meta.get("country_name", "")

        # ── 2. Observation node ────────────────────────────────────────────
        self._driver.run_write(
            """
            MERGE (o:Observation {observation_id: $obs_id})
            ON CREATE SET
                o.source_record_id   = $source_record_id,
                o.dataset_id         = $dataset_id,
                o.captured_at        = $captured_at,
                o.ground_truth_label = 'phishing',
                o.created_at         = $now
            """,
            {
                "obs_id":          obs_id,
                "source_record_id": meta.get("source_record_id", ""),
                "dataset_id":      meta.get("dataset_id", "phishpedia_primary"),
                "captured_at":     isotime,
                "now":             _now_iso(),
            },
        )
        nodes_merged += 1

        # ── 3. URL node + edge ─────────────────────────────────────────────
        if raw_url and url_hash:
            self._driver.run_write(
                """
                MERGE (u:URL {url_hash: $url_hash})
                ON CREATE SET u.raw_url = $raw_url, u.host = $host

                WITH u
                MATCH (o:Observation {observation_id: $obs_id})
                MERGE (o)-[r:CAPTURED_URL]->(u)
                ON CREATE SET r.timestamp = $captured_at
                """,
                {
                    "url_hash":    url_hash,
                    "raw_url":     raw_url,
                    "host":        host,
                    "obs_id":      obs_id,
                    "captured_at": isotime,
                },
            )
            nodes_merged += 1
            rels_merged  += 1

        # ── 4. Domain node + URL→Domain edge ──────────────────────────────
        if domain:
            self._driver.run_write(
                """
                MERGE (d:Domain {name: $domain})
                ON CREATE SET d.tld = $tld, d.registered_domain = $domain

                WITH d
                MATCH (u:URL {url_hash: $url_hash})
                MERGE (u)-[:HOSTED_ON]->(d)
                """,
                {"domain": domain, "tld": tld, "url_hash": url_hash},
            )
            nodes_merged += 1
            rels_merged  += 1

        # ── 5. IPAddress node + Domain→IP edge ────────────────────────────
        if ip:
            self._driver.run_write(
                """
                MERGE (i:IPAddress {ip: $ip})
                ON CREATE SET i.country_code = $cc, i.country_name = $cn

                WITH i
                MATCH (d:Domain {name: $domain})
                MERGE (d)-[:RESOLVED_TO]->(i)
                """,
                {"ip": ip, "cc": country_code, "cn": country_name, "domain": domain},
            )
            nodes_merged += 1
            rels_merged  += 1

        # ── 6. AutonomousSystem node + IP→AS edge ─────────────────────────
        if asn:
            asn_key = asn if asn.startswith("AS") else f"AS{asn}"
            self._driver.run_write(
                """
                MERGE (a:AutonomousSystem {asn: $asn})
                ON CREATE SET a.name = $asn_name

                WITH a
                MATCH (i:IPAddress {ip: $ip})
                MERGE (i)-[:ANNOUNCED_BY]->(a)
                """,
                {"asn": asn_key, "asn_name": asn_name, "ip": ip},
            )
            nodes_merged += 1
            rels_merged  += 1

        # ── 7. Brand node + Observation→Brand edge ────────────────────────
        if brand:
            brand_id = _slug(brand)
            self._driver.run_write(
                """
                MERGE (b:Brand {brand_id: $brand_id})
                ON CREATE SET b.name = $brand_name, b.sector = $sector

                WITH b
                MATCH (o:Observation {observation_id: $obs_id})
                MERGE (o)-[r:TARGETS_BRAND {is_ground_truth: true}]->(b)
                """,
                {
                    "brand_id":   brand_id,
                    "brand_name": brand,
                    "sector":     sector,
                    "obs_id":     obs_id,
                },
            )
            nodes_merged += 1
            rels_merged  += 1

        # ── 8. WebPageCapture node + edge ──────────────────────────────────
        # Check if we have artifact metadata (html_hash, screenshot_hash, etc.)
        html_hash = meta.get("html_hash", "")
        screenshot_hash = meta.get("screenshot_hash", "")
        has_html = bool(html_hash)
        has_ocr = bool(screenshot_hash)  # OCR availability inferred from screenshot

        if html_hash or screenshot_hash:
            capture_id = f"cap_{_sha256(obs_id)[:24]}"
            self._driver.run_write(
                """
                MERGE (c:WebPageCapture {capture_id: $capture_id})
                ON CREATE SET
                    c.screenshot_hash = $screenshot_hash,
                    c.html_hash = $html_hash,
                    c.capture_time = $isotime,
                    c.has_html = $has_html,
                    c.has_ocr = $has_ocr

                WITH c
                MATCH (o:Observation {observation_id: $obs_id})
                MERGE (o)-[r:STORED_AS]->(c)
                """,
                {
                    "capture_id":      capture_id,
                    "screenshot_hash": screenshot_hash,
                    "html_hash":       html_hash,
                    "isotime":         isotime,
                    "has_html":        has_html,
                    "has_ocr":         has_ocr,
                    "obs_id":          obs_id,
                },
            )
            nodes_merged += 1
            rels_merged  += 1

        # ── 9. CampaignCandidate node + edge ──────────────────────────────
        if family_id:
            camp_id = f"camp_{_sha256(family_id)[:24]}"
            self._driver.run_write(
                """
                MERGE (c:CampaignCandidate {campaign_id: $camp_id})
                ON CREATE SET c.family_id = $family_id, c.first_seen = $isotime

                WITH c
                MATCH (o:Observation {observation_id: $obs_id})
                MERGE (o)-[r:SUSPECTED_CAMPAIGN_MEMBER {method: 'source_family_id'}]->(c)
                ON CREATE SET r.similarity_score = 1.0
                """,
                {
                    "camp_id":   camp_id,
                    "family_id": family_id,
                    "isotime":   isotime,
                    "obs_id":    obs_id,
                },
            )
            nodes_merged += 1
            rels_merged  += 1

        # ── 9. ModelRun + Prediction nodes per model output ───────────────
        for envelope in outputs:
            n, r, w = self._ingest_model_output(envelope, obs_id, run_id)
            nodes_merged += n
            rels_merged  += r
            warnings.extend(w)

        return GraphIngestResult(
            nodes_merged=nodes_merged,
            relationships_merged=rels_merged,
            observation_id=obs_id,
            warnings=warnings,
        )

    def _ingest_model_output(
        self,
        envelope: Dict[str, Any],
        obs_id: str,
        parent_run_id: str,
    ) -> Tuple[int, int, List[str]]:
        """
        Write ModelRun and Prediction nodes from a single modality envelope.
        Returns (nodes_merged, rels_merged, warnings).
        """
        nodes = 0
        rels  = 0
        warns: List[str] = []

        model_meta    = envelope.get("model", {})
        model_name    = model_meta.get("name", "unknown")
        model_version = model_meta.get("version", "unknown")
        modality      = model_meta.get("modality", "unknown")
        latency_ms    = model_meta.get("latency_ms", 0.0)
        status        = envelope.get("status", "unknown")
        env_run_id    = envelope.get("run_id", parent_run_id)

        run_node_id = f"{env_run_id}_{modality}"

        # ModelRun node
        self._driver.run_write(
            """
            MERGE (r:ModelRun {run_id: $run_id})
            ON CREATE SET
                r.model_name  = $model_name,
                r.version     = $version,
                r.modality    = $modality,
                r.executed_at = $now,
                r.hardware    = 'cpu'

            WITH r
            MATCH (o:Observation {observation_id: $obs_id})
            MERGE (r)-[e:EVALUATED]->(o)
            ON CREATE SET e.latency_ms = $latency_ms
            """,
            {
                "run_id":     run_node_id,
                "model_name": model_name,
                "version":    model_version,
                "modality":   modality,
                "now":        _now_iso(),
                "obs_id":     obs_id,
                "latency_ms": latency_ms,
            },
        )
        nodes += 1
        rels  += 1

        # Prediction node (only if classification is available)
        classification = envelope.get("result", {}).get("classification", {})
        if not classification:
            warns.append(f"No classification in {modality} envelope - Prediction node skipped")
            return nodes, rels, warns

        verdict    = classification.get("verdict", "unknown")
        confidence = classification.get("confidence_score", 0.0)
        is_phish   = classification.get("is_phishing_predicted", False)
        pred_id    = f"pred_{_sha256(run_node_id + obs_id)}"

        # Top risk factors from URL analyzer (if present)
        top_factors = classification.get("top_risk_factors", [])

        self._driver.run_write(
            """
            MERGE (p:Prediction {prediction_id: $pred_id})
            ON CREATE SET
                p.verdict           = $verdict,
                p.confidence        = $confidence,
                p.is_phishing       = $is_phishing,
                p.top_risk_factors  = $top_risk_factors,
                p.modality          = $modality,
                p.status            = $status,
                p.created_at        = $now

            WITH p
            MATCH (r:ModelRun {run_id: $run_id})
            MERGE (r)-[:PRODUCED]->(p)

            WITH p
            MATCH (o:Observation {observation_id: $obs_id})
            MERGE (p)-[:APPLIES_TO]->(o)
            """,
            {
                "pred_id":          pred_id,
                "verdict":          verdict,
                "confidence":       confidence,
                "is_phishing":      is_phish,
                "top_risk_factors": top_factors,
                "modality":         modality,
                "status":           status,
                "now":              _now_iso(),
                "run_id":           run_node_id,
                "obs_id":           obs_id,
            },
        )
        nodes += 1
        rels  += 2

        # ── EvidenceItem nodes from risk factors ─────────────────────────
        # Extract evidence items from top_risk_factors and other model output fields
        evidence_items = self._extract_evidence_items(envelope, modality)
        for ev in evidence_items:
            ev_id = f"evid_{_sha256(pred_id + ev['metric_name'])[:24]}"
            self._driver.run_write(
                """
                MERGE (e:EvidenceItem {evidence_id: $ev_id})
                ON CREATE SET
                    e.modality    = $modality,
                    e.metric_name = $metric_name,
                    e.score       = $score,
                    e.description = $description,
                    e.created_at  = $now

                WITH e
                MATCH (p:Prediction {prediction_id: $pred_id})
                MERGE (p)-[r:SUPPORTED_BY]->(e)
                ON CREATE SET r.weight_contribution = $weight
                """,
                {
                    "ev_id":       ev_id,
                    "modality":    modality,
                    "metric_name": ev["metric_name"],
                    "score":       ev["score"],
                    "description": ev["description"],
                    "now":         _now_iso(),
                    "pred_id":     pred_id,
                    "weight":      ev.get("weight", 1.0),
                },
            )
            nodes += 1
            rels  += 1

        return nodes, rels, warns

    @staticmethod
    def _derive_obs_id(meta: Dict[str, Any]) -> str:
        """Generate a deterministic obs_id from URL + brand when not already present."""
        seed = f"{meta.get('url', '')}:{meta.get('brand', '')}"
        return f"obs_{hashlib.md5(seed.encode()).hexdigest()}"

    def _extract_evidence_items(
        self, envelope: Dict[str, Any], modality: str
    ) -> List[Dict[str, Any]]:
        """
        Extract evidence items from a model output envelope.
        Evidence items represent atomic pieces of evidence that support a prediction.

        Returns a list of dicts with keys: metric_name, score, description, weight
        """
        evidence: List[Dict[str, Any]] = []
        classification = envelope.get("result", {}).get("classification", {})

        # Extract from top_risk_factors (URL analyzer)
        top_factors = classification.get("top_risk_factors", [])
        for factor in top_factors:
            evidence.append({
                "metric_name": "risk_factor",
                "score": 1.0,  # Binary presence of risk factor
                "description": factor,
                "weight": 0.1,
            })

        # Extract from feature importance or scores if available
        result = envelope.get("result", {})
        features = result.get("features", {})
        if features:
            # Take top 5 most influential features by score
            sorted_features = sorted(
                features.items(),
                key=lambda x: abs(x[1]),
                reverse=True
            )[:5]
            for feat_name, feat_score in sorted_features:
                evidence.append({
                    "metric_name": feat_name,
                    "score": float(feat_score),
                    "description": f"Feature contribution: {feat_name}",
                    "weight": abs(float(feat_score)) / 10.0,  # Normalize weight
                })

        # Extract confidence score as an evidence item
        confidence = classification.get("confidence_score", 0.0)
        evidence.append({
            "metric_name": "confidence_score",
            "score": confidence,
            "description": f"Model confidence score for {modality} analysis",
            "weight": 0.2,
        })

        # Extract verdict as evidence
        verdict = classification.get("verdict", "unknown")
        evidence.append({
            "metric_name": "verdict",
            "score": 1.0 if verdict == "phishing" else 0.0,
            "description": f"Model verdict: {verdict}",
            "weight": 0.3,
        })

        return evidence
