"""
Recovery Manager - Handles task failures with intelligent retry strategies
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from enum import Enum

from app.database import database
from app.models import Task, TaskStatus, Agent, AgentStatus, Event, EventType
from app.core.state_machine import TaskStateMachine, TransitionResult


class RecoveryAction(str, Enum):
    """Possible recovery actions"""
    RETRY_SAME_AGENT = "retry_same_agent"
    RETRY_DIFFERENT_AGENT = "retry_different_agent"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    SKIP_WITH_FALLBACK = "skip_with_fallback"
    STOP_JOB = "stop_job"


class RecoveryManager:
    """
    Handles task failures with intelligent recovery strategies.
    
    Recovery policies:
    1. Retry same agent - for transient errors
    2. Retry different agent - for agent-specific failures
    3. Escalate to human - for complex failures
    4. Skip with fallback - when task is optional
    5. Stop job - for critical unrecoverable errors
    """
    
    # Error patterns that suggest specific recovery actions
    TRANSIENT_ERRORS = [
        "timeout", "connection", "rate limit", "temporary",
        "try again", "retry", "503", "429"
    ]
    
    AGENT_ERRORS = [
        "agent dead", "heartbeat", "unresponsive", "crashed"
    ]
    
    CRITICAL_ERRORS = [
        "authentication", "permission", "not found", "invalid",
        "fatal", "critical"
    ]
    
    @staticmethod
    def classify_error(error: str) -> RecoveryAction:
        """Determine the best recovery action based on error message"""
        error_lower = error.lower() if error else ""
        
        # Check for transient errors → retry same agent
        if any(pattern in error_lower for pattern in RecoveryManager.TRANSIENT_ERRORS):
            return RecoveryAction.RETRY_SAME_AGENT
        
        # Check for agent-specific errors → retry different agent
        if any(pattern in error_lower for pattern in RecoveryManager.AGENT_ERRORS):
            return RecoveryAction.RETRY_DIFFERENT_AGENT
        
        # Check for critical errors → escalate
        if any(pattern in error_lower for pattern in RecoveryManager.CRITICAL_ERRORS):
            return RecoveryAction.ESCALATE_TO_HUMAN
        
        # Default: retry same agent first
        return RecoveryAction.RETRY_SAME_AGENT
    
    @staticmethod
    async def decide_recovery(task: Task) -> RecoveryAction:
        """
        Decide the best recovery action for a failed task.
        
        Considers:
        - Number of attempts
        - Error type
        - Agent health
        - Task criticality
        """
        # Check attempt count
        if task.attempts >= task.max_attempts:
            return RecoveryAction.ESCALATE_TO_HUMAN
        
        # Classify the error
        action = RecoveryManager.classify_error(task.error)
        
        # If same agent retry suggested, check if agent is healthy
        if action == RecoveryAction.RETRY_SAME_AGENT and task.assigned_agent:
            agent = await database.agents.find_one({"_id": task.assigned_agent})
            if agent:
                agent_obj = Agent.from_mongo(agent)
                if not agent_obj.is_alive():
                    action = RecoveryAction.RETRY_DIFFERENT_AGENT
        
        return action
    
    @staticmethod
    async def execute_recovery(task_id: str) -> Dict[str, Any]:
        """
        Execute recovery for a failed task.
        
        Returns dict with recovery result.
        """
        task_doc = await database.tasks.find_one({"_id": task_id})
        if not task_doc:
            return {"success": False, "error": "Task not found"}
        
        task = Task.from_mongo(task_doc)
        
        if task.status != TaskStatus.FAILED:
            return {"success": False, "error": "Task is not in failed state"}
        
        # Decide recovery action
        action = await RecoveryManager.decide_recovery(task)
        
        # Log the recovery decision
        event = Event(
            job_id=task.job_id,
            task_id=task_id,
            type=EventType.RECOVERY_TRIGGERED,
            message=f"Recovery triggered: {action.value}",
            payload={
                "action": action.value,
                "attempts": task.attempts,
                "max_attempts": task.max_attempts,
                "error": task.error
            }
        )
        await database.events.insert_one(event.to_mongo())
        
        # Execute the recovery action
        if action == RecoveryAction.RETRY_SAME_AGENT:
            return await RecoveryManager._retry_same_agent(task)
        
        elif action == RecoveryAction.RETRY_DIFFERENT_AGENT:
            return await RecoveryManager._retry_different_agent(task)
        
        elif action == RecoveryAction.ESCALATE_TO_HUMAN:
            return await RecoveryManager._escalate_to_human(task)
        
        elif action == RecoveryAction.SKIP_WITH_FALLBACK:
            return await RecoveryManager._skip_with_fallback(task)
        
        elif action == RecoveryAction.STOP_JOB:
            return await RecoveryManager._stop_job(task)
        
        return {"success": False, "error": "Unknown recovery action"}
    
    @staticmethod
    async def _retry_same_agent(task: Task) -> Dict[str, Any]:
        """Retry the task with the same agent"""
        result, updated = await TaskStateMachine.retry_task(task.id)
        
        if result == TransitionResult.SUCCESS:
            await database.events.insert_one(Event(
                job_id=task.job_id,
                task_id=task.id,
                type=EventType.TASK_RETRY,
                message="Task queued for retry with same agent"
            ).to_mongo())
            
            return {
                "success": True,
                "action": RecoveryAction.RETRY_SAME_AGENT.value,
                "message": "Task queued for retry"
            }
        
        return {"success": False, "error": f"Retry failed: {result.value}"}
    
    @staticmethod
    async def _retry_different_agent(task: Task) -> Dict[str, Any]:
        """Retry with a different agent"""
        # Reset task and clear assigned agent
        await database.tasks.update_one(
            {"_id": task.id},
            {
                "$set": {
                    "status": TaskStatus.PENDING.value,
                    "assigned_agent": None,
                    "error": None,
                    "updated_at": datetime.utcnow()
                },
                "$inc": {"attempts": 1}
            }
        )
        
        # If previous agent exists, add to a blacklist for this task (optional)
        
        await database.events.insert_one(Event(
            job_id=task.job_id,
            task_id=task.id,
            type=EventType.TASK_REASSIGNED,
            message="Task reassigned to different agent for retry"
        ).to_mongo())
        
        return {
            "success": True,
            "action": RecoveryAction.RETRY_DIFFERENT_AGENT.value,
            "message": "Task reassigned for retry with different agent"
        }
    
    @staticmethod
    async def _escalate_to_human(task: Task) -> Dict[str, Any]:
        """Escalate to human intervention"""
        await database.events.insert_one(Event(
            job_id=task.job_id,
            task_id=task.id,
            type=EventType.HUMAN_INTERVENTION,
            message="Task escalated for human review",
            payload={
                "error": task.error,
                "attempts": task.attempts,
                "requires_action": True
            }
        ).to_mongo())
        
        return {
            "success": True,
            "action": RecoveryAction.ESCALATE_TO_HUMAN.value,
            "message": "Task escalated for human intervention",
            "requires_human_action": True
        }
    
    @staticmethod
    async def _skip_with_fallback(task: Task) -> Dict[str, Any]:
        """Skip the task with a fallback value"""
        await database.tasks.update_one(
            {"_id": task.id},
            {
                "$set": {
                    "status": TaskStatus.COMPLETED.value,
                    "outputs": {"_skipped": True, "_fallback": "Task skipped due to errors"},
                    "checkpoint": "[SKIPPED] Task was skipped due to errors",
                    "completed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return {
            "success": True,
            "action": RecoveryAction.SKIP_WITH_FALLBACK.value,
            "message": "Task skipped with fallback value"
        }
    
    @staticmethod
    async def _stop_job(task: Task) -> Dict[str, Any]:
        """Stop the entire job safely"""
        from app.models import JobStatus
        
        await database.jobs.update_one(
            {"_id": task.job_id},
            {
                "$set": {
                    "status": JobStatus.FAILED.value,
                    "error": f"Job stopped due to unrecoverable task failure: {task.name}",
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        await database.events.insert_one(Event(
            job_id=task.job_id,
            task_id=task.id,
            type=EventType.JOB_FAILED,
            message=f"Job stopped due to critical task failure: {task.name}"
        ).to_mongo())
        
        return {
            "success": True,
            "action": RecoveryAction.STOP_JOB.value,
            "message": "Job stopped safely due to critical failure"
        }


# Instance for easy import
recovery_manager = RecoveryManager()
