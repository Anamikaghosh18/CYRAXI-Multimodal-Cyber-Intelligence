"""
Investigation Workflow Service
End-to-end cybercrime investigation workflow combining multimodal detection and graph intelligence.
"""

import hashlib
import os
import time
import zipfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import uuid

from modules.dataset_adapter.reader import PhishpediaDatasetReader, parse_url_components
from modules.graph_enrichment_mapper.infra.neo4j_driver import Neo4jDriver, GraphConnectionError
from modules.graph_ai.candidate_generation import CandidateGenerator
from modules.graph_ai.similarity import SimilarityScorer
from modules.graph_ai.communities import CommunityDetector
from modules.graph_ai.ranking import EntityRanker
from modules.graph_ai.near_duplicate.detector import NearDuplicateDetector
from modules.graph_ai.temporal.analyzer import TemporalGraphAnalyzer
from modules.dataset_adapter.artifacts import read_artifact, read_artifact_bytes
from modules.dataset_adapter.s3_artifacts import S3ArtifactStore, load_project_env
from modules.url_analyzer.service import URLAnalysisService
from modules.html_analyzer.analyzer import analyze_html
from modules.ocr_extractor.extractor import extract_ocr
from modules.cv_detector.detector import detect_logo_candidates
from modules.fusion_engine.fusion import fuse_predictions
from modules.graph_enrichment_mapper.mapper import GraphEnrichmentMapper
from modules.graph_enrichment_mapper.domain.schemas import GraphIngestRequest


