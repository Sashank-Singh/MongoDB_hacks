"""
Task State Machine - Enforces deterministic task state transitions
"""
from datetime import datetime
from typing import Optional, Tuple
from enum import Enum

from app.models import TaskStatus
from app.database import database


class TransitionResult(Enum):
    """Result of a state transition attempt"""
    SUCCESS = "success"
    INVALID_TRANSITION = "invalid_transition"
    ALREADY_IN_STATE = "already_in_state"
    TASK_NOT_FOUND = "task_not_found"


# Valid state transitions
VALID_TRANSITIONS = {
    TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.FAILED},
    TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED},
    TaskStatus.FAILED: {TaskStatus.PENDING},  # Can retry → goes back to pending
    TaskStatus.COMPLETED: set(),  # Terminal state - no transitions out
}


class TaskStateMachine:
    """
    Enforces deterministic state transitions for tasks.
    
    State diagram:
    
    PENDING ──► RUNNING ──► COMPLETED
                   │
                   ▼
               FAILED ──► (retry) ──► PENDING
    """
    
    @staticmethod
    def can_transition(from_status: TaskStatus, to_status: TaskStatus) -> bool:
        """Check if a transition is valid"""
        return to_status in VALID_TRANSITIONS.get(from_status, set())
    
    @staticmethod
    async def transition(
        task_id: str,
        to_status: TaskStatus,
        error: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> Tuple[TransitionResult, Optional[dict]]:
        """
        Attempt to transition a task to a new state.
        Uses atomic MongoDB operations to prevent race conditions.
        
        Returns:
            Tuple of (result, updated_task_doc)
        """
        # Get current task
        task = await database.tasks.find_one({"_id": task_id})
        if not task:
            return TransitionResult.TASK_NOT_FOUND, None
        
        current_status = TaskStatus(task["status"])
        
        # Check if already in target state
        if current_status == to_status:
            return TransitionResult.ALREADY_IN_STATE, task
        
        # Validate transition
        if not TaskStateMachine.can_transition(current_status, to_status):
            return TransitionResult.INVALID_TRANSITION, None
        
        # Build update
        update = {
            "status": to_status.value,
            "updated_at": datetime.utcnow()
        }
        
        if to_status == TaskStatus.RUNNING:
            update["started_at"] = datetime.utcnow()
            if agent_id:
                update["assigned_agent"] = agent_id
        elif to_status == TaskStatus.COMPLETED:
            update["completed_at"] = datetime.utcnow()
        elif to_status == TaskStatus.FAILED:
            update["last_error_at"] = datetime.utcnow()
            if error:
                update["error"] = error
        elif to_status == TaskStatus.PENDING:
            # Retry - clear error and agent assignment
            update["error"] = None
            update["assigned_agent"] = None
        
        # Atomic update with status check
        result = await database.tasks.find_one_and_update(
            {"_id": task_id, "status": current_status.value},
            {"$set": update},
            return_document=True
        )
        
        if result:
            return TransitionResult.SUCCESS, result
        else:
            # Race condition - status changed before our update
            return TransitionResult.INVALID_TRANSITION, None
    
    @staticmethod
    async def retry_task(task_id: str) -> Tuple[TransitionResult, Optional[dict]]:
        """
        Retry a failed task by transitioning it back to PENDING.
        Also increments the attempt counter.
        """
        # Atomic update: only if status is FAILED
        result = await database.tasks.find_one_and_update(
            {"_id": task_id, "status": TaskStatus.FAILED.value},
            {
                "$set": {
                    "status": TaskStatus.PENDING.value,
                    "error": None,
                    "assigned_agent": None,
                    "updated_at": datetime.utcnow()
                },
                "$inc": {"attempts": 1}
            },
            return_document=True
        )
        
        if result:
            return TransitionResult.SUCCESS, result
        
        # Check why it failed
        task = await database.tasks.find_one({"_id": task_id})
        if not task:
            return TransitionResult.TASK_NOT_FOUND, None
        if task["status"] != TaskStatus.FAILED.value:
            return TransitionResult.INVALID_TRANSITION, None
        
        return TransitionResult.INVALID_TRANSITION, None
