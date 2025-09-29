import React, { useState } from 'react';
import "@chatscope/chat-ui-kit-styles/dist/default/styles.min.css";
import './index.css';
import { ChatProvider } from './context/ChatContext';
import { useChat } from './context/useChat';
import ChatToggleButton from './components/ChatToggleButton';
import ChatWidget from './components/ChatWidget';
import MaximizeChat from './components/MaximizeChat';

function Sidebar() {
  const { conversations, setConversations, activeIndex, setActiveIndex, newConversation, deleteConversation } = useChat();
  const [editing, setEditing] = useState(null);

  function rename(idx, value) {
    setConversations((prev) => {
      const copy = [...prev];
      copy[idx] = { ...copy[idx], title: value };
      return copy;
    });
  }

  return (
    <aside className="inventi-sidebar">
      <div className="sidebar-header">
        <div className="brand">
          <div className="brand-logo">INVENTI</div>
          <div className="brand-name">Conversations</div>
        </div>
        <button className="btn-primary btn-new" onClick={newConversation}>+ New</button>
      </div>
        <button
          className="btn-minimize"
          onClick={() => { window.location.pathname = '/minimize'; }}
          title="Minimize Chat"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <line x1="5" y1="12" x2="19" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <span style={{ marginLeft: 6 }}>Minimize</span>
        </button>
      <div className="conversations" role="list">
        {conversations.map((c, i) => (
          <div key={c.id} role="button" className={`conv-item ${i === activeIndex ? 'active' : ''}`} onClick={() => setActiveIndex(i)}>
            {editing === i ? (
              <input autoFocus className="conv-input" defaultValue={c.title} onBlur={(e) => { rename(i, e.target.value); setEditing(null); }} />
            ) : (
              <div className="conv-title-row">
                <div className="conv-title">{c.title || `Chat ${i+1}`}</div>
                <div className="conv-actions">
                  <button className="conv-edit" onClick={(e) => { e.stopPropagation(); setEditing(i); }}>✎</button>
                  <button className="conv-delete" onClick={(e) => { e.stopPropagation(); deleteConversation(i); }}>×</button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="sidebar-footer">
        <div className="small-note">Team PropertySlayers: Infinity Condo • James, Andrew, Romeo</div>
      </div>
    </aside>
  );
}

function MainChat() {
  // The chat widget is now full page in center; reuse ChatWidget for rendering input and messages
  const { openMaximized } = useChat();
  React.useEffect(() => { openMaximized(); }, [openMaximized]);
  return (
    <main className="inventi-main">
        <ChatWidget embedded />
    </main>
  );
}

export default function App() {
  // Simple route handling without adding react-router.
  const pathname = typeof window !== 'undefined' ? window.location.pathname : '/';
  // persistent toggle state for the minimize route (hooks must be called unconditionally)
  const [minimizeOpen, setMinimizeOpen] = useState(true);

  // /maximize -> full UI: sidebar + main chat (no floating toggle)
  if (pathname === '/maximize') {
    return (
      <ChatProvider>
        <header className="site-topbar">
          <div className="site-brand">
            <div className="site-logo">inventi</div>
            <div className="site-tag">All-in-one property management</div>
          </div>
        </header>

        <div className="inventi-root">
          <div className="inventi-layout">
            <Sidebar />
            <main className="inventi-main">
              <MaximizeChat />
            </main>
          </div>
        </div>
      </ChatProvider>
    );
  }

  // /minimize -> blank background and only the popup should be visible
  if (pathname === '/minimize') {
    return (
      <ChatProvider>
        <div className="minimized-route-root">
          {/* blank background handled by CSS */}
          <button className={`minimize-toggle-button ${minimizeOpen ? 'open' : 'closed'}`} onClick={() => setMinimizeOpen(v => !v)} aria-pressed={minimizeOpen} title={minimizeOpen ? 'Close chat' : 'Open chat'}>
            {/* simple message icon (SVG) */}
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10z" stroke="#fff" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
          {minimizeOpen && <ChatWidget />}
        </div>
      </ChatProvider>
    );
  }

  // default app: layout + floating toggle
  return (
    <ChatProvider>
      <header className="site-topbar">
        <div className="site-brand">
          <div className="site-logo">inventi</div>
          <div className="site-tag">All-in-one property management</div>
        </div>
      </header>

      <div className="inventi-root">
        <div className="inventi-layout">
          <Sidebar />
          <MainChat />
        </div>
      </div>

      <ChatToggleButton />
    </ChatProvider>
  );
}

