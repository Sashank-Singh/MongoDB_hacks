'use client';

import { useState, useEffect, useRef, useCallback, useMemo, memo } from 'react';
import ReactMarkdown from 'react-markdown';

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

// Memoized Icons
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
};

// Agent initials map
const AGENT_INITIALS: Record<string, string> = {
    planner: 'P',
    researcher: 'R',
    writer: 'W',
    coder: 'C',
    sentinel: 'S',
    data_builder: 'D',
};

const getAgentInitial = (role: string) => AGENT_INITIALS[role] || role[0]?.toUpperCase() || '?';

// Memoized Status Icon Component
const StatusIcon = memo(({ status }: { status: string }) => {
    switch (status) {
        case 'completed': return <span style={{ color: 'var(--accent-success)' }}>✓</span>;
        case 'running': return <span style={{ color: 'var(--accent-warning)' }}>◐</span>;
        case 'failed': return <span style={{ color: 'var(--accent-error)' }}>✕</span>;
        default: return <span style={{ color: 'var(--text-tertiary)' }}>○</span>;
    }
});
StatusIcon.displayName = 'StatusIcon';

// Memoized Agent Card Component
const AgentCard = memo(({ agent }: { agent: Agent }) => (
    <div className="agent-card">
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
));
AgentCard.displayName = 'AgentCard';

// Memoized Task Node Component
const TaskNode = memo(({ task, showConnector }: { task: Task; showConnector: boolean }) => (
    <div>
        {showConnector && <div className="dag-connector" />}
        <div className="dag-node">
            <div className={`dag-node-icon ${task.status}`}>
                <StatusIcon status={task.status} />
            </div>
            <span style={{ flex: 1 }}>{task.name.replace(/_/g, ' ')}</span>
            <span className={`task-badge ${task.status}`}>{task.status}</span>
        </div>
    </div>
));
TaskNode.displayName = 'TaskNode';

