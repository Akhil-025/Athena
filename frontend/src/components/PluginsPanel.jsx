import React from "react";

export default function PluginsPanel({ visible=false }) {
  if(!visible) return null;
  const plugins = (window.athenaPlugins || []).concat([
    {id:"pyq-solver", name:"PYQ Solver", run: ()=>alert("Run PYQ Solver")},
    {id:"lecture-gen", name:"Lecture Generator", run: ()=>alert("Run Lecture Generator")}
  ]);
  return (
    <div className="bg-white/3 p-3 rounded">
      <h4 className="text-xs text-slate-300 mb-2">Plugins</h4>
      <div className="flex flex-col gap-2">
        {plugins.map(p => <button key={p.id} onClick={()=>p.run()} className="text-left px-3 py-2 bg-white/5 rounded">{p.name}</button>)}
      </div>
    </div>
  );
}
