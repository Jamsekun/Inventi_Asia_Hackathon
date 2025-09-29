import React from 'react';
import './chat-widget.css';
import { useChat } from '../context/useChat';


export default function ChatToggleButton() {
  const { widgetMode, setWidgetMode } = useChat();

  const isOpen = widgetMode !== 'closed';

  function onClick() {
    if (widgetMode === 'closed') setWidgetMode('minimized');
    else if (widgetMode === 'minimized') setWidgetMode('maximized');
    else setWidgetMode('closed');
  }

  return (
    <button
      className={`chat-toggle-button ${isOpen ? 'open' : ''}`}
      aria-label={isOpen ? 'Close chat' : 'Open chat'}
      onClick={onClick}
    >
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
        <path d="M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10z" stroke="#fff" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    </button>
  );
}
