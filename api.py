"""
api.py — FastAPI entry point

Thay đổi so với phiên bản cũ:
  1. job_store dict in-memory → SQLite persistent (job_store.py)
  2. learning_roadmap_tool v2: thêm experience_level param, LLM fallback
  3. Thêm /api/jobs/cleanup endpoint (tiện cho maintenance)
  4. Startup event gọi init_db()
"""

import os
import time
import uuid
import json
import re
import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from playwright.sync_api import sync_playwright
import requests as http_requests

from crew_cv import CVMatchingCrew
from crew_improve import CVImproveCrewRunner as CVImproveCrew
from crew_jobs import JobMatchCrew

# ── Persistent job store (thay dict in-memory) ────────────────────────────────
from job_store import init_db, set_job, get_job, job_exists, cleanup_old_jobs


# ── App lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: khởi tạo SQLite DB
    init_db()
    print("[api] SQLite job store initialized.")
    yield
    # Shutdown: cleanup job cũ hơn 24h
    deleted = cleanup_old_jobs(older_than_seconds=86400)
    print(f"[api] Cleanup: removed {deleted} old jobs on shutdown.")


app = FastAPI(title="CV Analysis AI Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(max_workers=4)

MAX_CV_CHARS  = 1500
MAX_JD_CHARS  = 1500
MAX_JD_SCRAPE = 2000

TASK_DELAY_SECONDS = 25


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
    raise ValueError(f"Cannot parse JSON from crew output: {raw_output[:300]}")


def task_callback(output):
    time.sleep(TASK_DELAY_SECONDS)


# ── Models ────────────────────────────────────────────────────────────────────

class CVAnalysisRequest(BaseModel):
    cv_text: str
    jd_text: str
    jd_url: Optional[str] = ""
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

def run_crew_analysis(analysis_id: str, cv_text: str, jd_text: str, jd_url: str = ""):
    try:
        set_job(analysis_id, "processing")

        cv_text = cv_text[:MAX_CV_CHARS]
        jd_text = jd_text[:MAX_JD_CHARS]

        crew_instance = CVMatchingCrew()
        c = crew_instance.crew()
        c.task_callback = task_callback

        result = c.kickoff(inputs={
            "cv_text": cv_text,
            "jd_text": jd_text,
            "jd_url":  jd_url,
        })

        parsed = parse_crew_result(result.raw)
        set_job(analysis_id, "completed", result={
            "analysis_id":      analysis_id,
            "match_score":      int(parsed.get("matchScore", 0)),
            "cv_feedback":      parsed.get("cvFeedback", ""),
            "matched_keywords": parsed.get("matchedKeywords", []),
            "missing_keywords": parsed.get("missingKeywords", []),
            "ai_tips":          parsed.get("aiTips", ""),
        })
    except Exception as e:
        set_job(analysis_id, "failed", error=str(e))


@app.post("/api/analyze", response_model=JobStatus, status_code=202)
async def analyze_cv(request: CVAnalysisRequest, background_tasks: BackgroundTasks):
    analysis_id = request.analysis_id or str(uuid.uuid4())
    set_job(analysis_id, "pending")
    asyncio.get_running_loop().run_in_executor(
        executor, run_crew_analysis,
        analysis_id, request.cv_text, request.jd_text, request.jd_url or "",
    )
    return JobStatus(analysis_id=analysis_id, status="pending")


@app.get("/api/analyze/{analysis_id}/status", response_model=JobStatus)
async def get_analysis_status(analysis_id: str):
    job = get_job(analysis_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Analysis job not found")

    result = CVAnalysisResult(**job["result"]) if job.get("result") else None
    return JobStatus(
        analysis_id=analysis_id,
        status=job["status"],
        result=result,
        error=job.get("error"),
    )


# ── Improve CV ────────────────────────────────────────────────────────────────

def run_improve_job(task_id: str, cv_text: str, position_title: str,
                    position_key_skills: str, auth_token: str = ""):
    try:
        set_job(task_id, "processing")
        result = CVImproveCrew().crew().kickoff(inputs={
            "cv_text":             cv_text[:MAX_CV_CHARS],
            "position_title":      position_title,
            "position_key_skills": position_key_skills,
        })
        parsed = parse_crew_result(result.raw)
        set_job(task_id, "completed", result=parsed)

        if auth_token:
            try:
                BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080")
                http_requests.post(
                    f"{BACKEND_URL}/api/cv-improve",
                    json={
                        "cvText":            cv_text,
                        "positionTitle":     position_title,
                        "positionKeySkills": position_key_skills,
                        **parsed,
                    },
                    headers={"Authorization": f"Bearer {auth_token}"},
                    timeout=10,
                )
            except Exception as save_err:
                print(f"[api] Warning: không lưu được lịch sử: {save_err}")
    except Exception as e:
        set_job(task_id, "failed", error=str(e))


@app.post("/api/improve")
async def start_improve(request: ImproveRequest, authorization: str = Header(default="")):
    task_id = str(uuid.uuid4())
    set_job(task_id, "pending")
    auth_token = authorization.replace("Bearer ", "").strip() if authorization else ""
    asyncio.get_running_loop().run_in_executor(
        executor, run_improve_job,
        task_id, request.cv_text, request.position_title,
        request.position_key_skills, auth_token,
    )
    return {"id": task_id}


@app.get("/api/improve/{task_id}/status")
async def improve_status(task_id: str):
    job = get_job(task_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Improve job not found")
    return job


# ── Job Matching ──────────────────────────────────────────────────────────────

def run_jobs_job(session_id: str, cv_text: str, positions_list: str):
    try:
        set_job(session_id, "processing")
        result = JobMatchCrew().crew().kickoff(inputs={
            "cv_text":        cv_text[:MAX_CV_CHARS],
            "positions_list": positions_list,
        })
        parsed = parse_crew_result(result.raw)
        set_job(session_id, "completed", result=parsed)
    except Exception as e:
        set_job(session_id, "failed", error=str(e))


@app.post("/api/jobs/start")
async def start_jobs(request: JobsRequest, background_tasks: BackgroundTasks):
    session_id = request.session_id or str(uuid.uuid4())
    set_job(session_id, "pending")
    asyncio.get_running_loop().run_in_executor(
        executor, run_jobs_job,
        session_id, request.cv_text, request.positions_list,
    )
    return {"session_id": session_id, "status": "pending"}


@app.get("/api/jobs/{session_id}/status")
async def jobs_status(session_id: str):
    job = get_job(session_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Jobs job not found")
    return job


# ── Maintenance ───────────────────────────────────────────────────────────────

@app.delete("/api/jobs/cleanup")
async def cleanup_jobs(older_than_hours: int = 24):
    """Xóa các job cũ hơn N giờ. Dùng cho cron job hoặc manual cleanup."""
    deleted = cleanup_old_jobs(older_than_seconds=older_than_hours * 3600)
    return {"deleted": deleted, "older_than_hours": older_than_hours}


# ── Scrape JD ─────────────────────────────────────────────────────────────────

def _do_scrape(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
            viewport={"width": 1280, "height": 800},
            extra_http_headers={
                "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Referer":         "https://www.google.com/",
                "sec-ch-ua":       '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                "sec-ch-ua-mobile":   "?0",
                "sec-ch-ua-platform": '"Windows"',
                "Sec-Fetch-Dest":  "document",
                "Sec-Fetch-Mode":  "navigate",
                "Sec-Fetch-Site":  "cross-site",
                "Upgrade-Insecure-Requests": "1",
            },
        )

        # Ẩn dấu hiệu automation
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['vi-VN', 'vi', 'en-US'] });
            window.chrome = { runtime: {} };
        """)

        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        # Selector theo từng site
        site_selectors = {
            "topcv.vn":      [".job-description", ".job-detail__information-detail", "[class*='job-description']"],
            "itviec.com":    [".job-description__item", "[class*='job-description']", ".job-details"],
            "linkedin.com":  [".description__text", ".job-details-jobs-unified-top-card__job-insight"],
            "topdev.vn":     [".job-description", "[class*='description']"],
            "vietnamworks":  [".job-description", "[class*='description']"],
        }

        selectors = []
        for domain, domain_selectors in site_selectors.items():
            if domain in url:
                selectors = domain_selectors
                break

        # Fallback selectors chung
        selectors += [
            "[class*='job-description']",
            "[class*='description']",
            "main",
            "article",
        ]

        text = ""
        for selector in selectors:
            try:
                el = page.query_selector(selector)
                if el:
                    candidate = el.inner_text()
                    if len(candidate.strip()) > 200:
                        text = candidate
                        break
            except Exception:
                continue

        if not text.strip():
            text = page.inner_text("body")

        context.close()
        browser.close()
    return text


def scrape_with_timeout(url: str, timeout_sec: int = 25) -> str:
    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(_do_scrape, url)
        try:
            return future.result(timeout=timeout_sec)
        except FuturesTimeout:
            raise RuntimeError(f"Scrape timeout sau {timeout_sec}s")


class ScrapeRequest(BaseModel):
    url: str


@app.post("/api/scrape-jd")
async def scrape_jd(request: ScrapeRequest):
    if not request.url.strip():
        raise HTTPException(status_code=400, detail="Missing url")
    loop = asyncio.get_running_loop()
    try:
        text = await loop.run_in_executor(executor, _do_scrape, request.url)
        return {"jd_text": text[:MAX_JD_SCRAPE]}
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))
    
class RoadmapRequest(BaseModel):
    missing_skills: str          # "Docker, Kubernetes, ..."
    experience_level: Optional[str] = "fresher"

def run_roadmap_job(task_id: str, missing_skills: str, experience_level: str):
    try:
        set_job(task_id, "processing")
        from tools.learning_roadmap_tool import LearningRoadmapTool
        tool = LearningRoadmapTool()
        result = tool._run(
            missing_skills=missing_skills,
            experience_level=experience_level,
        )
        set_job(task_id, "completed", result={"roadmap": result})
    except Exception as e:
        set_job(task_id, "failed", error=str(e))

@app.post("/api/roadmap")
async def start_roadmap(request: RoadmapRequest):
    task_id = str(uuid.uuid4())
    set_job(task_id, "pending")
    asyncio.get_running_loop().run_in_executor(
        executor, run_roadmap_job,
        task_id, request.missing_skills, request.experience_level or "fresher",
    )
    return {"id": task_id}

@app.get("/api/roadmap/{task_id}/status")
async def roadmap_status(task_id: str):
    job = get_job(task_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Roadmap job not found")
    return job