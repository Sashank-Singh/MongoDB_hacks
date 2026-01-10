'use client';

import { useState, useEffect, useRef } from 'react';

// Types
interface Agent {
    id: string;
    name: string;
    role: string;
    status: 'idle' | 'busy' | 'dead';
    current_task_id?: string;
}

interface Task {
    id: string;
    name: string;
    description: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    assigned_agent?: string;
    depends_on: string[];
    outputs?: Record<string, any>;
    checkpoint?: string;
}

interface Job {
    id: string;
    goal: string;
    status: 'queued' | 'running' | 'paused' | 'done' | 'failed';
    created_at: string;
}

interface Message {
    id: string;
    type: 'user' | 'system' | 'agent';
    sender: string;
    content: string;
    timestamp: Date;
    agentRole?: string;
    tasks?: Task[];
}

interface Event {
    id: string;
    type: string;
    message: string;
    timestamp: string;
}

// Icons as simple SVG
const Icons = {
    send: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
        </svg>
    ),
    sun: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="5" />
            <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
        </svg>
    ),
    moon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
    ),
    play: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <polygon points="5 3 19 12 5 21 5 3" />
        </svg>
    ),
    pause: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="4" width="4" height="16" />
            <rect x="14" y="4" width="4" height="16" />
        </svg>
    ),
    refresh: (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M23 4v6h-6M1 20v-6h6M20.49 9A9 9 0 0 0 5.64 5.64L1 10M23 14l-4.64 4.36A9 9 0 0 1 3.51 15" />
        </svg>
    ),
    check: '✓',
    pending: '○',
    running: '◐',
    failed: '✕',
};

// Agent role colors
const getAgentInitial = (role: string) => {
    const initials: Record<string, string> = {
        planner: 'P',
        researcher: 'R',
        writer: 'W',
        coder: 'C',
        sentinel: 'S',
        data_builder: 'D',
    };
    return initials[role] || role[0]?.toUpperCase() || '?';
};

