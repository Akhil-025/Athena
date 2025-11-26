import React from "react";

export default function StreamingMessage({ message }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] p-4 rounded-2xl bg-white/5 text-slate-100">
        <pre style={{whiteSpace:'pre-wrap', margin:0}}>{message.content}</pre>
        {!message.done && <div className="mt-2 text-xs text-slate-400">⏳ streaming…</div>}
      </div>
    </div>
  );
}
