"""
Agent OS - FastAPI Main Application
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio

from app.database import database
from app.api import jobs, tasks, agents
from app.api import system
from app.api.system import start_workers
from app.core.scheduler import scheduler
from app.agents.sentinel import sentinel


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    await database.connect()
    print("🚀 Agent OS started")
    
    # Auto-start scheduler and sentinel
    asyncio.create_task(scheduler.run_loop())
    asyncio.create_task(sentinel.run_loop())
    
    # Start workers for registered agents
    await start_workers(database)
    
    yield
    
    # Shutdown
    scheduler.stop()
    sentinel.stop()
    await database.disconnect()
    print("👋 Agent OS stopped")


app = FastAPI(
    title="Agent OS",
    description="A MongoDB-backed control plane for durable, multi-agent workflows",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])
app.include_router(system.router, prefix="/api/system", tags=["System"])


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "name": "Agent OS",
        "status": "running",
        "description": "Control plane for durable, multi-agent workflows"
    }


@app.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "database": "connected",
        "scheduler_running": scheduler.running,
        "sentinel_running": sentinel.running
    }
