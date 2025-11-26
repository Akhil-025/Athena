import React from "react";

export default function SettingsModal({ open=false, onClose=()=>{} }) {
  if(!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-slate-900 border border-white/10 p-6 rounded-lg max-w-2xl w-full">
        <h3 className="text-lg font-bold mb-4">Settings</h3>
        <div className="text-sm text-slate-300">Controls: BM25 weight, chunk size, model timeouts can be added here.</div>
        <div className="mt-6 flex justify-end">
          <button onClick={onClose} className="px-3 py-2 rounded bg-white/5">Close</button>
        </div>
      </div>
    </div>
  );
}
