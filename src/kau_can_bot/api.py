from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .answer import WebsiteGroundedAssistant
from .branding import prepare_branding_assets
from .config import INDEX_PATH, ROOT_DIR, Settings
from .learning import learning_summary, log_feedback


api = FastAPI(title="KAÜ CAN Chat Bot", version="0.1.0")
STATIC_DIR = ROOT_DIR / "static"
BRANDING = prepare_branding_assets(ROOT_DIR)

if STATIC_DIR.exists():
    api.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class AskRequest(BaseModel):
    question: str


class SourceItem(BaseModel):
    title: str
    url: str
    score: float


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceItem] = Field(default_factory=list)
    interaction_id: Optional[str] = None
    status: str = "ok"


class FeedbackRequest(BaseModel):
    interaction_id: str
    rating: str
    comment: str = ""


@api.get("/", include_in_schema=False)
def home() -> FileResponse:
    index_path = Path(STATIC_DIR / "index.html")
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Arayüz dosyası bulunamadı.")
    return FileResponse(index_path)


@api.get("/health")
def health() -> Dict[str, object]:
    settings = Settings()
    ollama_status = _ollama_status(settings)
    return {
        "ok": True,
        "index_ready": INDEX_PATH.exists(),
        "llm_provider": settings.llm_provider,
        "crawl_scope": settings.crawl_scope,
        "learning": learning_summary(),
        "openai_configured": bool(settings.openai_api_key),
        "openai_model": settings.openai_model,
        "ollama_configured": bool(settings.ollama_model),
        "ollama_model": settings.ollama_model,
        "ollama_host": settings.ollama_host,
        "ollama_running": ollama_status["running"],
        "ollama_model_available": ollama_status["model_available"],
        "logo_url": BRANDING.logo_url,
    }


@api.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    if not INDEX_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Arama indeksi hazır değil. Önce site taranmalı ve indekslenmelidir.",
    )

    assistant = WebsiteGroundedAssistant()
    response = assistant.answer_with_context(request.question)
    return AskResponse(
        answer=response.answer,
        sources=[
            SourceItem(
                title=result.chunk.title,
                url=result.chunk.url,
                score=round(result.score, 6),
            )
            for result in response.sources
        ],
        interaction_id=response.interaction_id,
        status=response.status,
    )


@api.post("/feedback")
def feedback(request: FeedbackRequest) -> Dict[str, object]:
    rating = request.rating.strip().lower()
    if rating not in {"up", "down"}:
        raise HTTPException(status_code=400, detail="Geçerli değerler: up, down.")
    log_feedback(request.interaction_id, rating, request.comment)
    return {"ok": True}


def _ollama_status(settings: Settings) -> Dict[str, bool]:
    if settings.llm_provider != "ollama":
        return {"running": False, "model_available": False}

    try:
        response = requests.get(
            f"{settings.ollama_host.rstrip('/')}/api/tags",
            timeout=1.5,
        )
        response.raise_for_status()
    except requests.RequestException:
        return {"running": False, "model_available": False}

    model_names = [
        item.get("name", "")
        for item in response.json().get("models", [])
        if isinstance(item, dict)
    ]
    expected = settings.ollama_model
    expected_latest = expected if ":" in expected else f"{expected}:latest"
    return {
        "running": True,
        "model_available": expected in model_names or expected_latest in model_names,
    }
