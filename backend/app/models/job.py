"""
Job Model - Represents a user's goal/workflow
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from bson import ObjectId


class JobStatus(str, Enum):
    """Possible states for a job"""
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    DONE = "done"
    FAILED = "failed"


class JobCreate(BaseModel):
    """Schema for creating a new job"""
    goal: str = Field(..., min_length=1, description="The user's goal/objective")
    

class Job(BaseModel):
    """Full Job model with all fields"""
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    goal: str
    status: JobStatus = JobStatus.QUEUED
    task_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    
    class Config:
        populate_by_name = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }
    
    def to_mongo(self) -> dict:
        """Convert to MongoDB document"""
        data = self.model_dump(by_alias=True)
        return data
    
    @classmethod
    def from_mongo(cls, doc: dict) -> "Job":
        """Create from MongoDB document"""
        if doc.get("_id"):
            doc["_id"] = str(doc["_id"])
        return cls(**doc)
