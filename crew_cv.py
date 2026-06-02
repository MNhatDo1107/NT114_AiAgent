"""
crew_cv.py

Thay đổi v2:
- matching_agent gọi learning_roadmap_tool với experience_level từ parse_task
- task_delay giảm còn 20s (3 tasks → 3 lần delay)
"""
import time

from crewai import Agent, Task, Crew, Process
from crewai.project import CrewBase, agent, task, crew

from tools.learning_roadmap_tool import LearningRoadmapTool


def _task_delay(output):
    time.sleep(20)


@CrewBase
class CVMatchingCrew:
    agents_config = "config/analysis/agents.yaml"
    tasks_config  = "config/analysis/tasks.yaml"
    _roadmap_tool = LearningRoadmapTool()

    @agent
    def parser_agent(self) -> Agent:
        return Agent(config=self.agents_config["parser_agent"], verbose=True)

    @agent
    def matching_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["matching_agent"],
            tools=[self._roadmap_tool],
            verbose=True,
        )

    @agent
    def reviewer_agent(self) -> Agent:
        return Agent(config=self.agents_config["reviewer_agent"], verbose=True)

    @task
    def parse_task(self) -> Task:
        return Task(config=self.tasks_config["parse_task"])

    @task
    def match_task(self) -> Task:
        return Task(config=self.tasks_config["match_task"])

    @task
    def review_task(self) -> Task:
        return Task(config=self.tasks_config["review_task"])

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            task_callback=_task_delay,
            verbose=True,
        )