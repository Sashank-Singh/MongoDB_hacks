import streamlit as st
import httpx
import asyncio
import pandas as pd
from datetime import datetime
import json

# Configuration
BACKEND_URL = "http://localhost:8000"

st.set_page_config(
    page_title="Agent OS - Analysis Chat",
    page_icon="🤖",
    layout="wide",
)

# --- Helper Functions ---

async def api_call(method, endpoint, params=None, json_data=None):
    async with httpx.AsyncClient() as client:
        try:
            url = f"{BACKEND_URL}{endpoint}"
            if method == "GET":
                response = await client.get(url, params=params)
            else:
                response = await client.post(url, params=params, json=json_data)
            
            if response.status_code >= 400:
                return {"error": f"API Error {response.status_code}: {response.text}"}
            return response.json()
        except Exception as e:
            return {"error": str(e)}

# --- UI Components ---

st.title("🤖 Agent OS - Analysis Chat")

# Sidebar for Setup & Health
with st.sidebar:
    st.header("⚙️ System Control")
    
    # Detailed Health
    health = asyncio.run(api_call("GET", "/api/system/health/full"))
    if "error" not in health:
        st.success("🟢 Backend Connected")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Scheduler:**")
            st.write("✅" if health.get("scheduler_running") else "❌")
            st.write("**Sentinel:**")
            st.write("✅" if health.get("sentinel_running") else "❌")
        with col2:
            st.write("**Workers:**")
            st.write(f"🏃 {health.get('active_workers', 0)}")
            
        if not (health.get("scheduler_running") and health.get("sentinel_running") and health.get("active_workers", 0) > 0):
            if st.button("🚀 Start Orchestration", use_container_width=True):
                with st.spinner("Starting loops..."):
                    asyncio.run(api_call("POST", "/api/system/scheduler/start"))
                    asyncio.run(api_call("POST", "/api/system/sentinel/start"))
                    asyncio.run(api_call("POST", "/api/system/workers/start"))
                st.rerun()
    else:
        st.error(f"🔴 Backend Offline: {health.get('error', 'Unknown error')}")
    
    st.divider()
    
    # Quick Agent Setup
    st.subheader("👥 Agent Workers")
    agents = asyncio.run(api_call("GET", "/api/agents/"))
    if isinstance(agents, list):
        st.info(f"{len(agents)} agents registered")
    
    if st.button("🚀 Seed Default Agents", use_container_width=True):
        default_agents = [
            {"name": "Alice", "role": "researcher", "skills": ["web_search", "competitor_analysis"]},
            {"name": "Bob", "role": "writer", "skills": ["report_writing", "summarization"]},
            {"name": "Charlie", "role": "coder", "skills": ["python", "data_processing"]},
            {"name": "Dave", "role": "data_builder", "skills": ["scraping", "table_generation"]}
        ]
        for a in default_agents:
            asyncio.run(api_call("POST", "/api/agents/register", params={"name": a["name"], "role": a["role"]}, json_data=a["skills"]))
        # Also start workers for them
        asyncio.run(api_call("POST", "/api/system/workers/start"))
        st.success("Default agents registered and workers started!")
        st.rerun()

# Tabs for Main Interface
tab_chat, tab_jobs, tab_agents = st.tabs(["💬 Analysis Chat", "📊 Active Jobs", "👷 Agent Management"])

# --- Analysis Chat Tab ---
with tab_chat:
    st.header("Start a New Analysis")
    st.write("Enter an objective (e.g., 'Competitor analysis on MongoDB vs Pinecone')")
    
    # Current Job Status from session state if any
    goal = st.chat_input("Tell Agent OS what you want to analyze...")
    
    if goal:
        with st.spinner("Decomposing goal into tasks..."):
            res = asyncio.run(api_call("POST", "/api/jobs/", json_data={"goal": goal}))
            
            if "error" in res:
                st.error(f"Failed to create job: {res['error']}")
            else:
                job_data = res.get("job", {})
                job_id = job_data.get("_id") or job_data.get("id")
                st.success(f"Job created! ID: {job_id}")
                
                # Show Decomposition
                st.subheader("📋 Task Decomposition Plan")
                tasks = res.get("tasks", [])
                for t in tasks:
                    with st.expander(f"Task: {t['name']}"):
                        st.write(f"**Description:** {t['description']}")
                        st.write(f"**Required Skill:** {t['required_skill']}")
                        st.write(f"**Status:** {t['status']}")
                
                if st.button("▶️ Start Execution", key=f"start_new_{job_id}"):
                    asyncio.run(api_call("POST", f"/api/jobs/{job_id}/start"))
                    st.info("Job started!")
                    st.rerun()

# --- Active Jobs Tab ---
with tab_jobs:
    st.header("Job Control Center")
    all_jobs = asyncio.run(api_call("GET", "/api/jobs/"))
    
    if isinstance(all_jobs, list) and len(all_jobs) > 0:
        for job in all_jobs:
            job_id = job.get("_id") or job.get("id")
            with st.expander(f"Job: {job['goal']} ({job['status']})", expanded=(job['status'] == 'running')):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**ID:** {job_id}")
                    st.write(f"**Created:** {job['created_at']}")
                with col2:
                    if job['status'] == "queued":
                        if st.button("▶️ Start", key=f"start_{job_id}"):
                            asyncio.run(api_call("POST", f"/api/jobs/{job_id}/start"))
                            st.rerun()
                    elif job['status'] == "running":
                        if st.button("⏸️ Pause", key=f"pause_{job_id}"):
                            asyncio.run(api_call("POST", f"/api/jobs/{job_id}/pause"))
                            st.rerun()
                    elif job['status'] == "paused":
                        if st.button("▶️ Resume", key=f"resume_{job_id}"):
                            asyncio.run(api_call("POST", f"/api/jobs/{job_id}/resume"))
                            st.rerun()
                
                # Fetch Tasks for this Job
                tasks = asyncio.run(api_call("GET", "/api/tasks/", params={"job_id": job_id}))
                if isinstance(tasks, list):
                    st.divider()
                    st.subheader("Tasks Progress")
                    for t in tasks:
                        status_icon = "⏳" if t['status'] == "pending" else "⚙️" if t['status'] == "running" else "✅" if t['status'] == "completed" else "❌"
                        st.write(f"{status_icon} **{t['name']}**: {t['status']}")
                        if t.get('checkpoint'):
                            st.caption(f"🏁 {t['checkpoint']}")
    else:
        st.info("No active jobs found.")

# --- Agent Management Tab ---
with tab_agents:
    st.header("Worker Registry")
    if isinstance(agents, list):
        if len(agents) > 0:
            df = pd.DataFrame(agents)
            st.dataframe(df)
        else:
            st.warning("No agents registered. Use 'Seed Default Agents' in the sidebar.")
    else:
        st.error("Could not fetch agents.")
