"""
Sentinel - System health monitoring agent
Monitors agent heartbeats and detects failures
"""
import asyncio
from datetime import datetime, timedelta
from typing import List

from app.database import database
from app.models import Agent, AgentStatus, Task, TaskStatus, Event, EventType


class Sentinel:
    """
    The Sentinel monitors system health and detects failures.
    
    Responsibilities:
    - Monitor agent heartbeats
    - Detect dead agents (missed heartbeats)
    - Free tasks from dead agents
    - Log anomalies
    """
    
    def __init__(self, heartbeat_timeout: int = 60, poll_interval: float = 10.0):
        self.heartbeat_timeout = heartbeat_timeout  # seconds
        self.poll_interval = poll_interval
        self.running = False
    
    async def check_agent_health(self) -> List[Agent]:
        """Find and mark dead agents"""
        dead_agents = []
        cutoff = datetime.utcnow() - timedelta(seconds=self.heartbeat_timeout)
        
        # Find agents that haven't sent heartbeat
        cursor = database.agents.find({
            "status": {"$ne": AgentStatus.DEAD.value},
            "last_heartbeat": {"$lt": cutoff}
        })
        
        async for agent_doc in cursor:
            agent = Agent.from_mongo(agent_doc)
            dead_agents.append(agent)
            
            # Mark agent as dead
            await database.agents.update_one(
                {"_id": agent.id},
                {"$set": {"status": AgentStatus.DEAD.value}}
            )
            
            # Log event
            event = Event(
                agent_id=agent.id,
                type=EventType.AGENT_DEAD,
                message=f"Agent {agent.name} marked as dead (missed heartbeat)",
                payload={
                    "last_heartbeat": agent.last_heartbeat.isoformat(),
                    "timeout_seconds": self.heartbeat_timeout
                }
            )
            await database.events.insert_one(event.to_mongo())
            
            print(f"💀 Agent {agent.name} marked as dead")
        
        return dead_agents
    
    async def recover_orphaned_tasks(self) -> int:
        """Find tasks assigned to dead agents and reset them"""
        # Get all dead agent IDs
        cursor = database.agents.find(
            {"status": AgentStatus.DEAD.value},
            {"_id": 1}
        )
        dead_ids = [doc["_id"] async for doc in cursor]
        
        if not dead_ids:
            return 0
        
        # Find running tasks assigned to dead agents
        result = await database.tasks.update_many(
            {
                "status": TaskStatus.RUNNING.value,
                "assigned_agent": {"$in": dead_ids}
            },
            {
                "$set": {
                    "status": TaskStatus.PENDING.value,
                    "assigned_agent": None,
                    "error": "Agent died during execution",
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            print(f"🔄 Recovered {result.modified_count} orphaned tasks")
        
        return result.modified_count
    
    async def check_stuck_tasks(self, max_runtime: int = 300) -> int:
        """Find tasks that have been running too long"""
        cutoff = datetime.utcnow() - timedelta(seconds=max_runtime)
        
        cursor = database.tasks.find({
            "status": TaskStatus.RUNNING.value,
            "started_at": {"$lt": cutoff}
        })
        
        stuck_count = 0
        async for task_doc in cursor:
            task = Task.from_mongo(task_doc)
            stuck_count += 1
            
            # Log event
            event = Event(
                job_id=task.job_id,
                task_id=task.id,
                type=EventType.TASK_FAILED,
                message=f"Task stuck for over {max_runtime}s, marking as failed",
                payload={"started_at": task.started_at.isoformat() if task.started_at else None}
            )
            await database.events.insert_one(event.to_mongo())
            
            # Mark as failed
            await database.tasks.update_one(
                {"_id": task.id},
                {
                    "$set": {
                        "status": TaskStatus.FAILED.value,
                        "error": f"Task timeout after {max_runtime}s",
                        "updated_at": datetime.utcnow()
                    }
                }
            )
        
        if stuck_count > 0:
            print(f"⏰ Found {stuck_count} stuck tasks")
        
        return stuck_count
    
    async def run_loop(self):
        """Main sentinel monitoring loop"""
        self.running = True
        print("👁️ Sentinel started - monitoring system health")
        
        while self.running:
            try:
                # Check agent health
                dead_agents = await self.check_agent_health()
                
                # Recover orphaned tasks from dead agents
                await self.recover_orphaned_tasks()
                
                # Check for stuck tasks
                await self.check_stuck_tasks()
                
            except Exception as e:
                print(f"❌ Sentinel error: {e}")
            
            await asyncio.sleep(self.poll_interval)
        
        print("🛑 Sentinel stopped")
    
    def stop(self):
        """Stop the sentinel loop"""
        self.running = False


# Singleton sentinel
sentinel = Sentinel()
