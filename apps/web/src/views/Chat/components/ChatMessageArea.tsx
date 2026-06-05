import React, { useEffect, useRef } from 'react';
import { Bot } from 'lucide-react';
import { ChatMessageItem, type Message } from './ChatMessageItem';

export interface ChatMessageAreaProps {
  messages: Message[];
  isStreaming: boolean;
  isDarkMode: boolean;
}

export const ChatMessageArea: React.FC<ChatMessageAreaProps> = ({
  messages,
  isStreaming,
  isDarkMode,
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom whenever messages list updates or streaming starts/stops
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isStreaming]);

  return (
    <div
      style={{
        flex: 1,
        minHeight: 0,
        overflowY: 'auto',
        padding: '12px 8px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
        borderRadius: '12px',
        background: isDarkMode ? '#0b0f17' : '#f9fafb',
        border: '1px solid var(--border-color, #e5e7eb)',
        marginBottom: '20px',
      }}
    >
      {messages.length === 0 ? (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            color: '#9ca3af',
            gap: '8px',
          }}
        >
          <Bot size={40} strokeWidth={1.5} />
          <span className="font-outfit" style={{ fontWeight: 600 }}>
            This conversation is empty.
          </span>
          <span style={{ fontSize: '12px' }}>
            Type below to trigger the Aegra bypass graph execution.
          </span>
        </div>
      ) : (
        messages.map((msg) => (
          <ChatMessageItem key={msg.id} msg={msg} isDarkMode={isDarkMode} />
        ))
      )}

      {isStreaming && (
        <div style={{ display: 'flex', justifyContent: 'flex-start', width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginLeft: '8px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                background: isDarkMode ? '#1f2937' : '#e5e7eb',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: isDarkMode ? '#ffffff' : '#4b5563',
              }}
            >
              <Bot size={16} />
            </div>
            <div
              style={{
                background: isDarkMode ? '#111827' : '#ffffff',
                padding: '12px 16px',
                borderRadius: '4px 16px 16px 16px',
                border: '1px solid var(--border-color, #e5e7eb)',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <span className="dot-loading" />
              <span className="dot-loading" style={{ animationDelay: '0.2s' }} />
              <span className="dot-loading" style={{ animationDelay: '0.4s' }} />
            </div>
          </div>
        </div>
      )}
      <div ref={messagesEndRef} />
    </div>
  );
};
