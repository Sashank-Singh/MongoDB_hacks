"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";

// Types
interface Agent {
    id: string;
    name: string;
    role: string;
  status: "idle" | "busy" | "dead";
    current_task_id?: string;
}

interface Task {
    id: string;
    name: string;
    description: string;
  status: "pending" | "running" | "completed" | "failed";
    assigned_agent?: string;
    depends_on: string[];
  outputs?: Record<string, unknown>;
}

interface Job {
    id: string;
    goal: string;
  status: "queued" | "running" | "paused" | "done" | "failed";
    created_at: string;
}

interface AgentEvent {
  id: string;
  type: string;
  message: string;
  timestamp: string;
  agent_id?: string;
  task_id?: string;
}

interface Message {
    id: string;
  type: "user" | "agent" | "system";
    sender: string;
    content: string;
    timestamp: Date;
    tasks?: Task[];
}

export default function Home() {
  const [input, setInput] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      type: "system",
      sender: "Agent OS",
      content: "Welcome to Agent OS! I coordinate multiple AI agents to accomplish complex tasks. Enter your goal below and I'll break it down into tasks, assign them to specialized agents, and execute them with full observability.",
      timestamp: new Date(),
    },
  ]);
    const [isLoading, setIsLoading] = useState(false);
    const [agents, setAgents] = useState<Agent[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
    const [currentJob, setCurrentJob] = useState<Job | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [jobDoneProcessed, setJobDoneProcessed] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const messagesRef = useRef<HTMLDivElement | null>(null);

  const hasWorkflow = currentJob !== null && tasks.length > 0;

  // Auto-resize textarea
    useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  // Scroll to bottom on new messages
    useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
    }, [messages]);

  // Load agents on mount
  useEffect(() => {
    fetch("/api/agents")
      .then((res) => res.json())
      .then((data) => setAgents(data))
      .catch((err) => console.error("Failed to load agents:", err));
  }, []);

  // Poll for job updates
    useEffect(() => {
    if (!currentJob || (currentJob.status !== "running" && currentJob.status !== "done")) return;
    if (currentJob.status === "done" && jobDoneProcessed) return;

    const controller = new AbortController();

    const poll = async () => {
      try {
        const [jobRes, eventsRes, agentsRes] = await Promise.all([
          fetch(`/api/jobs/${currentJob.id}`, { signal: controller.signal }),
          fetch(`/api/jobs/${currentJob.id}/events?limit=10`, { signal: controller.signal }),
          fetch("/api/agents", { signal: controller.signal }),
        ]);

        if (!jobRes.ok) return;

        const data = await jobRes.json();
                    setTasks(data.tasks || []);

                if (eventsRes.ok) {
                    const eventsData = await eventsRes.json();
                    setEvents(eventsData);
        }

                if (agentsRes.ok) {
                    const agentsData = await agentsRes.json();
                    setAgents(agentsData);
                }

        // Handle job completion
        if (data.job.status === "done" && !jobDoneProcessed) {
                        setJobDoneProcessed(true);

                            const completedTasks = data.tasks || [];
          const outputs: string[] = [];
          completedTasks.forEach((t: Task) => {
            if (t.outputs) {
              if (t.outputs.content) {
                outputs.push(`### ${t.name.replace(/_/g, " ")}\n\n${t.outputs.content}`);
              } else if (t.outputs.code) {
                outputs.push(`### ${t.name.replace(/_/g, " ")}\n\n\`\`\`${t.outputs.language || ""}\n${t.outputs.code}\n\`\`\``);
              } else if (t.outputs.data) {
                outputs.push(`### ${t.name.replace(/_/g, " ")}\n\n${JSON.stringify(t.outputs.data, null, 2)}`);
                                }
                            }
                        });

          const finalOutput = outputs.length > 0 ? outputs.join("\n\n---\n\n") : "All tasks completed successfully!";

          setMessages((prev) => [
            ...prev,
            {
              id: Date.now().toString(),
              type: "agent",
              sender: "Agent OS",
              content: `## Job Complete\n\n${finalOutput}`,
              timestamp: new Date(),
            },
          ]);

          setCurrentJob(data.job);
        } else {
          setCurrentJob(data.job);
                }
            } catch (error) {
        if ((error as Error).name !== "AbortError") {
          console.log("Polling error:", error);
        }
      }
    };

    poll();
    const interval = setInterval(poll, 1500);

    return () => {
      controller.abort();
      clearInterval(interval);
    };
  }, [currentJob?.id, currentJob?.status, jobDoneProcessed]);

  const handleSend = useCallback(async () => {
        if (!input.trim() || isLoading) return;

        const userMessage: Message = {
            id: Date.now().toString(),
      type: "user",
      sender: "You",
            content: input,
            timestamp: new Date(),
        };

        setMessages((prev) => [...prev, userMessage]);
    setInput("");
        setIsLoading(true);
    setJobDoneProcessed(false);

    try {
      // Reset system first - this also starts scheduler, sentinel, and workers
      await fetch("/api/system/reset", { method: "POST" });

      // Create the job
      const response = await fetch("/api/jobs/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal: input, priority: 1 }),
      });

      if (!response.ok) throw new Error("Failed to create job");

                const data = await response.json();
                setCurrentJob(data.job);
                setTasks(data.tasks || []);

      // Add planner response and started message together
                    setMessages((prev) => [
                        ...prev,
                        {
          id: `plan-${Date.now()}`,
          type: "agent",
          sender: "Planner",
          content: `I've analyzed your goal and created a task plan with ${data.tasks?.length || 0} steps. Here's the execution plan:`,
                            timestamp: new Date(),
          tasks: data.tasks,
        },
        {
          id: `started-${Date.now()}`,
          type: "system",
          sender: "Agent OS",
          content: "Job started! Agents are now executing tasks.",
                        timestamp: new Date(),
                    },
                ]);
    } catch (error) {
      console.error("Error:", error);
            setMessages((prev) => [
                ...prev,
                {
          id: `error-${Date.now()}`,
          type: "system",
          sender: "System",
          content: "Something went wrong. Please try again.",
                    timestamp: new Date(),
                },
            ]);
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading]);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
      case "completed":
        return <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />;
      case "running":
        return <span className="inline-block h-2 w-2 rounded-full bg-amber-500 animate-pulse" />;
      case "failed":
        return <span className="inline-block h-2 w-2 rounded-full bg-red-500" />;
      default:
        return <span className="inline-block h-2 w-2 rounded-full bg-gray-300" />;
    }
  };

  const getAgentInitial = (role: string) => {
    switch (role) {
      case "planner":
        return "P";
      case "researcher":
        return "R";
      case "writer":
        return "W";
      case "coder":
        return "C";
      case "data_builder":
        return "D";
      case "sentinel":
        return "S";
      default:
        return "A";
    }
  };

  const workflowContainerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.1, delayChildren: 0.05 },
    },
  };

  const workflowItemVariants = {
    hidden: { opacity: 0, y: 10 },
    show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
  };

    return (
    <div className="relative flex h-screen overflow-hidden bg-gradient-to-br from-slate-50 via-white to-gray-100">
      {/* Animated background blobs */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-20 top-10 h-96 w-96 animate-pulse rounded-full bg-gradient-to-br from-cyan-300/40 via-blue-300/30 to-indigo-300/40 blur-3xl"></div>
        <div className="absolute bottom-20 right-20 h-[500px] w-[500px] rounded-full bg-gradient-to-tl from-emerald-300/35 via-teal-300/30 to-cyan-300/40 blur-3xl"></div>
        <div className="absolute right-1/3 top-1/3 h-80 w-80 rounded-full bg-gradient-to-r from-violet-300/30 via-purple-300/25 to-fuchsia-300/35 blur-3xl"></div>
        <div className="absolute bottom-1/4 left-1/3 h-96 w-96 rounded-full bg-gradient-to-bl from-rose-300/40 via-pink-300/30 to-orange-300/35 blur-3xl"></div>
      </div>

      {/* Header */}
      <div className="fixed left-4 top-4 z-30 flex items-center gap-3 sm:left-6 sm:top-6">
        <button
          onClick={() => setSidebarOpen((open) => !open)}
          className="flex h-11 w-11 items-center justify-center rounded-xl border border-gray-200/60 bg-white/70 shadow-sm backdrop-blur-sm transition-all hover:bg-white/90 hover:shadow-md text-gray-700 font-medium"
          aria-label="Toggle menu"
        >
          ≡
        </button>
        <div className="flex items-center rounded-full border border-gray-200/70 bg-white/70 px-4 py-2 shadow-sm backdrop-blur-sm">
          <span className="text-sm font-semibold tracking-wide text-zinc-800">Agent OS</span>
                    </div>
                </div>

      {/* Sidebar */}
      <AnimatePresence>
        {sidebarOpen && (
          <>
            <motion.button
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-20 bg-black/10 backdrop-blur-sm"
              onClick={() => setSidebarOpen(false)}
              aria-label="Close menu"
            />
            <motion.aside
              initial={{ x: -280, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: -280, opacity: 0 }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              className="fixed left-0 top-0 z-30 h-full w-72 border-r border-gray-200/50 bg-white/95 p-6 shadow-2xl backdrop-blur-xl"
            >
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900">Active Agents</h2>
                <button
                  onClick={() => setSidebarOpen(false)}
                  className="rounded-lg p-2 hover:bg-gray-100 text-gray-500 text-lg font-medium"
                >
                  ×
                </button>
              </div>

              <div className="mt-6 space-y-3">
                    {agents.map((agent) => (
                  <div
                    key={agent.id}
                    className="flex items-center gap-3 rounded-xl border border-gray-200/80 bg-white/80 p-3 shadow-sm transition-all hover:shadow-md"
                  >
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-900 text-white">
                      <span className="text-sm font-bold">{getAgentInitial(agent.role)}</span>
                            </div>
                    <div className="flex-1">
                      <div className="text-sm font-medium text-gray-900">{agent.name}</div>
                      <div className="flex items-center gap-1.5 text-xs text-gray-500">
                        <span
                          className={`h-2 w-2 rounded-full ${
                            agent.status === "idle"
                              ? "animate-pulse bg-emerald-500"
                              : agent.status === "busy"
                              ? "bg-amber-500"
                              : "bg-red-500"
                          }`}
                        />
                        {agent.status}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Main Content */}
      <main className="relative z-10 flex h-screen flex-col items-center overflow-hidden p-4 pt-20 pb-6 sm:p-8 sm:pt-24">
        <div
          className={`grid h-full w-full max-w-5xl mx-auto grid-cols-1 gap-6 transition-all duration-500 ${
            hasWorkflow ? "lg:grid-cols-[minmax(0,1fr)_340px]" : "max-w-3xl"
          }`}
        >
          {/* Chat Area */}
          <div className="flex min-h-0 flex-col gap-4 overflow-hidden mx-auto w-full">
            {/* Title */}
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-center flex-shrink-0"
            >
              <h1 className="bg-gradient-to-r from-gray-800 via-gray-700 to-gray-800 bg-clip-text text-3xl font-bold text-transparent sm:text-4xl">
                Agent OS
                    </h1>
              <p className="mt-1 text-sm text-gray-500">
                Multi-agent orchestration for complex tasks
              </p>
            </motion.div>

            {/* Messages - Scrollable Container */}
            <div
              ref={messagesRef}
              className="flex-1 min-h-0 flex flex-col gap-4 overflow-y-auto rounded-2xl border border-gray-200/60 bg-white/60 p-5 shadow-xl backdrop-blur-xl"
            >
              <AnimatePresence mode="popLayout">
                {messages.map((message) => (
                  <motion.div
                    key={message.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className={`flex gap-3 ${message.type === "user" ? "flex-row-reverse" : ""}`}
                  >
                    {/* Avatar */}
                    <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-gray-900 text-white">
                      <span className="text-xs font-bold">
                        {message.type === "user" ? "U" : "A"}
                      </span>
                    </div>

                    {/* Content */}
                    <div
                      className={`max-w-[80%] rounded-2xl px-4 py-3 shadow-sm ${
                        message.type === "user"
                          ? "bg-gradient-to-br from-gray-800 to-gray-900 text-white"
                          : "border border-gray-200/50 bg-white/90"
                      }`}
                    >
                      <div className="mb-1 flex items-center gap-2">
                        <span className={`text-xs font-medium ${message.type === "user" ? "text-gray-300" : "text-gray-500"}`}>
                          {message.sender}
                        </span>
                        <span className={`text-[10px] ${message.type === "user" ? "text-gray-400" : "text-gray-400"}`}>
                          {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </span>
                      </div>
                      <div className={`text-sm leading-relaxed ${message.type === "user" ? "text-white" : "text-gray-700"}`}>
                        {message.type === "agent" || message.type === "system" ? (
                          <div className="markdown-content">
                            <ReactMarkdown>{message.content}</ReactMarkdown>
                            </div>
                        ) : (
                          message.content
                        )}
                                        </div>

                      {/* Task Plan */}
                                        {message.tasks && message.tasks.length > 0 && (
                        <div className="mt-3 rounded-xl border border-gray-200/70 bg-gray-50/80 p-3">
                          <div className="mb-2 flex items-center justify-between">
                            <span className="text-xs font-semibold text-gray-700">Task Execution Plan</span>
                            <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                              currentJob?.status === "done"
                                ? "bg-emerald-100 text-emerald-700"
                                : currentJob?.status === "running"
                                ? "bg-amber-100 text-amber-700"
                                : "bg-gray-200 text-gray-600"
                            }`}>
                              {currentJob?.status?.toUpperCase() || "PENDING"}
                                                    </span>
                                                </div>
                          <div className="space-y-1.5">
                            {message.tasks.map((task, idx) => (
                              <div key={task.id} className="flex items-center gap-2">
                                {getStatusIcon(tasks.find((t) => t.id === task.id)?.status || task.status)}
                                <span className="text-xs text-gray-600">{task.name.replace(/_/g, " ")}</span>
                                                                    </div>
                            ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>

                        {isLoading && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex items-center gap-2 text-sm text-gray-500"
                >
                  <span className="inline-block h-3 w-3 rounded-full border-2 border-gray-400 border-t-transparent animate-spin" />
                  <span>Planning your request...</span>
                </motion.div>
              )}
                    </div>

            {/* Input */}
            <div className="relative mx-auto w-full rounded-2xl border border-gray-200/70 bg-white/80 shadow-xl backdrop-blur-xl">
                            <textarea
                ref={textareaRef}
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                placeholder="Enter your goal... (e.g., 'Create a competitor analysis report')"
                className="w-full resize-none bg-transparent px-5 py-4 pr-14 text-sm text-gray-900 placeholder-gray-400 focus:outline-none"
                                rows={1}
                style={{ maxHeight: "200px" }}
                            />
                            <button
                onClick={handleSend}
                                disabled={!input.trim() || isLoading}
                className="absolute bottom-3 right-3 rounded-xl bg-gradient-to-r from-gray-700 to-gray-900 p-2.5 text-white shadow-lg transition-all hover:from-gray-600 hover:to-gray-800 hover:shadow-xl disabled:cursor-not-allowed disabled:from-gray-300 disabled:to-gray-400"
                aria-label="Send message"
                            >
                →
              </button>
            </div>
          </div>

          {/* Workflow Panel */}
          <AnimatePresence>
            {hasWorkflow && (
              <motion.div
                initial={{ opacity: 0, x: 50 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 50 }}
                transition={{ duration: 0.4 }}
                className="flex min-h-0 flex-col rounded-2xl border border-gray-200/60 bg-white/70 p-5 shadow-xl backdrop-blur-xl overflow-y-auto"
              >
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-base font-semibold text-gray-800">Multi-Agent Workflow</h2>
                  <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${
                    currentJob?.status === "done"
                      ? "bg-emerald-100 text-emerald-700"
                      : currentJob?.status === "running"
                      ? "bg-amber-100 text-amber-700"
                      : "bg-gray-200 text-gray-600"
                  }`}>
                    {currentJob?.status}
                  </span>
                </div>

                <motion.div
                  className="flex flex-col gap-4"
                  variants={workflowContainerVariants}
                  initial="hidden"
                  animate="show"
                >
                  {/* Agents Working */}
                  {agents.filter(a => a.status === "busy" || tasks.some(t => t.assigned_agent === a.name)).slice(0, 4).map((agent) => {
                    const agentTasks = tasks.filter((t) => t.assigned_agent === agent.name || t.assigned_agent === agent.id);
                    return (
                      <motion.div
                        key={agent.id}
                        variants={workflowItemVariants}
                        className="rounded-xl border border-gray-200/80 bg-white/90 p-4 shadow-sm"
                      >
                        <div className="mb-2 flex items-center gap-2">
                          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-900 text-white">
                            <span className="text-xs font-bold">{getAgentInitial(agent.role)}</span>
                    </div>
                          <div>
                            <h3 className="text-sm font-semibold text-gray-900">{agent.name}</h3>
                            <p className="text-[11px] text-gray-500">{agent.role.replace(/_/g, " ")}</p>
                                </div>
                        </div>

                        <div className="space-y-2">
                          {agentTasks.length > 0 ? (
                            agentTasks.map((task) => (
                              <div
                                key={task.id}
                                className="flex items-center justify-between rounded-lg bg-gray-50/80 px-3 py-2"
                              >
                                <span className="text-xs text-gray-700">{task.name.replace(/_/g, " ")}</span>
                                <span
                                  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium uppercase ${
                                    task.status === "completed"
                                      ? "bg-emerald-100 text-emerald-700"
                                      : task.status === "running"
                                      ? "bg-amber-100 text-amber-700"
                                      : task.status === "failed"
                                      ? "bg-red-100 text-red-700"
                                      : "bg-gray-200 text-gray-600"
                                  }`}
                                >
                                  {getStatusIcon(task.status)}
                                  {task.status}
                                </span>
                                </div>
                            ))
                        ) : (
                            <div className="rounded-lg bg-gray-50/80 px-3 py-2 text-xs text-gray-500">
                              Waiting for tasks...
                            </div>
                        )}
                        </div>
                      </motion.div>
                    );
                  })}

                  {/* All Tasks Summary */}
                  <motion.div
                    variants={workflowItemVariants}
                    className="rounded-xl border border-gray-200/80 bg-gradient-to-br from-gray-50 to-white p-4"
                  >
                    <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
                      Task Progress
                    </h3>
                    <div className="space-y-2">
                      {tasks.map((task) => (
                        <div key={task.id} className="flex items-center gap-2">
                          {getStatusIcon(task.status)}
                          <span className="flex-1 text-xs text-gray-700">{task.name.replace(/_/g, " ")}</span>
                          <span className={`text-[10px] font-medium uppercase ${
                            task.status === "completed" ? "text-emerald-600" :
                            task.status === "running" ? "text-amber-600" :
                            task.status === "failed" ? "text-red-600" : "text-gray-400"
                          }`}>
                            {task.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  </motion.div>

                  {/* Recent Events */}
                  {events.length > 0 && (
                    <motion.div
                      variants={workflowItemVariants}
                      className="rounded-xl border border-gray-200/80 bg-white/90 p-4"
                    >
                      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
                        Recent Events
                      </h3>
                      <div className="space-y-2">
                        {events.slice(0, 5).map((event) => (
                          <div key={event.id} className="flex items-start gap-2 text-xs">
                            <div className="mt-0.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-cyan-500" />
                            <div className="flex-1">
                              <p className="text-gray-700">{event.message}</p>
                              <p className="text-[10px] text-gray-400">
                                {new Date(event.timestamp).toLocaleTimeString()}
                              </p>
                            </div>
                          </div>
                        ))}
                </div>
                    </motion.div>
                  )}
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>
        </div>
    );
}
