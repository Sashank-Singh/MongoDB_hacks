"""
Event Model - Append-only log for system observability
"""
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from bson import ObjectId


class EventType(str, Enum):
    """Types of events in the system"""
    # Job events
    JOB_CREATED = "job_created"
    JOB_STARTED = "job_started"
    JOB_PAUSED = "job_paused"
    JOB_RESUMED = "job_resumed"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    
    # Task events
    TASK_CREATED = "task_created"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_RETRY = "task_retry"
    TASK_REASSIGNED = "task_reassigned"
    
    # Agent events
    AGENT_REGISTERED = "agent_registered"
    AGENT_HEARTBEAT = "agent_heartbeat"
    AGENT_DEAD = "agent_dead"
    
    # System events
    SCHEDULER_RUN = "scheduler_run"
    RECOVERY_TRIGGERED = "recovery_triggered"
    HUMAN_INTERVENTION = "human_intervention"


class Event(BaseModel):
    """Immutable event log entry"""
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    
    # Context
    job_id: Optional[str] = None
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    
    # Event data
    type: EventType
    payload: Dict[str, Any] = Field(default_factory=dict)
    message: Optional[str] = None
    
    # Timestamp (never modified)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }
    
    def to_mongo(self) -> dict:
        return self.model_dump(by_alias=True)
    
    @classmethod
    def from_mongo(cls, doc: dict) -> "Event":
        if doc.get("_id"):
            doc["_id"] = str(doc["_id"])
        return cls(**doc)
