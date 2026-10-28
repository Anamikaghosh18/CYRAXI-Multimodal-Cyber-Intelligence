"""
Coordinate parser for YOLO / archive detection coordinates.
"""

import re
import math
from typing import List
from modules.cv_detector.domain.interfaces import ICoordinateParser


class StandardCoordinateParser(ICoordinateParser):
    """Parses whitespace separated or archive tuple coordinate lines."""

    def parse_coordinates(self, line: str) -> List[float]:
        number = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
        archive_row = re.fullmatch(
            rf"\(\s*({number})\s*,\s*({number})\s*,\s*({number})\s*,\s*({number})\s*\)\s+({number})",
            line.strip(),
        )
        if archive_row:
            values = [float(value) for value in archive_row.groups()[:4]]
            source_confidence = float(archive_row.group(5))
            if not math.isfinite(source_confidence) or not 0 <= source_confidence <= 1:
                raise ValueError("Source coordinate confidence must be in [0, 1]")
        else:
            values = [float(value) for value in line.split()]
            if len(values) != 4:
                raise ValueError("Expected four pixel coordinates or archive tuple plus source confidence")
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Coordinates must be finite numbers")
        return values
