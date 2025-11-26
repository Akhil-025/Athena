import React, { useState, useEffect } from "react";

export default function VoiceControls({ onSend, disabled }) {
  const [listening, setListening] = useState(false);

  const start = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if(!SpeechRecognition) return alert("SpeechRecognition not supported");
    const r = new SpeechRecognition();
    r.lang = "en-IN";
    r.interimResults = true;
    r.onresult = (ev) => {
      const transcript = Array.from(ev.results).map(r=>r[0].transcript).join("");
      if(ev.results[ev.results.length-1].isFinal) {
        onSend(transcript);
      }
    };
    r.onerror = () => setListening(false);
    r.onend = () => setListening(false);
    r.start();
    setListening(true);
  };

  return (
    <div>
      <button onClick={()=>!disabled && start()} className={`px-3 py-2 rounded ${listening ? "bg-rose-500" : "bg-white/5"}`} title="Voice Input">
        { listening ? "Listening…" : "🎙️" }
      </button>
    </div>
  );
}