class InvestigationService:
    """
    End-to-end investigation workflow service.
    """

    def __init__(
        self,
        archive_path: str = "data/phish_sample_30k.zip",
        neo4j_driver: Optional[Neo4jDriver] = None,
    ):
        load_project_env()
        self.archive_path = archive_path
        self.artifact_storage = os.getenv("CYRAXI_ARTIFACT_STORAGE", "zip").strip().lower()
        if self.artifact_storage not in {"zip", "s3"}:
            raise ValueError("CYRAXI_ARTIFACT_STORAGE must be either 'zip' or 's3'.")
        self.reader = PhishpediaDatasetReader(archive_path=archive_path)
        self.neo4j_driver = neo4j_driver or Neo4jDriver()
        self._artifact_archive = None
        self._artifact_source = S3ArtifactStore() if self.artifact_storage == "s3" else archive_path

        # Graph AI components
        self.candidate_generator = CandidateGenerator()
        self.similarity_scorer = SimilarityScorer()
        self.community_detector = CommunityDetector()
        self.entity_ranker = EntityRanker()
        self.near_duplicate_detector = NearDuplicateDetector()
        self.temporal_analyzer = TemporalGraphAnalyzer()

    def _generate_investigation_id(self, observation_id: str) -> str:
        """Generate stable investigation ID."""
        timestamp = datetime.now(timezone.utc).isoformat()
        hash_input = f"{observation_id}{timestamp}"
        return f"inv_{hashlib.md5(hash_input.encode()).hexdigest()}"

    def _validate_observation_id(self, obs_id: str) -> bool:
        """Validate observation ID format."""
        import re
        return bool(re.match(r'^obs_[a-f0-9]{32}$', obs_id))

    def _validate_url(self, url: str) -> bool:
        """Validate URL format."""
        from urllib.parse import urlparse
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    def _get_observation_by_id(self, obs_id: str) -> Optional[Dict]:
        """Retrieve observation by ID from archive."""
        for obs in self.reader.stream_observations(limit=100000, offset=0):
            if obs.get("observation_id") == obs_id:
                return obs
        return None

    def _get_observation_by_url(self, url: str) -> Optional[Dict]:
        """Retrieve observation by URL from archive."""
        for obs in self.reader.stream_observations(limit=100000, offset=0):
            if obs.get("url", {}).get("raw") == url:
                return obs
        return None

    @staticmethod
    def _archive_summary(observation: Dict[str, Any]) -> Dict[str, Any]:
        url = observation.get("url") or {}
        label = (observation.get("label") or {}).get("ground_truth") or {}
        availability = observation.get("availability") or {}
        return {
            "observation_id": observation.get("observation_id"),
            "source_record_id": observation.get("source_record_id"),
            "url": url.get("raw", ""),
            "domain": url.get("domain"),
            "target_brand": label.get("target_brand"),
            "captured_at": (observation.get("timestamps") or {}).get("captured_at"),
            "availability": availability,
        }

    @staticmethod
    def _database_record_to_observation(record: Dict[str, Any]) -> Dict[str, Any]:
        """Shape indexed Neo4j attack metadata into the archive observation contract."""
        raw_url = record.get("url") or ""
        source_record_id = record.get("source_record_id") or ""
        parsed_url = parse_url_components(raw_url)
        has_html = bool(record.get("has_html"))
        has_screenshot = bool(record.get("has_screenshot"))
        has_ocr = bool(record.get("has_ocr"))
        storage_medium = "object_storage" if os.getenv("CYRAXI_ARTIFACT_STORAGE", "zip").strip().lower() == "s3" else "zip_entry"
        return {
            "schema_version": "1.0.0",
            "observation_id": record.get("observation_id"),
            "dataset": {"dataset_id": record.get("dataset_id") or "phishpedia_primary", "version": "1.0.0", "split": None},
            "source_record_id": source_record_id,
            "source": {"collector_type": "archive_index", "feed_name": "phishpedia_primary", "family_id": record.get("family_id"), "phishing_kit": None},
            "url": parsed_url,
            "network": {"ip": record.get("ip"), "asn": record.get("asn"), "asn_name": record.get("asn_name"), "country_code": record.get("country_code"), "country_name": record.get("country_name")},
            "label": {"ground_truth": {"original_label": None, "normalized_label": record.get("ground_truth_label"), "target_brand": record.get("brand"), "target_sector": record.get("sector"), "confidence": None}},
            "artifacts": {
                # The Neo4j index may predate artifact availability flags. Try the
                # deterministic archive paths during a run and check the ZIP entry.
                "screenshot": {"relative_path": f"{source_record_id}/shot.png" if source_record_id else None, "format": "png", "storage_medium": storage_medium},
                "html": {"relative_path": f"{source_record_id}/html.txt" if source_record_id else None, "encoding": "utf-8", "storage_medium": storage_medium} if source_record_id else None,
                "ocr": {"relative_path": f"{source_record_id}/ocr.txt" if source_record_id else None, "storage_medium": storage_medium} if source_record_id else None,
                "metadata_annotation": {"relative_path": f"{source_record_id}/info.txt" if source_record_id else None, "storage_medium": storage_medium},
                "auxiliary": {"yolo_coords_path": f"{source_record_id}/yolo_coords.txt" if source_record_id else None},
            },
            "availability": {"has_screenshot": has_screenshot, "has_html": has_html, "has_ocr": has_ocr, "has_metadata": bool(source_record_id), "has_yolo_coords": False, "has_html_overlap": False},
            "content_hashes": {"screenshot_sha256": None, "html_sha256": None, "info_sha256": None},
            "timestamps": {"captured_at": record.get("captured_at"), "ingested_at": record.get("created_at")},
            "provenance": {"created_by": "neo4j_observation_index", "source_archive": "data/phish_sample_30k.zip", "transformation_notes": "Selected from Neo4j; artifacts are read from the configured object store or local archive."},
        }

    def _query_database_observations(self, cypher: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows = self.neo4j_driver.run_read(cypher, params)
        normalized_rows = []
        for row in rows:
            normalized_row = dict(row)
            url_properties = normalized_row.pop("url_properties", None) or {}
            normalized_row["url"] = url_properties.get("raw_url") or url_properties.get("url") or ""
            normalized_rows.append(normalized_row)
        return [self._database_record_to_observation(row) for row in normalized_rows]

    def list_database_observations(self, limit: int = 50, offset: int = 0, search: str = "") -> Dict[str, Any]:
        """Page/search observations from Neo4j, the company's attack index."""
        match = """
            MATCH (o:Observation)
            OPTIONAL MATCH (o)-[:CAPTURED_URL]->(u:URL)
            OPTIONAL MATCH (o)-[:TARGETS_BRAND]->(b:Brand)
            OPTIONAL MATCH (u)-[:HOSTED_ON]->(d:Domain)
            OPTIONAL MATCH (d)-[:RESOLVED_TO]->(ip:IPAddress)
            OPTIONAL MATCH (ip)-[:ANNOUNCED_BY]->(a:AutonomousSystem)
            OPTIONAL MATCH (o)-[:SUSPECTED_CAMPAIGN_MEMBER]->(c:CampaignCandidate)
            OPTIONAL MATCH (o)-[:STORED_AS]->(capture:WebPageCapture)
        """
        where = """
            WHERE $search = '' OR any(value IN [o.observation_id, o.source_record_id, toString(properties(u)), d.name, b.name]
                WHERE value IS NOT NULL AND toLower(toString(value)) CONTAINS toLower($search))
        """
        count_rows = self.neo4j_driver.run_read(
            match + where + "RETURN count(DISTINCT o) AS total",
            {"search": search.strip()},
        )
        total = count_rows[0].get("total", 0) if count_rows else 0
        rows = self._query_database_observations(
            match + where + """
            RETURN DISTINCT o.observation_id AS observation_id,
                o.source_record_id AS source_record_id, o.dataset_id AS dataset_id,
                o.captured_at AS captured_at, o.created_at AS created_at,
                o.ground_truth_label AS ground_truth_label,
                properties(u) AS url_properties,
                b.name AS brand, b.sector AS sector, c.family_id AS family_id,
                ip.ip AS ip, a.asn AS asn, a.name AS asn_name,
                ip.country_code AS country_code, ip.country_name AS country_name,
                coalesce(capture.has_html, capture.html_hash IS NOT NULL, false) AS has_html,
                coalesce(capture.has_screenshot, capture.screenshot_hash IS NOT NULL, false) AS has_screenshot,
                coalesce(capture.has_ocr, capture.screenshot_hash IS NOT NULL, false) AS has_ocr
            ORDER BY captured_at DESC
            SKIP $offset LIMIT $limit
            """,
            {"search": search.strip(), "offset": offset, "limit": limit},
        )
        return {"observations": [self._archive_summary(row) for row in rows], "offset": offset, "limit": limit, "has_more": offset + len(rows) < total, "matched_count": total}

    def sample_database_observations(self, count: int) -> List[Dict[str, Any]]:
        """Choose a random sample directly from indexed attack observations."""
        query = """
            MATCH (o:Observation)
            WITH o ORDER BY rand() LIMIT $count
            OPTIONAL MATCH (o)-[:CAPTURED_URL]->(u:URL)
            OPTIONAL MATCH (o)-[:TARGETS_BRAND]->(b:Brand)
            OPTIONAL MATCH (u)-[:HOSTED_ON]->(d:Domain)
            OPTIONAL MATCH (d)-[:RESOLVED_TO]->(ip:IPAddress)
            OPTIONAL MATCH (ip)-[:ANNOUNCED_BY]->(a:AutonomousSystem)
            OPTIONAL MATCH (o)-[:SUSPECTED_CAMPAIGN_MEMBER]->(c:CampaignCandidate)
            OPTIONAL MATCH (o)-[:STORED_AS]->(capture:WebPageCapture)
            RETURN DISTINCT o.observation_id AS observation_id,
                o.source_record_id AS source_record_id, o.dataset_id AS dataset_id,
                o.captured_at AS captured_at, o.created_at AS created_at,
                o.ground_truth_label AS ground_truth_label,
                properties(u) AS url_properties,
                b.name AS brand, b.sector AS sector, c.family_id AS family_id,
                ip.ip AS ip, a.asn AS asn, a.name AS asn_name,
                ip.country_code AS country_code, ip.country_name AS country_name,
                coalesce(capture.has_html, capture.html_hash IS NOT NULL, false) AS has_html,
                coalesce(capture.has_screenshot, capture.screenshot_hash IS NOT NULL, false) AS has_screenshot,
                coalesce(capture.has_ocr, capture.screenshot_hash IS NOT NULL, false) AS has_ocr
        """
        return self._query_database_observations(query, {"count": count})

    def get_database_observations(self, observation_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Load selected archive-backed observations from Neo4j in one query."""
        query = """
            MATCH (o:Observation) WHERE o.observation_id IN $observation_ids
            OPTIONAL MATCH (o)-[:CAPTURED_URL]->(u:URL)
            OPTIONAL MATCH (o)-[:TARGETS_BRAND]->(b:Brand)
            OPTIONAL MATCH (u)-[:HOSTED_ON]->(d:Domain)
            OPTIONAL MATCH (d)-[:RESOLVED_TO]->(ip:IPAddress)
            OPTIONAL MATCH (ip)-[:ANNOUNCED_BY]->(a:AutonomousSystem)
            OPTIONAL MATCH (o)-[:SUSPECTED_CAMPAIGN_MEMBER]->(c:CampaignCandidate)
            OPTIONAL MATCH (o)-[:STORED_AS]->(capture:WebPageCapture)
            RETURN DISTINCT o.observation_id AS observation_id,
                o.source_record_id AS source_record_id, o.dataset_id AS dataset_id,
                o.captured_at AS captured_at, o.created_at AS created_at,
                o.ground_truth_label AS ground_truth_label,
                properties(u) AS url_properties,
                b.name AS brand, b.sector AS sector, c.family_id AS family_id,
                ip.ip AS ip, a.asn AS asn, a.name AS asn_name,
                ip.country_code AS country_code, ip.country_name AS country_name,
                coalesce(capture.has_html, capture.html_hash IS NOT NULL, false) AS has_html,
                coalesce(capture.has_screenshot, capture.screenshot_hash IS NOT NULL, false) AS has_screenshot,
                coalesce(capture.has_ocr, capture.screenshot_hash IS NOT NULL, false) AS has_ocr
        """
        observations = self._query_database_observations(query, {"observation_ids": observation_ids})
        return {item["observation_id"]: item for item in observations if item.get("observation_id")}

    def _run_module(self, function, modality: str, obs_id: str, run_id: str) -> Dict[str, Any]:
        """Run one analyzer independently so unavailable artifacts remain visible."""
        try:
            result = function()
            payload = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
            if payload.get("observation_id") != obs_id or payload.get("run_id") != run_id:
                raise ValueError("Analyzer returned mismatched observation or run ID")
            return payload
        except Exception as exc:
            return {
                "schema_version": "1.0.0", "observation_id": obs_id, "run_id": run_id,
                "model": {"name": f"{modality}_analysis", "version": "1.0.0", "modality": modality,
                          "execution_hardware": "cpu", "latency_ms": 0.0},
                "status": "error", "created_at": datetime.now(timezone.utc).isoformat(),
                "result": {}, "warnings": [{"code": "E_MODULE_EXECUTION",
                    "message": f"{modality} analysis failed: {type(exc).__name__}: {exc}",
                    "artifact_ref": None}],
            }

    def _run_observation_analysis(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        """Run baseline analyzers for one archived observation and persist graph context."""
        obs_id = observation["observation_id"]
        run_id = f"inv_run_{uuid.uuid4().hex[:12]}"
        url = (observation.get("url") or {}).get("raw", "") or ""
        artifacts = observation.get("artifacts") or {}
        has_archive_artifacts = any((artifacts.get(name) or {}).get("relative_path") for name in ("html", "ocr", "screenshot"))
        has_archive_artifacts = has_archive_artifacts or bool((artifacts.get("auxiliary") or {}).get("yolo_coords_path"))
        if has_archive_artifacts and self.artifact_storage == "zip" and self._artifact_archive is None:
            archive = Path(self.archive_path)
            if archive.is_file() and archive.suffix.lower() == ".zip":
                try:
                    self._artifact_archive = zipfile.ZipFile(archive, "r")
                    self._artifact_source = self._artifact_archive
                except zipfile.BadZipFile:
                    self._artifact_source = self.archive_path
        html_text = read_artifact(self._artifact_source, observation, "html") or ""
        ocr_text = read_artifact(self._artifact_source, observation, "ocr") or ""
        screenshot = read_artifact_bytes(self._artifact_source, observation, "screenshot")
        coordinates = read_artifact(self._artifact_source, observation, "yolo_coords") or ""
        # Reflect files actually found in the local archive rather than relying
        # on possibly stale availability metadata from the database index.
        availability = observation.setdefault("availability", {})
        availability.update({
            "has_html": bool(html_text),
            "has_ocr": bool(ocr_text),
            "has_screenshot": screenshot is not None,
            "has_yolo_coords": bool(coordinates),
        })

        url_result = self._run_module(lambda: URLAnalysisService().analyze(url, obs_id, run_id), "url", obs_id, run_id)
        html_result = self._run_module(lambda: analyze_html(obs_id, run_id, html_text, url), "html_nlp", obs_id, run_id)
        ocr_result = self._run_module(lambda: extract_ocr(obs_id, run_id, ocr_text=ocr_text, screenshot_bytes=screenshot), "ocr", obs_id, run_id)
        cv_result = self._run_module(lambda: detect_logo_candidates(obs_id, run_id, coordinates_text=coordinates, screenshot_bytes=screenshot), "computer_vision", obs_id, run_id)
        fusion_result = self._run_module(lambda: fuse_predictions(obs_id, run_id, [url_result, html_result, ocr_result, cv_result]), "multimodal_fusion", obs_id, run_id)
        results = {
            "url": url_result, "html_nlp": html_result, "ocr": ocr_result,
            "computer_vision": cv_result, "multimodal_fusion": fusion_result,
        }

        try:
            parsed_url = observation.get("url") or {}
            label = (observation.get("label") or {}).get("ground_truth") or {}
            network = observation.get("network") or {}
            source = observation.get("source") or {}
            meta = {
                "observation_id": obs_id,
                "source_record_id": observation.get("source_record_id", ""),
                "dataset_id": (observation.get("dataset") or {}).get("dataset_id", "phishpedia_primary"),
                "url": url, "host": parsed_url.get("host") or "", "tld": parsed_url.get("tld") or "",
                "brand": label.get("target_brand") or "", "sector": label.get("target_sector") or "",
                "ip": network.get("ip") or "", "asn": network.get("asn") or "",
                "asn_name": network.get("asn_name") or "", "country_code": network.get("country_code") or "",
                "country_name": network.get("country_name") or "", "family_id": source.get("family_id") or "",
                "isotime": (observation.get("timestamps") or {}).get("captured_at") or "",
            }
            graph_result = GraphEnrichmentMapper(self.neo4j_driver).ingest(
                GraphIngestRequest(observation_meta=meta, model_outputs=list(results.values()), run_id=run_id))
            results["graph_persistence"] = {
                "status": "success", "nodes_merged": graph_result.nodes_merged,
                "relationships_merged": graph_result.relationships_merged,
                "warnings": graph_result.warnings,
            }
        except Exception as exc:
            results["graph_persistence"] = {
                "status": "error", "warnings": [f"Graph analysis persistence failed: {type(exc).__name__}: {exc}"]}
        return results

    def _retrieve_related_observations(
        self,
        obs_id: str,
        limit: int = 10,
    ) -> List[Dict]:
        """
        Retrieve related observations using graph similarity.
        """
        related = []

        try:
            # Query CANDIDATE_SIMILAR_TO relationships
            query = """
            MATCH (o:Observation {observation_id: $obs_id})-[r:CANDIDATE_SIMILAR_TO]->(related:Observation)
            RETURN related.observation_id as obs_id, r.similarity_score as score, r.feature_contributions as features
            ORDER BY r.similarity_score DESC
            LIMIT $limit
            """

            response = self.neo4j_driver.run_read(query, {"obs_id": obs_id, "limit": limit})

            if response:
                for record in response:
                    related.append({
                        "observation_id": record.get("obs_id"),
                        "similarity_score": record.get("score", 0.0),
                        "relationship_type": "candidate_similar_to",
                        "feature_contributions": record.get("features", {}),
                        "explanation": self._generate_similarity_explanation(record.get("features", {})),
                    })

        except Exception as e:
            pass

        return related

    def _retrieve_near_duplicates(
        self,
        obs_id: str,
        limit: int = 5,
    ) -> List[Dict]:
        """
        Retrieve near-duplicate observations.
        """
        related = []

        try:
            query = """
            MATCH (o:Observation {observation_id: $obs_id})-[r:NEAR_DUPLICATE_TO]->(related:Observation)
            RETURN related.observation_id as obs_id, r.jaccard_similarity as score
            ORDER BY r.jaccard_similarity DESC
            LIMIT $limit
            """

            response = self.neo4j_driver.run_read(query, {"obs_id": obs_id, "limit": limit})

            if response:
                for record in response:
                    related.append({
                        "observation_id": record.get("obs_id"),
                        "similarity_score": record.get("score", 0.0),
                        "relationship_type": "near_duplicate_to",
                        "explanation": f"HTML content near-duplicate (Jaccard: {record.get('score', 0.0):.3f})",
                    })

        except Exception as e:
            pass

        return related

    def _generate_similarity_explanation(self, features: Dict) -> str:
        """Generate deterministic explanation from feature contributions."""
        if not features:
            return "Similarity based on graph connectivity"

        top_features = sorted(features.items(), key=lambda x: x[1], reverse=True)[:3]
        feature_names = [f for f, v in top_features]
        return f"Similar due to: {', '.join(feature_names)}"

    def _retrieve_community_info(self, obs_id: str) -> Optional[Dict]:
        """Retrieve community/cluster information for observation."""
        try:
            query = """
            MATCH (o:Observation {observation_id: $obs_id})
            RETURN o.cluster_id as cluster_id, o.cluster_size as cluster_size
            """

            response = self.neo4j_driver.run_read(query, {"obs_id": obs_id})

            if response and len(response) > 0:
                record = response[0]
                return {
                    "cluster_id": record.get("cluster_id"),
                    "cluster_size": record.get("cluster_size"),
                    "explanation": f"Part of cluster {record.get('cluster_id')} with {record.get('cluster_size')} observations",
                }
        except Exception:
            pass

        return None

    def _retrieve_entity_ranking(self, obs_id: str) -> Optional[Dict]:
        """Retrieve entity ranking information."""
        try:
            query = """
            MATCH (o:Observation {observation_id: $obs_id})
            RETURN o.pagerank_score as pagerank, o.degree_centrality as degree
            """

            response = self.neo4j_driver.run_read(query, {"obs_id": obs_id})

            if response and len(response) > 0:
                record = response[0]
                return {
                    "observation_rank": record.get("pagerank"),
                    "explanation": f"PageRank score: {record.get('pagerank', 0.0):.4f}",
                }
        except Exception:
            pass

        return None

    def _retrieve_temporal_info(self, obs_id: str) -> Optional[Dict]:
        """Retrieve temporal analysis information."""
        try:
            query = """
            MATCH (o:Observation {observation_id: $obs_id})
            RETURN o.time_bucket as time_bucket
            """

            response = self.neo4j_driver.run_read(query, {"obs_id": obs_id})

            if response and len(response) > 0:
                record = response[0]
                return {
                    "time_bucket": record.get("time_bucket"),
                    "is_burst": False,  # Would check against TemporalBurst nodes
                }
        except Exception:
            pass

        return None

    def _build_report(
        self,
        investigation_id: str,
        observation_id: str,
        input_type: str,
        input_value: str,
        observation_data: Optional[Dict],
        module_results: Dict,
        related_observations: List[Dict],
        execution_metadata: Dict,
        warnings: List[Dict],
    ) -> Dict:
        """Build structured investigation report."""

        report = {
            "schema_version": "1.0.0",
            "investigation_id": investigation_id,
            "observation_id": observation_id,
            "input_type": input_type,
            "input_value": input_value,
            "status": "success" if observation_data else "error",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "observation_data": observation_data,
            "module_results": module_results,
            "related_observations": related_observations,
            "graph_intelligence": {
                "community": self._retrieve_community_info(observation_id),
                "entity_ranking": self._retrieve_entity_ranking(observation_id),
                "temporal_analysis": self._retrieve_temporal_info(observation_id),
            },
            "evidence_references": [],
            "graph_paths": [],
            "warnings": warnings,
            "algorithm_versions": {
                "similarity": "1.0.0",
                "community_detection": "louvain_1.0",
                "entity_ranking": "pagerank_1.0",
            },
            "execution_metadata": execution_metadata,
        }

        return report

    def investigate(
        self,
        input_value: str,
        input_type: str = "observation_id",
        limit_related: int = 10,
        observation_data: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """
        Run end-to-end investigation.

        Args:
            input_value: Observation ID or URL
            input_type: "observation_id" or "url"
            limit_related: Maximum number of related observations to retrieve

        Returns:
            Structured investigation report
        """
        start_time = time.time()
        warnings = []
        stage_times = {}

        # Validate input
        if input_type == "observation_id":
            if not self._validate_observation_id(input_value):
                warnings.append({
                    "code": "INVALID_OBSERVATION_ID",
                    "message": f"Invalid observation ID format: {input_value}",
                })
                return self._build_report(
                    self._generate_investigation_id(input_value),
                    input_value,
                    input_type,
                    input_value,
                    None,
                    {},
                    [],
                    {"total_runtime_ms": 0, "stages": {}},
                    warnings,
                )
        elif input_type == "url":
            if not self._validate_url(input_value):
                warnings.append({
                    "code": "INVALID_URL",
                    "message": f"Invalid URL format: {input_value}",
                })
                return self._build_report(
                    self._generate_investigation_id(input_value),
                    input_value,
                    input_type,
                    input_value,
                    None,
                    {},
                    [],
                    {"total_runtime_ms": 0, "stages": {}},
                    warnings,
                )

        # Retrieve observation
        stage_start = time.time()
        if observation_data is None:
            if input_type == "observation_id":
                observation_data = self._get_observation_by_id(input_value)
            else:
                observation_data = self._get_observation_by_url(input_value)
                if observation_data:
                    input_value = observation_data["observation_id"]

        stage_times["retrieve_observation"] = (time.time() - stage_start) * 1000

        if not observation_data:
            warnings.append({
                "code": "OBSERVATION_NOT_FOUND",
                "message": f"Observation not found for {input_type}: {input_value}",
            })
            return self._build_report(
                self._generate_investigation_id(input_value),
                input_value,
                input_type,
                input_value,
                None,
                {},
                [],
                {"total_runtime_ms": 0, "stages": stage_times},
                warnings,
            )

        obs_id = observation_data["observation_id"]
        investigation_id = self._generate_investigation_id(obs_id)

        # Run local analyzers against archived evidence and persist graph context.
        stage_start = time.time()
        module_results = self._run_observation_analysis(observation_data)
        stage_times["run_analysis_and_persist_graph"] = (time.time() - stage_start) * 1000

        for name in ("url", "html_nlp", "ocr", "computer_vision", "multimodal_fusion"):
            output = module_results.get(name) or {}
            if output.get("status") in ("skipped", "error"):
                warnings.append({"code": f"{name.upper()}_UNAVAILABLE",
                                 "message": f"{name.replace('_', ' ')} analysis status: {output.get('status')}"})
            for item in output.get("warnings", []):
                if isinstance(item, dict):
                    warnings.append({"code": item.get("code", "ANALYSIS_WARNING"),
                                     "message": item.get("message", "")})
        graph_persistence = module_results.get("graph_persistence", {})
        if graph_persistence.get("status") == "error":
            warnings.append({"code": "GRAPH_PERSISTENCE_FAILED",
                             "message": "; ".join(graph_persistence.get("warnings", []))})
        # Retrieve related observations
        stage_start = time.time()
        related_similar = self._retrieve_related_observations(obs_id, limit=limit_related)
        related_near_duplicates = self._retrieve_near_duplicates(obs_id, limit=limit_related // 2)
        related_observations = related_similar + related_near_duplicates
        related_observations = sorted(related_observations, key=lambda x: x["similarity_score"], reverse=True)[:limit_related]
        stage_times["retrieve_related"] = (time.time() - stage_start) * 1000

        # Build report
        total_runtime = (time.time() - start_time) * 1000
        execution_metadata = {
            "total_runtime_ms": total_runtime,
            "stages": stage_times,
        }

        return self._build_report(
            investigation_id,
            obs_id,
            input_type,
            input_value,
            observation_data,
            module_results,
            related_observations,
            execution_metadata,
            warnings,
        )
