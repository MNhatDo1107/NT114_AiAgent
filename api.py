from fastapi import FastAPI, HTTPException, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uuid
import json
import re
import asyncio
from concurrent.futures import ThreadPoolExecutor
from crew_cv import CVMatchingCrew
from crew_improve import CVImproveCrewRunner as CVImproveCrew
import requests as http_requests
from crew_jobs import JobMatchCrew

app = FastAPI(title="CV Analysis AI Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(max_workers=4)
job_store: dict = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_crew_result(raw_output: str) -> dict:
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_output, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    match = re.search(r"\{.*\}", raw_output, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"Cannot parse JSON: {raw_output[:200]}")


# ── Models ────────────────────────────────────────────────────────────────────

class CVAnalysisRequest(BaseModel):
    cv_text: str
    jd_text: str
    analysis_id: Optional[str] = None

class CVAnalysisResult(BaseModel):
    analysis_id: str
    match_score: int
    cv_feedback: str
    matched_keywords: list[str]
    missing_keywords: list[str]
    ai_tips: str

class JobStatus(BaseModel):
    analysis_id: str
    status: str
    result: Optional[CVAnalysisResult] = None
    error: Optional[str] = None

class ImproveRequest(BaseModel):
    cv_text: str
    position_title: str
    position_key_skills: str

class JobsRequest(BaseModel):
    cv_text: str
    positions_list: str
    session_id: Optional[str] = None


# ── CV Analysis ───────────────────────────────────────────────────────────────

def run_crew_analysis(analysis_id: str, cv_text: str, jd_text: str):
    try:
        job_store[analysis_id]["status"] = "processing"
        crew_instance = CVMatchingCrew()
        result = crew_instance.crew().kickoff(
            inputs={"cv_text": cv_text, "jd_text": jd_text}
        )
        parsed = parse_crew_result(result.raw)
        job_store[analysis_id] = {
            "status": "completed",
            "result": {
                "analysis_id": analysis_id,
                "match_score": int(parsed.get("matchScore", 0)),
                "cv_feedback": parsed.get("cvFeedback", ""),
                "matched_keywords": parsed.get("matchedKeywords", []),
                "missing_keywords": parsed.get("missingKeywords", []),
                "ai_tips": parsed.get("aiTips", ""),
            }
        }
    except Exception as e:
        job_store[analysis_id] = {"status": "failed", "error": str(e)}

@app.post("/api/analyze", response_model=JobStatus, status_code=202)
async def analyze_cv(request: CVAnalysisRequest, background_tasks: BackgroundTasks):
    analysis_id = request.analysis_id or str(uuid.uuid4())
    job_store[analysis_id] = {"status": "pending"}
    loop = asyncio.get_event_loop()
    loop.run_in_executor(executor, run_crew_analysis, analysis_id, request.cv_text, request.jd_text)
    return JobStatus(analysis_id=analysis_id, status="pending")

@app.get("/api/analyze/{analysis_id}/status", response_model=JobStatus)
async def get_analysis_status(analysis_id: str):
    if analysis_id not in job_store:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    job = job_store[analysis_id]
    result = CVAnalysisResult(**job["result"]) if job.get("result") else None
    return JobStatus(analysis_id=analysis_id, status=job["status"], result=result, error=job.get("error"))


# ── Improve CV ────────────────────────────────────────────────────────────────

def run_improve_job(task_id: str, cv_text: str, position_title: str,
                    position_key_skills: str, auth_token: str = ""):
    try:
        job_store[task_id]["status"] = "processing"
        result = CVImproveCrew().crew().kickoff(inputs={
            "cv_text":             cv_text,
            "position_title":      position_title,
            "position_key_skills": position_key_skills,
        })
        parsed = parse_crew_result(result.raw)
        job_store[task_id] = {"status": "completed", "result": parsed}

        # Gọi Spring Boot backend để lưu lịch sử
        if auth_token:
            try:
                BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080")
                http_requests.post(
                    f"{BACKEND_URL}/api/cv-improve",
                    json={
                        "cvText":             cv_text,
                        "positionTitle":      position_title,
                        "positionKeySkills":  position_key_skills,
                        **parsed,
                    },
                    headers={"Authorization": f"Bearer {auth_token}"},
                    timeout=10,
                )
            except Exception as save_err:
                print(f"[api] Warning: không lưu được lịch sử: {save_err}")
    except Exception as e:
        job_store[task_id] = {"status": "failed", "error": str(e)}

# POST /api/improve  →  trả về { "id": task_id }  (frontend dùng field "id")
@app.post("/api/improve")
async def start_improve(request: ImproveRequest, authorization: str = Header(default="")):
    task_id = str(uuid.uuid4())
    job_store[task_id] = {"status": "pending"}
    # Lấy token từ header Authorization: Bearer <token>
    auth_token = authorization.replace("Bearer ", "").strip() if authorization else ""
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        executor, run_improve_job,
        task_id, request.cv_text, request.position_title,
        request.position_key_skills, auth_token
    )
    return {"id": task_id}

# GET /api/improve/{task_id}/status  →  { status, result?, error? }
@app.get("/api/improve/{task_id}/status")
async def improve_status(task_id: str):
    if task_id not in job_store:
        raise HTTPException(status_code=404, detail="Improve job not found")
    return job_store[task_id]


# ── Job Matching ──────────────────────────────────────────────────────────────

def run_jobs_job(session_id: str, cv_text: str, positions_list: str):
    try:
        job_store[session_id]["status"] = "processing"
        result = JobMatchCrew().crew().kickoff(inputs={
            "cv_text": cv_text,
            "positions_list": positions_list,
        })
        parsed = parse_crew_result(result.raw)
        job_store[session_id] = {"status": "completed", "result": parsed}
    except Exception as e:
        job_store[session_id] = {"status": "failed", "error": str(e)}

@app.post("/api/jobs/start")
async def start_jobs(request: JobsRequest, background_tasks: BackgroundTasks):
    session_id = request.session_id or str(uuid.uuid4())
    job_store[session_id] = {"status": "pending"}
    loop = asyncio.get_event_loop()
    loop.run_in_executor(executor, run_jobs_job, session_id, request.cv_text, request.positions_list)
    return {"session_id": session_id, "status": "pending"}

@app.get("/api/jobs/{session_id}/status")
async def jobs_status(session_id: str):
    if session_id not in job_store:
        raise HTTPException(status_code=404, detail="Jobs job not found")
    return job_store[session_id]