"""
FastAPI HTTP server for OCR Extractor module.
"""

import base64
from typing import Dict, Any
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from modules.ocr_extractor.domain.schemas import ExtractOCRRequest
from modules.ocr_extractor.service import OCRExtractorService


def create_app() -> FastAPI:
    app = FastAPI(
        title="CYRAXI OCR Extraction API",
        version="1.0.0",
        description="Production API for screenshot optical character recognition."
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    service = OCRExtractorService()

    @app.get("/health", tags=["Health"])
    def health():
        return {"status": "healthy", "module": "ocr_extractor", "api_version": "1.0.0"}

    @app.post("/api/v1/ocr/extract", status_code=status.HTTP_200_OK, tags=["OCR Extraction"])
    def extract_endpoint(request: ExtractOCRRequest) -> Dict[str, Any]:
        screenshot_bytes = None
        if request.screenshot_base64:
            screenshot_bytes = base64.b64decode(request.screenshot_base64)

        return service.extract(
            observation_id=request.observation_id,
            run_id=request.run_id,
            ocr_text=request.ocr_text,
            screenshot_bytes=screenshot_bytes,
        )

    return app


app = create_app()
