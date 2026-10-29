"""
Candidate Generation Module
Generates plausible observation pairs for similarity analysis
using indexing strategies to avoid quadratic O(NÂ²) comparisons.
"""

from modules.graph_ai.candidate_generation.strategy import CandidateGenerator

__all__ = ["CandidateGenerator"]
