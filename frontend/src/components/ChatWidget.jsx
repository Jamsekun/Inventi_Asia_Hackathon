import React, { useEffect, useRef } from 'react';
import { MessageInput } from '@chatscope/chat-ui-kit-react';
import { useChat } from '../context/useChat';
import { sendChat } from '../chat_api';
import './chat-widget.css';

function timeNow() {
  const d = new Date();
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export default function ChatWidget({ embedded = false }) {
  const { conversations, setConversations, activeIndex, setActiveIndex, addUserMessage, isTyping, setIsTyping, widgetMode, setWidgetMode, newConversation } = useChat();
  const scrollRef = useRef(null);
  const pathname = typeof window !== 'undefined' ? window.location.pathname : '/';

  useEffect(() => {
    if ((widgetMode === 'maximized' || widgetMode === 'minimized') && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [widgetMode, conversations]);

  async function handleSend(text) {
    const clean = (text || '').trim();
    if (!clean) return;
    const msg = await addUserMessage(clean);
    setIsTyping(true);
    try {
      const currentConversation = conversations[activeIndex];
      const fullMessages = [...currentConversation.messages, msg];
      const backendMessages = fullMessages.map((m) => ({ role: m.role, content: m.text }));
      const request = await sendChat(backendMessages);
      const assistantReply = { id: Date.now()+1, text: request.response, role: 'assistant', time: timeNow() };
      setConversations((prev) => {
        const copy = [...prev];
        const target = { ...copy[activeIndex] };
        target.messages = [...target.messages, assistantReply];
        copy[activeIndex] = target;
        return copy;
      });
    } catch (err) {
      console.error('Chat error:', err);
    } finally {
      setIsTyping(false);
    }
  }

  const activeConv = conversations[activeIndex];

  // If this page is the dedicated /minimize route, always show popup (ignore widgetMode closed state)
        if (pathname === '/minimize') {
            const last = conversations[activeIndex]?.messages?.slice(-1)[0];
            return (
            <div
        className={`inventi-widget ${widgetMode === 'minimized' ? 'minimized' : 'fullpage'} animated slide-in`}
        role="dialog"
        aria-modal="true"
        style={{ resize: 'both', overflow: 'auto' }}
        >

        <div className="widget-header">
          <div className="widget-left">
            <div className="widget-title">InventiChat</div>
          </div>
          <div className="widget-right">
            {/* maximize with SVG + text */}
            <button className="widget-minimize" onClick={() => window.location.pathname = '/maximize'} title="Maximize">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="5" y="5" width="14" height="14" stroke="currentColor" strokeWidth="2" rx="2" />
              </svg>
              <strong style={{marginLeft:8}}>Maximize</strong>
            </button>
          </div>
        </div>
        <div className="widget-messages small-preview">
          <div className={`bubble ${last?.role === 'user' ? 'bubble-user' : 'bubble-bot'}`}>
            <div className="bubble-text">{last?.text}</div>
            <div className="bubble-meta">{last?.time}</div>
          </div>
        </div>
        <div className="widget-input">
          <MessageInput placeholder="Ask about properties..." onSend={handleSend} />
        </div>
      </div>
    );
  }

  // If the page is /maximize we want the chat as a centered, full-page element (no floating toggle)
  if (pathname === '/maximize' || embedded) {
    if (!conversations[activeIndex]) return null;
    return (
      <div className={`inventi-widget fullpage animated slide-in`} role="dialog" aria-modal="true">
        <div className="widget-header">
          <div className="widget-left">
            <button className="widget-menu-button" onClick={() => newConversation()} title="New">+</button>
            <div className="widget-title">InventiChat</div>
          </div>
          <div className="widget-right">
            <button className="widget-minimize" onClick={() => { if (pathname === '/maximize') window.location.pathname = '/minimize'; else setWidgetMode('minimized'); }} title="Minimize">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <line x1="5" y1="12" x2="19" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
              <strong style={{marginLeft:8}}>Minimize</strong>
            </button>
          </div>
        </div>

        <div id="messages-scroll-widget" ref={scrollRef} className="widget-messages">
          {conversations[activeIndex]?.messages?.map((m) => (
            <div key={m.id} className={`bubble ${m.role === 'user' ? 'bubble-user' : 'bubble-bot'}`}>
              <div className="bubble-text">{m.text}</div>
              <div className="bubble-meta">{m.time}</div>
            </div>
          ))}
          {isTyping && (
            <div className="bubble bubble-bot typing">
              <div className="typing-dots"><span/><span/><span/></div>
            </div>
          )}
        </div>

        <div className="widget-input">
          <MessageInput placeholder="Ask about properties..." onSend={handleSend} />
        </div>
      </div>
    );
  }

  // default floating behavior for widgetMode
  if (widgetMode === 'closed') return null;

  // minimized preview card
  if (widgetMode === 'minimized') {
    const last = conversations[activeIndex]?.messages?.slice(-1)[0];
    return (
      <div className="inventi-widget minimized animated fade-in" role="dialog">
        <div className="widget-header">
          <div className="widget-left">
            <div className="widget-title">InventiChat</div>
          </div>
          <div className="widget-right">
            <button className="widget-minimize" onClick={() => setWidgetMode('closed')} title="Close">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path d="M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10z" stroke="#fff" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
            <button className="widget-minimize" onClick={() => setWidgetMode('maximized')} title="Maximize">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="5" y="5" width="14" height="14" stroke="currentColor" strokeWidth="2" rx="2" />
              </svg>
              <strong style={{marginLeft:8}}>Maximize</strong>
            </button>
          </div>
        </div>
        <div className="widget-messages small-preview">
          <div className={`bubble ${last?.role === 'user' ? 'bubble-user' : 'bubble-bot'}`}>
            <div className="bubble-text">{last?.text}</div>
            <div className="bubble-meta">{last?.time}</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`inventi-widget animated slide-in`} role="dialog" aria-modal="true">
      <div className="widget-header">
        <div className="widget-left">
          <button className="widget-menu-button" onClick={() => newConversation()} title="New">＋</button>
          <div className="widget-title">InventiChat</div>
        </div>
          <div className="widget-right">
            <button className="widget-minimize" onClick={() => setWidgetMode('minimized')} title="Minimize">▾</button>
            <button className="widget-minimize" onClick={() => setWidgetMode('closed')} title="Close">✕</button>
          </div>
      </div>

      <div id="messages-scroll-widget" ref={scrollRef} className="widget-messages">
        {activeConv?.messages?.map((m) => (
          <div key={m.id} className={`bubble ${m.role === 'user' ? 'bubble-user' : 'bubble-bot'}`}>
            <div className="bubble-text">{m.text}</div>
            <div className="bubble-meta">{m.time}</div>
          </div>
        ))}
        {isTyping && (
          <div className="bubble bubble-bot typing">
            <div className="typing-dots"><span/><span/><span/></div>
          </div>
        )}
      </div>

      <div className="widget-input">
        <MessageInput placeholder="Ask about properties..." onSend={handleSend} />
      </div>
    </div>
  );
}
