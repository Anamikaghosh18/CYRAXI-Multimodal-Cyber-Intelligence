"""
Fusion Engine Domain Service — thin wrapper around the canonical fusion algorithm.
The full algorithm lives in fusion.py; this class adapts it to the service interface
used by the API server and future pipeline callers.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional

# Import the battle-tested canonical implementation unchanged
from modules.fusion_engine.fusion import fuse_predictions as _fuse_predictions


class FusionEngineService:
    """Service adapter exposing the canonical fusion algorithm via an OO interface."""

    def __init__(self, config_path: Optional[Path] = None):
        self._config_path = config_path

    def fuse(
        self,
        observation_id: str,
        run_id: str,
        outputs: List[Dict[str, Any]],
        config_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Delegate to the canonical fuse_predictions implementation.

        The config_path override is supported for test isolation; the canonical
        implementation reads CONFIG_PATH from its module-level variable.
        """
        active_path = config_path or self._config_path
        if active_path is not None:
            # Temporarily patch the module-level CONFIG_PATH for this call
            import modules.fusion_engine.fusion as _fusion_module
            original = _fusion_module.CONFIG_PATH
            _fusion_module.CONFIG_PATH = active_path
            try:
                return _fuse_predictions(observation_id, run_id, outputs)
            finally:
                _fusion_module.CONFIG_PATH = original
        return _fuse_predictions(observation_id, run_id, outputs)
