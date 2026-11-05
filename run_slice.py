"""
Run Slice Compatibility Shim
Re-exports validate_observation_record and slice helpers for backward compatibility.
"""

from modules.dataset_adapter.validator import validate_observation_record

__all__ = ["validate_observation_record"]