// Memoized Message Component
const MessageItem = memo(({ message, tasks, currentJobStatus }: { 
    message: Message; 
    tasks: Task[];
    currentJobStatus?: string;
}) => {
    const avatarStyle = useMemo(() => {
        if (message.agentRole) return {};
        if (message.type === 'user') return { background: 'linear-gradient(135deg, #0ea5e9, #0284c7)' };
        return { background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' };
    }, [message.agentRole, message.type]);

    const timeString = useMemo(() => 
        message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        [message.timestamp]
    );

    return (
        <div className={`message ${message.type}`}>
            <div
                className={`message-avatar ${message.type} ${message.agentRole || ''}`}
                style={avatarStyle}
            >
                {message.type === 'user' ? 'U' : message.agentRole ? getAgentInitial(message.agentRole) : 'OS'}
            </div>
            <div className="message-content">
                <div className="message-header">
                    <span className="message-sender">{message.sender}</span>
                    <span className="message-time">{timeString}</span>
                </div>
                <div className="message-text markdown-content">
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                </div>

                {message.tasks && message.tasks.length > 0 && (
                    <div className="task-card">
                        <div className="task-card-header">
                            <span className="task-card-title">Task Execution Plan</span>
                            <span className={`task-badge ${currentJobStatus || 'pending'}`}>
                                {currentJobStatus || 'pending'}
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
                                                <StatusIcon status={status} />
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
    );
});
MessageItem.displayName = 'MessageItem';

// Memoized Event Item Component
const EventItem = memo(({ event }: { event: Event }) => {
    const iconType = useMemo(() => {
        if (event.type.includes('FAILED')) return 'error';
        if (event.type.includes('COMPLETED')) return 'success';
        return 'info';
    }, [event.type]);

    const iconChar = useMemo(() => {
        if (event.type.includes('FAILED')) return '!';
        if (event.type.includes('COMPLETED')) return '✓';
        return 'i';
    }, [event.type]);

    const timeString = useMemo(() => 
        new Date(event.timestamp).toLocaleTimeString(),
        [event.timestamp]
    );

    return (
        <div className="event-item">
            <div className={`event-icon ${iconType}`}>{iconChar}</div>
            <div className="event-content">
                <div className="event-title">{event.message}</div>
                <div className="event-time">{timeString}</div>
            </div>
        </div>
    );
});
EventItem.displayName = 'EventItem';

export default function Home() {
    const [theme, setTheme] = useState<'light' | 'dark'>('dark');
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [agents, setAgents] = useState<Agent[]>([]);
    const [currentJob, setCurrentJob] = useState<Job | null>(null);
    const [tasks, setTasks] = useState<Task[]>([]);
    const [events, setEvents] = useState<Event[]>([]);
    const [jobDoneProcessed, setJobDoneProcessed] = useState(false);
    
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const agentsRef = useRef<Agent[]>([]);
    
    // Keep agents ref updated for use in polling
    useEffect(() => {
        agentsRef.current = agents;
    }, [agents]);

    // Theme toggle - optimized
    useEffect(() => {
        document.documentElement.setAttribute('data-theme', theme);
    }, [theme]);

    // Auto-scroll - debounced
    useEffect(() => {
        const timer = setTimeout(() => {
            messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }, 50);
        return () => clearTimeout(timer);
    }, [messages.length]);

    // Initial setup
    useEffect(() => {
        setMessages([{
            id: '1',
            type: 'system',
            sender: 'Agent OS',
            content: 'Welcome to Agent OS! I coordinate multiple AI agents to accomplish complex tasks. Enter your goal below and I\'ll break it down into tasks, assign them to specialized agents, and execute them with full observability.',
            timestamp: new Date(),
        }]);

        // Initial agent fetch
        fetch('/api/agents')
            .then(res => res.json())
            .then(data => setAgents(data))
            .catch(err => console.error('Failed to load agents:', err));
    }, []);

    // Optimized polling - batched requests with longer interval
    useEffect(() => {
        // Keep polling while job exists and is running OR just completed (to show results)
        if (!currentJob || (currentJob.status !== 'running' && currentJob.status !== 'done')) return;
        
        // If already processed completion, stop polling
        if (currentJob.status === 'done' && jobDoneProcessed) return;

        const controller = new AbortController();
        
        const poll = async () => {
            try {
                // Parallel fetch for better performance
                const [jobRes, eventsRes, agentsRes] = await Promise.all([
                    fetch(`/api/jobs/${currentJob.id}`, { signal: controller.signal }),
                    fetch(`/api/jobs/${currentJob.id}/events?limit=10`, { signal: controller.signal }),
                    fetch('/api/agents', { signal: controller.signal })
                ]);

                if (!jobRes.ok) return;
                
                const data = await jobRes.json();
                
                // Batch state updates
                setTasks(data.tasks || []);

                if (eventsRes.ok) {
                    const eventsData = await eventsRes.json();
                    setEvents(eventsData);
                }

                if (agentsRes.ok) {
                    const agentsData = await agentsRes.json();
                    setAgents(agentsData);
                }

                // Handle job completion - show final output
                if (data.job.status === 'done' && !jobDoneProcessed) {
                    setJobDoneProcessed(true);
                    
                    const completedTasks = data.tasks || [];
                    
                    // Build final output from all completed tasks
                    const outputs: string[] = [];
                    completedTasks.forEach((t: Task) => {
                        if (t.outputs) {
                            if (t.outputs.content) {
                                outputs.push(`### 📋 ${t.name.replace(/_/g, ' ')}\n\n${t.outputs.content}`);
                            } else if (t.outputs.code) {
                                outputs.push(`### 💻 ${t.name.replace(/_/g, ' ')}\n\n\`\`\`${t.outputs.language || ''}\n${t.outputs.code}\n\`\`\``);
                            } else if (t.outputs.data) {
                                outputs.push(`### 📊 ${t.name.replace(/_/g, ' ')}\n\n${JSON.stringify(t.outputs.data, null, 2)}`);
                            }
                        }
                    });

                    const finalOutput = outputs.length > 0 
                        ? outputs.join('\n\n---\n\n')
                        : 'All tasks completed successfully!';

                    // Add completion message with results
                    setMessages(prev => [...prev, {
                        id: Date.now().toString(),
                        type: 'agent',
                        sender: 'Agent OS',
                        agentRole: 'sentinel',
                        content: `## 🏁 Job Complete!\n\n${finalOutput}`,
                        timestamp: new Date(),
                    }]);
                    
                    // Update job status last
                    setCurrentJob(data.job);
                } else {
                    // Update job status for running jobs
                    setCurrentJob(data.job);
                }
            } catch (error) {
                if ((error as Error).name !== 'AbortError') {
                    console.log('Polling error:', error);
                }
            }
        };

        // Initial poll
        poll();
        
        // Poll every 1.5 seconds
        const interval = setInterval(poll, 1500);

        return () => {
            controller.abort();
            clearInterval(interval);
        };
    }, [currentJob?.id, currentJob?.status, jobDoneProcessed]);

    // Memoized submit handler
    const handleSubmit = useCallback(async () => {
        if (!input.trim() || isLoading) return;

        const userMessage: Message = {
            id: Date.now().toString(),
            type: 'user',
            sender: 'You',
            content: input,
            timestamp: new Date(),
        };

        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setIsLoading(true);
        setJobDoneProcessed(false);
        setTasks([]);
        setEvents([]);

        try {
            // Reset system before starting new job (clears old tasks, resets agents)
            await fetch('/api/system/reset', { method: 'POST' });
            
            // Refresh agents after reset
            const agentsRes = await fetch('/api/agents/');
            if (agentsRes.ok) {
                const agentsData = await agentsRes.json();
                setAgents(agentsData);
            }

            const response = await fetch('/api/jobs/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ goal: input }),
            });

            if (response.ok) {
                const data = await response.json();
                setCurrentJob(data.job);
                setTasks(data.tasks || []);

                setMessages(prev => [...prev, {
                    id: (Date.now() + 1).toString(),
                    type: 'agent',
                    sender: 'Planner',
                    agentRole: 'planner',
                    content: `I've analyzed your goal and created a task plan with ${data.tasks?.length || 0} steps. Here's the execution plan:`,
                    timestamp: new Date(),
                    tasks: data.tasks,
                }]);

                // Start the job
                await fetch(`/api/jobs/${data.job.id}/start`, { method: 'POST' });
                setCurrentJob(prev => prev ? { ...prev, status: 'running' } : null);

                setMessages(prev => [...prev, {
                    id: (Date.now() + 2).toString(),
                    type: 'system',
                    sender: 'Agent OS',
                    content: 'Job started! Agents are now executing tasks. Watch the progress in the panel on the right.',
                    timestamp: new Date(),
                }]);
            } else {
                throw new Error('Failed to create job');
            }
        } catch (error) {
            // Demo fallback
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

            setMessages(prev => [...prev, {
                id: (Date.now() + 1).toString(),
                type: 'agent',
                sender: 'Planner',
                agentRole: 'planner',
                content: `I've analyzed your goal and created a task plan with 4 steps:`,
                timestamp: new Date(),
                tasks: mockTasks,
            }]);
        }

        setIsLoading(false);
    }, [input, isLoading]);

    // Keyboard handler
    const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    }, [handleSubmit]);

    // Pause/Resume handler
    const handlePauseResume = useCallback(async () => {
        if (!currentJob) return;

        if (currentJob.status === 'running') {
            await fetch(`/api/jobs/${currentJob.id}/pause`, { method: 'POST' });
            setCurrentJob(prev => prev ? { ...prev, status: 'paused' } : null);
        } else if (currentJob.status === 'paused') {
            await fetch(`/api/jobs/${currentJob.id}/resume`, { method: 'POST' });
            setCurrentJob(prev => prev ? { ...prev, status: 'running' } : null);
        }
    }, [currentJob]);

    // Theme toggle handler
    const toggleTheme = useCallback(() => {
        setTheme(t => t === 'dark' ? 'light' : 'dark');
    }, []);

    // Memoized values
    const headerTitle = useMemo(() => 
        currentJob ? `Job: ${currentJob.goal.slice(0, 50)}...` : 'Multi-Agent Workflow',
        [currentJob?.goal]
    );

    const displayedEvents = useMemo(() => events.slice(0, 5), [events]);

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
                    {agents.map(agent => (
                        <AgentCard key={agent.id} agent={agent} />
                    ))}
                </div>
            </aside>

            {/* Main Chat Area */}
            <main className="main-content">
                <header className="header">
                    <h1 className="header-title">{headerTitle}</h1>
                    <div className="header-actions">
                        <button
                            className="theme-toggle"
                            onClick={toggleTheme}
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
                            messages.map(message => (
                                <MessageItem 
                                    key={message.id} 
                                    message={message} 
                                    tasks={tasks}
                                    currentJobStatus={currentJob?.status}
                                />
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
                        {currentJob ? `Status: ${currentJob.status}` : 'No active job'}
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
                                <TaskNode key={task.id} task={task} showConnector={index > 0} />
                            ))}
                        </div>
                    ) : (
                        <p style={{ color: 'var(--text-tertiary)', fontSize: '13px', marginBottom: '24px' }}>
                            Submit a goal to see task progress
                        </p>
                    )}

                    <div className="section-title">Recent Events</div>
                    <div className="event-timeline">
                        {displayedEvents.length > 0 ? (
                            displayedEvents.map(event => (
                                <EventItem key={event.id} event={event} />
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
