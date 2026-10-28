"""
FastAPI HTTP server for HTML/NLP analyzer module.
"""

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any

from modules.html_analyzer.domain.schemas import AnalyzeHTMLRequest
from modules.html_analyzer.service import HTMLAnalysisService


def create_app() -> FastAPI:
    app = FastAPI(
        title="CYRAXI HTML/NLP Analysis API",
        version="1.0.0",
        description="Production API for DOM feature extraction and urgency NLP analysis."
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    service = HTMLAnalysisService()

    @app.get("/health", tags=["Health"])
    def health():
        return {"status": "healthy", "module": "html_analyzer", "api_version": "1.0.0"}

    @app.post("/api/v1/html/analyze", status_code=status.HTTP_200_OK, tags=["HTML Analysis"])
    def analyze_endpoint(request: AnalyzeHTMLRequest) -> Dict[str, Any]:
        return service.analyze(
            observation_id=request.observation_id,
            run_id=request.run_id,
            html_text=request.html_text,
            page_url=request.page_url,
        )

    return app


app = create_app()
