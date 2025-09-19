import React, { useEffect, useState } from "react";
import "@chatscope/chat-ui-kit-styles/dist/default/styles.min.css";
import { MessageInput } from "@chatscope/chat-ui-kit-react";
import "./index.css";

function timeNow() {
  const d = new Date();
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function App() {
  // conversations (persisted)
  const [conversations, setConversations] = useState(() => {
    try {
      const raw = localStorage.getItem("conversations_v1");
      if (raw) return JSON.parse(raw);
    } catch (e) {}
    return [
      {
        id: Date.now(),
        title: "New conversation",
        messages: [{ id: Date.now(), text: "Hello! I am InventiChat", role: "bot", time: timeNow() }],
      },
    ];
  });

  const [activeIndex, setActiveIndex] = useState(0);
  const [isTyping, setIsTyping] = useState(false);
  const [themeDark, setThemeDark] = useState(() => {
    const v = localStorage.getItem("ui_theme");
    return v ? v === "dark" : true;
  });

  // NEW: widget open state (floating chat)
  const [widgetOpen, setWidgetOpen] = useState(false);

  // NEW: menu open state inside chat header
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    localStorage.setItem("conversations_v1", JSON.stringify(conversations));
  }, [conversations]);

  useEffect(() => {
    localStorage.setItem("ui_theme", themeDark ? "dark" : "light");
    document.documentElement.setAttribute("data-theme", themeDark ? "dark" : "light");
  }, [themeDark]);

  const activeConv = conversations[activeIndex];

  function newConversation() {
    const conv = {
      id: Date.now(),
      title: "New conversation",
      messages: [{ id: Date.now(), text: "Hello! I am InventiChat!", role: "bot", time: timeNow() }],
    };
    setConversations((prev) => [conv, ...prev]);
    setActiveIndex(0);
    setMenuOpen(false);
  }

  function deleteConversation(idx, e) {
    e?.stopPropagation();
    setConversations((prev) => {
      const next = prev.filter((_, i) => i !== idx);
      if (next.length === 0) {
        return [
          {
            id: Date.now(),
            title: "New conversation",
            messages: [{ id: Date.now(), text: "Hello! I am InventiChat!", role: "bot", time: timeNow() }],
          },
        ];
      }
      return next;
    });
    setActiveIndex((cur) => (idx === cur ? 0 : cur > idx ? cur - 1 : cur));
  }

  function mockReply(userText) {
    return new Promise((resolve) => {
      setTimeout(() => {
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
  }

  async function handleSend(text) {
    if (!text || !text.trim()) return;
    const msg = { id: Date.now(), text: text.trim(), role: "user", time: timeNow() };

    setConversations((prev) => {
      const copy = [...prev];
      const target = { ...copy[activeIndex] };
      target.messages = [...target.messages, msg];
      copy[activeIndex] = target;
      return copy;
    });

    setIsTyping(true);
    setTimeout(() => {
      const el = document.getElementById("messages-scroll-widget");
      if (el) el.scrollTop = el.scrollHeight;
    }, 20);

    const data = await mockReply(text);
    const botMsg = { id: Date.now() + 1, text: data.text, role: "bot", time: timeNow() };

    setConversations((prev) => {
      const copy = [...prev];
      const target = { ...copy[activeIndex] };
      target.messages = [...target.messages, botMsg];
      copy[activeIndex] = target;
      return copy;
    });

    setIsTyping(false);
    setTimeout(() => {
      const el = document.getElementById("messages-scroll-widget");
      if (el) el.scrollTop = el.scrollHeight;
    }, 50);
  }

  // helper to open widget and scroll to bottom
  function openWidget() {
    setWidgetOpen(true);
    setTimeout(() => {
      const el = document.getElementById("messages-scroll-widget");
      if (el) el.scrollTop = el.scrollHeight;
    }, 80);
  }

  // when selecting conversation from menu, activate and close menu
  function selectConversationFromMenu(idx) {
    setActiveIndex(idx);
    setMenuOpen(false);
    openWidget();
  }

  return (
    <>
      {/* Top page header (centered Inventi + tagline) */}
      <header className="site-topbar">
        <div className="site-brand">
          <div className="site-logo">inventi</div>
          <div className="site-tag">All-in-one property management</div>
        </div>
      </header>

      {/* Main layout remains behind — kept for larger screens if you like */}
      <div className="inventi-root">
        <div className="inventi-layout">
          {/* Left sidebar still available on wide screens */}
          <aside className="inventi-sidebar">
            <div className="sidebar-header">
              <div className="brand">
                <div className="brand-logo">INVENTI</div>
                <div className="brand-name">Inventi</div>
              </div>
              <button className="btn-primary btn-new" onClick={newConversation}>
                + New
              </button>
            </div>

            <div className="conversations" role="list">
              {conversations.map((c, i) => (
                <div
                  key={c.id}
                  role="button"
                  className={`conv-item ${i === activeIndex ? "active" : ""}`}
                  onClick={() => setActiveIndex(i)}
                >
                  <div className="conv-title">{c.title}</div>
                  <div className="conv-actions">
                    <button className="conv-delete" title="Delete conversation" onClick={(e) => deleteConversation(i, e)}>
                      ×
                    </button>
                  </div>
                </div>
              ))}
            </div>

            <div className="sidebar-footer">
              <div className="toggle-row">
                <label className="toggle-label">Dark</label>
                <input type="checkbox" checked={themeDark} onChange={() => setThemeDark((d) => !d)} />
              </div>
              <div className="small-note">Local demo • No keys</div>
            </div>
          </aside>

          {/* Main column (kept but your floating widget will overlap if opened) */}
          <main className="inventi-main" aria-hidden={widgetOpen ? "true" : "false"}>
            <div className="main-topbar">
              <div className="title-area">
                <div className="main-title">The Property Slayer</div>
              </div>
              <div className="top-actions">
                <select className="model-select" value={"gpt-mock"} onChange={() => {}} aria-label="Model selector">
                  <option value="gpt-mock"></option>
                </select>
              </div>
            </div>

            <section id="messages-scroll" className="messages-area" aria-live="polite">
              {activeConv?.messages?.map((m) => (
                <div key={m.id} className={`bubble ${m.role === "user" ? "bubble-user" : "bubble-bot"}`}>
                  <div className="bubble-text">{m.text}</div>
                  <div className="bubble-meta">{m.time}</div>
                </div>
              ))}

              {isTyping && (
                <div className="bubble bubble-bot typing">
                  <div className="typing-dots">
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              )}
            </section>

            <div className="input-bar">
              <MessageInput placeholder="Ask about properties or type a question..." onSend={handleSend} />
            </div>
          </main>
        </div>
      </div>

      {/* Floating chat toggle button (bottom-right) */}
      <button
        className={`chat-toggle-button ${widgetOpen ? "open" : ""}`}
        aria-label="Open chat"
        onClick={() => (widgetOpen ? setWidgetOpen(false) : openWidget())}
      >
        {/* simple message icon (SVG) */}
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
          <path d="M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10z" stroke="#fff" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
        </svg> 
      </button>

      {/* Floating widget: appears bottom-right when widgetOpen */}
      {widgetOpen && (
        <div className="inventi-widget" role="dialog" aria-modal="true" aria-label="Chat widget">
          <div className="widget-header">
            <div className="widget-left">
              <button
                className="widget-menu-button"
                title="Menu"
                onClick={() => setMenuOpen((s) => !s)}
                aria-expanded={menuOpen}
              >
                ≪
              </button>
              <div className="widget-title">InventiChat</div>
            </div>

            <div className="widget-right">
              <button className="widget-minimize" title="Close chat" onClick={() => setWidgetOpen(false)}>
                ✕
              </button>
            </div>

            {/* menu panel (small) */}
            {menuOpen && (
              <div className="menu-panel" role="menu">
                <div className="menu-panel-header">
                  <strong>Conversations</strong>
                </div>
                <div className="menu-list">
                  <button className="menu-new" onClick={newConversation}>+ New Conversation</button>
                  {conversations.map((c, i) => (
                    <button key={c.id} className="menu-item" onClick={() => selectConversationFromMenu(i)}>
                      {c.title}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* widget messages (same content but separate id/scroll target) */}
          <div id="messages-scroll-widget" className="widget-messages">
            {activeConv?.messages?.map((m) => (
              <div key={m.id} className={`bubble ${m.role === "user" ? "bubble-user" : "bubble-bot"}`}>
                <div className="bubble-text">{m.text}</div>
                <div className="bubble-meta">{m.time}</div>
              </div>
            ))}
            {isTyping && (
              <div className="bubble bubble-bot typing">
                <div className="typing-dots">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            )}
          </div>

          <div className="widget-input">
            <MessageInput placeholder="Ask about properties..." onSend={handleSend} />
          </div>
        </div>
      )}
    </>
  );
}
