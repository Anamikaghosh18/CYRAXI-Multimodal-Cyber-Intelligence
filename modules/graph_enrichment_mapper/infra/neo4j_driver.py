"""
Neo4j Driver Wrapper (Infrastructure Layer)
Handles connection lifecycle, retry logic, and raw Cypher execution.

Design:
- Uses the official neo4j Python driver (bolt protocol)
- Connection details read from environment variables:
    NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
  (NEO4J_USER is also accepted as a legacy fallback for NEO4J_USERNAME)
- Exposes run_query(), run_read(), and run_write() methods; callers pass
  Cypher + params (always parameterised — never string-concatenated).
- Fails gracefully with GraphConnectionError when Neo4j is not reachable
  so the FastAPI service starts cleanly and returns meaningful errors.

Install driver:
  pip install neo4j
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GraphConnectionError(RuntimeError):
    """Raised when the Neo4j driver cannot connect or is not installed."""


class Neo4jDriver:
    """Thin wrapper around the official neo4j Python driver."""

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self._uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        # Accept NEO4J_USERNAME (documented) and NEO4J_USER (legacy alias).
        self._user = (
            user
            or os.getenv("NEO4J_USERNAME")
            or os.getenv("NEO4J_USER", "neo4j")
        )
        self._password = password or os.getenv("NEO4J_PASSWORD", "cyraxi_dev")
        self._driver = None

        env = os.getenv("CYRAXI_ENV", "development").lower()
        if env != "development" and self._password == "cyraxi_dev":
            logger.warning(
                "NEO4J_PASSWORD is using the default dev value in a non-development "
                "environment (%s). Set NEO4J_PASSWORD in your environment.",
                env,
            )

    def connect(self) -> None:
        """Explicitly establish the Bolt connection.

        Moved out of __init__ so callers can control when the driver is
        connected. This also keeps the constructor side-effect free, which
        makes graph services easier to construct, test, and restart.
        """
        if self._driver is not None:
            return
        try:
            from neo4j import GraphDatabase  # type: ignore

            self._driver = GraphDatabase.driver(
                self._uri,
                auth=(self._user, self._password),
            )
            # Verify connectivity on startup
            self._driver.verify_connectivity()
            logger.info("Connected to Neo4j at %s as '%s'.", self._uri, self._user)
        except ImportError:
            raise GraphConnectionError(
                "neo4j Python package is not installed. "
                "Run: pip install neo4j"
            )
        except Exception as exc:
            raise GraphConnectionError(
                f"Cannot connect to Neo4j at {self._uri}: {exc}"
            ) from exc

    def run_query(
        self,
        cypher: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return all records as a list of dicts."""
        if self._driver is None:
            raise GraphConnectionError("Neo4j driver is not initialised.")
        with self._driver.session() as session:
            result = session.run(cypher, params or {})
            return [dict(record) for record in result]

    def run_read(
        self,
        cypher: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute a read query; kept as a semantic alias for service callers."""
        return self.run_query(cypher, params)

    def run_write(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Execute a write Cypher statement (MERGE / CREATE / SET)."""
        if self._driver is None:
            raise GraphConnectionError("Neo4j driver is not initialised.")
        with self._driver.session() as session:
            session.run(cypher, params or {})

    def apply_schema_constraints(self) -> None:
        """
        Create uniqueness constraints and indexes defined in NEO4J_DATA_MODEL.md.
        Safe to call multiple times (IF NOT EXISTS).

        Only genuine "already exists" errors are suppressed. All other
        exceptions (network failures, auth errors, version mismatches) are
        re-raised so they surface clearly rather than silently allowing the
        graph to operate without required constraints.
        """
        statements = [
            "CREATE CONSTRAINT c_obs_id IF NOT EXISTS FOR (o:Observation) REQUIRE o.observation_id IS UNIQUE",
            "CREATE CONSTRAINT c_url_hash IF NOT EXISTS FOR (u:URL) REQUIRE u.url_hash IS UNIQUE",
            "CREATE CONSTRAINT c_domain_name IF NOT EXISTS FOR (d:Domain) REQUIRE d.name IS UNIQUE",
            "CREATE CONSTRAINT c_ip_addr IF NOT EXISTS FOR (i:IPAddress) REQUIRE i.ip IS UNIQUE",
            "CREATE CONSTRAINT c_asn IF NOT EXISTS FOR (a:AutonomousSystem) REQUIRE a.asn IS UNIQUE",
            "CREATE CONSTRAINT c_brand_id IF NOT EXISTS FOR (b:Brand) REQUIRE b.brand_id IS UNIQUE",
            "CREATE CONSTRAINT c_run_id IF NOT EXISTS FOR (r:ModelRun) REQUIRE r.run_id IS UNIQUE",
            "CREATE CONSTRAINT c_pred_id IF NOT EXISTS FOR (p:Prediction) REQUIRE p.prediction_id IS UNIQUE",
            "CREATE CONSTRAINT c_campaign_id IF NOT EXISTS FOR (c:CampaignCandidate) REQUIRE c.campaign_id IS UNIQUE",
            "CREATE CONSTRAINT c_capture_id IF NOT EXISTS FOR (c:WebPageCapture) REQUIRE c.capture_id IS UNIQUE",
            "CREATE CONSTRAINT c_evidence_id IF NOT EXISTS FOR (e:EvidenceItem) REQUIRE e.evidence_id IS UNIQUE",
            "CREATE INDEX idx_obs_captured_at IF NOT EXISTS FOR (o:Observation) ON (o.captured_at)",
            "CREATE INDEX idx_brand_name IF NOT EXISTS FOR (b:Brand) ON (b.name)",
            "CREATE INDEX idx_campaign_family IF NOT EXISTS FOR (c:CampaignCandidate) ON (c.family_id)",
            "CREATE INDEX idx_capture_time IF NOT EXISTS FOR (c:WebPageCapture) ON (c.capture_time)",
            "CREATE INDEX idx_evidence_modality IF NOT EXISTS FOR (e:EvidenceItem) ON (e.modality)",
        ]
        for stmt in statements:
            try:
                self.run_write(stmt)
            except Exception as exc:
                msg = str(exc).lower()
                if "already exists" in msg or "equivalent" in msg:
                    # Idempotent re-run — genuinely safe to skip.
                    continue
                # Real error (auth failure, network, version mismatch, etc.).
                raise

    def close(self) -> None:
        if self._driver is not None:
            try:
                self._driver.close()
            finally:
                self._driver = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.close()
