"""
Observation Record Validator
Validates canonical observation record structures against expected schemas and fields.
"""

from typing import Any, Dict, List


def validate_observation_record(obs: Dict[str, Any]) -> List[Dict[str, str]]:
    """Validate observation structure, IDs, and required fields according to canonical schema."""
    warnings: List[Dict[str, str]] = []

    # Check observation_id
    obs_id = obs.get("observation_id", "")
    if not obs_id.startswith("obs_") or len(obs_id) != 36:
        warnings.append({
            "code": "W_INVALID_OBS_ID",
            "message": f"Malformed observation ID: {obs_id}",
            "artifact_ref": None,
        })

    # Check URL
    raw_url = obs.get("url", {}).get("raw", "")
    if not raw_url:
        warnings.append({
            "code": "W_MISSING_URL",
            "message": "Raw URL is missing or empty in observation",
            "artifact_ref": "url.raw",
        })

    # Check artifacts
    artifacts = obs.get("artifacts", {})
    if not artifacts.get("screenshot"):
        warnings.append({
            "code": "W_MISSING_SCREENSHOT_REF",
            "message": "Screenshot artifact reference is missing",
            "artifact_ref": "artifacts.screenshot",
        })

    return warnings
