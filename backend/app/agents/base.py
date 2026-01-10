"""
Base Agent - Abstract base class for all agent workers
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum

from app.models import Task, TaskStatus, Event, EventType
from app.database import database


class TaskResult:
    """Result of a task execution"""
    def __init__(
        self,
        success: bool,
        outputs: Dict[str, Any] = None,
        checkpoint: str = None,
        error: str = None
    ):
        self.success = success
        self.outputs = outputs or {}
        self.checkpoint = checkpoint  # Summary for downstream tasks
        self.error = error


class BaseAgent(ABC):
    """
    Abstract base class for agent workers.
    
    Agents are specialized workers that execute tasks. Each agent has:
    - A role (researcher, writer, coder, etc.)
    - Skills for task routing
    - Heartbeat for health monitoring
    - Context compression for checkpoint creation
    """
    
    def __init__(self, agent_id: str, name: str, role: str):
        self.agent_id = agent_id
        self.name = name
        self.role = role
        self.skills = []
    
    @abstractmethod
    async def execute(self, task: Task) -> TaskResult:
        """
        Execute a task and return the result.
        Must be implemented by each agent type.
        """
        pass
    
    async def send_heartbeat(self) -> None:
        """Update agent heartbeat in database"""
        await database.agents.update_one(
            {"_id": self.agent_id},
            {"$set": {"last_heartbeat": datetime.utcnow()}}
        )
    
    async def compress_context(self, result: Any) -> str:
        """
        Compress task output into a checkpoint summary.
        Used to provide context to downstream tasks without 
        passing full output (prevents context overflow).
        """
        # Default: simple string representation truncated
        result_str = str(result)
        if len(result_str) > 500:
            return result_str[:500] + "... [truncated]"
        return result_str
    
    async def log_event(
        self,
        event_type: EventType,
        task: Task,
        message: str,
        payload: Dict[str, Any] = None
    ) -> None:
        """Log an event to the events collection"""
        event = Event(
            job_id=task.job_id,
            task_id=task.id,
            agent_id=self.agent_id,
            type=event_type,
            message=message,
            payload=payload or {}
        )
        await database.events.insert_one(event.to_mongo())
    
    async def run_task(self, task: Task) -> TaskResult:
        """
        Full task execution lifecycle:
        1. Mark task as running
        2. Execute the task
        3. Handle success or failure
        4. Create checkpoint
        """
        # Mark task as running
        await database.tasks.update_one(
            {"_id": task.id},
            {
                "$set": {
                    "status": TaskStatus.RUNNING.value,
                    "assigned_agent": self.agent_id,
                    "started_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        await self.log_event(
            EventType.TASK_STARTED,
            task,
            f"Task started by agent {self.name}"
        )
        
        try:
            # Execute the task
            result = await self.execute(task)
            
            if result.success:
                # Create checkpoint from outputs
                checkpoint = await self.compress_context(result.outputs)
                
                # Mark task as completed
                await database.tasks.update_one(
                    {"_id": task.id},
                    {
                        "$set": {
                            "status": TaskStatus.COMPLETED.value,
                            "outputs": result.outputs,
                            "checkpoint": checkpoint,
                            "completed_at": datetime.utcnow(),
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                
                await self.log_event(
                    EventType.TASK_COMPLETED,
                    task,
                    f"Task completed successfully",
                    {"outputs_keys": list(result.outputs.keys())}
                )
            else:
                # Mark task as failed
                await database.tasks.update_one(
                    {"_id": task.id},
                    {
                        "$set": {
                            "status": TaskStatus.FAILED.value,
                            "error": result.error,
                            "last_error_at": datetime.utcnow(),
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                
                await self.log_event(
                    EventType.TASK_FAILED,
                    task,
                    f"Task failed: {result.error}",
                    {"error": result.error}
                )
            
            return result
            
        except Exception as e:
            # Unexpected exception
            error_msg = str(e)
            await database.tasks.update_one(
                {"_id": task.id},
                {
                    "$set": {
                        "status": TaskStatus.FAILED.value,
                        "error": error_msg,
                        "last_error_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            await self.log_event(
                EventType.TASK_FAILED,
                task,
                f"Task failed with exception: {error_msg}",
                {"error": error_msg, "exception_type": type(e).__name__}
            )
            
            return TaskResult(success=False, error=error_msg)
