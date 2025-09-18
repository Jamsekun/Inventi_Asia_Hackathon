import React, { useEffect, useState, useRef } from "react";
import "@chatscope/chat-ui-kit-styles/dist/default/styles.min.css";
import { MessageInput } from "@chatscope/chat-ui-kit-react";
import "./index.css"; // ensure our styles load

// Simple helper to format time
function timeNow() {
  const d = new Date();
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function App() {
  // conversations: array of { id, title, messages: [{id, text, role, time}] }
  const [conversations, setConversations] = useState(() => {
    try {
      const raw = localStorage.getItem("conversations_v1");
      if (raw) return JSON.parse(raw);
    } catch (e) {}
    // default single conversation
    return [
      {
        id: Date.now(),
        title: "New conversation",
        messages: [
          { id: Date.now(), text: "Hello! I'm Akaza, Upper Bai 3", role: "bot", time: timeNow() },
        ],
      },
    ];
  });

  const [activeConvIndex, setActiveConvIndex] = useState(0);
  const [isTyping, setIsTyping] = useState(false);
  const [dark, setDark] = useState(() => {
    const val = localStorage.getItem("ui_theme");
    return val ? val === "dark" : true;
  });

  const listRef = useRef(null);

  // persist conversations and theme
  useEffect(() => {
    localStorage.setItem("conversations_v1", JSON.stringify(conversations));
  }, [conversations]);
  useEffect(() => {
    localStorage.setItem("ui_theme", dark ? "dark" : "light");
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  }, [dark]);

  const activeConv = conversations[activeConvIndex];

  // create a new conversation
  function newConversation() {
    const conv = {
      id: Date.now(),
      title: "New conversation",
      messages: [{ id: Date.now(), text: "New conversation started.", role: "bot", time: timeNow() }],
    };
    setConversations((prev) => [conv, ...prev]);
    setActiveConvIndex(0);
  }

  // delete conversation
  function deleteConversation(idx, e) {
    e?.stopPropagation();
    setConversations((prev) => {
      const next = prev.filter((_, i) => i !== idx);
      if (next.length === 0) {
        // create fresh conv
        return [
          {
            id: Date.now(),
            title: "New conversation",
            messages: [{ id: Date.now(), text: "New conversation started.", role: "bot", time: timeNow() }],
          },
        ];
      }
      return next;
    });
    setActiveConvIndex((cur) => (idx === cur ? 0 : cur > idx ? cur - 1 : cur));
  }

  // send message (from input)
  async function handleSend(text) {
    if (!text || !text.trim()) return;
    const msg = { id: Date.now(), text: text.trim(), role: "user", time: timeNow() };

    setConversations((prev) => {
      const copy = [...prev];
      const target = { ...copy[activeConvIndex] };
      target.messages = [...target.messages, msg];
      copy[activeConvIndex] = target;
      return copy;
    });

    // simulate typing + mock reply
    setIsTyping(true);
    // small scroll to bottom after adding message - do this on next tick
    setTimeout(() => scrollToBottom(), 20);

    // mock reply function — you already used similar logic; keep it simple
    const mockReply = (userText) =>
      new Promise((resolve) => {
        setTimeout(() => {
          // basic heuristics
          const lower = userText.toLowerCase();
          let reply = `Mock reply to: "${userText}"`;
          if (/(hi|hello|hey)\b/.test(lower)) reply = "Hello! How can I help you today?";
          else if (/explain\s+(.+)/.test(lower)) {
            const m = lower.match(/explain\s+(.+)/);
            reply = `Here's a short explanation of ${m?.[1] ?? "that topic"}.`;
          } else if (/summarize\s+(.+)/.test(lower)) {
            const m = lower.match(/summarize\s+(.+)/);
            reply = `Summary of ${m?.[1] ?? "that text"}: (mock summary)`;
          }

          resolve({ text: reply });
        }, 700 + Math.random() * 700);
      });

    const data = await mockReply(text);
    const botMsg = { id: Date.now() + 1, text: data.text, role: "bot", time: timeNow() };

    setConversations((prev) => {
      const copy = [...prev];
      const target = { ...copy[activeConvIndex] };
      target.messages = [...target.messages, botMsg];
      copy[activeConvIndex] = target;
      return copy;
    });

    setIsTyping(false);
    setTimeout(() => scrollToBottom(), 50);
  }

  // helper to scroll messages to bottom
  function scrollToBottom() {
    try {
      const el = document.getElementById("messages-scroll");
      if (el) el.scrollTop = el.scrollHeight;
    } catch (e) {}
  }

  // rename conversation title from first user message (optional)
  function setConversationTitle(idx, title) {
    setConversations((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], title };
      return next;
    });
  }

  return (
    <div className="app-root">
      <div className="chat-container-full">
        {/* Sidebar */}
        <aside className="sidebar">
          <div className="sidebar-top">
            <div className="brand">The Property Slayer</div>
            <button className="btn-new" onClick={newConversation}>
              + New
            </button>
          </div>

          <div className="conversations-list" ref={listRef}>
            {conversations.map((c, i) => (
              <div
                key={c.id}
                className={`conversation-item ${i === activeConvIndex ? "active" : ""}`}
                onClick={() => setActiveConvIndex(i)}
              >
                <div className="conversation-title">{c.title}</div>
                <div className="conversation-meta">
                  <button
                    className="small-delete"
                    title="Delete conversation"
                    onClick={(e) => deleteConversation(i, e)}
                  >
                    ×
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className="sidebar-footer">
            <div className="theme-toggle">
              <label className="toggle-label">Moon Breathing</label>
              <input
                type="checkbox"
                checked={dark}
                onChange={() => setDark((d) => !d)}
                aria-label="Toggle dark mode"
              />
            </div>
            <div className="small-print">Infinity Castle</div>
          </div>
        </aside>

        {/* Main chat column */}
        <section className="chat-column">
          {/* Topbar */}
          <div className="chat-topbar">
            <div className="chat-top-left">
              <div className="title">The Property Slayer</div>
              <div className="subtitle">MuzanGPT</div>
            </div>
            <div className="chat-top-right">
              <select
                value={"gpt-mock"}
                onChange={() => {}}
                aria-label="Model selector"
                className="model-select"
              >
                <option value="gpt-mock"></option>
              </select>
            </div>
          </div>

          {/* Messages */}
          <div id="messages-scroll" className="chat-messages" onLoad={scrollToBottom}>
            {activeConv?.messages?.map((m) => (
              <div
                key={m.id}
                className={`msg ${m.role === "user" ? "msg-user" : "msg-bot"}`}
                title={m.time}
              >
                <div className="msg-content">{m.text}</div>
                <div className="msg-time">{m.time}</div>
              </div>
            ))}

            {isTyping && (
              <div className="msg msg-bot typing">
                <div className="typing-dots">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            )}
          </div>

          {/* Input bar fixed at bottom */}
          <div className="chat-input">
            {/* Using Chatscope MessageInput for convenience */}
            <MessageInput placeholder="Send a message..." onSend={handleSend} />
          </div>
        </section>
      </div>
    </div>
  );
}
