from crewai import Agent, Task, Crew, LLM
from crewai.project import CrewBase, agent, task, crew
from pydantic import BaseModel
from typing import List
import json


# ─────────────────────────────────────────────
# Output schema
# ─────────────────────────────────────────────

class InterviewQuestion(BaseModel):
    order_index: int
    question_text: str
    hint_text: str
    category: str
    difficulty: str


class InterviewPlan(BaseModel):
    questions: List[InterviewQuestion]
    total_questions: int
    estimated_duration_minutes: int


# ─────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────

def _parse_json_output(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


# ─────────────────────────────────────────────
# Crew class
# ─────────────────────────────────────────────

@CrewBase
class InterviewCrew():

    agents_config = "config/interview/handle/agents.yaml"
    tasks_config  = "config/interview/handle/tasks.yaml"

    llm = LLM(
   model="groq/llama-3.3-70b-versatile", 
   temperature=0,
)


    # ── Agents ──

    @agent
    def cv_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["cv_analyst"],
            llm=self.llm,
            verbose=True,
        )

    @agent
    def jd_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["jd_analyst"],
            llm=self.llm,
            verbose=True,
        )

    @agent
    def question_designer(self) -> Agent:
        return Agent(
            config=self.agents_config["question_designer"],
            llm=self.llm,
            verbose=True,
        )

    # ── Tasks ──

    @task
    def analyze_cv(self) -> Task:
        return Task(
            config=self.tasks_config["analyze_cv"],
            agent=self.cv_analyst(),
        )

    @task
    def analyze_jd(self) -> Task:
        return Task(
            config=self.tasks_config["analyze_jd"],
            agent=self.jd_analyst(),
        )

    @task
    def design_questions(self) -> Task:
        return Task(
            config=self.tasks_config["design_questions"],
            agent=self.question_designer(),
            context=[self.analyze_cv(), self.analyze_jd()],
        )

    # ── Crew ──

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[
                self.cv_analyst(),
                self.jd_analyst(),
                self.question_designer(),
            ],
            tasks=[
                self.analyze_cv(),
                self.analyze_jd(),
                self.design_questions(),
            ],
        )


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

def run_interview_crew(cv_text: str, jd_text: str, num_questions: int = 10) -> InterviewPlan:
    inputs = {
        "cv_text":       cv_text,
        "jd_text":       jd_text,
        "num_questions": num_questions,
    }

    result = InterviewCrew().crew().kickoff(inputs=inputs)
    return InterviewPlan(**_parse_json_output(result.tasks_output[-1].raw))