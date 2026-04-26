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
from .official_data import ensure_faculty_content, get_official_snapshot


api = FastAPI(title="KAÜ CAN Chat Bot", version="0.1.0")
STATIC_DIR = ROOT_DIR / "static"
BRANDING = prepare_branding_assets(ROOT_DIR)

if STATIC_DIR.exists():
    api.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@api.middleware("http")
async def disable_cache_for_ui(request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


class AskRequest(BaseModel):
    question: str
    client_id: str = ""
    preferred_language: str = ""


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


class HighlightItem(BaseModel):
    title: str
    url: str
    image_url: str = ""
    date: str = ""
    summary: str = ""
    category: str = ""


class HighlightsResponse(BaseModel):
    announcements: list[HighlightItem] = Field(default_factory=list)
    news: list[HighlightItem] = Field(default_factory=list)
    events: list[HighlightItem] = Field(default_factory=list)
    updated_at: str = ""


@api.get("/", include_in_schema=False)
def home() -> FileResponse:
    index_path = Path(STATIC_DIR / "index.html")
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Arayüz dosyası bulunamadı.")
    return FileResponse(
        index_path,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


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
        "chat_logo_url": BRANDING.chat_logo_url,
    }


@api.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    if not INDEX_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Arama indeksi hazır değil. Önce site taranmalı ve indekslenmelidir.",
    )

    assistant = WebsiteGroundedAssistant()
    response = assistant.answer_with_context(
        request.question,
        client_id=request.client_id,
        preferred_language=request.preferred_language,
    )
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


@api.get("/highlights", response_model=HighlightsResponse)
def highlights() -> HighlightsResponse:
    try:
        snapshot = ensure_faculty_content(get_official_snapshot())
    except Exception:
        snapshot = {"faculty_content": {}, "updated_at": ""}

    faculty_content = snapshot.get("faculty_content", {})
    return HighlightsResponse(
        announcements=_serialize_highlights(faculty_content.get("announcements", [])),
        news=_serialize_highlights(faculty_content.get("news", [])),
        events=_serialize_highlights(faculty_content.get("events", [])),
        updated_at=str(snapshot.get("updated_at", "")),
    )


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


def _serialize_highlights(items: list[dict]) -> list[HighlightItem]:
    return [
        HighlightItem(
            title=str(item.get("title", "")),
            url=str(item.get("url", "")),
            image_url=str(item.get("image_url", "")),
            date=str(item.get("date", "")),
            summary=str(item.get("summary", "")),
            category=str(item.get("type", "")),
        )
        for item in items
        if item.get("title") and item.get("url")
    ]
