#api.py
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uuid
import json
import re
import asyncio
from concurrent.futures import ThreadPoolExecutor
from crew_cv import CVMatchingCrew
app = FastAPI(title="CV Analysis AI Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(max_workers=4)
job_store: dict = {}
    

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

    raise ValueError(f"Cannot parse JSON from CrewAI output: {raw_output[:200]}")


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
        job_store[analysis_id] = {
            "status": "failed",
            "error": str(e)
        }


@app.post("/api/analyze", response_model=JobStatus, status_code=202)
async def analyze_cv(request: CVAnalysisRequest, background_tasks: BackgroundTasks):
    analysis_id = request.analysis_id or str(uuid.uuid4())
    job_store[analysis_id] = {"status": "pending"}

    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        executor,
        run_crew_analysis,
        analysis_id,
        request.cv_text,
        request.jd_text
    )

    return JobStatus(analysis_id=analysis_id, status="pending")


@app.get("/api/analyze/{analysis_id}/status", response_model=JobStatus)
async def get_analysis_status(analysis_id: str):
    if analysis_id not in job_store:
        raise HTTPException(status_code=404, detail="Analysis job not found")

    job = job_store[analysis_id]
    result = CVAnalysisResult(**job["result"]) if job.get("result") else None

    return JobStatus(
        analysis_id=analysis_id,
        status=job["status"],
        result=result,
        error=job.get("error")
    )


@app.get("/health")
async def health():
    return {"status": "ok"}