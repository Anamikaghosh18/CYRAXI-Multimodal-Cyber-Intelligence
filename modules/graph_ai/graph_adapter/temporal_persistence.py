"""
Persistence for Near-Duplicate and Temporal Results
"""

from typing import Dict, List
from datetime import datetime, timezone
import hashlib
from modules.graph_enrichment_mapper.infra.neo4j_driver import Neo4jDriver


class NearDuplicatePersistence:
    """Persists near-duplicate relationships to Neo4j."""

    def __init__(self, driver: Neo4jDriver):
        self.driver = driver
        self._apply_schema()

    def _apply_schema(self) -> None:
        statements = [
            "CREATE CONSTRAINT c_near_dup_id IF NOT EXISTS FOR (r:NEAR_DUPLICATE_TO) REQUIRE r.near_dup_id IS UNIQUE",
            "CREATE INDEX idx_near_dup_obs1 IF NOT EXISTS FOR ()-[r:NEAR_DUPLICATE_TO]->() ON (r.observation_id_1)",
            "CREATE INDEX idx_near_dup_score IF NOT EXISTS FOR ()-[r:NEAR_DUPLICATE_TO]->() ON (r.jaccard_similarity)",
        ]
        for stmt in statements:
            try:
                self.driver.run_write(stmt)
            except Exception:
                pass

    def persist_near_duplicate(
        self,
        obs_id_1: str,
        obs_id_2: str,
        jaccard_similarity: float,
        run_id: str,
    ) -> None:
        near_dup_id = f"near_dup_{hashlib.md5(f'{obs_id_1}_{obs_id_2}'.encode()).hexdigest()}"

        self.driver.run_write(
            """
            MERGE (o1:Observation {observation_id: $obs_id_1})
            MERGE (o2:Observation {observation_id: $obs_id_2})

            MERGE (o1)-[r:NEAR_DUPLICATE_TO]->(o2)
            ON CREATE SET
                r.near_dup_id = $near_dup_id,
                r.jaccard_similarity = $score,
                r.algorithm = 'minhash_lsh',
                r.run_id = $run_id,
                r.detected_at = $detected_at
            """,
            {
                "obs_id_1": obs_id_1,
                "obs_id_2": obs_id_2,
                "near_dup_id": near_dup_id,
                "score": jaccard_similarity,
                "run_id": run_id,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            },
        )


class TemporalPersistence:
    """Persists temporal analysis results to Neo4j."""

    def __init__(self, driver: Neo4jDriver):
        self.driver = driver
        self._apply_schema()

    def _apply_schema(self) -> None:
        statements = [
            "CREATE CONSTRAINT c_burst_id IF NOT EXISTS FOR (b:TemporalBurst) REQUIRE b.burst_id IS UNIQUE",
            "CREATE INDEX idx_burst_bucket IF NOT EXISTS FOR (b:TemporalBurst) ON (b.time_bucket)",
        ]
        for stmt in statements:
            try:
                self.driver.run_write(stmt)
            except Exception:
                pass

    def persist_burst(
        self,
        time_bucket: str,
        observation_count: int,
        threshold: float,
        run_id: str,
    ) -> None:
        burst_id = f"burst_{hashlib.md5(time_bucket.encode()).hexdigest()}"

        self.driver.run_write(
            """
            MERGE (b:TemporalBurst {burst_id: $burst_id})
            ON CREATE SET
                b.time_bucket = $time_bucket,
                b.observation_count = $count,
                b.threshold = $threshold,
                b.is_burst = true,
                b.run_id = $run_id,
                b.detected_at = $detected_at
            """,
            {
                "burst_id": burst_id,
                "time_bucket": time_bucket,
                "count": observation_count,
                "threshold": threshold,
                "run_id": run_id,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            },
        )
