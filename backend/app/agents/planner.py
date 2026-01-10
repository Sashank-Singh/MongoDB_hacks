"""
Planner Agent - Converts user goals into task DAGs
"""
import json
from typing import List, Dict, Any
from datetime import datetime

from openai import AsyncOpenAI

from app.config import settings
from app.models import Task, TaskStatus


# System prompt for the planner
PLANNER_SYSTEM_PROMPT = """You are a task planner that decomposes user goals into a directed acyclic graph (DAG) of tasks.

Given a goal, you must:
1. Break it down into discrete, actionable tasks
2. Identify dependencies between tasks
3. Assign a required skill to each task (researcher, writer, coder, or data_builder)

RULES:
- Each task must have a unique name (snake_case)
- Dependencies must be specified by task name
- Tasks cannot depend on themselves
- The DAG must be acyclic (no circular dependencies)
- Order tasks so dependencies come before dependent tasks

OUTPUT FORMAT (JSON only, no markdown):
{
  "tasks": [
    {
      "name": "task_name",
      "description": "What this task does",
      "depends_on": [],
      "required_skill": "researcher|writer|coder|data_builder"
    }
  ]
}

Example for goal "Create a competitor analysis report":
{
  "tasks": [
    {
      "name": "research_competitors",
      "description": "Research main competitors in the market",
      "depends_on": [],
      "required_skill": "researcher"
    },
    {
      "name": "analyze_strengths_weaknesses",
      "description": "Analyze strengths and weaknesses of each competitor",
      "depends_on": ["research_competitors"],
      "required_skill": "researcher"
    },
    {
      "name": "write_analysis_report",
      "description": "Write the final competitor analysis report",
      "depends_on": ["analyze_strengths_weaknesses"],
      "required_skill": "writer"
    }
  ]
}
"""


class PlannerAgent:
    """
    Planner agent that uses LLM to decompose goals into task DAGs.
    This is the "brain" of Agent OS - it determines what work needs to be done.
    """
    
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.FIREWORK_API,
            base_url=settings.FIREWORKS_BASE_URL
        ) if settings.FIREWORK_API else None
        self.model = settings.FIREWORKS_MODEL
    
    async def decompose_goal(self, job_id: str, goal: str) -> List[Task]:
        """
        Convert a user goal into a list of tasks with dependencies.
        
        Args:
            job_id: The job this task belongs to
            goal: The user's natural language goal
            
        Returns:
            List of Task objects with proper dependencies
        """
        if self.client:
            # Use LLM for intelligent decomposition
            task_defs = await self._llm_decompose(goal)
        else:
            # Fallback: simple rule-based decomposition
            task_defs = self._simple_decompose(goal)
        
        # Convert to Task objects with proper IDs and dependency resolution
        return self._build_tasks(job_id, task_defs)
    
    async def _llm_decompose(self, goal: str) -> List[Dict[str, Any]]:
        """Use OpenAI to decompose the goal"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Decompose this goal into tasks:\n\n{goal}\n\nRespond with valid JSON only."}
                ]
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get("tasks", [])
            
        except Exception as e:
            print(f"LLM decomposition failed: {e}")
            # Fallback to simple decomposition
            return self._simple_decompose(goal)
    
    def _simple_decompose(self, goal: str) -> List[Dict[str, Any]]:
        """
        Simple rule-based decomposition fallback.
        Creates a basic research → analysis → output pipeline.
        """
        goal_lower = goal.lower()
        
        tasks = []
        
        # Always start with research
        tasks.append({
            "name": "research_topic",
            "description": f"Research and gather information about: {goal}",
            "depends_on": [],
            "required_skill": "researcher"
        })
        
        # Add analysis step
        tasks.append({
            "name": "analyze_findings",
            "description": "Analyze the research findings and identify key insights",
            "depends_on": ["research_topic"],
            "required_skill": "researcher"
        })
        
        # Determine output type based on keywords
        if any(word in goal_lower for word in ["code", "implement", "build", "create app"]):
            tasks.append({
                "name": "implement_solution",
                "description": "Implement the solution based on analysis",
                "depends_on": ["analyze_findings"],
                "required_skill": "coder"
            })
        elif any(word in goal_lower for word in ["table", "data", "spreadsheet", "csv"]):
            tasks.append({
                "name": "build_data_output",
                "description": "Create data tables and structured output",
                "depends_on": ["analyze_findings"],
                "required_skill": "data_builder"
            })
        else:
            tasks.append({
                "name": "write_report",
                "description": "Write a comprehensive report based on analysis",
                "depends_on": ["analyze_findings"],
                "required_skill": "writer"
            })
        
        # Final review step
        tasks.append({
            "name": "final_review",
            "description": "Review and finalize all outputs",
            "depends_on": [tasks[-1]["name"]],
            "required_skill": "writer"
        })
        
        return tasks
    
    def _build_tasks(self, job_id: str, task_defs: List[Dict[str, Any]]) -> List[Task]:
        """
        Convert task definitions to Task objects with proper ID resolution.
        """
        # First pass: create tasks and build name -> id mapping
        name_to_id = {}
        tasks = []
        
        for task_def in task_defs:
            task = Task(
                job_id=job_id,
                name=task_def["name"],
                description=task_def.get("description", ""),
                depends_on=[],  # Will fill in second pass
                required_skill=task_def.get("required_skill"),
                status=TaskStatus.PENDING,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            tasks.append(task)
            name_to_id[task_def["name"]] = task.id
        
        # Second pass: resolve dependency names to IDs
        for i, task_def in enumerate(task_defs):
            dep_names = task_def.get("depends_on", [])
            tasks[i].depends_on = [
                name_to_id[name] 
                for name in dep_names 
                if name in name_to_id
            ]
        
        return tasks
