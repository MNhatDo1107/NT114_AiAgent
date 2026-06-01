from crewai import Agent, Task, Crew, LLM
from crewai.project import CrewBase, agent, task, crew
from dotenv import load_dotenv

load_dotenv()

llm = LLM(
    model="groq/llama-3.3-70b-versatile",
    temperature=0,
)

@CrewBase
class JobMatchCrew():

    agents_config = "config/jobs/agents.yaml"
    tasks_config = "config/jobs/tasks.yaml"

    @agent
    def cv_skills_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["cv_skills_agent"],
            llm=llm,
            verbose=True,
        )

    @agent
    def job_matcher_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["job_matcher_agent"],
            llm=llm,
            verbose=True,
        )

    @task
    def extract_skills_task(self) -> Task:
        return Task(
            config=self.tasks_config["extract_skills_task"],
            agent=self.cv_skills_agent()
        )

    @task
    def match_jobs_task(self) -> Task:
        return Task(
            config=self.tasks_config["match_jobs_task"],
            agent=self.job_matcher_agent()
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[
                self.cv_skills_agent(),
                self.job_matcher_agent(),
            ],
            tasks=[
                self.extract_skills_task(),
                self.match_jobs_task(),
            ],
        )