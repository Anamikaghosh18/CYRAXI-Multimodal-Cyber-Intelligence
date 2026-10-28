"""
Fusion Engine package exports.
The canonical algorithm is in fusion.py; this file just wires public symbols.
"""

from modules.fusion_engine.fusion import (
    fuse_predictions,
    FusionConfigurationError,
    CONFIG_PATH,
    ALL_MODALITIES,
    PROBABILITY_MODALITIES,
    _load_weights,
)
from modules.fusion_engine.service import FusionEngineService

__all__ = [
    "fuse_predictions",
    "FusionEngineService",
    "FusionConfigurationError",
    "CONFIG_PATH",
    "ALL_MODALITIES",
    "PROBABILITY_MODALITIES",
    "_load_weights",
]
