"""
Agent Model - Represents a worker agent in the system
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from bson import ObjectId


class AgentRole(str, Enum):
    """Specialized roles agents can fulfill"""
    PLANNER = "planner"       # Converts goals to task DAGs
    RESEARCHER = "researcher"  # Web research and data gathering
    WRITER = "writer"         # Content creation
    CODER = "coder"           # Code generation and analysis
    DATA_BUILDER = "data_builder"  # Data processing and tables
    SENTINEL = "sentinel"     # System health monitoring
    RECOVERY = "recovery"     # Failure handling


class AgentStatus(str, Enum):
    """Agent availability states"""
    IDLE = "idle"       # Ready to accept tasks
    BUSY = "busy"       # Currently executing a task
    DEAD = "dead"       # Not responding (missed heartbeats)


class Agent(BaseModel):
    """Worker agent that executes tasks"""
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    name: str
    role: AgentRole
    skills: List[str] = Field(default_factory=list)  # Additional capabilities
    
    # Status
    status: AgentStatus = AgentStatus.IDLE
    current_task_id: Optional[str] = None
    
    # Health monitoring
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)
    heartbeat_interval_seconds: int = 30
    
    # Performance tracking
    tasks_completed: int = 0
    tasks_failed: int = 0
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }
    
    def to_mongo(self) -> dict:
        return self.model_dump(by_alias=True)
    
    @classmethod
    def from_mongo(cls, doc: dict) -> "Agent":
        if doc.get("_id"):
            doc["_id"] = str(doc["_id"])
        return cls(**doc)
    
    def is_alive(self, timeout_seconds: int = 60) -> bool:
        """Check if agent is responding (within heartbeat timeout)"""
        elapsed = (datetime.utcnow() - self.last_heartbeat).total_seconds()
        return elapsed < timeout_seconds
    
    def can_handle(self, required_skill: Optional[str]) -> bool:
        """Check if agent has the required skill"""
        if not required_skill:
            return True
        return required_skill in self.skills or required_skill == self.role.value
