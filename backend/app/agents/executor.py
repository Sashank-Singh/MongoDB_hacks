"""
Executor Agents - Worker agents that execute specific tasks with real AI
"""
import asyncio
from typing import Dict, Any
from datetime import datetime

from openai import AsyncOpenAI

from app.agents.base import BaseAgent, TaskResult
from app.models import Task, AgentRole, EventType
from app.config import settings


class ResearcherAgent(BaseAgent):
    """Agent specialized in research and data gathering using AI"""
    
    def __init__(self, agent_id: str, name: str = "Researcher"):
        super().__init__(agent_id, name, AgentRole.RESEARCHER.value)
        self.skills = ["research", "data_gathering", "web_search", "analysis"]
        self.client = AsyncOpenAI(
            api_key=settings.FIREWORK_API,
            base_url=settings.FIREWORKS_BASE_URL
        ) if settings.FIREWORK_API else None
        self.model = settings.FIREWORKS_MODEL
    
    async def execute(self, task: Task) -> TaskResult:
        """Execute a research task with AI"""
        if not self.client:
            return TaskResult(
                success=True,
                outputs={"content": f"[Mock research for: {task.description}]", "type": "mock"},
                checkpoint=f"Mock research completed for '{task.name}'"
            )
        
        try:
            # Get context from previous task outputs if available
            # Get context from previous task outputs if available
            context = task.inputs.get("context", "")
            
            await self.log_event(EventType.AGENT_THINKING, task, "Scanning knowledge base and external sources...")

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert researcher. Provide detailed, factual research findings. Be thorough but concise. Use bullet points for key findings."},
                    {"role": "user", "content": f"Research task: {task.description}\n\nPrevious context: {context}\n\nProvide comprehensive research findings."}
                ],
                max_tokens=1000
            )
            
            content = response.choices[0].message.content
            
            return TaskResult(
                success=True,
                outputs={
                    "content": content,
                    "type": "research",
                    "model": self.model,
                    "timestamp": datetime.utcnow().isoformat()
                },
                checkpoint=f"Research completed: {content[:200]}..."
            )
            
        except Exception as e:
            return TaskResult(success=False, error=str(e))


class WriterAgent(BaseAgent):
    """Agent specialized in content creation using AI"""
    
    def __init__(self, agent_id: str, name: str = "Writer"):
        super().__init__(agent_id, name, AgentRole.WRITER.value)
        self.skills = ["writing", "editing", "summarization", "report_creation"]
        self.client = AsyncOpenAI(
            api_key=settings.FIREWORK_API,
            base_url=settings.FIREWORKS_BASE_URL
        ) if settings.FIREWORK_API else None
        self.model = settings.FIREWORKS_MODEL
    
    async def execute(self, task: Task) -> TaskResult:
        """Execute a writing task with AI"""
        if not self.client:
            return TaskResult(
                success=True,
                outputs={"content": f"[Mock writing for: {task.description}]", "type": "mock"},
                checkpoint=f"Mock writing completed for '{task.name}'"
            )
        
        try:
            context = task.inputs.get("context", "")
            
            await self.log_event(EventType.AGENT_THINKING, task, "Drafting content structure and writing...")

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert content writer. Create well-structured, professional content. Use clear headings, bullet points, and organize information logically."},
                    {"role": "user", "content": f"Writing task: {task.description}\n\nSource material/context: {context}\n\nCreate professional, well-formatted content."}
                ],
                max_tokens=1500
            )
            
            content = response.choices[0].message.content
            
            return TaskResult(
                success=True,
                outputs={
                    "content": content,
                    "type": "document",
                    "word_count": len(content.split()),
                    "timestamp": datetime.utcnow().isoformat()
                },
                checkpoint=f"Written content: {content[:200]}..."
            )
            
        except Exception as e:
            return TaskResult(success=False, error=str(e))


