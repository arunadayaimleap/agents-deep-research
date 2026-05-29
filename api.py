#!/usr/bin/env python3
"""
FastAPI app for criminal case news research.
Endpoints:
  POST /research     - Start research, returns task_id
  GET  /research/{task_id}/status
  GET  /research/{task_id}/report
"""

import json
import os
import sys
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

_project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv

load_dotenv(_project_root / ".env")
os.environ.setdefault("SEARCH_PROVIDER", "openrouter")

from run_crime_research import _timestamped_basename, run_research

app = FastAPI(title="Crime Case Research API", version="1.0.0")
TASKS: dict[str, dict] = {}


class ResearchRequest(BaseModel):
    region: str | None = Field(None, description="Geographic focus (US, UK, global, etc.)")
    max_cases: int = Field(5, description="Number of top cases to cover")
    case: str | None = Field(None, description="Specific case headline/name instead of top-N")
    model: str | None = Field(None, description="OpenRouter model (default: deepseek/deepseek-v3.2)")
    max_iterations: int = Field(5)
    max_time: int = Field(45, description="Max time in minutes")


class ResearchStartResponse(BaseModel):
    task_id: str


class ResearchStatusResponse(BaseModel):
    task_id: str
    status: str
    error: str | None = None


class ResearchReportResponse(BaseModel):
    task_id: str
    report_path: str


async def _run_research_task(task_id: str, req: ResearchRequest):
    base = _timestamped_basename(req.region, req.case)
    out_dir = _project_root / "outputs"
    out_dir.mkdir(exist_ok=True)
    report_path = out_dir / f"{base}.md"
    json_path = out_dir / f"{base}.json"
    relative_md = f"outputs/{base}.md"
    relative_json = f"outputs/{base}.json"

    try:
        TASKS[task_id]["status"] = "running"
        report, extracted = await run_research(
            region=req.region,
            max_cases=req.max_cases,
            case_hint=req.case,
            max_iterations=req.max_iterations,
            max_time=req.max_time,
            model=req.model,
        )
        report_path.write_text(report, encoding="utf-8")
        if extracted:
            json_path.write_text(json.dumps(extracted, indent=2, ensure_ascii=False), encoding="utf-8")
        TASKS[task_id]["status"] = "completed"
        TASKS[task_id]["report_path"] = relative_md
        TASKS[task_id]["json_path"] = relative_json
    except Exception as e:
        TASKS[task_id]["status"] = "failed"
        TASKS[task_id]["error"] = str(e)


@app.post("/research", response_model=ResearchStartResponse)
async def start_research(req: ResearchRequest, background_tasks: BackgroundTasks):
    """Start crime case research. Returns task_id to poll status and get report."""
    task_id = str(uuid.uuid4())
    TASKS[task_id] = {"status": "pending", "report_path": None, "error": None}
    background_tasks.add_task(_run_research_task, task_id, req)
    return ResearchStartResponse(task_id=task_id)


@app.get("/research/{task_id}/status", response_model=ResearchStatusResponse)
async def get_status(task_id: str):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    t = TASKS[task_id]
    return ResearchStatusResponse(task_id=task_id, status=t["status"], error=t.get("error"))


@app.get("/research/{task_id}/report", response_model=ResearchReportResponse)
async def get_report_path(task_id: str):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    t = TASKS[task_id]
    if t["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Task not completed (status: {t['status']})")
    path = t.get("report_path")
    if not path:
        raise HTTPException(status_code=500, detail="Report path not set")
    return ResearchReportResponse(task_id=task_id, report_path=path)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
