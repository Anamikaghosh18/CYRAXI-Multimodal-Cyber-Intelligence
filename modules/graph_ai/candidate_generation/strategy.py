"""
Candidate Generation Strategy
Generates observation pairs for similarity analysis using indexing strategies.
"""

from typing import Dict, List, Set, Tuple, Optional, Generator
from collections import defaultdict
import hashlib


class CandidateGenerator:
    """
    Generates candidate observation pairs for similarity analysis.

    Uses multiple indexing strategies to find plausible pairs without
    comparing every observation against every other observation.
    """

    def __init__(
        self,
        max_candidates_per_obs: int = 100,
        use_domain_index: bool = True,
        use_ip_index: bool = True,
        use_brand_index: bool = True,
        use_url_similarity: bool = False,
        brand_candidate_limit: int = 50,
    ):
        """
        Initialize candidate generator.

        Args:
            max_candidates_per_obs: Maximum candidates to generate per observation
            use_domain_index: Use domain-based indexing
            use_ip_index: Use IP-based indexing
            use_brand_index: Use brand-based indexing (with limits)
            use_url_similarity: Use URL token similarity (more expensive)
            brand_candidate_limit: Max candidates per brand to avoid popular brands
        """
        self.max_candidates_per_obs = max_candidates_per_obs
        self.use_domain_index = use_domain_index
        self.use_ip_index = use_ip_index
        self.use_brand_index = use_brand_index
        self.use_url_similarity = use_url_similarity
        self.brand_candidate_limit = brand_candidate_limit

        # Indexes
        self.domain_index: Dict[str, List[str]] = defaultdict(list)
        self.ip_index: Dict[str, List[str]] = defaultdict(list)
        self.brand_index: Dict[str, List[str]] = defaultdict(list)
        self.observation_data: Dict[str, Dict] = {}

    def add_observation(self, obs_id: str, obs_data: Dict) -> None:
        """
        Add an observation to the indexes.

        Args:
            obs_id: Observation ID
            obs_data: Dictionary containing url, host, domain, ip, brand, etc.
        """
        self.observation_data[obs_id] = obs_data

        # Domain index
        if self.use_domain_index:
            domain = obs_data.get("domain") or obs_data.get("host")
            if domain:
                self.domain_index[domain].append(obs_id)

        # IP index
        if self.use_ip_index:
            ip = obs_data.get("ip")
            if ip:
                self.ip_index[ip].append(obs_id)

        # Brand index
        if self.use_brand_index:
            brand = obs_data.get("brand")
            if brand:
                self.brand_index[brand].append(obs_id)

    def generate_candidates(
        self,
        obs_id: Optional[str] = None,
    ) -> Generator[Tuple[str, str, str], None, None]:
        """
        Generate candidate observation pairs.

        Args:
            obs_id: If provided, only generate candidates for this observation.
                    If None, generate candidates for all observations.

        Yields:
            Tuples of (obs_id_1, obs_id_2, method) where method indicates
            how the pair was discovered (e.g., "shared_domain", "shared_ip").
        """
        target_obs_ids = [obs_id] if obs_id else list(self.observation_data.keys())

        for target_id in target_obs_ids:
            if target_id not in self.observation_data:
                continue

            obs_data = self.observation_data[target_id]
            candidates: Set[str] = set()

            # Domain-based candidates
            if self.use_domain_index:
                domain = obs_data.get("domain") or obs_data.get("host")
                if domain and domain in self.domain_index:
                    for candidate in self.domain_index[domain]:
                        if candidate != target_id:
                            candidates.add(candidate)
                            yield (target_id, candidate, "shared_domain")

            # IP-based candidates
            if self.use_ip_index:
                ip = obs_data.get("ip")
                if ip and ip in self.ip_index:
                    for candidate in self.ip_index[ip]:
                        if candidate != target_id:
                            candidates.add(candidate)
                            yield (target_id, candidate, "shared_ip")

            # Brand-based candidates (with limit)
            if self.use_brand_index:
                brand = obs_data.get("brand")
                if brand and brand in self.brand_index:
                    brand_obs = self.brand_index[brand]
                    # Limit candidates from popular brands
                    if len(brand_obs) > self.brand_candidate_limit:
                        # Take first N (could be random in production)
                        brand_obs = brand_obs[:self.brand_candidate_limit]
                    for candidate in brand_obs:
                        if candidate != target_id and candidate not in candidates:
                            candidates.add(candidate)
                            yield (target_id, candidate, "shared_brand")

            # Enforce per-observation limit
            if len(candidates) > self.max_candidates_per_obs:
                # In production, could use ranking to keep best candidates
                # For now, just take first N
                candidates = set(list(candidates)[:self.max_candidates_per_obs])

    def get_statistics(self) -> Dict:
        """Get statistics about the indexes."""
        return {
            "total_observations": len(self.observation_data),
            "unique_domains": len(self.domain_index),
            "unique_ips": len(self.ip_index),
            "unique_brands": len(self.brand_index),
            "avg_observations_per_domain": (
                sum(len(v) for v in self.domain_index.values()) / max(len(self.domain_index), 1)
            ),
            "avg_observations_per_ip": (
                sum(len(v) for v in self.ip_index.values()) / max(len(self.ip_index), 1)
            ),
            "avg_observations_per_brand": (
                sum(len(v) for v in self.brand_index.values()) / max(len(self.brand_index), 1)
            ),
        }
