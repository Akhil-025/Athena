import React, { useState } from "react";
import { FileText, ChevronDown, ChevronUp, ArrowUpRight } from "lucide-react";
import PDFViewer from "./PDFViewer";

export default function SourcePreviewer({ sources = [], onFollowUp }) {
  const [open, setOpen] = useState(null);

  if (!sources || sources.length === 0) {
    return (
      <div className="p-4 text-slate-500 text-sm bg-slate-900/40 border border-white/5 rounded-xl">
        No sources detected.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {sources.map((src, i) => (
        <div key={i} className="bg-slate-900/60 border border-white/5 rounded-xl">
          <div className="p-3 flex items-center justify-between cursor-pointer hover:bg-white/5" onClick={() => setOpen(open === i ? null : i)}>
            <div className="flex items-center gap-2">
              <FileText size={16} className="text-indigo-300" />
              <span className="text-sm">{src.file_name || src.file || "unknown"}</span>
              <span className="text-xs text-slate-500">· Page {src.page || src.page_number || "?"}</span>
            </div>
            {open === i ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </div>

          {open === i && (
            <div className="p-3 space-y-4 border-t border-white/5">
              <div>
                <h4 className="text-xs uppercase text-slate-500 mb-1">Excerpt</h4>
                <div className="bg-black/30 p-3 rounded border border-white/5 text-sm text-slate-200 max-h-40 overflow-auto">
                  {src.text || src.document || "(no excerpt)"}
                </div>
              </div>

              {typeof src.score === "number" && <div className="text-xs text-slate-400">Similarity: <span className="text-indigo-300">{(1 - src.score).toFixed(2)}</span></div>}

              <button onClick={() => onFollowUp?.(`Explain this source:\n\n${src.text || src.document || ""}`)} className="flex items-center gap-1 text-xs text-indigo-300 hover:text-indigo-200">
                <ArrowUpRight size={12} /> Ask about this
              </button>

              { (src.file_path || src.file) && (
                <div className="h-56 border border-white/5 rounded-lg overflow-hidden">
                  <PDFViewer file={src.file_path || src.file} page={src.page || src.page_number || 1} />
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
