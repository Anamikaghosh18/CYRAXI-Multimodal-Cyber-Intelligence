"""
Investigation Report Persistence
Stores investigation reports in Neo4j and/or filesystem.
"""

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict

from modules.graph_enrichment_mapper.infra.neo4j_driver import Neo4jDriver


class InvestigationPersistence:
    """Persists investigation reports to Neo4j and filesystem."""

    def __init__(
        self,
        neo4j_driver: Optional[Neo4jDriver] = None,
        output_dir: str = "output/investigations",
    ):
        self.neo4j_driver = neo4j_driver
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._apply_schema()

    def _apply_schema(self) -> None:
        """Apply Neo4j schema for investigation reports."""
        if not self.neo4j_driver:
            return

        statements = [
            "CREATE CONSTRAINT c_investigation_id IF NOT EXISTS FOR (i:Investigation) REQUIRE i.investigation_id IS UNIQUE",
            "CREATE INDEX idx_investigation_obs IF NOT EXISTS FOR (i:Investigation) ON (i.observation_id)",
            "CREATE INDEX idx_investigation_created IF NOT EXISTS FOR (i:Investigation) ON (i.created_at)",
        ]

        for stmt in statements:
            try:
                self.neo4j_driver.run_write(stmt)
            except Exception:
                pass

    def persist_to_neo4j(self, report: Dict) -> None:
        """Persist investigation report to Neo4j."""
        if not self.neo4j_driver:
            return

        try:
            query = """
            MERGE (i:Investigation {investigation_id: $investigation_id})
            ON CREATE SET
                i.investigation_id = $investigation_id,
                i.observation_id = $observation_id,
                i.input_type = $input_type,
                i.input_value = $input_value,
                i.status = $status,
                i.created_at = $created_at,
                i.schema_version = $schema_version
            ON MATCH SET
                i.status = $status,
                i.created_at = $created_at
            """

            self.neo4j_driver.run_write(
                query,
                {
                    "investigation_id": report["investigation_id"],
                    "observation_id": report["observation_id"],
                    "input_type": report["input_type"],
                    "input_value": report["input_value"],
                    "status": report["status"],
                    "created_at": report["created_at"],
                    "schema_version": report["schema_version"],
                },
            )

            # Store related observations as relationships
            for related in report.get("related_observations", []):
                self.neo4j_driver.run_write(
                    """
                    MATCH (i:Investigation {investigation_id: $investigation_id})
                    MATCH (o:Observation {observation_id: $related_obs_id})
                    MERGE (i)-[r:INVESTIGATED_WITH]->(o)
                    ON CREATE SET
                        r.similarity_score = $score,
                        r.relationship_type = $rel_type
                    """,
                    {
                        "investigation_id": report["investigation_id"],
                        "related_obs_id": related["observation_id"],
                        "score": related.get("similarity_score", 0.0),
                        "rel_type": related.get("relationship_type", "unknown"),
                    },
                )

        except Exception as e:
            print(f"Warning: Failed to persist to Neo4j: {e}")

    def persist_to_filesystem(self, report: Dict) -> str:
        """Persist investigation report to filesystem as JSON."""
        filename = f"{report['investigation_id']}.json"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return str(filepath)

    def persist(self, report: Dict, neo4j: bool = True, filesystem: bool = True) -> Dict:
        """Persist investigation report to configured backends."""
        result = {
            "neo4j": None,
            "filesystem": None,
        }

        if neo4j:
            try:
                self.persist_to_neo4j(report)
                result["neo4j"] = "success"
            except Exception as e:
                result["neo4j"] = f"error: {e}"

        if filesystem:
            try:
                filepath = self.persist_to_filesystem(report)
                result["filesystem"] = filepath
            except Exception as e:
                result["filesystem"] = f"error: {e}"

        return result
