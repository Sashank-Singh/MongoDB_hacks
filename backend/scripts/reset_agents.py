
import asyncio
import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId

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
    
    # Also clear stuck tasks
    print("🗑️ Clearing stuck/running tasks...")
    result = db.tasks.update_many(
        {"status": {"$in": ["running", "failed"]}},
        {"$set": {"status": "pending", "assigned_agent": None, "error": None}}
    )
    print(f"   Reset {result.modified_count} tasks")
    
    now = datetime.now(timezone.utc)
    
    # Define new agents with STRING IDs (critical for matching)
    new_agents = [
        {
            "_id": str(ObjectId()),  # String ID for compatibility
            "name": "Planner",
            "role": "planner",
            "skills": ["planning", "coordination"],
            "status": "idle",
            "last_heartbeat": now,
            "created_at": now
        },
        {
            "_id": str(ObjectId()),
            "name": "Research Agent",
            "role": "researcher",
            "skills": ["research", "search", "reading"],
            "status": "idle",
            "last_heartbeat": now,
            "created_at": now
        },
        {
            "_id": str(ObjectId()),
            "name": "Writer Agent",
            "role": "writer",
            "skills": ["writing", "editing", "blogging"],
            "status": "idle",
            "last_heartbeat": now,
            "created_at": now
        },
        {
            "_id": str(ObjectId()),
            "name": "Coder Agent",
            "role": "coder",
            "skills": ["python", "javascript", "debugging"],
            "status": "idle",
            "last_heartbeat": now,
            "created_at": now
        },
        {
            "_id": str(ObjectId()),
            "name": "Data Analyst",
            "role": "data_builder",
            "skills": ["analysis", "csv", "data-processing"],
            "status": "idle",
            "last_heartbeat": now,
            "created_at": now
        },
        {
            "_id": str(ObjectId()),
            "name": "Sentinel",
            "role": "sentinel",
            "skills": ["monitoring", "recovery"],
            "status": "idle",
            "last_heartbeat": now,
            "created_at": now
        }
    ]
    
    # Insert new agents
    print("🌱 Seeding new agents...")
    db.agents.insert_many(new_agents)
    
    print("✅ Successfully reset agents:")
    for agent in new_agents:
        print(f"   - {agent['name']} ({agent['role']}) ID: {agent['_id']}")

if __name__ == "__main__":
    reset_agents()
