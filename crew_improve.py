import json
import re
import os
import yaml
from crewai import Agent, Task, Crew, Process, LLM
from crewai.project import CrewBase, agent, task, crew
from pathlib import Path


def _get_llm() -> LLM:
    """
    Tạo LLM dùng Groq.
    GROQ_API_KEY đọc từ .env hoặc environment variable.
    Model mặc định: llama-3.1-8b-instant (nhanh, miễn phí).
    Đổi sang llama-3.3-70b-versatile nếu cần kết quả tốt hơn.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY chưa được set trong .env")
    return LLM(
        model="groq/llama-3.1-8b-instant",
        api_key=api_key,
        temperature=0.3,
    )

FALLBACK_RESULT = {
    "overallScore": 0,
    "summary": "Không thể phân tích CV lúc này. Vui lòng thử lại sau.",
    "improvements": [],
    "missingSkills": [],
    "strongPoints": [],
    "quickWins": []
}


def _load_yaml(path: str) -> dict:
    """Load YAML file relative to this script's directory."""
    base = Path(__file__).parent
    with open(base / path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


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


class CVImproveCrew:
    """
    3-agent crew chạy tuần tự:
      1. cv_reader_agent     — trích xuất thông tin CV
      2. position_analyst    — phân tích yêu cầu vị trí
      3. improve_agent       — gap analysis, trả JSON
    
    KHÔNG dùng @CrewBase để tránh lỗi "str has no attribute get".
    Load YAML thủ công, tự gán agent cho task.
    """

    def __init__(self):
        self._agents_cfg = _load_yaml("config/improve/agents.yaml")
        self._tasks_cfg  = _load_yaml("config/improve/tasks.yaml")

    def _make_agents(self):
        llm = _get_llm()
        return {
            "cv_reader": Agent(
                role=self._agents_cfg["cv_reader_agent"]["role"],
                goal=self._agents_cfg["cv_reader_agent"]["goal"],
                backstory=self._agents_cfg["cv_reader_agent"]["backstory"],
                llm=llm,
                verbose=True,
                allow_delegation=False,
            ),
            "analyst": Agent(
                role=self._agents_cfg["position_analyst_agent"]["role"],
                goal=self._agents_cfg["position_analyst_agent"]["goal"],
                backstory=self._agents_cfg["position_analyst_agent"]["backstory"],
                llm=llm,
                verbose=True,
                allow_delegation=False,
            ),
            "improver": Agent(
                role=self._agents_cfg["improve_agent"]["role"],
                goal=self._agents_cfg["improve_agent"]["goal"],
                backstory=self._agents_cfg["improve_agent"]["backstory"],
                llm=llm,
                verbose=True,
                allow_delegation=False,
            ),
        }

    def crew(self) -> Crew:
        agents = self._make_agents()

        read_cv = Task(
            description=self._tasks_cfg["read_cv_task"]["description"],
            expected_output=self._tasks_cfg["read_cv_task"]["expected_output"],
            agent=agents["cv_reader"],
        )

        analyze_pos = Task(
            description=self._tasks_cfg["analyze_position_task"]["description"],
            expected_output=self._tasks_cfg["analyze_position_task"]["expected_output"],
            agent=agents["analyst"],
        )

        improve = Task(
            description=self._tasks_cfg["improve_task"]["description"],
            expected_output=self._tasks_cfg["improve_task"]["expected_output"],
            agent=agents["improver"],
            context=[read_cv, analyze_pos],   # nhận output từ 2 task trước
        )

        return Crew(
            agents=list(agents.values()),
            tasks=[read_cv, analyze_pos, improve],
            process=Process.sequential,
            verbose=True,
        )


# ── Test chạy trực tiếp: python crew_improve.py ──────────────────────────────

if __name__ == "__main__":
    SAMPLE_CV = """
    Nguyễn Văn An - DevOps Engineer, 2 năm kinh nghiệm
    Skills: Linux, Docker, Docker Compose, Jenkins, Python, Bash, AWS EC2/S3 cơ bản, Git
    Kinh nghiệm: DevOps tại Công ty ABC (2022-nay)
    - Quản lý server Linux, deploy ứng dụng bằng Docker
    - Viết Jenkins pipeline cho 3 dự án nội bộ
    Học vấn: Đại học Bách Khoa CNTT 2022
    """

    crew_instance = CVImproveCrew()
    result = crew_instance.crew().kickoff(inputs={
        "cv_text":             SAMPLE_CV,
        "position_title":      "DevOps Engineer (Junior)",
        "position_key_skills": "Docker,Kubernetes,Jenkins,GitHub Actions,AWS,Terraform,Ansible,Linux,Prometheus,Grafana",
    })

    parsed = extract_json(result.raw)
    final  = validate_result(parsed)
    print(json.dumps(final, ensure_ascii=False, indent=2))