class CoderAgent(BaseAgent):
    """Agent specialized in code generation using AI"""
    
    def __init__(self, agent_id: str, name: str = "Coder"):
        super().__init__(agent_id, name, AgentRole.CODER.value)
        self.skills = ["coding", "debugging", "code_review", "implementation"]
        self.client = AsyncOpenAI(
            api_key=settings.FIREWORK_API,
            base_url=settings.FIREWORKS_BASE_URL
        ) if settings.FIREWORK_API else None
        self.model = settings.FIREWORKS_MODEL
    
    async def execute(self, task: Task) -> TaskResult:
        """Execute a coding task with AI"""
        if not self.client:
            return TaskResult(
                success=True,
                outputs={"code": f"# Mock code for: {task.description}", "type": "mock"},
                checkpoint=f"Mock code completed for '{task.name}'"
            )
        
        try:
            context = task.inputs.get("context", "")
            
            await self.log_event(EventType.AGENT_THINKING, task, "Analyzing requirements and generating code...")

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert programmer. Write clean, well-documented code. Include comments explaining the logic."},
                    {"role": "user", "content": f"Coding task: {task.description}\n\nContext: {context}\n\nWrite the implementation."}
                ],
                max_tokens=1500
            )
            
            content = response.choices[0].message.content
            
            return TaskResult(
                success=True,
                outputs={
                    "code": content,
                    "type": "code",
                    "language": "python",
                    "timestamp": datetime.utcnow().isoformat()
                },
                checkpoint=f"Coded implementation for '{task.name}'"
            )
            
        except Exception as e:
            return TaskResult(success=False, error=str(e))


class DataBuilderAgent(BaseAgent):
    """Agent specialized in data processing using AI"""
    
    def __init__(self, agent_id: str, name: str = "DataBuilder"):
        super().__init__(agent_id, name, AgentRole.DATA_BUILDER.value)
        self.skills = ["data_processing", "table_creation", "csv", "spreadsheet"]
        self.client = AsyncOpenAI(
            api_key=settings.FIREWORK_API,
            base_url=settings.FIREWORKS_BASE_URL
        ) if settings.FIREWORK_API else None
        self.model = settings.FIREWORKS_MODEL
    
    async def execute(self, task: Task) -> TaskResult:
        """Execute a data building task with AI"""
        if not self.client:
            return TaskResult(
                success=True,
                outputs={"data": [{"mock": "data"}], "type": "mock"},
                checkpoint=f"Mock data completed for '{task.name}'"
            )
        
        try:
            context = task.inputs.get("context", "")
            
            await self.log_event(EventType.AGENT_THINKING, task, "Processing data and formatting tables...")

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a data analyst. Create structured data tables in markdown format. Use proper headers and organize data clearly."},
                    {"role": "user", "content": f"Data task: {task.description}\n\nContext: {context}\n\nCreate a well-organized data table or structured output."}
                ],
                max_tokens=1000
            )
            
            content = response.choices[0].message.content
            
            return TaskResult(
                success=True,
                outputs={
                    "content": content,
                    "type": "data_table",
                    "format": "markdown",
                    "timestamp": datetime.utcnow().isoformat()
                },
                checkpoint=f"Built data table for '{task.name}'"
            )
            
        except Exception as e:
            return TaskResult(success=False, error=str(e))


# Factory function to create the right agent type
def create_agent(agent_id: str, role: AgentRole, name: str = None) -> BaseAgent:
    """Create an agent based on its role"""
    agent_classes = {
        AgentRole.RESEARCHER: ResearcherAgent,
        AgentRole.WRITER: WriterAgent,
        AgentRole.CODER: CoderAgent,
        AgentRole.DATA_BUILDER: DataBuilderAgent,
    }
    
    agent_class = agent_classes.get(role)
    if agent_class:
        return agent_class(agent_id, name or role.value)
    
    raise ValueError(f"Unknown agent role: {role}")
