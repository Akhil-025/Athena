import React from "react";
import { Sparkles, Layers, FileText } from "lucide-react";

export default function Sidebar({
  stats,
  onOpenPlugins,
  currentAgent,
  setCurrentAgent,
  currentModel,
  setCurrentModel,
  models,
  agents
}) {
  return (
    <aside className="w-72 border-r border-white/6 p-4 bg-gradient-to-b from-black/20 to-transparent flex flex-col">
      <div className="mb-6">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-gradient-to-br from-indigo-600 to-purple-600 rounded-lg">
            <Sparkles size={18} />
          </div>
          <div>
            <h1 className="text-lg font-bold">Athena</h1>
            <div className="text-xs text-slate-400">Local Research AI</div>
          </div>
        </div>
      </div>

      <div className="mb-4">
        <h3 className="text-xs text-slate-400 uppercase">Subjects</h3>
        <div className="mt-2 flex flex-col gap-2">
          {(stats.subjects || []).slice(0, 10).map((s) => (
            <button key={s} className="text-left text-sm py-2 px-3 rounded hover:bg-white/5">
              {s}
            </button>
          ))}
          {(!stats.subjects || stats.subjects.length === 0) && (
            <div className="text-sm text-slate-500">No subjects loaded</div>
          )}
        </div>
      </div>

      <div className="mb-4">
        <h3 className="text-xs text-slate-400 uppercase">Modules</h3>
        <div className="mt-2 flex flex-col gap-2">
          {(stats.modules || []).slice(0, 12).map((m) => (
            <div key={m} className="text-sm py-2 px-3 rounded hover:bg-white/5 flex items-center gap-2">
              <Layers size={14} /> {m}
            </div>
          ))}
        </div>
      </div>

      <div className="mt-6">
        <h3 className="text-xs text-slate-400 uppercase">Quick Tools</h3>
        <div className="mt-2 flex flex-col gap-2">
          <button className="flex items-center gap-2 px-3 py-2 rounded hover:bg-white/5" onClick={onOpenPlugins}>
            <FileText size={14} /> Plugins
          </button>
          <span className="text-xs text-slate-400 mt-4 block">Built-in: PYQ Solver, LectureGen</span>
        </div>
      </div>

      <div className="mt-auto text-xs text-slate-500">
        <div className="mt-6">Model: <span className="font-medium">{currentModel}</span></div>
        <div className="mt-1">Agent: <span className="font-medium">{currentAgent}</span></div>
      </div>
    </aside>
  );
}
