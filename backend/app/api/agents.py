"""
Agents API Router
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends

from app.database import database, get_database, Database
from app.models import Agent, AgentStatus, AgentRole, Event, EventType

router = APIRouter()


@router.post("/register")
async def register_agent(
    name: str,
    role: AgentRole,
    skills: List[str] = [],
    db: Database = Depends(get_database)
):
    """Register a new agent worker"""
    agent = Agent(
        name=name,
        role=role,
        skills=skills,
        status=AgentStatus.IDLE
    )
    
    await db.agents.insert_one(agent.to_mongo())
    
    # Log event
    event = Event(
        agent_id=agent.id,
        type=EventType.AGENT_REGISTERED,
        message=f"Agent {name} registered with role {role.value}"
    )
    await db.events.insert_one(event.to_mongo())
    
    return {"message": "Agent registered", "agent": agent.model_dump()}


@router.get("/", response_model=List[dict])
async def list_agents(
    status: Optional[AgentStatus] = None,
    role: Optional[AgentRole] = None,
    db: Database = Depends(get_database)
):
    """List all registered agents"""
    query = {}
    if status:
        query["status"] = status.value
    if role:
        query["role"] = role.value
    
    cursor = db.agents.find(query)
    agents = await cursor.to_list(length=100)
    return [Agent.from_mongo(a).model_dump() for a in agents]


@router.get("/{agent_id}")
async def get_agent(agent_id: str, db: Database = Depends(get_database)):
    """Get agent by ID"""
    agent_doc = await db.agents.find_one({"_id": agent_id})
    if not agent_doc:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return Agent.from_mongo(agent_doc).model_dump()


@router.post("/{agent_id}/heartbeat")
async def agent_heartbeat(agent_id: str, db: Database = Depends(get_database)):
    """Update agent heartbeat (called periodically by agent workers)"""
    result = await db.agents.find_one_and_update(
        {"_id": agent_id},
        {"$set": {"last_heartbeat": datetime.utcnow()}},
        return_document=True
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.get("/idle", response_model=List[dict])
async def get_idle_agents(
    skill: Optional[str] = None,
    db: Database = Depends(get_database)
):
    """Get all idle agents, optionally filtered by skill"""
    query = {"status": AgentStatus.IDLE.value}
    if skill:
        query["$or"] = [
            {"skills": skill},
            {"role": skill}
        ]
    
    cursor = db.agents.find(query)
    agents = await cursor.to_list(length=100)
    return [Agent.from_mongo(a).model_dump() for a in agents]
