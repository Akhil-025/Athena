import { Cpu } from "lucide-react";
import React from "react";

export default function InputBar({ question, setQuestion, onSend, loading }) {
  return (
    <div className="p-4 border-t border-white/10 bg-slate-900/80">
      <div className="flex items-end gap-3">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSend(question);
            }
          }}
          placeholder="Ask Athena…"
          rows={1}
          className="flex-1 bg-slate-800 text-white p-3 rounded-xl resize-none border border-white/10 focus:ring-2 focus:ring-indigo-500"
        />

        <button
          disabled={!question.trim() || loading}
          onClick={() => onSend(question)}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-600 px-4 py-3 rounded-xl text-white flex items-center justify-center"
        >
          <Cpu size={20} />
        </button>
      </div>
    </div>
  );
}
