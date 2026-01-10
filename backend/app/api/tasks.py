"""
Tasks API Router
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends

from app.database import database, get_database, Database
from app.models import Task, TaskStatus, Event, EventType

router = APIRouter()


@router.get("/", response_model=List[dict])
async def list_tasks(
    job_id: Optional[str] = None,
    status: Optional[TaskStatus] = None,
    limit: int = 50,
    db: Database = Depends(get_database)
):
    """List tasks, optionally filtered by job or status"""
    query = {}
    if job_id:
        query["job_id"] = job_id
    if status:
        query["status"] = status.value
    
    cursor = db.tasks.find(query).sort("created_at", 1).limit(limit)
    tasks = await cursor.to_list(length=limit)
    return [Task.from_mongo(t).model_dump() for t in tasks]


@router.get("/{task_id}")
async def get_task(task_id: str, db: Database = Depends(get_database)):
    """Get a task by ID"""
    task_doc = await db.tasks.find_one({"_id": task_id})
    if not task_doc:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return Task.from_mongo(task_doc).model_dump()


@router.post("/{task_id}/retry")
async def retry_task(task_id: str, db: Database = Depends(get_database)):
    """Manually retry a failed task"""
    task_doc = await db.tasks.find_one({"_id": task_id})
    if not task_doc:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = Task.from_mongo(task_doc)
    
    if task.status != TaskStatus.FAILED:
        raise HTTPException(status_code=400, detail="Task is not in failed state")
    
    # Reset task for retry
    result = await db.tasks.find_one_and_update(
        {"_id": task_id},
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
    
    # Log event
    event = Event(
        job_id=task.job_id,
        task_id=task_id,
        type=EventType.TASK_RETRY,
        message="Task manually retried by user"
    )
    await db.events.insert_one(event.to_mongo())
    
    return {"message": "Task queued for retry", "task": Task.from_mongo(result).model_dump()}


@router.post("/{task_id}/reassign")
async def reassign_task(
    task_id: str,
    agent_id: Optional[str] = None,
    db: Database = Depends(get_database)
):
    """Reassign a task to a different agent"""
    task_doc = await db.tasks.find_one({"_id": task_id})
    if not task_doc:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = Task.from_mongo(task_doc)
    
    if task.status == TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Cannot reassign completed task")
    
    # Reset and reassign
    update = {
        "status": TaskStatus.PENDING.value,
        "assigned_agent": agent_id,
        "updated_at": datetime.utcnow()
    }
    
    result = await db.tasks.find_one_and_update(
        {"_id": task_id},
        {"$set": update},
        return_document=True
    )
    
    # Log event
    event = Event(
        job_id=task.job_id,
        task_id=task_id,
        type=EventType.TASK_REASSIGNED,
        message=f"Task reassigned to agent: {agent_id or 'any'}",
        payload={"new_agent_id": agent_id}
    )
    await db.events.insert_one(event.to_mongo())
    
    return {"message": "Task reassigned", "task": Task.from_mongo(result).model_dump()}


@router.get("/{task_id}/events")
async def get_task_events(
    task_id: str,
    limit: int = 20,
    db: Database = Depends(get_database)
):
    """Get event log for a specific task"""
    cursor = db.events.find({"task_id": task_id}).sort("timestamp", -1).limit(limit)
    events = await cursor.to_list(length=limit)
    return [Event.from_mongo(e).model_dump() for e in events]


@router.get("/{task_id}/outputs")
async def get_task_outputs(task_id: str, db: Database = Depends(get_database)):
    """Get the outputs of a completed task"""
    task_doc = await db.tasks.find_one({"_id": task_id})
    if not task_doc:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = Task.from_mongo(task_doc)
    
    return {
        "task_id": task.id,
        "name": task.name,
        "status": task.status.value,
        "outputs": task.outputs,
        "checkpoint": task.checkpoint
    }
