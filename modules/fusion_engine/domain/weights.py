"""
YAML / Configuration loader for Fusion Engine weights.
"""

import math
import re
from pathlib import Path
from typing import Dict, Optional

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = ROOT / "configs" / "fusion_weights.yaml"
CONFIG_PATH = DEFAULT_CONFIG_PATH
ALL_MODALITIES = ("url", "html_nlp", "ocr", "computer_vision")
PROBABILITY_MODALITIES = ("url", "html_nlp")


class FusionConfigurationError(ValueError):
    """Raised when fusion weights are absent or malformed."""


def load_yaml_weights(config_path: Optional[Path] = None) -> Dict[str, float]:
    path = Path(config_path or DEFAULT_CONFIG_PATH)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise FusionConfigurationError(
            f"Could not read fusion weights from {path}: {exc}"
        ) from exc

    in_weights = False
    found_weights = False
    weights = {}
    for line_number, raw_line in enumerate(lines, start=1):
        content = raw_line.split("#", 1)[0].rstrip()
        if not content.strip():
            continue
        indent = len(content) - len(content.lstrip())
        stripped = content.strip()

        if indent == 0:
            in_weights = stripped == "weights:"
            found_weights = found_weights or in_weights
            continue

        if not in_weights:
            continue

        if indent != 2:
            raise FusionConfigurationError(
                f"Invalid indentation in weights at {path}:{line_number}"
            )
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*):\s*([^\s]+)", stripped)
        if not match:
            raise FusionConfigurationError(
                f"Invalid weight entry at {path}:{line_number}: {stripped}"
            )
        name, raw_value = match.groups()
        if name not in ALL_MODALITIES:
            raise FusionConfigurationError(
                f"Unknown modality weight '{name}' at {path}:{line_number}"
            )
        if name in weights:
            raise FusionConfigurationError(
                f"Duplicate modality weight '{name}' at {path}:{line_number}"
            )
        try:
            value = float(raw_value)
        except ValueError as exc:
            raise FusionConfigurationError(
                f"Weight for {name} must be a finite non-negative number"
            ) from exc
        if not math.isfinite(value) or value < 0:
            raise FusionConfigurationError(
                f"Weight for {name} must be a finite non-negative number"
            )
        weights[name] = value

    if not found_weights:
        raise FusionConfigurationError(f"Missing 'weights:' mapping in {path}")
    missing = [name for name in ALL_MODALITIES if name not in weights]
    if missing:
        raise FusionConfigurationError(
            "Missing modality weights: " + ", ".join(missing)
        )
    if sum(weights[name] for name in PROBABILITY_MODALITIES) <= 0:
        raise FusionConfigurationError(
            "At least one probability-capable modality weight must be positive"
        )
    if not math.isfinite(sum(weights[name] for name in PROBABILITY_MODALITIES)):
        raise FusionConfigurationError(
            "Probability-capable modality weights have a non-finite total"
        )
    return weights
