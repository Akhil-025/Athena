import React from "react";

export default function AgentSelector({ current, setCurrent, agents = ["Researcher","Teacher","Simplifier"] }) {
  return (
    <select value={current} onChange={(e)=>setCurrent(e.target.value)} className="px-2 py-1 rounded bg-white/5">
      {agents.map(a => <option key={a} value={a}>{a}</option>)}
    </select>
  );
}
