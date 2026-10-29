"""
Graph Adapter Module
Handles persistence of similarity results, clusters, and rankings to Neo4j.
"""

from modules.graph_ai.graph_adapter.similarity_persistence import SimilarityPersistence

__all__ = ["SimilarityPersistence"]
