# Agent OS Backend

A MongoDB-backed control plane for durable, multi-agent workflows.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your MongoDB Atlas connection string and OpenAI API key

# Run the server
python run.py
```

## Architecture

- **Planner Agent**: Converts user goals into task DAGs
- **Scheduler**: Assigns runnable tasks to available agents
- **Recovery Logic**: Handles failures with retry/reassign/escalate strategies
- **State Machine**: Enforces deterministic task transitions
