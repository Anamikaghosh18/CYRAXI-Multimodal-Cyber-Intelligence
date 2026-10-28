"""
FastAPI HTTP server for Multimodal Fusion Engine module.
"""

from typing import Dict, Any
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from modules.fusion_engine.domain.schemas import FuseOutputsRequest
from modules.fusion_engine.service import FusionEngineService


def create_app() -> FastAPI:
    app = FastAPI(
        title="CYRAXI Multimodal Fusion Engine API",
        version="1.1.0",
        description="Production API for calibrated probability and evidence fusion across modalities."
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    service = FusionEngineService()

    @app.get("/health", tags=["Health"])
    def health():
        return {"status": "healthy", "module": "fusion_engine", "api_version": "1.1.0"}

    @app.post("/api/v1/fusion/fuse", status_code=status.HTTP_200_OK, tags=["Fusion"])
    def fuse_endpoint(request: FuseOutputsRequest) -> Dict[str, Any]:
        return service.fuse(
            observation_id=request.observation_id,
            run_id=request.run_id,
            outputs=request.outputs,
        )

    return app


app = create_app()
