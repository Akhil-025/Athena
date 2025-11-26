import React, { useEffect, useState, useCallback } from "react";
import {
  MessageSquare,
  Zap,
  Database,
  Settings,
  Send,
  Mic,
  Download,
  Search,
  Brain,
  Cpu,
  ChevronRight,
  Clock,
  Sparkles,
  Sun,
  Moon
} from "lucide-react";

import { API_URL, ASK_ENDPOINT, STATS_ENDPOINT, STREAM_ENDPOINT } from "./config";
import { fetchStats, askQuestionAPI, askQuestionStream } from "./utils/api";
import useLocalStorage from "./hooks/useLocalStorage";
import useHotkeys from "./hooks/useHotkeys";

export default function App() {
  // Persistent state
  const [conversation, setConversation] = useLocalStorage("athena:conversation", []);
  const [useCloud, setUseCloud] = useLocalStorage("athena:useCloud", false);
  const [theme, setTheme] = useLocalStorage("athena:theme", "dark");
  const [agents] = useLocalStorage("athena:agents", [
    "Researcher",
    "Teacher",
    "Simplifier",
    "Critic"
  ]);
  const [currentAgent, setCurrentAgent] = useLocalStorage("athena:agent", "Researcher");
  const [models] = useLocalStorage("athena:models", [
    "mistral",
    "llama",
    "gemini",
    "gpt-4"
  ]);
  const [currentModel, setCurrentModel] = useLocalStorage("athena:model", "mistral");

  // Ephemeral state
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState({
    subjects: [],
    modules: [],
    total_chunks: 0
  });
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [latency, setLatency] = useState(null);
  const [question, setQuestion] = useState("");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // --- DARK MODE HANDLING ---
  useEffect(() => {
    if (theme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [theme]);

  // --- RAG STATS FETCH ---
  useEffect(() => {
    (async () => {
      const s = await fetchStats(API_URL + STATS_ENDPOINT);
      if (s) setStats(s);
    })();
  }, []);

  // --- HOTKEYS (optional, can extend later) ---
  useHotkeys({
    "ctrl.'": () => setSettingsOpen((v) => !v)
  });

  // --- MAIN SEND FUNCTION (STREAMING + FALLBACK) ---
  const sendQuestion = useCallback(
    async (raw) => {
      const q = (raw || question || "").trim();
      if (!q || loading) return;

      // push user message
      const userMsg = {
        id: Date.now() + "_u",
        type: "user",
        content: q,
        time: Date.now()
      };
      setConversation((prev) => [...prev, userMsg]);
      setQuestion("");
      setLoading(true);
      setLatency(null);
      const start = Date.now();

      // helper to add / update streaming chunk
      const pushStreamChunk = (chunk) => {
        setConversation((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.type === "stream" && !last.done) {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...last,
              content: (last.content || "") + chunk
            };
            return updated;
          }
          return [
            ...prev,
            {
              id: Date.now() + "_s",
              type: "stream",
              content: chunk,
              time: Date.now(),
              done: false
            }
          ];
        });
      };

      // 1) Try streaming endpoint
      try {
        const result = await askQuestionStream(
          API_URL + STREAM_ENDPOINT,
          {
            question: q,
            use_cloud: useCloud,
            model: currentModel,
            agent: currentAgent
          },
          pushStreamChunk
        );

        const final = result || {};
        const duration = Date.now() - start;

        setConversation((prev) => {
          const withDone = prev.map((m) =>
            m.type === "stream" ? { ...m, done: true } : m
          );
          return [
            ...withDone,
            {
              id: Date.now() + "_a",
              type: "ai",
              content: final.text || "(no content)",
              sources: final.sources || [],
              cached: final.cached || false,
              mode: final.mode || (useCloud ? "cloud" : "local"),
              meta: { duration }
            }
          ];
        });

        setLatency(duration);
        setLoading(false);
        return;
      } catch (err) {
        console.warn("Streaming failed, using fallback:", err);
      }

      // 2) Fallback to non-streaming /api/ask
      try {
        const res = await askQuestionAPI(API_URL + ASK_ENDPOINT, {
          question: q,
          use_cloud: useCloud,
          model: currentModel,
          agent: currentAgent
        });
        const duration = Date.now() - start;

        setConversation((prev) => [
          ...prev,
          {
            id: Date.now() + "_a",
            type: "ai",
            content: res.answer || "(no answer)",
            sources: res.sources || [],
            cached: res.cached || false,
            mode: res.mode || (useCloud ? "cloud" : "local"),
            meta: { duration }
          }
        ]);
        setLatency(duration);
      } catch (e) {
        setConversation((prev) => [
          ...prev,
          {
            id: Date.now() + "_err",
            type: "error",
            content: "Error: " + (e?.message || e),
            time: Date.now()
          }
        ]);
      } finally {
        setLoading(false);
      }
    },
    [question, loading, useCloud, currentModel, currentAgent, setConversation]
  );

  // --- RENDER ---

  return (
    <div className="flex h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white overflow-hidden">
      {/* Animated background blobs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 -left-32 w-96 h-96 bg-violet-500/10 rounded-full blur-3xl animate-pulse" />
        <div
          className="absolute bottom-1/4 -right-32 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl animate-pulse"
          style={{ animationDelay: "1s" }}
        />
      </div>

      {/* LEFT SIDEBAR */}
      <aside
        className={`relative flex flex-col border-r border-white/5 bg-black/40 backdrop-blur-xl transition-all duration-300 ${
          sidebarCollapsed ? "w-16" : "w-72"
        }`}
      >
        {/* Logo + Collapse */}
        <div className="flex items-center justify-between p-4 border-b border-white/5">
          {!sidebarCollapsed && (
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-gradient-to-br from-violet-500 to-cyan-500 rounded-lg flex items-center justify-center">
                <Brain className="w-5 h-5" />
              </div>
              <span className="font-bold text-lg bg-gradient-to-r from-violet-400 to-cyan-400 bg-clip-text text-transparent">
                ATHENA
              </span>
            </div>
          )}
          <button
            onClick={() => setSidebarCollapsed((v) => !v)}
            className="p-1.5 hover:bg-white/5 rounded-lg transition-colors"
          >
            <ChevronRight
              className={`w-4 h-4 transition-transform ${
                sidebarCollapsed ? "" : "rotate-180"
              }`}
            />
          </button>
        </div>

        {/* Sidebar content (hidden when collapsed) */}
        {!sidebarCollapsed && (
          <>
            {/* Quick Stats */}
            <div className="p-4 space-y-3">
              <div className="bg-gradient-to-r from-violet-500/10 to-cyan-500/10 rounded-xl p-4 border border-white/5">
                <div className="flex items-center gap-2 mb-3">
                  <Database className="w-4 h-4 text-cyan-400" />
                  <span className="text-xs font-medium text-slate-300">
                    Knowledge Base
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-3 text-center">
                  <div>
                    <div className="text-xl font-bold text-white">
                      {stats.subjects?.length || 0}
                    </div>
                    <div className="text-xs text-slate-400">Subjects</div>
                  </div>
                  <div>
                    <div className="text-xl font-bold text-white">
                      {stats.modules?.length || 0}
                    </div>
                    <div className="text-xs text-slate-400">Modules</div>
                  </div>
                  <div>
                    <div className="text-xl font-bold text-white">
                      {((stats.total_chunks || 0) / 1000).toFixed(1)}k
                    </div>
                    <div className="text-xs text-slate-400">Chunks</div>
                  </div>
                </div>
              </div>

              {/* Latency */}
              <div className="flex items-center justify-between p-3 bg-white/5 rounded-lg border border-white/5">
                <div className="flex items-center gap-2">
                  <Zap className="w-4 h-4 text-yellow-400" />
                  <span className="text-sm text-slate-300">Latency</span>
                </div>
                <span className="text-sm font-mono font-bold text-green-400">
                  {latency != null ? `${latency}ms` : "—"}
                </span>
              </div>
            </div>

            {/* Agent & Model selection */}
            <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-4">
              <div>
                <label className="text-xs uppercase text-slate-500 font-semibold mb-2 block">
                  Active Agent
                </label>
                <div className="space-y-1">
                  {agents.map((agent) => (
                    <button
                      key={agent}
                      onClick={() => setCurrentAgent(agent)}
                      className={`w-full text-left px-3 py-2 rounded-lg transition-all ${
                        currentAgent === agent
                          ? "bg-gradient-to-r from-violet-500/20 to-cyan-500/20 border border-violet-500/30 text-white"
                          : "hover:bg-white/5 text-slate-400 border border-transparent"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <Brain className="w-4 h-4" />
                        <span className="text-sm font-medium">{agent}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-xs uppercase text-slate-500 font-semibold mb-2 block">
                  Model
                </label>
                <div className="space-y-1">
                  {models.map((model) => (
                    <button
                      key={model}
                      onClick={() => setCurrentModel(model)}
                      className={`w-full text-left px-3 py-2 rounded-lg transition-all ${
                        currentModel === model
                          ? "bg-gradient-to-r from-violet-500/20 to-cyan-500/20 border border-violet-500/30 text-white"
                          : "hover:bg-white/5 text-slate-400 border border-transparent"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <Cpu className="w-4 h-4" />
                        <span className="text-sm font-medium">{model}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Settings Button */}
            <div className="p-4 border-t border-white/5">
              <button
                onClick={() => setSettingsOpen(true)}
                className="w-full flex items-center gap-2 px-4 py-2.5 bg-white/5 hover:bg-white/10 rounded-lg transition-colors"
              >
                <Settings className="w-4 h-4" />
                <span className="text-sm font-medium">Settings</span>
              </button>
            </div>
          </>
        )}
      </aside>

      {/* MAIN COLUMN */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* TOP HEADER */}
        <header className="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-black/20 backdrop-blur-xl">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-bold bg-gradient-to-r from-violet-400 via-purple-400 to-cyan-400 bg-clip-text text-transparent">
              Ultra Intelligence
            </h1>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-500/10 border border-green-500/20">
              <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
              <span className="text-xs font-medium text-green-400">
                Local · Private
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Theme toggle */}
            <button
              onClick={() =>
                setTheme((t) => (t === "dark" ? "light" : "dark"))
            }
              className="p-2 hover:bg-white/5 rounded-lg transition-colors"
              title="Toggle theme"
            >
              {theme === "dark" ? (
                <Moon className="w-5 h-5 text-slate-300" />
              ) : (
                <Sun className="w-5 h-5 text-yellow-300" />
              )}
            </button>

            {/* Placeholder controls (hook up later if you want) */}
            <button
              className="p-2 hover:bg-white/5 rounded-lg transition-colors"
              title="Voice Input"
            >
              <Mic className="w-5 h-5 text-slate-400 hover:text-white" />
            </button>
            <button
              className="p-2 hover:bg-white/5 rounded-lg transition-colors"
              title="Export"
            >
              <Download className="w-5 h-5 text-slate-400 hover:text-white" />
            </button>
            <button
              className="p-2 hover:bg-white/5 rounded-lg transition-colors"
              title="Search"
            >
              <Search className="w-5 h-5 text-slate-400 hover:text-white" />
            </button>

            {/* Local / Cloud toggle */}
            <div className="flex items-center gap-1 p-1 bg-white/5 rounded-lg">
              <button
                onClick={() => setUseCloud(false)}
                className={`px-3 py-1.5 rounded text-xs font-medium transition-all ${
                  !useCloud
                    ? "bg-violet-500 text-white"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Local
              </button>
              <button
                onClick={() => setUseCloud(true)}
                className={`px-3 py-1.5 rounded text-xs font-medium transition-all ${
                  useCloud
                    ? "bg-cyan-500 text-white"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Cloud
              </button>
            </div>
          </div>
        </header>

        {/* CHAT SCROLL AREA */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
          {conversation.length === 0 && !loading && (
            <div className="flex flex-col items-center justify-center h-full">
              <div className="w-20 h-20 bg-gradient-to-br from-violet-500 to-cyan-500 rounded-2xl flex items-center justify-center mb-6">
                <Sparkles className="w-10 h-10 text-white" />
              </div>
              <h2 className="text-3xl font-bold mb-2">
                How can I help you today?
              </h2>
              <p className="text-slate-400 text-center max-w-md">
                Ask anything from your PDFs, notes, and textbooks. Athena will
                search your knowledge base, retrieve sources, and explain.
              </p>
            </div>
          )}

          {conversation.map((msg) => {
            const isUser = msg.type === "user";
            const isAI = msg.type === "ai" || msg.type === "stream";
            const isError = msg.type === "error";

            return (
              <div
                key={msg.id}
                className={`flex gap-4 ${
                  isUser ? "justify-end" : "justify-start"
                }`}
              >
                {isAI && (
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-cyan-500 flex items-center justify-center flex-shrink-0">
                    <Brain className="w-5 h-5 text-white" />
                  </div>
                )}

                <div
                  className={`flex flex-col max-w-3xl ${
                    isUser ? "items-end" : "items-start"
                  }`}
                >
                  <div
                    className={`rounded-2xl px-5 py-3 ${
                      isUser
                        ? "bg-gradient-to-r from-violet-500 to-cyan-500 text-white"
                        : isError
                        ? "bg-red-900/60 border border-red-500/50 text-red-50"
                        : "bg-white/5 border border-white/10 backdrop-blur-xl"
                    }`}
                  >
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">
                      {msg.content}
                    </p>
                    {msg.type === "stream" && !msg.done && (
                      <div className="mt-2 text-xs text-slate-400">
                        ⏳ streaming…
                      </div>
                    )}
                  </div>

                  {msg.type === "ai" && msg.sources?.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-2">
                      {msg.sources.map((source, i) => (
                        <span
                          key={i}
                          className="text-xs px-2 py-1 bg-white/5 rounded-full text-slate-400 border border-white/10"
                        >
                          {source.file_name} · p.{source.page}
                        </span>

                      ))}
                    </div>
                  )}

                  {msg.meta?.duration && (
                    <div className="flex items-center gap-2 mt-1 text-xs text-slate-500">
                      <Clock className="w-3 h-3" />
                      <span>{msg.meta.duration}ms</span>
                    </div>
                  )}
                </div>

                {isUser && (
                  <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center flex-shrink-0">
                    <MessageSquare className="w-5 h-5 text-slate-400" />
                  </div>
                )}
              </div>
            );
          })}

          {/* generic loading indicator in addition to streaming bubble */}
          {loading && (
            <div className="flex gap-4">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-cyan-500 flex items-center justify-center flex-shrink-0">
                <Brain className="w-5 h-5 text-white animate-pulse" />
              </div>
              <div className="flex gap-2 items-center bg-white/5 border border-white/10 rounded-2xl px-5 py-3">
                <div className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" />
                <div
                  className="w-2 h-2 bg-purple-400 rounded-full animate-bounce"
                  style={{ animationDelay: "0.1s" }}
                />
                <div
                  className="w-2 h-2 bg-cyan-400 rounded-full animate-bounce"
                  style={{ animationDelay: "0.2s" }}
                />
              </div>
            </div>
          )}
        </div>

        {/* INPUT BAR */}
        <div className="border-t border-white/5 bg-black/20 backdrop-blur-xl p-6">
          <div className="max-w-4xl mx-auto">
            <div className="relative">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendQuestion(e.currentTarget.value);
                  }
                }}
                placeholder="Ask anything from your library…"
                disabled={loading}
                className="w-full px-6 py-4 bg-white/5 border border-white/10 rounded-2xl text-white placeholder-slate-500 focus:outline-none focus:border-violet-500/50 focus:bg-white/10 transition-all disabled:opacity-50"
              />
              <button
                onClick={() => sendQuestion(question)}
                disabled={loading || !question.trim()}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-3 bg-gradient-to-r from-violet-500 to-cyan-500 rounded-xl hover:shadow-lg hover:shadow-violet-500/25 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Send className="w-5 h-5 text-white" />
              </button>
            </div>

            <div className="flex items-center justify-between mt-3 text-xs text-slate-500">
              <span>
                Powered by {currentModel} · {currentAgent} mode ·{" "}
                {useCloud ? "Cloud" : "Local"} RAG
              </span>
              <span>Press Enter to send • Shift+Enter for new line (soon)</span>
            </div>
          </div>
        </div>
      </div>

      {/* SETTINGS MODAL */}
      {settingsOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50"
          onClick={() => setSettingsOpen(false)}
        >
          <div
            className="bg-slate-900 border border-white/10 rounded-2xl p-6 max-w-md w-full mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-xl font-bold mb-2">Settings</h3>
            <p className="text-slate-400 text-sm mb-4">
              Future: tune BM25 vs semantic weight, chunk size, timeouts, cloud
              usage and more.
            </p>
            <button
              onClick={() => setSettingsOpen(false)}
              className="w-full px-4 py-2 bg-violet-500 hover:bg-violet-600 rounded-lg transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
