import React, { useState, useMemo } from 'react';
import { User, Bot, AlertTriangle, Brain, FileText, BookOpen } from 'lucide-react';
import { MarkdownPreview } from '@/components/MarkdownPreview';
import type { Reference, Message } from '@/views/Chat/types';
import styles from './ChatMessageItem.module.css';

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
    <div className={`${styles.messageItem} ${isHuman ? styles.human : styles.bot}`}>
      <div className={`${styles.messageInner} ${isHuman ? styles.human : styles.bot}`}>
        
        {/* Avatar Icon */}
        <div className={`${styles.avatar} ${isHuman ? styles.human : isError ? styles.error : styles.bot}`}>
          {isHuman ? <User size={16} /> : isError ? <AlertTriangle size={16} /> : <Bot size={16} />}
        </div>

        {/* Speech Bubble */}
        <div className={`${styles.bubble} ${isHuman ? styles.human : isError ? styles.error : styles.bot}`}>
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
                  className={styles.thinkingDetails}
                >
                  <summary className={styles.thinkingSummary}>
                    <Brain size={14} />
                    Thinking
                  </summary>
                  <div className={styles.thinkingContent}>
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
                <div className={styles.referencesWrapper}>
                  {(citedReferences.length > 0 || showAllRefs) && (
                    <>
                      <div className={styles.referencesHeader}>
                        <BookOpen size={13} />
                        <span>References ({showAllRefs ? msg.references.length : citedReferences.length})</span>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {(showAllRefs ? msg.references : citedReferences).map((ref) => (
                          <details
                            key={ref.chunk_id || ref.index}
                            id={`ref-detail-${msg.id}-${ref.index}`}
                            className={styles.refDetails}
                          >
                            <summary className={styles.refSummary}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flex: 1, minWidth: 0 }}>
                                <span className={styles.refIndexBadge}>
                                  {ref.index}
                                </span>
                                <FileText size={13} style={{ flexShrink: 0, color: '#3b82f6' }} />
                                <span className={styles.refSource}>
                                  {ref.source}
                                </span>
                                {ref.page !== null && ref.page !== undefined && (
                                  <span style={{ color: '#9ca3af', fontSize: '11px', flexShrink: 0 }}>
                                    (p. {ref.page})
                                  </span>
                                )}
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                                <span className={styles.refMatchScore}>
                                  {ref.rerank_score !== null && ref.rerank_score !== undefined
                                    ? `${(ref.rerank_score * 100).toFixed(0)}% match`
                                    : `${(ref.score * 100).toFixed(0)}% match`}
                                </span>
                              </div>
                            </summary>
                            <div className={styles.refContentContainer}>
                              {ref.page_content ? (
                                <div className={styles.pageContentWrapper}>
                                  <div>
                                    <span className={styles.pageContentLabel}>
                                      Page Content (Parent):
                                    </span>
                                    {ref.page_content}
                                  </div>
                                  <details className={styles.childChunkDetails}>
                                    <summary className={styles.childChunkSummary}>
                                      View Matched Chunk (Child)
                                    </summary>
                                    <div className={styles.childChunkText}>
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
