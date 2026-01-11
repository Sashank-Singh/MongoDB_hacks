"use client";

import React, { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Menu, Send } from "lucide-react";

type ChatMessage = {
  id: string;
  text: string;
  createdAt: string;
  threadId: string;
};

type WorkflowStepStatus = "done" | "in_progress" | "queued";

type WorkflowStep = {
  title: string;
  status: WorkflowStepStatus;
};

type WorkflowAgent = {
  name: string;
  task: string;
  steps: WorkflowStep[];
};

type WorkflowRun = {
  id: string;
  question: string;
  agents: WorkflowAgent[];
};

type ChatPair = {
  id: string;
  user: string;
  agent: string;
  createdAt: string;
};

type ThreadSummary = {
  id: string;
  title: string;
  updatedAt: string;
};

export default function Home() {
  const [input, setInput] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [allMessages, setAllMessages] = useState<ChatMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showTimestamps, setShowTimestamps] = useState(false);
  const [workflowRuns, setWorkflowRuns] = useState<WorkflowRun[]>([]);
  const [chatHistory, setChatHistory] = useState<ChatPair[]>([]);
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [currentThreadId, setCurrentThreadId] = useState<string>("default");
  const [showHistory, setShowHistory] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const messagesRef = useRef<HTMLDivElement | null>(null);
  const hasWorkflow = workflowRuns.length > 0;
  const shouldShiftInput = hasWorkflow;
  const workflowContainerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.12, delayChildren: 0.04 },
    },
  };
  const workflowItemVariants = {
    hidden: { opacity: 0, y: 8 },
    show: { opacity: 1, y: 0, transition: { duration: 0.35 } },
  };

  const buildAgentResponse = (text: string) =>
    `${text}`;

  const buildThreadSummary = (group: ChatMessage[]): ThreadSummary => {
    const latest = group[group.length - 1];
    return {
      id: latest.threadId,
      title: group[0]?.text || "Untitled thread",
      updatedAt: latest.createdAt,
    };
  };

  const loadMessages = async () => {
    const response = await fetch("/api/messages");
    if (!response.ok) return;
    const data = (await response.json()) as { messages: ChatMessage[] };
    const normalized = data.messages.map((message) => ({
      ...message,
      threadId: message.threadId || "default",
    }));
    const grouped = normalized.reduce<Record<string, ChatMessage[]>>(
      (acc, message) => {
        acc[message.threadId] ||= [];
        acc[message.threadId].push(message);
        return acc;
      },
      {}
    );
    const summaries = Object.values(grouped)
      .map(buildThreadSummary)
      .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
    const activeThread = summaries[0]?.id || "default";
    const activeMessages =
      grouped[currentThreadId] || grouped[activeThread] || [];
    const orderedActiveMessages = [...activeMessages].sort((a, b) =>
      a.createdAt.localeCompare(b.createdAt)
    );
    setAllMessages(normalized);
    setThreads(summaries);
    setCurrentThreadId(grouped[currentThreadId] ? currentThreadId : activeThread);
    setMessages(orderedActiveMessages);
    setWorkflowRuns(
      orderedActiveMessages.map((message) =>
        buildWorkflowRun(message.text, message.id)
      )
    );
    setChatHistory(
      orderedActiveMessages.map((message) => ({
        id: message.id,
        user: message.text,
        agent: buildAgentResponse(message.text),
        createdAt: message.createdAt,
      }))
    );
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        200
      )}px`;
    }
  }, [input]);

  useEffect(() => {
    void loadMessages();
  }, []);

  const buildWorkflowRun = (question: string, id?: string): WorkflowRun => {
    return {
      id: id ?? `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      question,
      agents: [
        {
          name: "Planner",
          task: "Clarify the request and split into sub-tasks.",
          steps: [
            { title: "Parse intent and constraints", status: "done" },
            { title: "Break into actionable steps", status: "queued" },
            { title: "Assign work to agents", status: "done" },
          ],
        },
        {
          name: "Researcher",
          task: "Gather context and validate assumptions.",
          steps: [
            { title: "Check existing data and files", status: "done" },
            { title: "Confirm technical requirements", status: "done" },
            { title: "Summarize relevant findings", status: "done" },
          ],
        },
        {
          name: "Builder",
          task: "Implement the solution and wire it up.",
          steps: [
            { title: "Draft core changes", status: "done" },
            { title: "Integrate with UI/logic", status: "done" },
            { title: "Verify behavior locally", status: "done" },
          ],
        },
        {
          name: "Reviewer",
          task: "Check quality, edge cases, and final output.",
          steps: [
            { title: "Review for regressions", status: "in_progress" },
            { title: "Validate output format", status: "done" },
            { title: "Approve final response", status: "done" },
          ],
        },
      ],
    };
  };

  const handleSend = async () => {
    if (!input.trim() || isSending) return;
    setIsSending(true);
    const trimmed = input.trim();
    const threadId = currentThreadId || "default";
    const payload = { text: trimmed, threadId };
    setInput("");
    const response = await fetch("/api/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (response.ok) {
      const data = (await response.json()) as { message: ChatMessage };
      setAllMessages((prev) => [...prev, data.message]);
      setMessages((prev) => [...prev, data.message]);
      setWorkflowRuns((prev) => [
        ...prev,
        buildWorkflowRun(trimmed, data.message.id),
      ]);
      setChatHistory((prev) => [
        ...prev,
        {
          id: data.message.id,
          user: data.message.text,
          agent: buildAgentResponse(data.message.text),
          createdAt: data.message.createdAt,
        },
      ]);
    }
    setIsSending(false);
  };

  const handleNewChat = async () => {
    const newThreadId = `${Date.now()}-${Math.random()
      .toString(36)
      .slice(2, 8)}`;
    setCurrentThreadId(newThreadId);
    setMessages([]);
    setChatHistory([]);
    setWorkflowRuns([]);
    setShowHistory(false);
    setShowSettings(false);
    setSidebarOpen(false);
  };

  const handleHistory = async () => {
    await loadMessages();
    setShowHistory((prev) => !prev);
    setShowSettings(false);
    setSidebarOpen(true);
  };

  const handleSettings = () => {
    setShowSettings((prev) => !prev);
    setShowHistory(false);
    setSidebarOpen(false);
  };

  const handleSelectThread = (threadId: string) => {
    const grouped = allMessages.reduce<Record<string, ChatMessage[]>>(
      (acc, message) => {
        acc[message.threadId] ||= [];
        acc[message.threadId].push(message);
        return acc;
      },
      {}
    );
    const activeMessages = grouped[threadId] || [];
    const orderedActiveMessages = [...activeMessages].sort((a, b) =>
      a.createdAt.localeCompare(b.createdAt)
    );
    setCurrentThreadId(threadId);
    setMessages(orderedActiveMessages);
    setWorkflowRuns(
      orderedActiveMessages.map((message) =>
        buildWorkflowRun(message.text, message.id)
      )
    );
    setChatHistory(
      orderedActiveMessages.map((message) => ({
        id: message.id,
        user: message.text,
        agent: buildAgentResponse(message.text),
        createdAt: message.createdAt,
      }))
    );
    setSidebarOpen(false);
  };

  const handleDeleteThread = async (
    event: React.MouseEvent,
    threadId: string
  ) => {
    event.stopPropagation();
    await fetch(`/api/messages?threadId=${encodeURIComponent(threadId)}`, {
      method: "DELETE",
    });
    await loadMessages();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="relative flex h-screen overflow-hidden bg-gradient-to-br from-gray-50 via-white to-gray-100">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-20 top-10 h-96 w-96 animate-pulse rounded-full bg-gradient-to-br from-blue-300/40 via-purple-300/30 to-pink-300/40 blur-3xl"></div>
        <div className="absolute bottom-20 right-20 h-[500px] w-[500px] rounded-full bg-gradient-to-tl from-cyan-300/35 via-teal-300/30 to-emerald-300/40 blur-3xl"></div>
        <div className="absolute right-1/3 top-1/3 h-80 w-80 rounded-full bg-gradient-to-r from-amber-300/30 via-orange-300/25 to-rose-300/35 blur-3xl"></div>
        <div className="absolute bottom-1/4 left-1/3 h-96 w-96 rounded-full bg-gradient-to-bl from-indigo-300/40 via-violet-300/30 to-purple-300/35 blur-3xl"></div>
        <div className="absolute left-1/2 top-1/2 h-[600px] w-[600px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-gradient-to-r from-fuchsia-200/25 via-pink-200/20 to-purple-200/25 blur-3xl"></div>
      </div>

      <div className="fixed left-4 top-4 z-30 flex items-center gap-2 sm:left-6 sm:top-6">
        <button
          onClick={() => setSidebarOpen((open) => !open)}
          className="flex h-12 w-12 items-center justify-center rounded-xl border border-gray-200/60 bg-white/60 backdrop-blur-sm transition-all hover:bg-white/80"
          aria-label="Toggle menu"
        >
          <Menu size={24} className="text-gray-700" />
        </button>
        <span className="rounded-full border border-gray-200/70 bg-white/60 px-3 py-1 text-sm font-semibold tracking-wide text-zinc-700 shadow-sm backdrop-blur-sm">
          A4A
        </span>
      </div>

      {sidebarOpen && (
        <>
          <button
            className="fixed inset-0 z-20 bg-black/10 backdrop-blur-sm"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close menu"
          />
          <aside className="fixed left-0 top-0 z-30 h-full w-64 border-r border-gray-200 bg-white/95 p-6 shadow-2xl backdrop-blur-xl">
            <div className="mt-16">
              <h2 className="mb-4 text-lg font-semibold text-gray-900">Menu</h2>
              <div className="space-y-2">
                <button
                  onClick={handleNewChat}
                  className="w-full rounded-lg px-4 py-2 text-left text-gray-700 transition-colors hover:bg-gray-100"
                >
                  New Chat
                </button>
                <button
                  onClick={handleHistory}
                  className="w-full rounded-lg px-4 py-2 text-left text-gray-700 transition-colors hover:bg-gray-100"
                >
                  History
                </button>
                <button
                  onClick={handleSettings}
                  className="w-full rounded-lg px-4 py-2 text-left text-gray-700 transition-colors hover:bg-gray-100"
                >
                  Settings
                </button>
              </div>
              {showHistory && (
                <div className="mt-5 border-t border-gray-200 pt-4">
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
                    Threads
                  </div>
                  <div className="flex max-h-64 flex-col gap-2 overflow-y-auto pr-1">
                    {threads.length === 0 ? (
                      <div className="text-xs text-gray-500">
                        No saved threads yet.
                      </div>
                    ) : (
                      threads.map((thread) => (
                        <div
                          key={thread.id}
                          className={`flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-xs transition-colors ${
                            thread.id === currentThreadId
                              ? "bg-gray-100 text-gray-900"
                              : "text-gray-700 hover:bg-gray-100"
                          }`}
                        >
                          <button
                            onClick={() => handleSelectThread(thread.id)}
                            className="flex-1 text-left"
                          >
                            <div className="font-semibold">
                              {thread.title.length > 32
                                ? `${thread.title.slice(0, 32)}...`
                                : thread.title}
                            </div>
                            <div className="text-[10px] text-gray-500">
                              {new Date(thread.updatedAt).toLocaleString()}
                            </div>
                          </button>
                          <button
                            onClick={(event) =>
                              handleDeleteThread(event, thread.id)
                            }
                            className="rounded-full border border-gray-200 px-2 py-1 text-[10px] font-semibold text-gray-500 transition hover:border-gray-300 hover:text-gray-700"
                            aria-label="Delete thread"
                          >
                            Delete
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>
          </aside>
        </>
      )}

      <main
        className={`relative z-10 flex flex-1 items-center justify-center p-8 pb-10 pt-[env(safe-area-inset-top)] pr-[env(safe-area-inset-right)] pl-[env(safe-area-inset-left)] transition-all duration-300 ${
          sidebarOpen ? "lg:pl-[calc(env(safe-area-inset-left)+16rem)]" : ""
        }`}
      >
        <div
          className={`grid w-full max-w-6xl grid-cols-1 gap-6 transition-all duration-500 ${
            hasWorkflow ? "lg:grid-cols-[minmax(0,7fr)_minmax(0,3fr)]" : ""
          }`}
        >
          <div className="flex min-h-0 flex-col gap-6 transition-all duration-500">
            <div
              className="text-center text-4xl font-semibold text-zinc-700 transition-all duration-500 sm:text-5xl"
            >
              Agent4Agents
            </div>
            {showSettings && (
              <div className="rounded-2xl border border-gray-200 bg-white/60 p-4 text-sm text-gray-700 shadow-xl backdrop-blur-xl">
                <label className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={showTimestamps}
                    onChange={(event) =>
                      setShowTimestamps(event.target.checked)
                    }
                    className="h-4 w-4"
                  />
                  Show timestamps
                </label>
              </div>
            )}
            <div className="flex min-h-0 flex-1 flex-col gap-6">
              {chatHistory.length > 0 && (
                <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto rounded-2xl border border-gray-200 bg-white/60 p-4 shadow-xl backdrop-blur-xl">
                  {chatHistory.map((pair) => (
                    <div key={pair.id} className="flex flex-col gap-3">
                      <div className="ml-auto max-w-[85%] rounded-2xl bg-gray-900 px-4 py-2 text-sm text-white shadow-md">
                        <div>{pair.user}</div>
                        {showTimestamps && (
                          <div className="mt-1 text-[11px] text-gray-300">
                            {new Date(pair.createdAt).toLocaleString()}
                          </div>
                        )}
                      </div>
                      <div className="mr-auto max-w-[85%] rounded-2xl bg-white px-4 py-2 text-sm text-gray-800 shadow-md">
                        <div>{pair.agent}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <motion.div
                className="relative mx-auto w-full max-w-3xl rounded-2xl border border-gray-200 bg-white/70 shadow-2xl backdrop-blur-xl"
                initial={false}
                animate={{
                  x: shouldShiftInput ? -24 : 0,
                  y: shouldShiftInput ? 16 : 0,
                }}
                transition={{ duration: 0.6, ease: "easeInOut" }}
              >
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask anything..."
                  className="w-full resize-none bg-transparent px-6 py-5 pr-14 text-base text-gray-900 placeholder-gray-400 focus:outline-none"
                  rows={1}
                  style={{ maxHeight: "200px" }}
                />
                <button
                  onClick={handleSend}
                  disabled={!input.trim() || isSending}
                  className="absolute bottom-4 right-4 rounded-xl bg-gradient-to-r from-gray-700 to-gray-900 p-3 text-white shadow-lg transition-all hover:from-gray-600 hover:to-gray-800 disabled:cursor-not-allowed disabled:from-gray-300 disabled:to-gray-400"
                  aria-label="Send message"
                >
                  <Send size={20} />
                </button>
              </motion.div>
            </div>
          </div>
          {hasWorkflow && (
            <div
              ref={messagesRef}
              className="flex min-h-0 flex-col rounded-2xl border border-gray-200 bg-white/60 p-6 shadow-xl backdrop-blur-xl lg:max-h-[calc(100vh-5rem)] lg:overflow-y-auto"
            >
              <div className="mb-4 text-lg font-semibold text-gray-800">
                Multi-agent workflow
              </div>
              <motion.div
                className="flex flex-col gap-6"
                variants={workflowContainerVariants}
                initial={false}
                animate="show"
                layout
              >
                {workflowRuns.map((run) => (
                  <motion.div
                    key={run.id}
                    variants={workflowItemVariants}
                    className="rounded-2xl border border-gray-200 bg-white/70 p-4 shadow-sm"
                    layout
                  >
                    <div className="flex flex-col gap-4">
                      {run.agents.map((agent) => (
                        <motion.div
                          key={agent.name}
                          variants={workflowItemVariants}
                          className="rounded-xl border border-gray-200 bg-white p-3"
                          layout
                        >
                          <h2 className="text-base font-semibold text-gray-900">
                            {agent.name}
                          </h2>
                          <div className="mb-2 text-xs text-gray-500">
                            {agent.task}
                          </div>
                          <div className="flex flex-col gap-2">
                            {agent.steps.map((step, index) => (
                              <div
                                key={`${agent.name}-${index}`}
                                className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-700"
                              >
                                <span>{step.title}</span>
                                <span
                                  className={`inline-flex items-center justify-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-[10px] uppercase tracking-wide ${
                                    step.status === "done"
                                      ? "bg-emerald-100 text-emerald-700"
                                      : step.status === "in_progress"
                                      ? "bg-amber-100 text-amber-700"
                                      : "bg-slate-200 text-slate-700"
                                  }`}
                                  aria-label={
                                    step.status === "done"
                                      ? "Completed"
                                      : step.status === "in_progress"
                                      ? "Working"
                                      : "Running"
                                  }
                                >
                                  {step.status === "done"
                                    ? "Completed"
                                    : step.status === "in_progress"
                                    ? "Working"
                                    : "Running"}
                                </span>
                              </div>
                            ))}
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  </motion.div>
                ))}
              </motion.div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
