"""
Temporal Graph Analysis Module
Analyzes temporal patterns in phishing observations.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import networkx as nx


class TemporalGraphAnalyzer:
    """
    Analyzes temporal patterns in phishing observations.
    """

    def __init__(self):
        self.observations_by_time: List[Tuple[str, datetime]] = []
        self.graph = nx.Graph()

    def add_observation(self, obs_id: str, timestamp: str) -> None:
        """Add observation with timestamp."""
        try:
            if timestamp.endswith('Z'):
                ts = datetime.fromisoformat(timestamp)
            else:
                ts = datetime.fromisoformat(timestamp)
            self.observations_by_time.append((obs_id, ts))
        except Exception:
            pass  # Skip invalid timestamps

    def build_time_windowed_graph(
        self,
        window_days: int = 7,
    ) -> nx.Graph:
        """
        Build graph with edges between observations within time window.
        """
        if not self.observations_by_time:
            return self.graph

        # Sort by time
        sorted_obs = sorted(self.observations_by_time, key=lambda x: x[1])

        # Add all nodes first
        for obs_id, ts in sorted_obs:
            self.graph.add_node(obs_id, timestamp=ts, type='observation', time_bucket=ts.strftime('%Y-%W'))

        # Create edges between observations within time window
        for i, (obs_id_1, ts_1) in enumerate(sorted_obs):
            for obs_id_2, ts_2 in sorted_obs[i+1:]:
                time_diff = (ts_2 - ts_1).days
                if time_diff <= window_days:
                    self.graph.add_edge(obs_id_1, obs_id_2, weight=1.0 / (time_diff + 1))
                else:
                    break  # Stop when beyond window (since sorted)

        return self.graph

    def detect_bursts(
        self,
        window_days: int = 7,
        min_observations: int = 5,
    ) -> List[Dict]:
        """
        Detect time periods with unusually high observation volume.
        """
        if not self.observations_by_time:
            return []

        # Group by week
        weekly_counts = defaultdict(int)
        for obs_id, ts in self.observations_by_time:
            week_key = ts.strftime('%Y-%W')
            weekly_counts[week_key] += 1

        # Find bursts (weeks with significantly higher than average)
        counts = list(weekly_counts.values())
        if not counts:
            return []

        avg_count = sum(counts) / len(counts)
        std_count = (sum((c - avg_count) ** 2 for c in counts) / len(counts)) ** 0.5
        threshold = avg_count + 2 * std_count

        bursts = []
        for week_key, count in weekly_counts.items():
            if count >= threshold and count >= min_observations:
                bursts.append({
                    "time_bucket": week_key,
                    "observation_count": count,
                    "is_burst": True,
                    "threshold": threshold,
                })

        return sorted(bursts, key=lambda x: x["observation_count"], reverse=True)

    def analyze_temporal_clusters(
        self,
        observation_data: Dict[str, Dict],
    ) -> List[Dict]:
        """
        Analyze how communities evolve over time.
        """
        if not self.graph.number_of_nodes():
            return []

        # Group observations by time bucket
        time_buckets = defaultdict(list)
        for node, data in self.graph.nodes(data=True):
            if 'time_bucket' in data:
                time_buckets[data['time_bucket']].append(node)

        cluster_analysis = []
        for bucket, obs_ids in time_buckets.items():
            if len(obs_ids) >= 2:
                # Extract brands for this time bucket
                brands = set()
                for obs_id in obs_ids:
                    obs = observation_data.get(obs_id, {})
                    brand = obs.get("brand", "")
                    if brand:
                        brands.add(brand)

                cluster_analysis.append({
                    "time_bucket": bucket,
                    "observation_count": len(obs_ids),
                    "unique_brands": len(brands),
                    "top_brands": list(brands)[:5],
                })

        return sorted(cluster_analysis, key=lambda x: x["observation_count"], reverse=True)

    def get_statistics(self) -> Dict:
        """Get temporal statistics."""
        if not self.observations_by_time:
            return {"total_observations": 0}

        timestamps = [ts for _, ts in self.observations_by_time]
        return {
            "total_observations": len(self.observations_by_time),
            "earliest": min(timestamps).isoformat(),
            "latest": max(timestamps).isoformat(),
            "time_span_days": (max(timestamps) - min(timestamps)).days,
        }
