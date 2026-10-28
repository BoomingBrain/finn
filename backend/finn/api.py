"""The Render service. It exists only for live research on tickers without a precomputed dossier;
everything else is served as static files from the Hugging Face Space."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

LOCAL_DEV_ORIGIN = "http://localhost:5173"


def create_app() -> FastAPI:
    app = FastAPI(title="FINN research API", docs_url=None, redoc_url=None)
    origins = [o.strip() for o in os.environ.get("WEB_ORIGIN", "").split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins + [LOCAL_DEV_ORIGIN], allow_methods=["GET"],
                       allow_headers=["*"])

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "service": "finn-research"}

    @app.get("/", include_in_schema=False)
    def root():
        # This service has no pages of its own; send people who open its URL to the app.
        if origins:
            return RedirectResponse(origins[0])
        return {"service": "finn-research", "app": "not configured"}

    return app


app = create_app()
