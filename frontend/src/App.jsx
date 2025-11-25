import React, { useState } from "react";
import { createRoot } from "react-dom/client";

function App() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [useCloud, setUseCloud] = useState(false);
  const [conversation, setConversation] = useState([]);

  async function askQuestion() {
    if (!question.trim()) return;
    
    setLoading(true);
    const userQuestion = question;
    setQuestion(""); // Clear input immediately
    
    // Add user question to conversation
    const newConversation = [...conversation, { type: 'user', content: userQuestion }];
    setConversation(newConversation);
    
    try {
      const response = await fetch("http://127.0.0.1:5000/api/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: userQuestion,
          use_cloud: useCloud
        }),
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      // Add AI response to conversation
      setConversation(prev => [...prev, { 
        type: 'ai', 
        content: data.answer,
        mode: data.mode 
      }]);
      
    } catch (error) {
      console.error("Error:", error);
      setConversation(prev => [...prev, { 
        type: 'error', 
        content: `Failed to get answer: ${error.message}` 
      }]);
    } finally {
      setLoading(false);
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      askQuestion();
    }
  };

  const clearConversation = () => {
    setConversation([]);
    setAnswer("");
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      padding: '20px',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    }}>
      <div style={{
        maxWidth: '900px',
        margin: '0 auto',
        background: 'white',
        borderRadius: '20px',
        boxShadow: '0 20px 40px rgba(0,0,0,0.1)',
        overflow: 'hidden'
      }}>
        {/* Header */}
        <div style={{
          background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
          color: 'white',
          padding: '30px',
          textAlign: 'center'
        }}>
          <h1 style={{ margin: '0 0 10px 0', fontSize: '2.5rem', fontWeight: '700' }}>
            CADCAM Study Assistant
          </h1>
          <p style={{ margin: 0, opacity: 0.9, fontSize: '1.1rem' }}>
            Local-First AI with Optional Cloud Enhancement
          </p>
        </div>

        {/* Controls */}
        <div style={{
          padding: '20px',
          borderBottom: '1px solid #e5e7eb',
          background: '#f8fafc'
        }}>
          <div style={{
            display: 'flex',
            gap: '15px',
            alignItems: 'center',
            flexWrap: 'wrap'
          }}>
            <label style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              cursor: 'pointer',
              padding: '10px 15px',
              background: useCloud ? '#dcfce7' : '#f1f5f9',
              borderRadius: '10px',
              border: `2px solid ${useCloud ? '#22c55e' : '#cbd5e1'}`,
              fontWeight: '600',
              color: useCloud ? '#166534' : '#475569'
            }}>
              <input
                type="checkbox"
                checked={useCloud}
                onChange={(e) => setUseCloud(e.target.checked)}
                style={{ display: 'none' }}
              />
              <div style={{
                width: '20px',
                height: '20px',
                borderRadius: '50%',
                background: useCloud ? '#22c55e' : '#94a3b8',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'white',
                fontSize: '12px'
              }}>
                {useCloud ? '✓' : ''}
              </div>
              ☁️ Use Cloud AI
            </label>

            <button
              onClick={clearConversation}
              style={{
                padding: '10px 20px',
                background: '#ef4444',
                color: 'white',
                border: 'none',
                borderRadius: '10px',
                cursor: 'pointer',
                fontWeight: '600',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              🗑️ Clear Chat
            </button>

            <div style={{
              marginLeft: 'auto',
              padding: '8px 16px',
              background: useCloud ? '#fef3c7' : '#dbeafe',
              color: useCloud ? '#92400e' : '#1e40af',
              borderRadius: '8px',
              fontWeight: '600',
              fontSize: '14px'
            }}>
              {useCloud ? '☁️ Cloud Mode' : '💻 Local Mode'}
            </div>
          </div>
        </div>

        {/* Conversation */}
        <div style={{
          height: '500px',
          overflowY: 'auto',
          padding: '20px',
          background: '#f8fafc'
        }}>
          {conversation.length === 0 ? (
            <div style={{
              textAlign: 'center',
              color: '#64748b',
              padding: '60px 20px'
            }}>
              <div style={{ fontSize: '4rem', marginBottom: '20px' }}>🎓</div>
              <h3 style={{ marginBottom: '10px', color: '#475569' }}>
                Welcome to CADCAM Study Assistant!
              </h3>
              <p>Ask questions about CAD/CAM, CNC programming, transformations, and more.</p>
              <p style={{ marginTop: '10px', fontSize: '14px', opacity: 0.7 }}>
                Toggle cloud mode for enhanced answers (requires GOOGLE_API_KEY)
              </p>
            </div>
          ) : (
            conversation.map((item, index) => (
              <div
                key={index}
                style={{
                  marginBottom: '20px',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: item.type === 'user' ? 'flex-end' : 'flex-start'
                }}
              >
                <div style={{
                  maxWidth: '80%',
                  padding: '15px 20px',
                  borderRadius: '20px',
                  background: item.type === 'user' 
                    ? 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)' 
                    : item.type === 'error' ? '#fef2f2' : '#ffffff',
                  color: item.type === 'user' ? 'white' : '#1f2937',
                  border: item.type === 'error' ? '1px solid #fecaca' : '1px solid #e5e7eb',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word'
                }}>
                  {item.type === 'ai' && (
                    <div style={{
                      fontSize: '12px',
                      fontWeight: '600',
                      marginBottom: '8px',
                      color: useCloud ? '#059669' : '#2563eb',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px'
                    }}>
                      {useCloud ? '☁️' : '💻'} 
                      {useCloud ? 'Cloud AI' : 'Local AI'}
                    </div>
                  )}
                  {item.content}
                </div>
              </div>
            ))
          )}
          {loading && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '15px 20px',
              background: 'white',
              borderRadius: '20px',
              border: '1px solid #e5e7eb',
              marginBottom: '20px',
              maxWidth: 'fit-content'
            }}>
              <div style={{
                width: '20px',
                height: '20px',
                border: '2px solid #e5e7eb',
                borderTop: '2px solid #4f46e5',
                borderRadius: '50%',
                animation: 'spin 1s linear infinite'
              }}></div>
              <span style={{ color: '#6b7280', fontWeight: '600' }}>
                Thinking{useCloud ? ' with Cloud AI' : ' Locally'}...
              </span>
            </div>
          )}
        </div>

        {/* Input Area */}
        <div style={{
          padding: '20px',
          borderTop: '1px solid #e5e7eb',
          background: 'white'
        }}>
          <div style={{
            display: 'flex',
            gap: '10px',
            alignItems: 'flex-end'
          }}>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask about CAD/CAM, CNC programming, transformations..."
              style={{
                flex: 1,
                padding: '15px',
                border: '2px solid #e5e7eb',
                borderRadius: '15px',
                resize: 'none',
                fontFamily: 'inherit',
                fontSize: '16px',
                minHeight: '60px',
                maxHeight: '120px'
              }}
              rows="2"
            />
            <button
              onClick={askQuestion}
              disabled={loading || !question.trim()}
              style={{
                padding: '15px 25px',
                background: question.trim() && !loading 
                  ? 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)' 
                  : '#9ca3af',
                color: 'white',
                border: 'none',
                borderRadius: '15px',
                cursor: question.trim() && !loading ? 'pointer' : 'not-allowed',
                fontWeight: '600',
                fontSize: '16px',
                minWidth: '100px'
              }}
            >
              {loading ? '⏳' : '🚀'} Ask
            </button>
          </div>
          <div style={{
            fontSize: '12px',
            color: '#6b7280',
            marginTop: '8px',
            textAlign: 'center'
          }}>
            Press Enter to send, Shift+Enter for new line
          </div>
        </div>
      </div>

      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);