
import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient

# Load env variables
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = "agent_os" 

if not MONGODB_URI:
    print("❌ MONGODB_URI not found in environment")
    sys.exit(1)

def reset_agents():
    print("🔄 Connecting to MongoDB...")
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    
    # Clear existing agents
    print("🗑️ Clearing existing agents...")
    result = db.agents.delete_many({})
    print(f"   Deleted {result.deleted_count} agents")
    
    # Define new agents with proper names
    new_agents = [
        {
            "name": "Planner",
            "role": "planner",
            "skills": ["planning", "coordination"],
            "status": "idle",
            "last_heartbeat": datetime.utcnow(),
            "created_at": datetime.utcnow()
        },
        {
            "name": "Research Agent",
            "role": "researcher",
            "skills": ["research", "search", "reading"],
            "status": "idle",
            "last_heartbeat": datetime.utcnow(),
            "created_at": datetime.utcnow()
        },
        {
            "name": "Writer Agent",
            "role": "writer",
            "skills": ["writing", "editing", "blogging"],
            "status": "idle",
            "last_heartbeat": datetime.utcnow(),
            "created_at": datetime.utcnow()
        },
        {
            "name": "Coder Agent",
            "role": "coder",
            "skills": ["python", "javascript", "debugging"],
            "status": "idle",
            "last_heartbeat": datetime.utcnow(),
            "created_at": datetime.utcnow()
        },
        {
            "name": "Data Analyst",
            "role": "data_builder",
            "skills": ["analysis", "csv", "data-processing"],
            "status": "idle",
            "last_heartbeat": datetime.utcnow(),
            "created_at": datetime.utcnow()
        },
        {
            "name": "Sentinel",
            "role": "sentinel",
            "skills": ["monitoring", "recovery"],
            "status": "idle",
            "last_heartbeat": datetime.utcnow(),
            "created_at": datetime.utcnow()
        }
    ]
    
    # Insert new agents
    print("🌱 Seeding new agents...")
    db.agents.insert_many(new_agents)
    
    print("✅ Successfully reset agents:")
    for agent in new_agents:
        print(f"   - {agent['name']} ({agent['role']})")

if __name__ == "__main__":
    reset_agents()