export default function Home() {
    const [theme, setTheme] = useState<'light' | 'dark'>('dark');
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [agents, setAgents] = useState<Agent[]>([]);
    const [currentJob, setCurrentJob] = useState<Job | null>(null);
    const [tasks, setTasks] = useState<Task[]>([]);
    const [events, setEvents] = useState<Event[]>([]);
    const [stream, setStream] = useState<Array<{
        id: string;
        agent: string;
        role: string;
        message: string;
        timestamp: Date;
        type: string;
    }>>([]);
    const [jobDoneProcessed, setJobDoneProcessed] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);

    // Theme toggle
    useEffect(() => {
        document.documentElement.setAttribute('data-theme', theme);
    }, [theme]);

    // Auto-scroll messages
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    // Initial welcome message
    useEffect(() => {
        setMessages([
            {
                id: '1',
                type: 'system',
                sender: 'Agent OS',
                content: 'Welcome to Agent OS! I coordinate multiple AI agents to accomplish complex tasks. Enter your goal below and I\'ll break it down into tasks, assign them to specialized agents, and execute them with full observability.',
                timestamp: new Date(),
            },
        ]);

        // Initial agent fetch
        fetch('/api/agents')
            .then(res => res.json())
            .then(data => setAgents(data))
            .catch(err => console.error('Failed to load agents:', err));
    }, []);

    // Polling for updates when job is running
    useEffect(() => {
        if (!currentJob || currentJob.status !== 'running') return;

        const interval = setInterval(async () => {
            try {
                // Fetch job status
                const jobRes = await fetch(`/api/jobs/${currentJob.id}`);
                let data: any = null;
                if (jobRes.ok) {
                    data = await jobRes.json();
                    setCurrentJob(data.job);
                    setTasks(data.tasks || []);
                }

                // Fetch events
                const eventsRes = await fetch(`/api/jobs/${currentJob.id}/events?limit=20`);
                if (eventsRes.ok) {
                    const eventsData = await eventsRes.json();
                    setEvents(eventsData);

                    // Add agent events to stream
                    eventsData.forEach((event: any) => {
                        // Only add if it has an agent_id and isn't already in stream (by ID)
                        if (event.agent_id) {
                            setStream(prev => {
                                if (prev.find(s => s.id === event.id)) return prev;

                                const agent = agents.find(a => a.id === event.agent_id);
                                if (!agent) return prev;

                                return [...prev, {
                                    id: event.id,
                                    agent: agent.name,
                                    role: agent.role,
                                    message: event.message,
                                    timestamp: new Date(event.timestamp),
                                    type: event.type.includes('failed') ? 'warning' : 'info'
                                }].sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
                            });
                        }
                    });
                }

                // Fetch agents real-time status
                const agentsRes = await fetch('/api/agents');
                if (agentsRes.ok) {
                    const agentsData = await agentsRes.json();
                    setAgents(agentsData);
                }

                if (data) {
                    // Check for job completion
                    if (data.job.status === 'done' && !jobDoneProcessed) {
                        setJobDoneProcessed(true);

                        // Allow time for last polling update to catch all tasks
                        setTimeout(() => {
                            const completedTasks = data.tasks || [];
                            const finalOutput = completedTasks
                                .filter((t: Task) => t.outputs && (t.outputs.content || t.outputs.code || t.outputs.data))
                                .map((t: Task) => {
                                    const out = t.outputs;
                                    if (!out) return '';
                                    if (out.content) return `### ${t.name}\n${out.content}`;
                                    if (out.code) return `### ${t.name}\n\`\`\`${out.language || ''}\n${out.code}\n\`\`\``;
                                    if (out.data) return `### ${t.name}\n${JSON.stringify(out.data, null, 2)}`;
                                    return '';
                                })
                                .join('\n\n');

                            const completionMessage: Message = {
                                id: Date.now().toString(),
                                type: 'agent',
                                sender: 'Agent OS',
                                agentRole: 'sentinel',
                                content: `## 🏁 Job Complete!\n\nHere are the results:\n\n${finalOutput || 'Tasks completed successfully.'}`,
                                timestamp: new Date(),
                            };
                            setMessages(prev => [...prev, completionMessage]);
                            setCurrentJob(prev => prev ? { ...prev, status: 'done' } : null);
                        }, 1000);
                    }

                    // Update stream from checkpoints
                    if (data.tasks) {
                        data.tasks.forEach((task: Task) => {
                            if (task.checkpoint && !stream.find(s => s.message === task.checkpoint)) {
                                const agent = agents.find(a => a.id === task.assigned_agent);
                                if (agent) {
                                    setStream(prev => [...prev, {
                                        id: Date.now() + Math.random().toString(),
                                        agent: agent.name,
                                        role: agent.role,
                                        message: task.checkpoint!,
                                        timestamp: new Date(),
                                        type: 'success'
                                    }]);
                                }
                            }
                        });
                    }
                }
            } catch (error) {
                console.log('Polling error:', error);
            }
        }, 1000);

        return () => clearInterval(interval);
    }, [currentJob]);

    const handleSubmit = async () => {
        if (!input.trim() || isLoading) return;

        const userMessage: Message = {
            id: Date.now().toString(),
            type: 'user',
            sender: 'You',
            content: input,
            timestamp: new Date(),
        };

        setMessages((prev) => [...prev, userMessage]);
        setInput('');
        setIsLoading(true);
        setJobDoneProcessed(false);
        setStream([]);

        try {
            // Create job via API
            const response = await fetch('/api/jobs/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ goal: input }),
            });

            if (response.ok) {
                const data = await response.json();
                setCurrentJob(data.job);
                setTasks(data.tasks || []);

                // Add system response with task DAG
                const plannerMessage: Message = {
                    id: (Date.now() + 1).toString(),
                    type: 'agent',
                    sender: 'Planner',
                    agentRole: 'planner',
                    content: `I've analyzed your goal and created a task plan with ${data.tasks?.length || 0} steps. Here's the execution plan:`,
                    timestamp: new Date(),
                    tasks: data.tasks,
                };

                setMessages((prev) => [...prev, plannerMessage]);

                // Update agent status
                setAgents((prev) =>
                    prev.map((a) =>
                        a.role === 'planner' ? { ...a, status: 'busy' as const } : a
                    )
                );

                // Start the job
                await fetch(`/api/jobs/${data.job.id}/start`, { method: 'POST' });
                setCurrentJob((prev) => prev ? { ...prev, status: 'running' } : null);

                // Add execution message
                setTimeout(() => {
                    setMessages((prev) => [
                        ...prev,
                        {
                            id: (Date.now() + 2).toString(),
                            type: 'system',
                            sender: 'Agent OS',
                            content: 'Job started! Agents are now executing tasks. Watch the progress in the panel on the right.',
                            timestamp: new Date(),
                        },
                    ]);
                }, 500);
            } else {
                throw new Error('Failed to create job');
            }
        } catch (error) {
            // Fallback for demo when backend is offline
            const mockTasks: Task[] = [
                { id: '1', name: 'research_topic', description: 'Research and gather information', status: 'completed', depends_on: [], assigned_agent: '2' },
                { id: '2', name: 'analyze_findings', description: 'Analyze the research findings', status: 'running', depends_on: ['1'], assigned_agent: '2' },
                { id: '3', name: 'write_report', description: 'Write the final report', status: 'pending', depends_on: ['2'] },
                { id: '4', name: 'final_review', description: 'Review and finalize', status: 'pending', depends_on: ['3'] },
            ];

            setTasks(mockTasks);
            setCurrentJob({
                id: 'demo-1',
                goal: input,
                status: 'running',
                created_at: new Date().toISOString(),
            });

            const plannerMessage: Message = {
                id: (Date.now() + 1).toString(),
                type: 'agent',
                sender: 'Planner',
                agentRole: 'planner',
                content: `I've analyzed your goal and created a task plan with 4 steps:`,
                timestamp: new Date(),
                tasks: mockTasks,
            };

            setMessages((prev) => [...prev, plannerMessage]);

            // Simulate agents working
            setAgents((prev) =>
                prev.map((a) =>
                    a.role === 'researcher' ? { ...a, status: 'busy' as const } : a
                )
            );

            // Simulate progress
            simulateProgress(mockTasks);
        }

        setIsLoading(false);
    };

    // Demo simulation
    const simulateProgress = (initialTasks: Task[]) => {
        let taskIndex = 1; // Start from second task

        const progressInterval = setInterval(() => {
            if (taskIndex >= initialTasks.length) {
                clearInterval(progressInterval);

                setMessages((prev) => [
                    ...prev,
                    {
                        id: Date.now().toString(),
                        type: 'agent',
                        sender: 'Writer Agent',
                        agentRole: 'writer',
                        content: 'All tasks completed successfully! Your goal has been achieved.',
                        timestamp: new Date(),
                    },
                ]);

                setCurrentJob((prev) => prev ? { ...prev, status: 'done' } : null);
                setAgents((prev) => prev.map((a) => ({ ...a, status: 'idle' as const })));
                return;
            }

            // Complete current task
            setTasks((prev) =>
                prev.map((t, i) => {
                    if (i === taskIndex) return { ...t, status: 'running' as const };
                    if (i === taskIndex - 1) return { ...t, status: 'completed' as const };
                    return t;
                })
            );

            // Add progress message
            const task = initialTasks[taskIndex];
            setMessages((prev) => [
                ...prev,
                {
                    id: Date.now().toString(),
                    type: 'agent',
                    sender: taskIndex === 1 ? 'Research Agent' : taskIndex === 2 ? 'Writer Agent' : 'Writer Agent',
                    agentRole: taskIndex === 1 ? 'researcher' : 'writer',
                    content: `Working on: ${task.description}`,
                    timestamp: new Date(),
                },
            ]);

            taskIndex++;
        }, 3000);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    };

    const handlePauseResume = async () => {
        if (!currentJob) return;

        if (currentJob.status === 'running') {
            await fetch(`/api/jobs/${currentJob.id}/pause`, { method: 'POST' });
            setCurrentJob((prev) => prev ? { ...prev, status: 'paused' } : null);
        } else if (currentJob.status === 'paused') {
            await fetch(`/api/jobs/${currentJob.id}/resume`, { method: 'POST' });
            setCurrentJob((prev) => prev ? { ...prev, status: 'running' } : null);
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'completed': return <span style={{ color: 'var(--accent-success)' }}>✓</span>;
            case 'running': return <span style={{ color: 'var(--accent-warning)' }}>◐</span>;
            case 'failed': return <span style={{ color: 'var(--accent-error)' }}>✕</span>;
            default: return <span style={{ color: 'var(--text-tertiary)' }}>○</span>;
        }
    };

    return (
        <div className="app-container">
            {/* Sidebar - Agents */}
            <aside className="sidebar">
                <div className="sidebar-header">
                    <div className="logo">
                        <div className="logo-icon">OS</div>
                        <span>Agent OS</span>
                    </div>
                </div>

                <div className="agents-section">
                    <div className="section-title">Active Agents ({agents.length})</div>
                    {agents.map((agent) => (
                        <div key={agent.id} className="agent-card">
                            <div className={`agent-avatar ${agent.role}`}>
                                {getAgentInitial(agent.role)}
                            </div>
                            <div className="agent-info">
                                <div className="agent-name">{agent.name}</div>
                                <div className="agent-status">
                                    <span className={`status-dot ${agent.status}`} />
                                    {agent.status.charAt(0).toUpperCase() + agent.status.slice(1)}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </aside>

            {/* Main Chat Area */}
            <main className="main-content">
                <header className="header">
                    <h1 className="header-title">
                        {currentJob ? `Job: ${currentJob.goal.slice(0, 50)}...` : 'Multi-Agent Workflow'}
                    </h1>
                    <div className="header-actions">
                        <button
                            className="theme-toggle"
                            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
                        >
                            {theme === 'dark' ? Icons.sun : Icons.moon}
                        </button>
                    </div>
                </header>

                <div className="chat-container">
                    <div className="chat-messages">
                        {messages.length === 0 ? (
                            <div className="empty-state">
                                <div className="empty-state-icon">🤖</div>
                                <h3 className="empty-state-title">Start a New Workflow</h3>
                                <p className="empty-state-text">
                                    Enter your goal below and Agent OS will break it down into tasks,
                                    assign them to specialized agents, and execute with full observability.
                                </p>
                            </div>
                        ) : (
                            messages.map((message) => (
                                <div key={message.id} className={`message ${message.type}`}>
                                    <div
                                        className={`message-avatar ${message.type} ${message.agentRole || ''}`}
                                        style={
                                            message.agentRole
                                                ? {}
                                                : message.type === 'user'
                                                    ? { background: 'linear-gradient(135deg, #0ea5e9, #0284c7)' }
                                                    : { background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }
                                        }
                                    >
                                        {message.type === 'user'
                                            ? 'U'
                                            : message.agentRole
                                                ? getAgentInitial(message.agentRole)
                                                : 'OS'}
                                    </div>
                                    <div className="message-content">
                                        <div className="message-header">
                                            <span className="message-sender">{message.sender}</span>
                                            <span className="message-time">
                                                {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                            </span>
                                        </div>
                                        <div className="message-text">{message.content}</div>

                                        {/* Task DAG visualization */}
                                        {message.tasks && message.tasks.length > 0 && (
                                            <div className="task-card">
                                                <div className="task-card-header">
                                                    <span className="task-card-title">Task Execution Plan</span>
                                                    <span className={`task-badge ${currentJob?.status || 'pending'}`}>
                                                        {currentJob?.status || 'pending'}
                                                    </span>
                                                </div>
                                                <div className="task-dag">
                                                    {message.tasks.map((task, index) => {
                                                        const currentTask = tasks.find((t) => t.id === task.id);
                                                        const status = currentTask?.status || task.status;
                                                        return (
                                                            <div key={task.id}>
                                                                {index > 0 && <div className="dag-connector" />}
                                                                <div className="dag-node">
                                                                    <div className={`dag-node-icon ${status}`}>
                                                                        {getStatusIcon(status)}
                                                                    </div>
                                                                    <span>{task.name.replace(/_/g, ' ')}</span>
                                                                </div>
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ))
                        )}

                        {isLoading && (
                            <div className="message agent">
                                <div className="message-avatar planner">P</div>
                                <div className="message-content">
                                    <div className="typing-indicator">
                                        <span />
                                        <span />
                                        <span />
                                    </div>
                                </div>
                            </div>
                        )}

                        <div ref={messagesEndRef} />
                    </div>

                    {/* Chat Input */}
                    <div className="chat-input-container">
                        <div className="chat-input-wrapper">
                            <textarea
                                ref={inputRef}
                                className="chat-input"
                                placeholder="Enter your goal... (e.g., 'Create a competitor analysis report')"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                rows={1}
                            />
                            <button
                                className="send-button"
                                onClick={handleSubmit}
                                disabled={!input.trim() || isLoading}
                            >
                                {Icons.send}
                            </button>
                        </div>
                    </div>
                </div>
            </main>

            {/* Right Panel - Job Details */}
            <aside className="right-panel">
                <div className="panel-header">
                    <h2 className="panel-title">Job Details</h2>
                    <p className="panel-subtitle">
                        {currentJob
                            ? `Status: ${currentJob.status}`
                            : 'No active job'}
                    </p>
                </div>

                {currentJob && (
                    <div className="job-controls">
                        <button
                            className={`control-button ${currentJob.status === 'running' ? '' : 'primary'}`}
                            onClick={handlePauseResume}
                            disabled={currentJob.status === 'done' || currentJob.status === 'failed'}
                        >
                            {currentJob.status === 'running' ? Icons.pause : Icons.play}
                            {currentJob.status === 'running' ? 'Pause' : 'Resume'}
                        </button>
                        <button className="control-button" title="Refresh">
                            {Icons.refresh}
                            Refresh
                        </button>
                    </div>
                )}

                <div className="panel-content">
                    <div className="section-title">Task Progress</div>
                    {tasks.length > 0 ? (
                        <div className="task-dag" style={{ marginBottom: '24px' }}>
                            {tasks.map((task, index) => (
                                <div key={task.id}>
                                    {index > 0 && <div className="dag-connector" />}
                                    <div className="dag-node">
                                        <div className={`dag-node-icon ${task.status}`}>
                                            {getStatusIcon(task.status)}
                                        </div>
                                        <span style={{ flex: 1 }}>{task.name.replace(/_/g, ' ')}</span>
                                        <span className={`task-badge ${task.status}`}>{task.status}</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p style={{ color: 'var(--text-tertiary)', fontSize: '13px', marginBottom: '24px' }}>
                            Submit a goal to see task progress
                        </p>
                    )}

                    <div className="section-title">Recent Events</div>
                    <div className="event-timeline">
                        {events.length > 0 ? (
                            events.slice(0, 5).map((event) => (
                                <div key={event.id} className="event-item">
                                    <div className={`event-icon ${event.type.includes('FAILED') ? 'error' : event.type.includes('COMPLETED') ? 'success' : 'info'}`}>
                                        {event.type.includes('FAILED') ? '!' : event.type.includes('COMPLETED') ? '✓' : 'i'}
                                    </div>
                                    <div className="event-content">
                                        <div className="event-title">{event.message}</div>
                                        <div className="event-time">
                                            {new Date(event.timestamp).toLocaleTimeString()}
                                        </div>
                                    </div>
                                </div>
                            ))
                        ) : (
                            <div className="event-item">
                                <div className="event-icon info">i</div>
                                <div className="event-content">
                                    <div className="event-title">Waiting for events...</div>
                                    <div className="event-time">Start a job to see activity</div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </aside>
        </div>
    );
}
