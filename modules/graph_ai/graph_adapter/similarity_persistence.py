"""
Similarity Persistence
Persists computed similarity results to Neo4j.
"""

from typing import Dict, List, Optional
from datetime import datetime, timezone
import hashlib
from modules.graph_enrichment_mapper.infra.neo4j_driver import Neo4jDriver


class SimilarityPersistence:
    """Persists similarity relationships to Neo4j."""

    def __init__(self, driver: Neo4jDriver):
        self.driver = driver
        self._apply_schema()

    def _apply_schema(self) -> None:
        """Create constraints and indexes for similarity relationships."""
        statements = [
            # Constraint for similarity result ID
            "CREATE CONSTRAINT c_sim_id IF NOT EXISTS FOR (s:SimilarityResult) REQUIRE s.similarity_id IS UNIQUE",
            # Indexes for query performance
            "CREATE INDEX idx_sim_obs1 IF NOT EXISTS FOR ()-[r:CANDIDATE_SIMILAR_TO]->() ON (r.observation_id_1)",
            "CREATE INDEX idx_sim_obs2 IF NOT EXISTS FOR ()-[r:CANDIDATE_SIMILAR_TO]->() ON (r.observation_id_2)",
            "CREATE INDEX idx_sim_score IF NOT EXISTS FOR ()-[r:CANDIDATE_SIMILAR_TO]->() ON (r.similarity_score)",
        ]
        for stmt in statements:
            try:
                self.driver.run_write(stmt)
            except Exception:
                pass

    def persist_similarity(
        self,
        obs_id_1: str,
        obs_id_2: str,
        similarity_result: Dict,
        run_id: str,
    ) -> None:
        """
        Persist a similarity result to Neo4j.

        Creates a CANDIDATE_SIMILAR_TO relationship between observations
        with all supporting metadata.
        """
        # Generate stable similarity ID
        sim_id = f"sim_{hashlib.md5(f'{obs_id_1}_{obs_id_2}_{run_id}'.encode()).hexdigest()}"

        self.driver.run_write(
            """
            MERGE (o1:Observation {observation_id: $obs_id_1})
            MERGE (o2:Observation {observation_id: $obs_id_2})

            MERGE (o1)-[r:CANDIDATE_SIMILAR_TO]->(o2)
            ON CREATE SET
                r.similarity_id = $sim_id,
                r.similarity_score = $score,
                r.category = $category,
                r.contributing_features = $features,
                r.explanation = $explanation,
                r.algorithm_version = $version,
                r.run_id = $run_id,
                r.computed_at = $computed_at
            ON MATCH SET
                r.similarity_score = $score,
                r.category = $category,
                r.contributing_features = $features,
                r.explanation = $explanation,
                r.computed_at = $computed_at
            """,
            {
                "obs_id_1": obs_id_1,
                "obs_id_2": obs_id_2,
                "sim_id": sim_id,
                "score": similarity_result["similarity_score"],
                "category": similarity_result["category"],
                "features": similarity_result["contributing_features"],
                "explanation": similarity_result["explanation"],
                "version": similarity_result["algorithm_version"],
                "run_id": run_id,
                "computed_at": similarity_result["computed_at"],
            },
        )

    def batch_persist_similarities(
        self,
        similarities: List[Dict],
        run_id: str,
    ) -> int:
        """Persist multiple similarity results in batch."""
        count = 0
        for sim in similarities:
            self.persist_similarity(
                sim["observation_id_1"],
                sim["observation_id_2"],
                sim,
                run_id,
            )
            count += 1
        return count

    def get_similar_observations(
        self,
        obs_id: str,
        min_score: float = 0.0,
        limit: int = 50,
    ) -> List[Dict]:
        """Retrieve observations similar to a given observation."""
        rows = self.driver.run_query(
            """
            MATCH (o1:Observation {observation_id: $obs_id})-[r:CANDIDATE_SIMILAR_TO]->(o2:Observation)
            WHERE r.similarity_score >= $min_score
            RETURN
                o2.observation_id AS observation_id,
                r.similarity_score AS similarity_score,
                r.category AS category,
                r.explanation AS explanation,
                r.contributing_features AS features
            ORDER BY r.similarity_score DESC
            LIMIT $limit
            """,
            {"obs_id": obs_id, "min_score": min_score, "limit": limit},
        )
        return rows
