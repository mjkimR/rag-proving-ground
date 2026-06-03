import React, { useState, useEffect, useRef } from 'react';
import { Spin, Alert } from 'antd';
import { AlertTriangle, Bot } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useThemeStore } from '@/stores/themeStore';
import { getModelCatalogOptionsApiV1ModelCatalogOptionsGet } from '@/generated/api/sdk.gen';
import { ChatHeader } from './ChatHeader';
import { ChatInput } from './ChatInput';
import { ChatMessageItem, type Message } from './ChatMessageItem';

interface ChatDetailProps {
  assistantId: string;
  onBack: () => void;
}

const AEGRA_API_URL = import.meta.env.VITE_AEGRA_URL || 'http://localhost:2026';

export const ChatDetail: React.FC<ChatDetailProps> = ({ assistantId, onBack }) => {
  const { isDarkMode } = useThemeStore();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [threadId, setThreadId] = useState<string | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const [isStreaming, setIsStreaming] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string | undefined>(undefined);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { data: modelOptions } = useQuery({
    queryKey: ['modelOptions'],
    queryFn: () => getModelCatalogOptionsApiV1ModelCatalogOptionsGet({ throwOnError: true }),
  });

  useEffect(() => {
    if (modelOptions?.data?.llm_models && modelOptions.data.llm_models.length > 0 && !selectedModel) {
      setSelectedModel(modelOptions.data.llm_models[0]);
    }
  }, [modelOptions, selectedModel]);

  // Initialize new thread on mount
  useEffect(() => {
    createNewThread();
  }, [assistantId]);

  // Scroll to bottom whenever messages list updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isStreaming]);

  const createNewThread = async () => {
    setIsInitializing(true);
    setErrorMsg(null);
    setMessages([]);

    try {
      const res = await fetch(`${AEGRA_API_URL}/threads`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });

      if (!res.ok) {
        throw new Error('Failed to create a conversation thread.');
      }

      const data = await res.json();
      setThreadId(data.thread_id);
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || 'Could not reach the Aegra server. Please verify it is running on port 2026.');
    } finally {
      setIsInitializing(false);
    }
  };

  const handleSend = async () => {
    if (!inputValue.trim() || !threadId || isStreaming) return;

    const userText = inputValue.trim();
    setInputValue('');
    setErrorMsg(null);

    // 1. Add user message
    const userMsgId = `user-${Date.now()}`;
    const newMessages: Message[] = [
      ...messages,
      { id: userMsgId, type: 'human', content: userText },
    ];
    setMessages(newMessages);
    setIsStreaming(true);

    let runId: string | null = null;
    try {
      // 2. Call stream endpoint
      const response = await fetch(`${AEGRA_API_URL}/threads/${threadId}/runs/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          assistant_id: assistantId,
          input: {
            messages: [{ type: 'human', content: userText }],
          },
          stream_mode: ['messages-tuple'],
          config: {
            configurable: {
              model_name: selectedModel || null,
            },
          },
        }),
      });

      if (!response.ok) {
        throw new Error(`Server returned error code: ${response.status}`);
      }

      if (!response.body) {
        throw new Error('Readable stream not supported by server response.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep the last partial line

        let currentEvent = '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('event: ')) {
            currentEvent = trimmed.slice(7).trim();
          } else if (trimmed.startsWith('data: ')) {
            const dataStr = trimmed.slice(6).trim();

            if (currentEvent === 'metadata') {
              try {
                const parsed = JSON.parse(dataStr);
                if (parsed && parsed.run_id) {
                  runId = parsed.run_id;
                }
              } catch (e) {
                console.error('Failed to parse metadata event:', e);
              }
            } else if (currentEvent === 'messages') {
              try {
                const parsed = JSON.parse(dataStr);
                // parsed is [ AIMessageChunk, RunContext ]
                if (Array.isArray(parsed) && parsed.length > 0) {
                  const msgChunk = parsed[0];
                  if (msgChunk && msgChunk.content !== undefined) {
                    const chunkContent = msgChunk.content;
                    const chunkId = msgChunk.id || `ai-${Date.now()}`;

                    setMessages((prev) => {
                      const existingIndex = prev.findIndex((m) => m.id === chunkId);
                      if (existingIndex > -1) {
                        const updated = [...prev];
                        updated[existingIndex] = {
                          ...updated[existingIndex],
                          content: updated[existingIndex].content + chunkContent,
                        };
                        return updated;
                      } else {
                        return [
                          ...prev,
                          { id: chunkId, type: 'ai', content: chunkContent },
                        ];
                      }
                    });
                  }
                }
              } catch (e) {
                console.error('Failed to parse message event payload:', e);
              }
            } else if (currentEvent === 'error') {
              try {
                const parsed = JSON.parse(dataStr);
                let errMsg = parsed.message || parsed.error || 'An error occurred during execution.';

                if (runId && threadId) {
                  try {
                    const runRes = await fetch(`${AEGRA_API_URL}/threads/${threadId}/runs/${runId}`);
                    if (runRes.ok) {
                      const runData = await runRes.json();
                      if (runData.error_message || runData.error) {
                        errMsg = runData.error_message || runData.error;
                      }
                    }
                  } catch (fetchErr) {
                    console.error('Failed to fetch detailed run error:', fetchErr);
                  }
                }

                setMessages((prev) => [
                  ...prev,
                  { id: `error-${Date.now()}`, type: 'error', content: errMsg },
                ]);
              } catch (e) {
                setMessages((prev) => [
                  ...prev,
                  { id: `error-${Date.now()}`, type: 'error', content: 'An error occurred during execution.' },
                ]);
              }
            }
          }
        }
      }
    } catch (err: any) {
      console.error(err);
      let errMsg = err.message || 'An error occurred during streaming execution.';

      if (runId && threadId) {
        try {
          const runRes = await fetch(`${AEGRA_API_URL}/threads/${threadId}/runs/${runId}`);
          if (runRes.ok) {
            const runData = await runRes.json();
            if (runData.error_message || runData.error) {
              errMsg = runData.error_message || runData.error;
            }
          }
        } catch (fetchErr) {
          console.error('Failed to fetch detailed run error in catch block:', fetchErr);
        }
      }

      setMessages((prev) => [
        ...prev,
        { id: `error-${Date.now()}`, type: 'error', content: errMsg },
      ]);
    } finally {
      setIsStreaming(false);
    }
  };

  if (isInitializing) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '400px' }}>
        <Spin size="large" />
        <p className="font-outfit" style={{ marginTop: '16px', fontWeight: 600, color: isDarkMode ? '#f3f4f6' : '#1f2937' }}>
          Opening safe secure channel to Aegra...
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 180px)', padding: '0 24px' }}>
      <ChatHeader
        assistantId={assistantId}
        threadId={threadId}
        onBack={onBack}
        llmModels={modelOptions?.data?.llm_models}
        selectedModel={selectedModel}
        setSelectedModel={setSelectedModel}
        isStreaming={isStreaming}
        onReset={createNewThread}
      />

      {errorMsg && (
        <Alert
          message="Server Connection Alert"
          description={errorMsg}
          type="error"
          showIcon
          icon={<AlertTriangle size={18} />}
          style={{ marginBottom: '16px', borderRadius: '10px' }}
        />
      )}

      {/* Messages Scroll Area */}
      <div
        style={{
          flex: 1,
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
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#9ca3af', gap: '8px' }}>
            <Bot size={40} strokeWidth={1.5} />
            <span className="font-outfit" style={{ fontWeight: 600 }}>This conversation is empty.</span>
            <span style={{ fontSize: '12px' }}>Type below to trigger the Aegra bypass graph execution.</span>
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

      <ChatInput
        inputValue={inputValue}
        setInputValue={setInputValue}
        onSend={handleSend}
        isStreaming={isStreaming}
        isDarkMode={isDarkMode}
      />
    </div>
  );
};
