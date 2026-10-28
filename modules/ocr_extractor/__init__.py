"""
OCR Extractor package exports.
"""

from modules.ocr_extractor.extractor import extract_ocr, pytesseract
from modules.ocr_extractor.service import OCRExtractorService

__all__ = ["extract_ocr", "OCRExtractorService", "pytesseract"]
