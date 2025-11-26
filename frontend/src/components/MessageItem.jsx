import React from "react";
import { marked } from "marked";

export default function MessageItem({ message }) {
  const isUser = message.type === "user";
  const isError = message.type === "error";
  const isAi = message.type === "ai";

  const classes = isUser ? "self-end bg-indigo-600 text-white" : isError ? "bg-red-900/60 text-red-100 border border-red-500/30" : "bg-white/5 text-slate-100";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[80%] p-4 rounded-2xl ${classes}`}>
        {isUser && <div className="whitespace-pre-wrap">{message.content}</div>}
        {isError && <div className="whitespace-pre-wrap">{message.content}</div>}
        {isAi && <div dangerouslySetInnerHTML={{ __html: marked.parse(message.content || "") }} />}

        {isAi && (
          <div className="mt-3 text-xs text-slate-400 flex gap-2 flex-wrap">
            <div>{message.mode === "cloud" ? "Cloud" : "Local"}</div>
            {message.cached && <div className="text-emerald-300">Cached</div>}
            {message.sources && message.sources.length>0 && <div>{message.sources.length} sources</div>}
          </div>
        )}
      </div>
    </div>
  );
}
