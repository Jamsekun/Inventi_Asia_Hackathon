import React, { createContext, useEffect, useState } from 'react';

const ChatContext = createContext(null);

export function ChatProvider({ children }) {
  function timeNow() {
    const d = new Date();
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  const [conversations, setConversations] = useState(() => {
    try {
      const raw = localStorage.getItem('conversations_v1');
      if (raw) return JSON.parse(raw);
    } catch {
      // ignore parse errors
    }
    return [
      {
        id: Date.now(),
        title: 'New conversation',
        messages: [{ id: Date.now(), text: 'Hello! I am InventiChat', role: 'bot', time: timeNow() }],
      },
    ];
  });

  const [activeIndex, setActiveIndex] = useState(0);
  const [isTyping, setIsTyping] = useState(false);
  // widgetMode: 'closed' | 'minimized' | 'maximized'
  const [widgetMode, setWidgetMode] = useState('closed');

  useEffect(() => {
    localStorage.setItem('conversations_v1', JSON.stringify(conversations));
  }, [conversations]);

  function newConversation() {
    const conv = {
      id: Date.now(),
      title: 'New conversation',
      messages: [{ id: Date.now(), text: 'Hello! I am InventiChat!', role: 'bot', time: timeNow() }],
    };
    setConversations((prev) => [conv, ...prev]);
    setActiveIndex(0);
  }

  function deleteConversation(idx) {
    setConversations((prev) => {
      const next = prev.filter((_, i) => i !== idx);
      if (next.length === 0) {
        return [
          {
            id: Date.now(),
            title: 'New conversation',
            messages: [{ id: Date.now(), text: 'Hello! I am InventiChat!', role: 'bot', time: timeNow() }],
          },
        ];
      }
      return next;
    });
    setActiveIndex((cur) => (idx === cur ? 0 : cur > idx ? cur - 1 : cur));
  }

  async function addUserMessage(text) {
    if (!text || !text.trim()) return;
    const msg = { id: Date.now(), text: text.trim(), role: 'user', time: timeNow() };
    setConversations((prev) => {
      const copy = [...prev];
      const target = { ...copy[activeIndex] };
      target.messages = [...target.messages, msg];
      copy[activeIndex] = target;
      return copy;
    });
    return msg;
  }

  const value = {
    conversations,
    setConversations,
    activeIndex,
    setActiveIndex,
    newConversation,
    deleteConversation,
    addUserMessage,
    isTyping,
    setIsTyping,
    widgetMode,
    setWidgetMode,
    openMinimized: () => setWidgetMode('minimized'),
    openMaximized: () => setWidgetMode('maximized'),
    closeWidget: () => setWidgetMode('closed'),
  };

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export default ChatContext;
