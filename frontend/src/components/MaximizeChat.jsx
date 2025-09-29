import React, { useEffect, useRef, useState, useCallback } from 'react';
import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';
import { useChat } from '../context/useChat';
import { sendChat } from '../chat_api';
import './chat-widget.css';

const md = new MarkdownIt({
  breaks: true,
  linkify: true,
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(str, { language: lang }).value;
      } catch {
        // fall through - ignore highlighting errors
      }
    }
    return '';
  }
});

export default function MaximizeChat() {
  const {
    conversations,
    setConversations,
    activeIndex,
    addUserMessage,
    isTyping,
  } = useChat();

  const idx = typeof activeIndex === 'number' ? activeIndex : 0;
  const activeConv = conversations[idx] || { messages: [], title: 'Conversation' };

  const [input, setInput] = useState('');
  const [numRows, setNumRows] = useState(1);
  const [pending, setPending] = useState(false);
  const [errors, setErrors] = useState([]);

  const scrollingRef = useRef(null);
  const inputRef = useRef(null);
  const userScrolled = useRef(false);

  const autoScrollDown = useCallback(() => {
    if (scrollingRef.current && !userScrolled.current) {
      scrollingRef.current.scrollTop = scrollingRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    autoScrollDown();
  }, [conversations, isTyping, autoScrollDown]);

  function checkIfUserScrolled() {
    if (scrollingRef.current) {
      userScrolled.current = scrollingRef.current.scrollTop + scrollingRef.current.clientHeight !== scrollingRef.current.scrollHeight;
    }
  }

  async function handleSend() {
    const clean = (input || '').trim();
    if (!clean) return;
    try {
      setPending(true);
      userScrolled.current = false;
      if (inputRef.current) inputRef.current.blur();
      await addUserMessage(clean);
      setInput('');
      autoScrollDown();

      // Prepare backend messages and send
      const currentConversation = conversations[activeIndex] || { messages: [] };
      const backendMessages = (currentConversation.messages || []).map((m) => ({ role: m.role, content: m.text }));
      const response = await sendChat(backendMessages);

      const assistantText = (response && (response.response || response.answer || response.text)) || 'Sorry, no response.';
      const assistantReply = { id: Date.now() + 1, text: assistantText, role: 'assistant', time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) };

      setConversations((prev) => {
        const copy = [...prev];
        const target = { ...(copy[idx] || {}) };
        target.messages = [...(target.messages || []), assistantReply];
        copy[idx] = target;
        return copy;
      });
    } catch (_) {
      // log to console for debugging
      // error details intentionally ignored to satisfy linter for unused var
      console.error(_);
      setErrors((prev) => [...prev, { id: Date.now(), message: _?.message || String(_) }]);
    } finally {
      setPending(false);
    }
  }

  function handleKeyDown(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSend();
    }
  }

  function removeError(id) {
    setErrors((prev) => prev.filter((x) => x.id !== id));
  }

  return (
    <div className="inventi-root" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Alerts (errors) */}
      <div style={{ padding: 12 }}>
        {errors.map((err) => (
          <div key={err.id} style={{ background: '#fee2e2', color: '#7f1d1d', padding: 10, borderRadius: 8, marginBottom: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>{err.message}</div>
              <button onClick={() => removeError(err.id)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: '#7f1d1d' }}>✕</button>
            </div>
          </div>
        ))}
      </div>

      {/* Messages scroll area */}
      <main ref={scrollingRef} onScroll={checkIfUserScrolled} style={{ flex: 1, padding: 16, overflow: 'auto' }}>
        {activeConv?.messages?.map((message, index) => (
          <div key={message.id || index} style={{ display: 'flex' }}>
            {message.role === 'user' ? (
                <div
                    className="message-content bubble-user animated"
                    dangerouslySetInnerHTML={{ __html: md.render(message.text || message.content || '') }}
                />
                ) : (
                <div
                    className="message-content bubble-bot animated"
                    dangerouslySetInnerHTML={{ __html: md.render(message.text || message.content || '') }}
                />
            )}

          </div>
        ))}
      </main>

      {/* Input area */}
      <div style={{ display: 'flex', width: '100%', padding: 16, alignItems: 'flex-end' }} onFocus={() => setNumRows(10)} onBlur={() => setNumRows(1)}>
        <textarea
          ref={inputRef}
          className="input-textarea"
          rows={numRows}
          placeholder={pending ? 'Answering...' : `Chat...`}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={pending}
          style={{ flex: 1, padding: 10, borderRadius: 8, border: '1px solid var(--border)', background: 'var(--panel-bg)' }}
        />

        <button onClick={handleSend} disabled={pending || input.trim().length === 0} style={{ marginLeft: 12, padding: '10px 12px', borderRadius: 8, background: 'var(--accent)', color: '#fff', border: 'none', cursor: 'pointer' }}>
          {!pending ? (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M5 12L19 5L12 19L5 12Z" fill="currentColor"/></svg>
          ) : (
            <span style={{ display: 'inline-block', width: 18, height: 18, border: '2px solid rgba(255,255,255,0.6)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
          )}
        </button>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } } .input-textarea:disabled { opacity: 0.6; } .message-content pre { background: #f8fafc; padding: 8px; border-radius: 6px; }`}</style>
    </div>
  );
}

