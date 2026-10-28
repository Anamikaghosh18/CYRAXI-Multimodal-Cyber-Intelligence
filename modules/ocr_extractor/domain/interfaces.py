"""
Interfaces for OCR Extractor.
Following Dependency Inversion Principle (DIP).
"""

from abc import ABC, abstractmethod
from typing import Tuple, List, Dict, Any, Optional
from PIL import Image


class IOCREngine(ABC):
    """Abstract interface for low-level optical character recognition engines."""

    @abstractmethod
    def extract_words(self, image: Image.Image, warnings: List[Dict[str, Any]]) -> Tuple[str, List[float], List[Dict[str, Any]]]:
        """Return (full_text, confidences, bounding_boxes)."""
        pass
