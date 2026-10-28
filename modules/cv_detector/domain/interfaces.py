"""
Interfaces for Computer Vision Detector.
Following Dependency Inversion Principle (DIP).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple
from PIL import Image


class ICoordinateParser(ABC):
    """Abstract interface for parsing bounding coordinates."""

    @abstractmethod
    def parse_coordinates(self, line: str) -> List[float]:
        """Parse a line into [x1, y1, x2, y2]."""
        pass
