import React, { useState, useMemo } from 'react';
import { User, Bot, AlertTriangle, Brain, FileText, BookOpen } from 'lucide-react';
import { MarkdownPreview } from '@/components/MarkdownPreview';

import type { Reference, Message } from '@/views/Chat/types';

const PAGE_CONTENT_WRAPPER_STYLE: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: '8px'
};

const PAGE_CONTENT_LABEL_STYLE: React.CSSProperties = {
  fontSize: '11px',
  fontWeight: 700,
  color: '#3b82f6',
  display: 'block',
  marginBottom: '4px'
};

const getDetailsStyle = (isDarkMode: boolean): React.CSSProperties => ({
  borderTop: isDarkMode ? '1px solid #1f2937' : '1px solid #e5e7eb',
  paddingTop: '6px'
});

const getDetailsSummaryStyle = (isDarkMode: boolean): React.CSSProperties => ({
  cursor: 'pointer',
  fontSize: '11px',
  color: isDarkMode ? '#9ca3af' : '#4b5563',
  outline: 'none',
  fontWeight: 600
});

const getChildChunkStyle = (isDarkMode: boolean): React.CSSProperties => ({
  marginTop: '4px',
  fontSize: '11px',
  color: isDarkMode ? '#9ca3af' : '#4b5563',
  fontStyle: 'italic'
});

const getRefContentContainerStyle = (isDarkMode: boolean): React.CSSProperties => ({
  padding: '10px 12px',
  borderTop: isDarkMode ? '1px solid #1f2937' : '1px solid #e5e7eb',
  color: isDarkMode ? '#9ca3af' : '#4b5563',
  lineHeight: 1.5,
  background: isDarkMode ? '#030712' : '#ffffff',
  whiteSpace: 'pre-wrap',
  maxHeight: '160px',
  overflowY: 'auto'
});


interface ChatMessageItemProps {
  msg: Message;
  isDarkMode: boolean;
}

