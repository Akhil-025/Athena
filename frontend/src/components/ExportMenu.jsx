import React from "react";

export default function ExportMenu({ conversation = [] }) {
  const exportMarkdown = () => {
    let md = "# Athena Conversation\n\n";
    for(const m of conversation) {
      if(m.type === "user") md += `## Q: ${m.content}\n\n`;
      if(m.type === "ai") md += `### A:\n${m.content}\n\n`;
    }
    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "athena_conversation.md";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <button onClick={exportMarkdown} className="px-3 py-2 rounded bg-white/5">Export</button>
    </div>
  );
}
