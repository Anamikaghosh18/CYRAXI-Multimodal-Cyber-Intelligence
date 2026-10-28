"""
FastAPI HTTP server for Computer Vision logo detector module.
"""

import base64
from typing import Dict, Any
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from modules.cv_detector.domain.schemas import DetectCVRequest
from modules.cv_detector.service import CVDetectorService


def create_app() -> FastAPI:
    app = FastAPI(
        title="CYRAXI Computer Vision Detector API",
        version="1.0.0",
        description="Production API for logo detection and screenshot candidate cropping."
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    service = CVDetectorService()

    @app.get("/health", tags=["Health"])
    def health():
        return {"status": "healthy", "module": "cv_detector", "api_version": "1.0.0"}

    @app.post("/api/v1/cv/detect", status_code=status.HTTP_200_OK, tags=["CV Detection"])
    def detect_endpoint(request: DetectCVRequest) -> Dict[str, Any]:
        screenshot_bytes = None
        if request.screenshot_base64:
            screenshot_bytes = base64.b64decode(request.screenshot_base64)

        return service.detect(
            observation_id=request.observation_id,
            run_id=request.run_id,
            coordinates_text=request.coordinates_text,
            screenshot_bytes=screenshot_bytes,
        )

    return app


app = create_app()