export const ChatMessageItem: React.FC<ChatMessageItemProps> = React.memo(({ msg, isDarkMode }) => {
  const isHuman = msg.type === 'human';
  const isError = msg.type === 'error';
  const hasThinking = !isHuman && !isError && Boolean(msg.thinking?.trim());

  const [showAllRefs, setShowAllRefs] = useState(false);

  const { citedReferences, uncitedReferences } = useMemo(() => {
    const cited = new Set<number>();
    if (msg.content) {
      const matches = msg.content.matchAll(/\[cite:(\d+)\]/g);
      for (const match of matches) {
        cited.add(parseInt(match[1], 10));
      }
    }
    const citedList: Reference[] = [];
    const uncitedList: Reference[] = [];
    if (msg.references) {
      for (const ref of msg.references) {
        if (cited.has(ref.index)) {
          citedList.push(ref);
        } else {
          uncitedList.push(ref);
        }
      }
    }
    return { citedReferences: citedList, uncitedReferences: uncitedList };
  }, [msg.references, msg.content]);

  const handleScrollToRef = (refIndex: number) => {
    const element = document.getElementById(`ref-detail-${msg.id}-${refIndex}`);
    if (element) {
      element.setAttribute('open', 'true');
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      
      const originalBg = element.style.background;
      const originalBorderColor = element.style.borderColor;
      const originalBoxShadow = element.style.boxShadow;

      element.style.background = isDarkMode ? 'rgba(59, 130, 246, 0.15)' : 'rgba(59, 130, 246, 0.08)';
      element.style.borderColor = '#3b82f6';
      element.style.boxShadow = isDarkMode ? '0 0 12px rgba(59, 130, 246, 0.4)' : '0 0 12px rgba(59, 130, 246, 0.2)';
      
      setTimeout(() => {
        element.style.background = originalBg;
        element.style.borderColor = originalBorderColor;
        element.style.boxShadow = originalBoxShadow;
      }, 2000);
    }
  };

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
                <MarkdownPreview
                  markdown={msg.content}
                  className="chat-markdown-preview"
                  references={msg.references}
                  onReferenceClick={handleScrollToRef}
                  isDarkMode={isDarkMode}
                />
              ) : hasThinking ? null : (
                <span style={{ color: isDarkMode ? '#9ca3af' : '#6b7280', fontStyle: 'italic' }}>
                  Waiting for response...
                </span>
              )}

              {msg.references && msg.references.length > 0 && (
                <div
                  style={{
                    marginTop: '12px',
                    paddingTop: '12px',
                    borderTop: isDarkMode ? '1px dashed #263244' : '1px dashed #e5e7eb',
                  }}
                >
                  {(citedReferences.length > 0 || showAllRefs) && (
                    <>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          fontSize: '12px',
                          fontWeight: 700,
                          color: isDarkMode ? '#9ca3af' : '#4b5563',
                          marginBottom: '8px',
                        }}
                      >
                        <BookOpen size={13} />
                        <span>References ({showAllRefs ? msg.references.length : citedReferences.length})</span>
                      </div>
                      <div
                        style={{
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '8px',
                        }}
                      >
                        {(showAllRefs ? msg.references : citedReferences).map((ref) => (
                          <details
                            key={ref.chunk_id || ref.index}
                            id={`ref-detail-${msg.id}-${ref.index}`}
                            style={{
                              width: '100%',
                              border: isDarkMode ? '1px solid #1f2937' : '1px solid #e5e7eb',
                              borderRadius: '8px',
                              background: isDarkMode ? '#0b0f17' : '#f9fafb',
                              overflow: 'hidden',
                              fontSize: '12px',
                              transition: 'all 0.3s ease',
                            }}
                          >
                            <summary
                              style={{
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                padding: '8px 12px',
                                userSelect: 'none',
                                listStyle: 'none',
                              }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flex: 1, minWidth: 0 }}>
                                <span
                                  style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    width: '18px',
                                    height: '18px',
                                    borderRadius: '50%',
                                    background: isDarkMode ? '#1f2937' : '#e5e7eb',
                                    color: isDarkMode ? '#9ca3af' : '#4b5563',
                                    fontSize: '10px',
                                    fontWeight: 700,
                                    flexShrink: 0,
                                  }}
                                >
                                  {ref.index}
                                </span>
                                <FileText size={13} style={{ flexShrink: 0, color: '#3b82f6' }} />
                                <span
                                  style={{
                                    whiteSpace: 'nowrap',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    fontWeight: 600,
                                    color: isDarkMode ? '#cbd5e1' : '#374151',
                                  }}
                                >
                                  {ref.source}
                                </span>
                                {ref.page !== null && ref.page !== undefined && (
                                  <span style={{ color: '#9ca3af', fontSize: '11px', flexShrink: 0 }}>
                                    (p. {ref.page})
                                  </span>
                                )}
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                                <span
                                  style={{
                                    fontSize: '11px',
                                    background: isDarkMode ? '#1e293b' : '#eff6ff',
                                    color: '#3b82f6',
                                    padding: '2px 6px',
                                    borderRadius: '4px',
                                    fontWeight: 600,
                                  }}
                                >
                                  {ref.rerank_score !== null && ref.rerank_score !== undefined
                                    ? `${(ref.rerank_score * 100).toFixed(0)}% match`
                                    : `${(ref.score * 100).toFixed(0)}% match`}
                                </span>
                              </div>
                            </summary>
                            <div style={getRefContentContainerStyle(isDarkMode)}>
                              {ref.page_content ? (
                                <div style={PAGE_CONTENT_WRAPPER_STYLE}>
                                  <div>
                                    <span style={PAGE_CONTENT_LABEL_STYLE}>
                                      Page Content (Parent):
                                    </span>
                                    {ref.page_content}
                                  </div>
                                  <details style={getDetailsStyle(isDarkMode)}>
                                    <summary style={getDetailsSummaryStyle(isDarkMode)}>
                                      View Matched Chunk (Child)
                                    </summary>
                                    <div style={getChildChunkStyle(isDarkMode)}>
                                      {ref.content}
                                    </div>
                                  </details>
                                </div>
                              ) : (
                                ref.content
                              )}
                            </div>
                          </details>
                        ))}
                      </div>
                    </>
                  )}

                  {uncitedReferences.length > 0 && (
                    <div
                      style={{
                        marginTop: (citedReferences.length > 0 || showAllRefs) ? '10px' : '0',
                        display: 'flex',
                        justifyContent: 'flex-start',
                      }}
                    >
                      <button
                        onClick={() => setShowAllRefs(!showAllRefs)}
                        style={{
                          background: 'transparent',
                          border: 'none',
                          padding: 0,
                          color: '#3b82f6',
                          cursor: 'pointer',
                          fontSize: '12px',
                          fontWeight: 600,
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          transition: 'opacity 0.2s',
                        }}
                        className="popover-action-link"
                      >
                        {showAllRefs ? (
                          <span>Hide uncited references</span>
                        ) : (
                          <span>Show all retrieved references ({msg.references.length})</span>
                        )}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
});
