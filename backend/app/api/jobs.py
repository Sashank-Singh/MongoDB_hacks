"""
Jobs API Router
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends

from app.database import database, get_database, Database
from app.models import Job, JobStatus, JobCreate, Task, Event, EventType
from app.agents.planner import PlannerAgent

router = APIRouter()


@router.post("/", response_model=dict)
async def create_job(job_input: JobCreate, db: Database = Depends(get_database)):
    """
    Create a new job from a user goal.
    The Planner agent will decompose the goal into a task DAG.
    """
    # Create job
    job = Job(goal=job_input.goal)
    
    # Use Planner to generate task DAG
    planner = PlannerAgent()
    tasks = await planner.decompose_goal(job.id, job_input.goal)
    
    # Update job with task IDs
    job.task_ids = [t.id for t in tasks]
    job.status = JobStatus.QUEUED
    
    # Save to MongoDB
    await db.jobs.insert_one(job.to_mongo())
    
    # Save all tasks
    if tasks:
        await db.tasks.insert_many([t.to_mongo() for t in tasks])
    
    # Log event
    event = Event(
        job_id=job.id,
        type=EventType.JOB_CREATED,
        message=f"Job created with {len(tasks)} tasks",
        payload={"goal": job.goal, "task_count": len(tasks)}
    )
    await db.events.insert_one(event.to_mongo())
    
    return {
        "job": job.model_dump(),
        "tasks": [t.model_dump() for t in tasks],
        "message": f"Created job with {len(tasks)} tasks"
    }


@router.get("/", response_model=List[dict])
async def list_jobs(
    status: Optional[JobStatus] = None,
    limit: int = 20,
    db: Database = Depends(get_database)
):
    """List all jobs, optionally filtered by status"""
    query = {}
    if status:
        query["status"] = status.value
    
    cursor = db.jobs.find(query).sort("created_at", -1).limit(limit)
    jobs = await cursor.to_list(length=limit)
    return [Job.from_mongo(j).model_dump() for j in jobs]


@router.get("/{job_id}")
async def get_job(job_id: str, db: Database = Depends(get_database)):
    """Get a job by ID with its tasks"""
    job_doc = await db.jobs.find_one({"_id": job_id})
    if not job_doc:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = Job.from_mongo(job_doc)
    
    # Get associated tasks
    tasks_cursor = db.tasks.find({"job_id": job_id})
    tasks = await tasks_cursor.to_list(length=100)
    
    return {
        "job": job.model_dump(),
        "tasks": [Task.from_mongo(t).model_dump() for t in tasks]
    }


@router.post("/{job_id}/start")
async def start_job(job_id: str, db: Database = Depends(get_database)):
    """Start executing a job"""
    result = await db.jobs.find_one_and_update(
        {"_id": job_id, "status": JobStatus.QUEUED.value},
        {
            "$set": {
                "status": JobStatus.RUNNING.value,
                "updated_at": datetime.utcnow()
            }
        },
        return_document=True
    )
    
    if not result:
        raise HTTPException(status_code=400, detail="Job not found or not in queued state")
    
    # Log event
    event = Event(
        job_id=job_id,
        type=EventType.JOB_STARTED,
        message="Job execution started"
    )
    await db.events.insert_one(event.to_mongo())
    
    return {"message": "Job started", "job": Job.from_mongo(result).model_dump()}


@router.post("/{job_id}/pause")
async def pause_job(job_id: str, db: Database = Depends(get_database)):
    """Pause a running job"""
    result = await db.jobs.find_one_and_update(
        {"_id": job_id, "status": JobStatus.RUNNING.value},
        {
            "$set": {
                "status": JobStatus.PAUSED.value,
                "updated_at": datetime.utcnow()
            }
        },
        return_document=True
    )
    
    if not result:
        raise HTTPException(status_code=400, detail="Job not found or not running")
    
    event = Event(
        job_id=job_id,
        type=EventType.JOB_PAUSED,
        message="Job paused by user"
    )
    await db.events.insert_one(event.to_mongo())
    
    return {"message": "Job paused", "job": Job.from_mongo(result).model_dump()}


@router.post("/{job_id}/resume")
async def resume_job(job_id: str, db: Database = Depends(get_database)):
    """Resume a paused job"""
    result = await db.jobs.find_one_and_update(
        {"_id": job_id, "status": JobStatus.PAUSED.value},
        {
            "$set": {
                "status": JobStatus.RUNNING.value,
                "updated_at": datetime.utcnow()
            }
        },
        return_document=True
    )
    
    if not result:
        raise HTTPException(status_code=400, detail="Job not found or not paused")
    
    event = Event(
        job_id=job_id,
        type=EventType.JOB_RESUMED,
        message="Job resumed by user"
    )
    await db.events.insert_one(event.to_mongo())
    
    return {"message": "Job resumed", "job": Job.from_mongo(result).model_dump()}


@router.get("/{job_id}/events")
async def get_job_events(
    job_id: str,
    limit: int = 50,
    db: Database = Depends(get_database)
):
    """Get event log for a job"""
    cursor = db.events.find({"job_id": job_id}).sort("timestamp", -1).limit(limit)
    events = await cursor.to_list(length=limit)
    return [Event.from_mongo(e).model_dump() for e in events]
