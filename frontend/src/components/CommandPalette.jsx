import React, { useEffect, useState } from "react";

/**
 * Simple Command Palette that listens to `open:palette` event
 * and dispatches an `athena:send` custom event with {question}
 */
export default function CommandPalette({ onSend }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");

  useEffect(() => {
    const handler = () => setOpen(true);
    document.addEventListener("open:palette", handler);
    return () => document.removeEventListener("open:palette", handler);
  }, []);

  useEffect(() => {
    if(open) {
      const esc = (e) => { if(e.key === "Escape") setOpen(false); };
      window.addEventListener("keydown", esc);
      return () => window.removeEventListener("keydown", esc);
    }
  }, [open]);

  function submit() {
    setOpen(false);
    if(!q.trim()) return;
    document.dispatchEvent(new CustomEvent("athena:send", { detail: { question: q } }));
    setQ("");
  }

  if(!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 px-4">
      <div className="w-full max-w-2xl bg-black/70 border border-white/10 rounded-xl p-4 backdrop-blur">
        <input autoFocus value={q} onChange={(e)=>setQ(e.target.value)} onKeyDown={(e)=>e.key==='Enter' && submit()} placeholder="Run command or ask Athena..." className="w-full bg-transparent p-3 outline-none text-white text-lg" />
        <div className="mt-3 text-xs text-slate-400">Press Enter to run • Esc to close</div>
      </div>
    </div>
  );
}
