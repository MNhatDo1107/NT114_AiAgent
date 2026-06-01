import json
import re
import os
import time
import yaml
from crewai import Agent, Task, Crew, Process, LLM
from pathlib import Path

FALLBACK_RESULT = {
    "overallScore": 0,
    "summary": "Không thể phân tích CV lúc này. Vui lòng thử lại sau.",
    "improvements": [],
    "missingSkills": [],
    "strongPoints": [],
    "quickWins": []
}


# Models còn active trên Groq (tháng 5/2026)
# Ref: https://console.groq.com/docs/models
GROQ_MODELS = [
    "groq/llama-3.3-70b-versatile",   # primary — chất lượng cao nhất
    "groq/llama-3.1-8b-instant",      # fallback — nhanh, ít token hơn
]


def _get_llm(model: str = GROQ_MODELS[0]) -> LLM:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY chưa được set trong .env")
    return LLM(
        model=model,
        api_key=api_key,
        temperature=0.3,
        max_tokens=2048,
    )


def extract_json(text: str) -> dict:
    if not text or not text.strip():
        return FALLBACK_RESULT
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        try:
            return json.loads(brace.group(0))
        except json.JSONDecodeError:
            pass
    return FALLBACK_RESULT


def validate_result(data: dict) -> dict:
    return {
        "overallScore": int(data.get("overallScore", 0)),
        "summary": str(data.get("summary", "")),
        "improvements": [
            {
                "section":    str(imp.get("section", "General")),
                "issue":      str(imp.get("issue", "")),
                "suggestion": str(imp.get("suggestion", "")),
                "priority":   imp.get("priority", "medium")
                              if imp.get("priority") in ("high", "medium", "low")
                              else "medium",
            }
            for imp in (data.get("improvements") or [])
            if isinstance(imp, dict)
        ],
        "missingSkills": [str(s) for s in (data.get("missingSkills") or [])],
        "strongPoints":  [str(s) for s in (data.get("strongPoints") or [])],
        "quickWins":     [str(s) for s in (data.get("quickWins") or [])],
    }


def _truncate_cv(cv_text: str, max_chars: int = 1500) -> str:
    """Cắt CV nếu quá dài để tiết kiệm token."""
    if len(cv_text) <= max_chars:
        return cv_text
    return cv_text[:max_chars] + "\n... [CV đã được rút gọn]"


def _truncate_skills(skills: str, max_skills: int = 20) -> str:
    """Chỉ lấy tối đa N skills để tránh vượt TPM."""
    parts = [s.strip() for s in skills.split(",") if s.strip()]
    return ", ".join(parts[:max_skills])


