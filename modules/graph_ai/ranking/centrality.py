"""
Entity Ranking using Graph Centrality
Computes degree centrality and PageRank for graph entities.
"""

from typing import Dict, List, Optional
import networkx as nx
from datetime import datetime, timezone


class EntityRanker:
    """
    Computes centrality and PageRank scores for graph entities.
    """

    def __init__(self):
        self.graph = nx.Graph()

    def build_graph_from_observations(
        self,
        observations: List[Dict],
    ) -> nx.Graph:
        """
        Build domain-based graph from observations.

        Nodes = domains, edges = shared observations between domains.
        """
        self.graph = nx.Graph()
        domain_to_obs: Dict[str, List[str]] = {}

        # Group observations by domain
        for obs in observations:
            obs_id = obs["observation_id"]
            domain = obs.get("domain") or obs.get("host", "")
            if domain:
                if domain not in domain_to_obs:
                    domain_to_obs[domain] = []
                domain_to_obs[domain].append(obs_id)

        # Create edges between domains sharing observations
        domains = list(domain_to_obs.keys())
        for i, d1 in enumerate(domains):
            for d2 in domains[i+1:]:
                # Count shared observations
                shared = set(domain_to_obs[d1]) & set(domain_to_obs[d2])
                if shared:
                    self.graph.add_edge(d1, d2, weight=len(shared))

        return self.graph

    def compute_degree_centrality(self) -> Dict[str, float]:
        """Compute degree centrality for all nodes."""
        if self.graph.number_of_nodes() == 0:
            return {}
        return nx.degree_centrality(self.graph)

    def compute_pagerank(self, alpha: float = 0.85) -> Dict[str, float]:
        """
        Compute PageRank for all nodes.

        Args:
            alpha: Damping parameter (default 0.85)
        """
        if self.graph.number_of_nodes() == 0:
            return {}
        return nx.pagerank(self.graph, alpha=alpha)

    def rank_entities(
        self,
        method: str = "pagerank",
        top_k: int = 50,
    ) -> List[Dict]:
        """
        Rank entities by centrality score.

        Args:
            method: "degree" or "pagerank"
            top_k: Number of top entities to return

        Returns:
            List of ranked entities with scores
        """
        if method == "degree":
            scores = self.compute_degree_centrality()
        elif method == "pagerank":
            scores = self.compute_pagerank()
        else:
            raise ValueError(f"Unknown method: {method}")

        # Sort by score descending
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        return [
            {
                "entity_id": entity_id,
                "score": round(score, 4),
                "method": method,
                "rank": i + 1,
            }
            for i, (entity_id, score) in enumerate(ranked)
        ]
