import React from 'react';
import { User, Bot, AlertTriangle, Brain } from 'lucide-react';
import { MarkdownPreview } from '@/components/MarkdownPreview';

export interface Message {
  id: string;
  type: 'human' | 'ai' | 'error';
  content: string;
  thinking?: string;
}

interface ChatMessageItemProps {
  msg: Message;
  isDarkMode: boolean;
}

export const ChatMessageItem: React.FC<ChatMessageItemProps> = ({ msg, isDarkMode }) => {
  const isHuman = msg.type === 'human';
  const isError = msg.type === 'error';
  const hasThinking = !isHuman && !isError && Boolean(msg.thinking?.trim());

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: isHuman ? 'flex-end' : 'flex-start',
        width: '100%',
      }}
    >
      <div
        style={{
          display: 'flex',
          flexDirection: isHuman ? 'row-reverse' : 'row',
          alignItems: 'flex-start',
          maxWidth: '80%',
          gap: '10px',
        }}
      >
        {/* Avatar Icon */}
        <div
          style={{
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            background: isHuman
              ? 'linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%)'
              : isError
                ? isDarkMode ? '#451a1a' : '#fee2e2'
                : isDarkMode ? '#1f2937' : '#e5e7eb',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: isHuman
              ? '#ffffff'
              : isError
                ? '#ef4444'
                : isDarkMode ? '#ffffff' : '#4b5563',
            boxShadow: isHuman ? '0 2px 8px rgba(79,70,229,0.15)' : 'none',
            flexShrink: 0,
          }}
        >
          {isHuman ? <User size={16} /> : isError ? <AlertTriangle size={16} /> : <Bot size={16} />}
        </div>

        {/* Speech Bubble */}
        <div
          style={{
            background: isHuman
              ? 'linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%)'
              : isError
                ? isDarkMode ? '#2d1414' : '#fff5f5'
                : isDarkMode ? '#111827' : '#ffffff',
            color: isHuman
              ? '#ffffff'
              : isError
                ? isDarkMode ? '#fca5a5' : '#b91c1c'
                : 'inherit',
            padding: '12px 16px',
            borderRadius: isHuman ? '16px 4px 16px 16px' : '4px 16px 16px 16px',
            border: isHuman
              ? 'none'
              : isError
                ? isDarkMode ? '1px solid #7f1d1d' : '1px solid #fecaca'
                : '1px solid var(--border-color, #e5e7eb)',
            boxShadow: '0 2px 10px rgba(0,0,0,0.02)',
            fontSize: '14px',
            lineHeight: '1.5',
            width: 'fit-content',
            maxWidth: '100%',
          }}
        >
          {isHuman ? (
            <span style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</span>
          ) : isError ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span style={{ fontWeight: 600, fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                Graph Execution Error
              </span>
              <span style={{ fontFamily: 'monospace', whiteSpace: 'pre-wrap', fontSize: '12px' }}>{msg.content}</span>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: msg.content ? '12px' : '0' }}>
              {hasThinking && (
                <details
                  open={!msg.content}
                  style={{
                    border: isDarkMode ? '1px solid #263244' : '1px solid #dbe4ef',
                    borderRadius: '10px',
                    background: isDarkMode ? '#0b1220' : '#f8fafc',
                    overflow: 'hidden',
                  }}
                >
                  <summary
                    style={{
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '8px 10px',
                      color: isDarkMode ? '#bfdbfe' : '#1d4ed8',
                      fontSize: '12px',
                      fontWeight: 700,
                      userSelect: 'none',
                    }}
                  >
                    <Brain size={14} />
                    Thinking
                  </summary>
                  <div
                    style={{
                      borderTop: isDarkMode ? '1px solid #263244' : '1px solid #dbe4ef',
                      padding: '10px',
                      color: isDarkMode ? '#cbd5e1' : '#334155',
                      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                      fontSize: '12px',
                      lineHeight: 1.55,
                      whiteSpace: 'pre-wrap',
                      maxHeight: '240px',
                      overflowY: 'auto',
                    }}
                  >
                    {msg.thinking}
                  </div>
                </details>
              )}
              {msg.content ? (
                <MarkdownPreview markdown={msg.content} className="chat-markdown-preview" />
              ) : hasThinking ? null : (
                <span style={{ color: isDarkMode ? '#9ca3af' : '#6b7280', fontStyle: 'italic' }}>
                  Waiting for response...
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
