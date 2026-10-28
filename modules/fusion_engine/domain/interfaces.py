"""
Interfaces for Multimodal Fusion Engine.
Following Dependency Inversion Principle (DIP).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pathlib import Path


class IFusionWeightsLoader(ABC):
    """Abstract interface for loading and validating fusion weights."""

    @abstractmethod
    def load_weights(self, config_path: Optional[Path] = None) -> Dict[str, float]:
        """Load and return validated modality weights."""
        pass


class IFusionStrategy(ABC):
    """Abstract interface for fusing calibrated probabilities and evidence."""

    @abstractmethod
    def fuse(
        self,
        observation_id: str,
        run_id: str,
        outputs: List[Dict[str, Any]],
        weights: Dict[str, float]
    ) -> Dict[str, Any]:
        """Produce the fused result dictionary and status."""
        pass
