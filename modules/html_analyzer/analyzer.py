"""
HTML / NLP Analysis Module.
Exposes public API and service for modular usage.
"""

from modules.html_analyzer.service import HTMLAnalysisService

_default_service = HTMLAnalysisService()


def analyze_html(observation_id, run_id, html_text, page_url=""):
    """Public functional entry-point preserving 100% backward compatibility."""
    return _default_service.analyze(
        observation_id=observation_id,
        run_id=run_id,
        html_text=html_text,
        page_url=page_url,
    )


__all__ = ["HTMLAnalysisService", "analyze_html"]
