import React, { useRef, useEffect } from "react";
import MessageItem from "./MessageItem";
import StreamingMessage from "./StreamingMessage";
import SourcePreviewer from "./SourcePreviewer";

export default function ChatWindow({ conversation = [], loading, onSend }) {
  const ref = useRef();

  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: "smooth" });
  }, [conversation, loading]);

  return (
    <div className="flex-1 p-4 overflow-auto" ref={ref}>
      <div className="space-y-6">
        {conversation.map((msg) => (
          <div key={msg.id}>
            {msg.type === "stream" ? (
              <StreamingMessage message={msg} />
            ) : (
              <MessageItem message={msg} />
            )}

            {msg.sources && msg.sources.length > 0 && (
              <div className="mt-3">
                <SourcePreviewer
                  sources={msg.sources}
                  onFollowUp={(q) => onSend(q)}
                />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
