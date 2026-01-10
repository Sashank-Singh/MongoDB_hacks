"""
Worker Runner - Background process that executes tasks
"""
import asyncio
from datetime import datetime
from typing import Optional

from app.database import database
from app.models import Task, TaskStatus, Agent, AgentStatus, AgentRole, Event, EventType
from app.agents.executor import create_agent
from app.core.recovery import recovery_manager


class Worker:
    """
    A Worker is a background process that:
    1. Registers itself as an agent
    2. Polls for assigned tasks
    3. Executes tasks
    4. Sends heartbeats
    5. Handles failures with recovery
    """
    
    def __init__(self, name: str, role: AgentRole):
        self.name = name
        self.role = role
        self.agent_id: Optional[str] = None
        self.running = False
        self.heartbeat_interval = 15  # seconds
        self.poll_interval = 2  # seconds
    
    async def register(self) -> str:
        """Register this worker as an agent in the database"""
        agent = Agent(
            name=self.name,
            role=self.role,
            skills=[self.role.value],
            status=AgentStatus.IDLE
        )
        
        await database.agents.insert_one(agent.to_mongo())
        self.agent_id = agent.id
        
        # Log registration
        event = Event(
            agent_id=agent.id,
            type=EventType.AGENT_REGISTERED,
            message=f"Worker {self.name} registered as {self.role.value}"
        )
        await database.events.insert_one(event.to_mongo())
        
        print(f"✅ Worker registered: {self.name} (ID: {self.agent_id})")
        return self.agent_id
    
    async def send_heartbeat(self):
        """Send heartbeat to indicate worker is alive"""
        if not self.agent_id:
            return
        
        await database.agents.update_one(
            {"_id": self.agent_id},
            {"$set": {"last_heartbeat": datetime.utcnow()}}
        )
    
    async def heartbeat_loop(self):
        """Background task to send periodic heartbeats"""
        while self.running:
            await self.send_heartbeat()
            await asyncio.sleep(self.heartbeat_interval)
    
    async def get_assigned_task(self) -> Optional[Task]:
        """Check if we have an assigned task"""
        task_doc = await database.tasks.find_one({
            "assigned_agent": self.agent_id,
            "status": TaskStatus.RUNNING.value
        })
        
        if task_doc:
            return Task.from_mongo(task_doc)
        return None
    
    async def execute_task(self, task: Task):
        """Execute a task"""
        print(f"📋 Executing task: {task.name}")
        
        # Create the appropriate agent executor
        executor = create_agent(self.agent_id, self.role, self.name)
        
        # Run the task
        result = await executor.run_task(task)
        
        if result.success:
            print(f"✅ Task completed: {task.name}")
        else:
            print(f"❌ Task failed: {task.name} - {result.error}")
            
            # Trigger recovery
            recovery_result = await recovery_manager.execute_recovery(task.id)
            print(f"🔄 Recovery: {recovery_result}")
        
        # Mark worker as idle
        await database.agents.update_one(
            {"_id": self.agent_id},
            {
                "$set": {
                    "status": AgentStatus.IDLE.value,
                    "current_task_id": None
                }
            }
        )
    
    async def run_loop(self):
        """Main worker loop"""
        if not self.agent_id:
            await self.register()
        
        self.running = True
        
        # Start heartbeat in background
        heartbeat_task = asyncio.create_task(self.heartbeat_loop())
        
        print(f"🔄 Worker {self.name} started - polling for tasks")
        
        try:
            while self.running:
                # Check for assigned task
                task = await self.get_assigned_task()
                
                if task:
                    await self.execute_task(task)
                
                await asyncio.sleep(self.poll_interval)
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
        
        print(f"🛑 Worker {self.name} stopped")
    
    def stop(self):
        """Stop the worker"""
        self.running = False


async def run_worker(name: str, role: AgentRole):
    """Convenience function to run a worker"""
    worker = Worker(name, role)
    await worker.run_loop()
