#crew_cv.py
from crewai import Agent, Task, Crew, LLM
from crewai.project import CrewBase, agent, task, crew
# from crewai_tools import ScrapeWebsiteTool
from dotenv import load_dotenv

load_dotenv()

llm = LLM(
   model="groq/llama-3.3-70b-versatile", 
   temperature=0,
)

# tool = ScrapeWebsiteTool(
#     website = "https://careerviet.vn/viec-lam-noi-bat-trong-tuan-l8a30"
# )

@CrewBase
class CVMatchingCrew():

    agents_config = "config/analysis/agents.yaml"
    tasks_config = "config/analysis/tasks.yaml"

    # ================= AGENTS =================

    @agent
    def cv_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["cv_agent"],
            llm=llm,
            verbose=True,
            # tools=[tool]
        )

    @agent
    def jd_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["jd_agent"],
            llm=llm,
            verbose=True,
            # tools=[tool]
        )

    @agent
    def matching_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["matching_agent"],
            llm=llm,
            verbose=True,
            # tools=[tool]
        )

    @agent
    def gap_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["gap_agent"],
            llm=llm,
            verbose=True,
            # tools=[tool]
        )

    @agent
    def reviewer_agent(self) -> Agent:
        return Agent(
            config=self.agents_config["reviewer_agent"],
            llm=llm,
            verbose=True,
            # tools=[tool]
        )

    # ================= TASKS =================

    @task
    def cv_task(self) -> Task:
        return Task(
            config=self.tasks_config["cv_task"],
            agent=self.cv_agent()
        )

    @task
    def jd_task(self) -> Task:
        return Task(
            config=self.tasks_config["jd_task"],
            agent=self.jd_agent()
        )

    @task
    def match_task(self) -> Task:
        return Task(
            config=self.tasks_config["match_task"], 
            agent=self.matching_agent()
        )

    @task
    def gap_task(self) -> Task:
        return Task(
            config=self.tasks_config["gap_task"],
            agent=self.gap_agent()
        )

    @task
    def review_task(self) -> Task:
        return Task(
            config=self.tasks_config["review_task"],
            agent=self.reviewer_agent()
        )
    


    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=[
                self.cv_agent(), 
                self.jd_agent(), 
                self.matching_agent(), 
                self.gap_agent(), 
                self.reviewer_agent(),
            ],
            tasks=[
                self.cv_task(), 
                self.jd_task(), 
                self.match_task(), 
                self.gap_task(), 
                self.review_task(),
            ],    
        )
    
def multi_input(prompt):
    print(prompt)
    print("(Nhập nhiều dòng. Gõ 'END' để kết thúc)\n")

    lines = []
    while True:
        line = input()
        if line.strip().upper() == "END":
            break
        lines.append(line)

    return "\n".join(lines)


if __name__ == "__main__":
    crew_base = CVMatchingCrew()

    cv_text = multi_input("=== NHẬP CV ===")
    jd_text = multi_input("=== NHẬP JD ===")

    result = crew_base.crew().kickoff(
        inputs={
            "cv_text": cv_text, 
            "jd_text": jd_text,
        } 
    )

    print(result)
