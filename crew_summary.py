from crewai import Agent, Task, Crew, LLM
from crewai.project import CrewBase, agent, task, crew
from pydantic import BaseModel
from typing import List, Dict
import json


# ─────────────────────────────────────────────
# Input / Output schema
# ─────────────────────────────────────────────

class AnsweredQuestion(BaseModel):
    order_index: int
    question_text: str
    category: str
    difficulty: str
    user_answer: str
    score: float
    comment: str
    better_answer: str


class CategoryScore(BaseModel):
    category: str
    avg_score: float
    question_count: int
    assessment: str


class InterviewSummary(BaseModel):
    total_score: float
    grade: str
    overall_feedback: str
    strengths: str
    weaknesses: str
    category_scores: List[CategoryScore]
    top_recommendations: List[str]
    hiring_recommendation: str
    hiring_reason: str


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _parse_json_output(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def _compute_category_stats(questions: List[AnsweredQuestion]) -> Dict[str, dict]:
    stats: Dict[str, dict] = {}
    for q in questions:
        cat = q.category
        if cat not in stats:
            stats[cat] = {"total_score": 0.0, "count": 0}
        stats[cat]["total_score"] += q.score
        stats[cat]["count"] += 1
    return {
        cat: {
            "avg_score": round(v["total_score"] / v["count"], 2),
            "count": v["count"],
        }
        for cat, v in stats.items()
    }


def _format_qa_block(questions: List[AnsweredQuestion]) -> str:
    lines = []
    for q in questions:
        answered = q.user_answer.strip() if q.user_answer else "(Bỏ qua)"
        lines.append(
            f"[Câu {q.order_index}] [{q.category.upper()} | {q.difficulty}] "
            f"Điểm: {q.score}/10\n"
            f"  Hỏi    : {q.question_text}\n"
            f"  Trả lời: {answered[:300]}{'...' if len(answered) > 300 else ''}\n"
            f"  Nhận xét AI: {q.comment}\n"
        )
    return "\n".join(lines)


def _format_category_stats_text(stats: Dict[str, dict]) -> str:
    return "\n".join(
        f"  - {cat}: {v['avg_score']}/10 ({v['count']} câu)"
        for cat, v in stats.items()
    )


# ─────────────────────────────────────────────
# Crew class
# ─────────────────────────────────────────────

@CrewBase
class SummaryCrew():

    agents_config = "config/interview/summary/agents.yaml"
    tasks_config  = "config/interview/summary/tasks.yaml"

    llm = LLM(
   model="groq/llama-3.3-70b-versatile", 
   temperature=0,
)


    # ── Agents ──

    @agent
    def performance_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["performance_analyst"],
            llm=self.llm,
            verbose=True,
        )

    @agent
    def hiring_advisor(self) -> Agent:
        return Agent(
            config=self.agents_config["hiring_advisor"],
            llm=self.llm,
            verbose=True,
        )

    # ── Tasks ──

    @task
    def analyze_performance(self) -> Task:
        return Task(
            config=self.tasks_config["analyze_performance"],
            agent=self.performance_analyst(),
        )

    @task
    def generate_report(self) -> Task:
        return Task(
            config=self.tasks_config["generate_report"],
            agent=self.hiring_advisor(),
            context=[self.analyze_performance()],
        )

    # ── Crew ──

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[
                self.performance_analyst(),
                self.hiring_advisor(),
            ],
            tasks=[
                self.analyze_performance(),
                self.generate_report(),
            ],
        )


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

def run_summary_crew(
    questions: List[AnsweredQuestion],
    cv_text: str,
    jd_text: str,
) -> InterviewSummary:

    if not questions:
        raise ValueError("Không có câu hỏi nào để tổng kết.")

    category_stats = _compute_category_stats(questions)
    total_score    = round(sum(q.score for q in questions) / len(questions), 2)
    answered_count = sum(1 for q in questions if q.user_answer.strip())
    skipped_count  = len(questions) - answered_count

    inputs = {
        "total_questions":     len(questions),
        "answered_count":      answered_count,
        "skipped_count":       skipped_count,
        "total_score":         total_score,
        "category_stats_text": _format_category_stats_text(category_stats),
        "category_stats_json": json.dumps(category_stats, ensure_ascii=False),
        "qa_block":            _format_qa_block(questions),
        "cv_text":             cv_text[:1500],
        "jd_text":             jd_text[:1500],
    }

    result = SummaryCrew().crew().kickoff(inputs=inputs)
    return InterviewSummary(**_parse_json_output(result.tasks_output[-1].raw))  