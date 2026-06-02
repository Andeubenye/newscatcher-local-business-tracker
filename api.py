"""
FastAPI backend for the local business tracker demo.
Not shown in the article — wired to the map frontend separately.

Routes:
    POST /api/search          — submit a tracker job
    GET  /api/status/{job_id} — poll job status
    GET  /api/results/{job_id}— pull normalized results
    GET  /health              — health check
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional

from core.catchall_client import submit, get_status, pull_all, create_monitor
from core.skill import SKILL_CONTEXT, SKILL_VALIDATORS, SKILL_ENRICHMENTS
from core.normalize import normalize_record, deduplicate, filter_by_qualifier, filter_by_confidence


app = FastAPI(title="Local Business Tracker API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    business_type: str = Field(..., example="restaurant")
    city: str = Field(..., example="Yishun")
    country: str = Field(..., example="Singapore")
    street: Optional[str] = Field(default="", example="")
    days: int = Field(default=14, ge=1, le=30)
    signal_term: str = Field(default="grand opening", example="grand opening")
    limit: Optional[int] = Field(default=50, ge=1, le=200)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def serve_frontend():
    """Serve the map frontend — wired separately."""
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"message": "Frontend not yet wired. See index.html."}


@app.post("/api/search")
def api_search(body: SearchRequest):
    """
    Submit a local business opening job to CatchAll.
    Returns job_id for polling.
    """
    location = (
        f"{body.street}, {body.city}, {body.country}".strip(", ")
        if body.street
        else f"{body.city}, {body.country}"
    )
    query = f"{body.signal_term} {body.business_type} {location} last {body.days} days"

    try:
        job_id = submit(
            query=query,
            context=SKILL_CONTEXT,
            validators=SKILL_VALIDATORS,
            enrichments=SKILL_ENRICHMENTS,
            limit=body.limit,
        )
        return {"job_id": job_id, "query": query, "status": "submitted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status/{job_id}")
def api_status(job_id: str):
    """Poll job status."""
    try:
        return get_status(job_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/results/{job_id}")
def api_results(
    job_id: str,
    qualifier: Optional[str] = None,
    confidence: Optional[str] = None,
):
    """
    Pull and normalize results for a completed job.
    Optional query params:
        qualifier  — comma-separated: now_open,event_held,date_announced,coming_soon
        confidence — high, medium, or low
    """
    try:
        raw = pull_all(job_id)
        normalized = [normalize_record(r) for r in raw]
        results = deduplicate(normalized)

        if qualifier:
            qualifiers = [q.strip() for q in qualifier.split(",")]
            results = filter_by_qualifier(results, qualifiers)

        if confidence:
            results = filter_by_confidence(results, confidence)

        return {
            "job_id": job_id,
            "total": len(results),
            "results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/monitor/create")
def api_create_monitor(job_id: str, schedule: str = "every day at 8 AM UTC"):
    """Turn a completed job into a daily recurring monitor."""
    try:
        monitor_id = create_monitor(job_id, schedule)
        return {"monitor_id": monitor_id, "schedule": schedule}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
