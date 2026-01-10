"""
Scheduler - Assigns runnable tasks to available agents
"""
import asyncio
from datetime import datetime
from typing import List, Optional, Tuple

from app.database import database
from app.models import Task, TaskStatus, Agent, AgentStatus, Job, JobStatus, Event, EventType


class Scheduler:
    """
    The Scheduler is the heart of Agent OS execution.
    
    It continuously:
    1. Finds runnable tasks (pending + all dependencies completed)
    2. Matches tasks to available agents based on skills
    3. Claims tasks atomically to prevent double-execution
    """
    
    def __init__(self, poll_interval: float = 2.0):
        self.poll_interval = poll_interval
        self.running = False
    
    async def get_completed_task_ids(self, job_id: str) -> set:
        """Get IDs of all completed tasks for a job"""
        cursor = database.tasks.find(
            {"job_id": job_id, "status": TaskStatus.COMPLETED.value},
            {"_id": 1}
        )
        completed = await cursor.to_list(length=1000)
        return {doc["_id"] for doc in completed}
    
    async def find_runnable_tasks(self, job_id: str) -> List[Task]:
        """
        Find tasks that are ready to run.
        A task is runnable if:
        - Status is PENDING
        - All dependencies are COMPLETED
        """
        completed_ids = await self.get_completed_task_ids(job_id)
        
        # Get all pending tasks
        cursor = database.tasks.find({
            "job_id": job_id,
            "status": TaskStatus.PENDING.value
        })
        pending_tasks = await cursor.to_list(length=100)
        
        runnable = []
        for task_doc in pending_tasks:
            task = Task.from_mongo(task_doc)
            # Check if all dependencies are completed
            if task.is_runnable(completed_ids):
                runnable.append(task)
        
        return runnable
    
    async def find_available_agent(self, required_skill: Optional[str] = None) -> Optional[Agent]:
        """Find an idle agent that can handle the required skill"""
        query = {"status": AgentStatus.IDLE.value}
        
        if required_skill:
            query["$or"] = [
                {"skills": required_skill},
                {"role": required_skill}
            ]
        
        agent_doc = await database.agents.find_one(query)
        if agent_doc:
            return Agent.from_mongo(agent_doc)
        return None
    
    async def claim_task(self, task: Task, agent: Agent) -> Optional[Task]:
        """
        Atomically claim a task for an agent.
        Uses findOneAndUpdate to prevent race conditions.
        """
        now = datetime.utcnow()
        
        # Atomically update task if still pending
        result = await database.tasks.find_one_and_update(
            {
                "_id": task.id,
                "status": TaskStatus.PENDING.value
            },
            {
                "$set": {
                    "status": TaskStatus.RUNNING.value,
                    "assigned_agent": agent.id,
                    "started_at": now,
                    "updated_at": now
                }
            },
            return_document=True
        )
        
        if not result:
            return None  # Task was claimed by another scheduler
        
        # Update agent status
        await database.agents.update_one(
            {"_id": agent.id},
            {
                "$set": {
                    "status": AgentStatus.BUSY.value,
                    "current_task_id": task.id
                }
            }
        )
        
        # Log event
        event = Event(
            job_id=task.job_id,
            task_id=task.id,
            agent_id=agent.id,
            type=EventType.TASK_STARTED,
            message=f"Task claimed by agent {agent.name}"
        )
        await database.events.insert_one(event.to_mongo())
        
        return Task.from_mongo(result)
    
    async def schedule_once(self) -> List[Tuple[Task, Agent]]:
        """
        Run one scheduling cycle.
        Returns list of (task, agent) pairs that were scheduled.
        """
        scheduled = []
        
        # Get all running jobs
        cursor = database.jobs.find({"status": JobStatus.RUNNING.value})
        running_jobs = await cursor.to_list(length=100)
        
        for job_doc in running_jobs:
            job = Job.from_mongo(job_doc)
            
            # Find runnable tasks for this job
            runnable = await self.find_runnable_tasks(job.id)
            
            for task in runnable:
                # Find an agent for this task
                agent = await self.find_available_agent(task.required_skill)
                
                if agent:
                    # Claim the task
                    claimed = await self.claim_task(task, agent)
                    if claimed:
                        scheduled.append((claimed, agent))
        
        return scheduled
    
    async def check_job_completion(self, job_id: str) -> bool:
        """Check if all tasks are completed and update job status"""
        # Count tasks by status
        pipeline = [
            {"$match": {"job_id": job_id}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]
        
        cursor = database.tasks.aggregate(pipeline)
        status_counts = {doc["_id"]: doc["count"] async for doc in cursor}
        
        total = sum(status_counts.values())
        completed = status_counts.get(TaskStatus.COMPLETED.value, 0)
        failed = status_counts.get(TaskStatus.FAILED.value, 0)
        
        # All completed
        if completed == total:
            await database.jobs.update_one(
                {"_id": job_id},
                {
                    "$set": {
                        "status": JobStatus.DONE.value,
                        "completed_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            event = Event(
                job_id=job_id,
                type=EventType.JOB_COMPLETED,
                message="All tasks completed successfully"
            )
            await database.events.insert_one(event.to_mongo())
            return True
        
        # Any failed and nothing running or pending
        pending = status_counts.get(TaskStatus.PENDING.value, 0)
        running = status_counts.get(TaskStatus.RUNNING.value, 0)
        
        if failed > 0 and pending == 0 and running == 0:
            # Job failed - no more tasks can run
            await database.jobs.update_one(
                {"_id": job_id},
                {
                    "$set": {
                        "status": JobStatus.FAILED.value,
                        "error": f"{failed} task(s) failed",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            event = Event(
                job_id=job_id,
                type=EventType.JOB_FAILED,
                message=f"Job failed with {failed} failed tasks"
            )
            await database.events.insert_one(event.to_mongo())
            return True
        
        return False
    
    async def run_loop(self):
        """Main scheduler loop - runs until stopped"""
        self.running = True
        print("🔄 Scheduler started")
        
        while self.running:
            try:
                # Run scheduling cycle
                scheduled = await self.schedule_once()
                
                if scheduled:
                    for task, agent in scheduled:
                        print(f"📋 Scheduled task '{task.name}' → agent '{agent.name}'")
                
                # Check for completed jobs
                cursor = database.jobs.find({"status": JobStatus.RUNNING.value})
                async for job_doc in cursor:
                    await self.check_job_completion(job_doc["_id"])
                
                # Log scheduler heartbeat
                event = Event(
                    type=EventType.SCHEDULER_RUN,
                    payload={"tasks_scheduled": len(scheduled)}
                )
                await database.events.insert_one(event.to_mongo())
                
            except Exception as e:
                print(f"❌ Scheduler error: {e}")
            
            await asyncio.sleep(self.poll_interval)
        
        print("🛑 Scheduler stopped")
    
    def stop(self):
        """Stop the scheduler loop"""
        self.running = False


# Singleton scheduler
scheduler = Scheduler()
