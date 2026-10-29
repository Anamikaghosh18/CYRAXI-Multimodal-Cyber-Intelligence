"""
Community Detection using Python Graph Libraries
Implements Louvain clustering for observation similarity graphs.
"""

from typing import Dict, List, Optional, Tuple
import networkx as nx
from datetime import datetime, timezone


class CommunityDetector:
    """
    Detects communities in observation similarity graphs using Louvain algorithm.

    Uses networkx for graph operations and python-louvain for clustering.
    """

    def __init__(self, use_louvain: bool = True):
        """
        Initialize community detector.

        Args:
            use_louvain: Use Louvain algorithm (requires python-louvain)
        """
        self.use_louvain = use_louvain
        self.graph = nx.Graph()

    def build_similarity_graph(
        self,
        similarities: List[Dict],
        min_weight: float = 0.3,
    ) -> nx.Graph:
        """
        Build a NetworkX graph from similarity results.

        Args:
            similarities: List of similarity result dictionaries
            min_weight: Minimum similarity score to include as edge

        Returns:
            NetworkX graph
        """
        self.graph = nx.Graph()

        for sim in similarities:
            obs1 = sim["observation_id_1"]
            obs2 = sim["observation_id_2"]
            weight = sim["similarity_score"]

            if weight >= min_weight:
                self.graph.add_edge(obs1, obs2, weight=weight)

        return self.graph

    def detect_communities(self, resolution: float = 1.0) -> Dict[str, int]:
        """
        Detect communities using Louvain algorithm.

        Args:
            resolution: Resolution parameter for Louvain (higher = fewer communities)

        Returns:
            Dictionary mapping observation_id to community_id
        """
        if self.graph.number_of_nodes() == 0:
            return {}

        try:
            import community as community_louvain
            partition = community_louvain.best_partition(self.graph, resolution=resolution)
            return partition
        except ImportError:
            # Fallback to connected components if python-louvain not available
            print("  [WARNING] python-louvain not installed, using connected components")
            return self._connected_components_fallback()

    def _connected_components_fallback(self) -> Dict[str, int]:
        """Fallback to connected components if Louvain unavailable."""
        partition = {}
        for i, component in enumerate(nx.connected_components(self.graph)):
            for node in component:
                partition[node] = i
        return partition

    def analyze_cluster(
        self,
        community_id: int,
        partition: Dict[str, int],
        observation_data: Dict[str, Dict],
    ) -> Dict:
        """
        Analyze a community cluster.

        Args:
            community_id: Community ID to analyze
            partition: Full partition mapping
            observation_data: Observation metadata

        Returns:
            Cluster analysis dictionary
        """
        members = [obs_id for obs_id, cid in partition.items() if cid == community_id]

        if not members:
            return {}

        # Extract cluster statistics
        domains = set()
        brands = set()
        ips = set()
        family_ids = set()

        for obs_id in members:
            obs = observation_data.get(obs_id, {})
            domains.add(obs.get("domain") or obs.get("host", ""))
            brands.add(obs.get("brand", ""))
            ips.add(obs.get("ip", ""))
            family_ids.add(obs.get("family_id", ""))

        # Find internal edges
        internal_edges = 0
        total_edge_weight = 0.0

        for i, obs1 in enumerate(members):
            for obs2 in members[i+1:]:
                if self.graph.has_edge(obs1, obs2):
                    internal_edges += 1
                    total_edge_weight += self.graph[obs1][obs2].get("weight", 0.0)

        return {
            "cluster_id": community_id,
            "member_count": len(members),
            "member_ids": members,
            "unique_domains": len([d for d in domains if d]),
            "unique_brands": len([b for b in brands if b]),
            "unique_ips": len([ip for ip in ips if ip]),
            "unique_family_ids": len([f for f in family_ids if f]),
            "internal_edges": internal_edges,
            "avg_edge_weight": total_edge_weight / internal_edges if internal_edges > 0 else 0.0,
            "top_domains": list(domains)[:5],
            "top_brands": list(brands)[:5],
            "representative_observation": members[0] if members else None,
        }

    def get_all_clusters(
        self,
        partition: Dict[str, int],
        observation_data: Dict[str, Dict],
        min_cluster_size: int = 2,
    ) -> List[Dict]:
        """Get analysis for all clusters above minimum size."""
        unique_communities = set(partition.values())
        clusters = []

        for comm_id in unique_communities:
            analysis = self.analyze_cluster(comm_id, partition, observation_data)
            if analysis and analysis["member_count"] >= min_cluster_size:
                clusters.append(analysis)

        # Sort by member count descending
        clusters.sort(key=lambda x: x["member_count"], reverse=True)
        return clusters