class CVImproveCrew:
    """
    Single-agent crew — 1 agent, 1 task.
    Gộp đọc CV + phân tích vị trí + gợi ý vào 1 lần gọi LLM
    để tránh rate limit Groq free tier.
    """

    def __init__(self, model: str = GROQ_MODELS[0]):
        self._model = model

    def crew(self) -> Crew:
        llm = _get_llm(self._model)

        agent = Agent(
            role="Chuyên gia phân tích CV IT",
            goal="Phân tích CV và đưa ra gợi ý cải thiện phù hợp với vị trí IT",
            backstory=(
                "Bạn là Career Coach IT với 10 năm kinh nghiệm, "
                "đã tư vấn hàng trăm ứng viên tối ưu CV để pass ATS "
                "và gây ấn tượng với nhà tuyển dụng kỹ thuật."
            ),
            llm=llm,
            verbose=True,
            allow_delegation=False,
        )

        task = Task(
            description="""
Phân tích CV sau và đưa ra gợi ý cải thiện cho vị trí {position_title}.

CV:
{cv_text}

KEY SKILLS yêu cầu (tag: [CORE]=bắt buộc, [JUNIOR]=cần từ 1-3 năm, [PLUS]=ưu tiên):
{position_key_skills}

Trả về JSON hợp lệ DUY NHẤT, KHÔNG có text khác, KHÔNG có markdown:
{{
  "overallScore": <0-100>,
  "summary": "<nhận xét tổng thể 2 câu tiếng Việt>",
  "improvements": [
    {{
      "section": "<Skills|Experience|Projects|Summary|Education>",
      "issue": "<vấn đề>",
      "suggestion": "<gợi ý cụ thể>",
      "priority": "<high|medium|low>"
    }}
  ],
  "missingSkills": ["<chỉ [CORE] và [JUNIOR] còn thiếu>"],
  "strongPoints": ["<điểm mạnh>"],
  "quickWins": ["<việc 1>", "<việc 2>", "<việc 3>"]
}}

Giới hạn: tối đa 4 improvements, 5 missingSkills, 3 strongPoints, đúng 3 quickWins.
""",
            expected_output="JSON hợp lệ với overallScore, summary, improvements, missingSkills, strongPoints, quickWins",
            agent=agent,
        )

        return Crew(
            agents=[agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
        )


def run_with_retry(cv_text: str, position_title: str, position_key_skills: str) -> dict:
    """
    Chạy crew với fallback model + retry khi rate limit.
    Thử lần lượt: llama-3.3-70b → llama-3.1-8b-instant
    Mỗi model retry tối đa 2 lần với delay 15s.
    """
    cv_short     = _truncate_cv(cv_text, max_chars=1500)
    skills_short = _truncate_skills(position_key_skills, max_skills=20)
    inputs = {
        "cv_text":             cv_short,
        "position_title":      position_title,
        "position_key_skills": skills_short,
    }

    for model in GROQ_MODELS:
        for attempt in range(1, 3):
            try:
                print(f"[CVImproveCrew] Model={model} attempt={attempt}...")
                crew_instance = CVImproveCrew(model=model)
                result = crew_instance.crew().kickoff(inputs=inputs)
                raw    = result.raw if hasattr(result, "raw") else str(result)
                parsed = extract_json(raw)
                return validate_result(parsed)

            except Exception as e:
                err_msg = str(e)
                is_rate_limit   = "rate_limit_exceeded" in err_msg or "RateLimitError" in err_msg
                is_decommission = "decommissioned" in err_msg or "BadRequestError" in err_msg

                if is_decommission:
                    print(f"[CVImproveCrew] Model {model} decommissioned, thử model tiếp theo...")
                    break  # bỏ qua model này, sang model tiếp
                elif is_rate_limit:
                    wait = 15 * attempt
                    print(f"[CVImproveCrew] Rate limit. Chờ {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"[CVImproveCrew] Lỗi: {err_msg[:300]}")
                    return {**FALLBACK_RESULT, "summary": f"Lỗi: {err_msg[:200]}"}

    return {**FALLBACK_RESULT, "summary": "Không thể kết nối AI. Vui lòng thử lại sau vài phút."}


# ── Để api.py gọi ─────────────────────────────────────────────────────────────

class CVImproveCrewRunner:
    """Wrapper cho api.py — giữ interface cũ."""

    def crew(self):
        return _FakeCrew()


class _FakeCrew:
    def kickoff(self, inputs: dict) -> "_FakeResult":
        result = run_with_retry(
            cv_text=inputs.get("cv_text", ""),
            position_title=inputs.get("position_title", ""),
            position_key_skills=inputs.get("position_key_skills", ""),
        )
        return _FakeResult(json.dumps(result, ensure_ascii=False))


class _FakeResult:
    def __init__(self, raw: str):
        self.raw = raw


# ── Test trực tiếp ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    SAMPLE_CV = """
    Nguyễn Văn An - DevOps Engineer, 2 năm kinh nghiệm
    Skills: Linux, Docker, Jenkins, Python, Bash, Git, AWS EC2/S3 cơ bản
    Kinh nghiệm: DevOps tại Công ty ABC (2022-nay)
    - Quản lý server Linux, deploy ứng dụng bằng Docker
    - Viết Jenkins pipeline cho 3 dự án
    Học vấn: Đại học Bách Khoa CNTT 2022
    """

    final = run_with_retry(
        cv_text=SAMPLE_CV,
        position_title="DevOps Engineer (Junior)",
        position_key_skills=(
            "[CORE]Linux,[CORE]Docker,[CORE]Jenkins,[CORE]Git,"
            "[JUNIOR]Kubernetes,[JUNIOR]Terraform,[JUNIOR]AWS,[JUNIOR]Prometheus,"
            "[PLUS]Helm,[PLUS]ArgoCD"
        ),
    )
    print(json.dumps(final, ensure_ascii=False, indent=2))