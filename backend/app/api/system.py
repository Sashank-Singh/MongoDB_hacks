"""
System API Router - Scheduler, Recovery, and System Control
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
import asyncio

from app.database import get_database, Database
from app.core.scheduler import scheduler
from app.core.recovery import recovery_manager, RecoveryAction
from app.agents.sentinel import sentinel
from app.agents.worker import Worker
from app.models import Event, EventType, AgentRole, AgentStatus

router = APIRouter()

# Global state for background tasks
_scheduler_task = None
_sentinel_task = None
_worker_tasks = []


@router.post("/scheduler/start")
async def start_scheduler(background_tasks: BackgroundTasks):
    """Start the scheduler loop in the background"""
    global _scheduler_task
    
    if scheduler.running:
        return {"status": "already_running"}
    
    # Start scheduler in background
    loop = asyncio.get_event_loop()
    _scheduler_task = loop.create_task(scheduler.run_loop())
    
    return {"status": "started", "message": "Scheduler started"}


@router.post("/scheduler/stop")
async def stop_scheduler():
    """Stop the scheduler loop"""
    if not scheduler.running:
        return {"status": "not_running"}
    
    scheduler.stop()
    return {"status": "stopped", "message": "Scheduler stopped"}


@router.get("/scheduler/status")
async def scheduler_status():
    """Get scheduler status"""
    return {
        "running": scheduler.running,
        "poll_interval": scheduler.poll_interval
    }


@router.post("/sentinel/start")
async def start_sentinel(background_tasks: BackgroundTasks):
    """Start the sentinel monitoring loop"""
    global _sentinel_task
    
    if sentinel.running:
        return {"status": "already_running"}
    
    loop = asyncio.get_event_loop()
    _sentinel_task = loop.create_task(sentinel.run_loop())
    
    return {"status": "started", "message": "Sentinel started"}


@router.post("/sentinel/stop")
async def stop_sentinel():
    """Stop the sentinel loop"""
    if not sentinel.running:
        return {"status": "not_running"}
    
    sentinel.stop()
    return {"status": "stopped", "message": "Sentinel stopped"}


@router.get("/sentinel/status")
async def sentinel_status():
    """Get sentinel status"""
    return {
        "running": sentinel.running,
        "heartbeat_timeout": sentinel.heartbeat_timeout,
        "poll_interval": sentinel.poll_interval
    }


@router.post("/recovery/{task_id}")
async def trigger_recovery(task_id: str, db: Database = Depends(get_database)):
    """Manually trigger recovery for a task"""
    result = await recovery_manager.execute_recovery(task_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.get("/events")
async def get_system_events(
    limit: int = 100,
    event_type: Optional[str] = None,
    db: Database = Depends(get_database)
):
    """Get recent system events"""
    query = {}
    if event_type:
        query["type"] = event_type
    
    cursor = db.events.find(query).sort("timestamp", -1).limit(limit)
    events = await cursor.to_list(length=limit)
    return [Event.from_mongo(e).model_dump() for e in events]


@router.post("/workers/start")
async def start_workers(db: Database = Depends(get_database)):
    """Start background worker loops for all registered agents"""
    global _worker_tasks
    
    # Find ALL agents (idle, busy, or dead) - we need workers for all of them
    cursor = db.agents.find({})
    agents = await cursor.to_list(length=100)
    
    started_count = 0
    loop = asyncio.get_event_loop()
    
    for agent_doc in agents:
        agent_id = agent_doc["_id"]
        # Avoid double-starting workers for the same agent ID
        if any(t.get("agent_id") == agent_id for t in _worker_tasks if not t["task"].done()):
            continue
            
        # Reset agent status to IDLE if it was DEAD
        if agent_doc["status"] == AgentStatus.DEAD.value:
            await db.agents.update_one(
                {"_id": agent_id},
                {"$set": {"status": AgentStatus.IDLE.value, "last_heartbeat": datetime.utcnow()}}
            )
            
        worker = Worker(name=agent_doc["name"], role=AgentRole(agent_doc["role"]))
        worker.agent_id = agent_id
        
        task = loop.create_task(worker.run_loop())
        _worker_tasks.append({
            "agent_id": agent_id,
            "task": task,
            "worker": worker
        })
        started_count += 1
        
    return {
        "status": "success", 
        "started_count": started_count,
        "total_active_workers": len([t for t in _worker_tasks if not t["task"].done()])
    }


@router.post("/workers/stop")
async def stop_workers():
    """Stop all background worker loops"""
    global _worker_tasks
    
    stopped_count = 0
    for item in _worker_tasks:
        if not item["task"].done():
            item["worker"].stop()
            stopped_count += 1
            
    return {"status": "success", "stopped_count": stopped_count}


@router.post("/reset")
async def reset_system(db: Database = Depends(get_database)):
    """
    Full system reset - clears all running tasks and resets agents.
    Call this before starting a new job to ensure clean state.
    """
    global _worker_tasks, _scheduler_task, _sentinel_task
    
    # 1. Stop scheduler and sentinel
    scheduler.stop()
    sentinel.stop()
    
    # 2. Stop all workers
    stopped_count = 0
    for item in _worker_tasks:
        if not item["task"].done():
            item["worker"].stop()
            stopped_count += 1
    
    # Wait briefly for tasks to stop
    await asyncio.sleep(0.2)
    
    # Clear worker tasks list
    _worker_tasks = []
    
    # 3. Cancel all running/pending tasks
    tasks_result = await db.tasks.update_many(
        {"status": {"$in": ["running", "pending"]}},
        {"$set": {"status": "cancelled", "assigned_agent": None}}
    )
    
    # 4. Mark all running jobs as cancelled
    jobs_result = await db.jobs.update_many(
        {"status": {"$in": ["running", "queued"]}},
        {"$set": {"status": "cancelled"}}
    )
    
    # 5. Reset all agents to idle
    agents_result = await db.agents.update_many(
        {},
        {"$set": {
            "status": AgentStatus.IDLE.value,
            "current_task_id": None,
            "last_heartbeat": datetime.utcnow()
        }}
    )
    
    # 6. Restart scheduler
    loop = asyncio.get_event_loop()
    _scheduler_task = loop.create_task(scheduler.run_loop())
    
    # 7. Restart sentinel
    _sentinel_task = loop.create_task(sentinel.run_loop())
    
    # 8. Restart workers
    cursor = db.agents.find({})
    agents = await cursor.to_list(length=100)
    
    started_count = 0
    for agent_doc in agents:
        agent_id = agent_doc["_id"]
        worker = Worker(name=agent_doc["name"], role=AgentRole(agent_doc["role"]))
        worker.agent_id = agent_id
        
        task = loop.create_task(worker.run_loop())
        _worker_tasks.append({
            "agent_id": agent_id,
            "task": task,
            "worker": worker
        })
        started_count += 1
    
    return {
        "status": "success",
        "message": "System reset complete",
        "workers_stopped": stopped_count,
        "workers_started": started_count,
        "tasks_cancelled": tasks_result.modified_count,
        "jobs_cancelled": jobs_result.modified_count,
        "agents_reset": agents_result.modified_count
    }


@router.get("/health/full")
async def full_health_check(db: Database = Depends(get_database)):
    """Comprehensive system health check"""
    from app.models import JobStatus, TaskStatus, AgentStatus
    
    # Count active workers in memory
    active_worker_count = len([t for t in _worker_tasks if not t["task"].done()])
    
    # Count jobs by status
    job_pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    job_counts = {}
    async for doc in db.jobs.aggregate(job_pipeline):
        job_counts[doc["_id"]] = doc["count"]
    
    # Count tasks by status
    task_pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    task_counts = {}
    async for doc in db.tasks.aggregate(task_pipeline):
        task_counts[doc["_id"]] = doc["count"]
    
    # Count agents by status
    agent_pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
    ]
    agent_counts = {}
    async for doc in db.agents.aggregate(agent_pipeline):
        agent_counts[doc["_id"]] = doc["count"]
    
    return {
        "status": "healthy",
        "scheduler_running": scheduler.running,
        "sentinel_running": sentinel.running,
        "active_workers": active_worker_count,
        "jobs": job_counts,
        "tasks": task_counts,
        "agents": agent_counts
    }
