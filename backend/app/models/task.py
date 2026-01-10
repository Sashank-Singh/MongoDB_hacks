"""
Task Model - Represents a single step in a job's DAG
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from bson import ObjectId


class TaskStatus(str, Enum):
    """Task state machine states"""
    PENDING = "pending"      # Waiting for dependencies
    RUNNING = "running"      # Currently being executed
    COMPLETED = "completed"  # Successfully finished
    FAILED = "failed"        # Failed (may be retried)


class TaskCreate(BaseModel):
    """Schema for creating a new task"""
    job_id: str
    name: str
    description: str = ""
    depends_on: List[str] = Field(default_factory=list)
    required_skill: Optional[str] = None
    inputs: Dict[str, Any] = Field(default_factory=dict)


class Task(BaseModel):
    """Full Task model - a node in the job's DAG"""
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    job_id: str
    name: str
    description: str = ""
    
    # Dependencies (task IDs this task depends on)
    depends_on: List[str] = Field(default_factory=list)
    
    # Execution state
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3
    
    # I/O
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    
    # Checkpoint for context compression
    checkpoint: Optional[str] = None  # Summary for downstream tasks
    
    # Error tracking
    error: Optional[str] = None
    last_error_at: Optional[datetime] = None
    
    # Skill required for routing
    required_skill: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }
    
    def to_mongo(self) -> dict:
        """Convert to MongoDB document"""
        return self.model_dump(by_alias=True)
    
    @classmethod
    def from_mongo(cls, doc: dict) -> "Task":
        """Create from MongoDB document"""
        if doc.get("_id"):
            doc["_id"] = str(doc["_id"])
        return cls(**doc)
    
    def is_runnable(self, completed_task_ids: set) -> bool:
        """Check if this task can run (all dependencies completed)"""
        if self.status != TaskStatus.PENDING:
            return False
        return all(dep_id in completed_task_ids for dep_id in self.depends_on)
