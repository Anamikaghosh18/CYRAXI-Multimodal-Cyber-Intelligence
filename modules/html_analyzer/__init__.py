"""
HTML / NLP Module package exports.
"""

from modules.html_analyzer.analyzer import analyze_html
from modules.html_analyzer.service import HTMLAnalysisService

__all__ = ["analyze_html", "HTMLAnalysisService"]
