"""
api/main.py — FastAPI server for PostMortemAI
Exposes: POST /analyze, GET /stats, GET /health
"""

import os
import uuid
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from agents.orchestrator import run_analysis
from ingestion.embedder import get_db_stats

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PostMortemAI",
    description="Analyzes your startup against 5000+ failure postmortems",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    description: str
    thread_id: str = ""


class AnalyzeResponse(BaseModel):
    risk_report: str
    startup_profile: dict
    source_postmortems: list[dict]
    similar_failures_count: int
    thread_id: str
    error: str = ""


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/stats")
async def stats():
    try:
        db_stats = get_db_stats()
        return db_stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    if not req.description or len(req.description.strip()) < 20:
        raise HTTPException(
            status_code=400,
            detail="Please describe your startup in at least 20 characters"
        )

    thread_id = req.thread_id or str(uuid.uuid4())

    try:
        result = await run_analysis(req.description, thread_id=thread_id)
        return AnalyzeResponse(thread_id=thread_id, **result)
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
