#!/usr/bin/env python3
"""
FastAPI app for MRO deep research.
Endpoints:
  POST /research     - Start research, returns task_id
  GET  /research/{task_id}/status - Get task status
  GET  /research/{task_id}/report - Get relative path to md report
"""

import asyncio
import json
import uuid
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

# Add project root to path before imports
_project_root = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv
load_dotenv(_project_root / ".env")

from run_mro_research import (
    run_research,
    _slug,
    extract_json_from_report,
)

app = FastAPI(title="MRO Deep Research API", version="1.0.0")

# In-memory task store: task_id -> {status, report_path, error}
TASKS: dict[str, dict] = {}


class ResearchRequest(BaseModel):
    aircraft: str = Field(..., description="Aircraft model (e.g. Boeing 737-800)")
    engine: str = Field(..., description="Engine model (e.g. CFM56-7B)")
    supplier: str = Field(..., description="Engine supplier (e.g. CFM International)")
    context: str | None = Field(None, description="Optional context")
    model: str | None = Field(None, description="LLM model (default: deepseek/deepseek-v3.2)")
    max_iterations: int = Field(5, description="Max research iterations")
    max_time: int = Field(60, description="Max time in minutes")


class ResearchStartResponse(BaseModel):
    task_id: str


class ResearchStatusResponse(BaseModel):
    task_id: str
    status: str  # pending, running, completed, failed
    error: str | None = None


class ResearchReportResponse(BaseModel):
    task_id: str
    report_path: str  # Relative path, e.g. outputs/boeing_737-800_..._mro_report.md


async def _run_research_task(task_id: str, req: ResearchRequest):
    slug = f"{_slug(req.aircraft)}_{_slug(req.engine)}_{_slug(req.supplier)}"
    out_dir = _project_root / "outputs"
    out_dir.mkdir(exist_ok=True)
    report_path = out_dir / f"{slug}_mro_report.md"
    relative_path = f"outputs/{slug}_mro_report.md"

    try:
        TASKS[task_id]["status"] = "running"
        report, extracted = await run_research(
            aircraft=req.aircraft,
            engine=req.engine,
            supplier=req.supplier,
            context=req.context,
            max_iterations=req.max_iterations,
            max_time=req.max_time,
            model=req.model,
        )
        report_path.write_text(report, encoding="utf-8")
        if extracted:
            json_path = report_path.with_suffix(".json")
            json_path.write_text(json.dumps(extracted, indent=2, ensure_ascii=False), encoding="utf-8")
        TASKS[task_id]["status"] = "completed"
        TASKS[task_id]["report_path"] = relative_path
    except Exception as e:
        TASKS[task_id]["status"] = "failed"
        TASKS[task_id]["error"] = str(e)


@app.post("/research", response_model=ResearchStartResponse)
async def start_research(req: ResearchRequest, background_tasks: BackgroundTasks):
    """Start MRO deep research. Returns task_id to poll status and get report."""
    task_id = str(uuid.uuid4())
    TASKS[task_id] = {"status": "pending", "report_path": None, "error": None}
    background_tasks.add_task(_run_research_task, task_id, req)
    return ResearchStartResponse(task_id=task_id)


@app.get("/research/{task_id}/status", response_model=ResearchStatusResponse)
async def get_status(task_id: str):
    """Get research task status."""
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    t = TASKS[task_id]
    return ResearchStatusResponse(
        task_id=task_id,
        status=t["status"],
        error=t.get("error"),
    )


@app.get("/research/{task_id}/report", response_model=ResearchReportResponse)
async def get_report_path(task_id: str):
    """Get relative path to the md report. Returns 404 if task not completed."""
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    t = TASKS[task_id]
    if t["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Task not completed (status: {t['status']})",
        )
    path = t.get("report_path")
    if not path:
        raise HTTPException(status_code=500, detail="Report path not set")
    return ResearchReportResponse(task_id=task_id, report_path=path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
