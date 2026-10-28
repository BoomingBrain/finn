"""The Render service. It exists only for live research on tickers without a precomputed dossier;
everything else is served as static files from the Hugging Face Space."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

LOCAL_DEV_ORIGIN = "http://localhost:5173"


def create_app() -> FastAPI:
    app = FastAPI(title="FINN research API", docs_url=None, redoc_url=None)
    origins = [o.strip() for o in os.environ.get("WEB_ORIGIN", "").split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins + [LOCAL_DEV_ORIGIN], allow_methods=["GET"],
                       allow_headers=["*"])

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "service": "finn-research"}

    return app


app = create_app()
