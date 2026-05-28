from crewai import Agent, Task, Crew, LLM
from crewai.project import CrewBase, agent, task, crew
from dotenv import load_dotenv

load_dotenv()

llm = LLM(
    model="groq/llama-3.3-70b-versatile",
    temperature=0,
)

@CrewBase
class CVImproveCrew():

    agents_config = "config/improve/agents.yaml"
    tasks_config = "config/improve/tasks.yaml"

    @agent
    def cv_reader_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["cv_reader_agent"],
            llm=llm,
            verbose=True,
        )

    @agent
    def position_analyst_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["position_analyst_agent"],
            llm=llm,
            verbose=True,
        )

    @agent
    def improve_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["improve_agent"],
            llm=llm,
            verbose=True,
        )

    @task
    def read_cv_task(self) -> Task:
        return Task(
            config=self.tasks_config["read_cv_task"],
            agent=self.cv_reader_agent()
        )

    @task
    def analyze_position_task(self) -> Task:
        return Task(
            config=self.tasks_config["analyze_position_task"],
            agent=self.position_analyst_agent()
        )

    @task
    def improve_task(self) -> Task:
        return Task(
            config=self.tasks_config["improve_task"],
            agent=self.improve_agent()
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[
                self.cv_reader_agent(),
                self.position_analyst_agent(),
                self.improve_agent(),
            ],
            tasks=[
                self.read_cv_task(),
                self.analyze_position_task(),
                self.improve_task(),
            ],
        )