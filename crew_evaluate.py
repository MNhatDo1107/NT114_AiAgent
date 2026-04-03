from crewai import Agent, Task, Crew, LLM
from crewai.project import CrewBase, agent, task, crew
from pydantic import BaseModel, Field
from typing import Optional
from dotenv import load_dotenv
import json

load_dotenv()

llm = LLM(
    model="groq/llama-3.3-70b-versatile",
    temperature=0,
)

class EvaluationResult(BaseModel):
    score: float = Field(..., ge=0.0, le=10.0)
    comment: str
    strengths: str
    weaknesses: str
    better_answer: str
    improvement_tips: str

def _parse_json_output(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    data = json.loads(raw.strip())
    for field in ("comment", "strengths", "weaknesses", "better_answer", "improvement_tips"):
        if field in data and isinstance(data[field], list):
            data[field] = " ".join(str(x) for x in data[field])
    return data

@CrewBase
class EvaluateCrew():
    agents_config = "config/interview/evaluate/agents.yaml"
    tasks_config  = "config/interview/evaluate/tasks.yaml"

    @agent
    def answer_evaluator(self) -> Agent:
        return Agent(config=self.agents_config["answer_evaluator"], llm=llm, verbose=True)

    @agent
    def answer_coach(self) -> Agent:
        return Agent(config=self.agents_config["answer_coach"], llm=llm, verbose=True)

    @task
    def evaluate_answer(self) -> Task:
        return Task(config=self.tasks_config["evaluate_answer"], agent=self.answer_evaluator())

    @task
    def coach_answer(self) -> Task:
        return Task(config=self.tasks_config["coach_answer"], agent=self.answer_coach(), context=[self.evaluate_answer()])

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[self.answer_evaluator(), self.answer_coach()],
            tasks=[self.evaluate_answer(), self.coach_answer()],
        )

def run_evaluate_crew(
    question_text: str,
    user_answer: str,
    hint_text: str,
    category: str = "technical",
    difficulty: str = "medium",
    cv_summary: Optional[str] = None,
) -> EvaluationResult:
    if not user_answer or not user_answer.strip():
        return EvaluationResult(
            score=0.0,
            comment="Ung vien da bo qua cau hoi nay.",
            strengths="Khong co.",
            weaknesses="Khong co cau tra loi de danh gia.",
            better_answer=hint_text,
            improvement_tips="Hay co gang tra loi tat ca cau hoi.",
        )
    inputs = {
        "question_text": question_text,
        "user_answer":   user_answer.strip(),
        "hint_text":     hint_text,
        "category":      category,
        "difficulty":    difficulty,
        "cv_context": (f"\n--- Tom tat CV ung vien ---\n{cv_summary}\n" if cv_summary else ""),
    }
    result = EvaluateCrew().crew().kickoff(inputs=inputs)
    return EvaluationResult(**_parse_json_output(result.tasks_output[-1].raw))
