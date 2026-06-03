import React, { useState, useEffect, useRef } from 'react';
import { Button, Input, Space, Spin, Alert, Typography, Tooltip, Select } from 'antd';
import { ArrowLeft, Send, RotateCcw, AlertTriangle, User, Bot } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useThemeStore } from '@/stores/themeStore';
import { MarkdownPreview } from '@/components/MarkdownPreview';
import { getModelCatalogOptionsApiV1ModelCatalogOptionsGet } from '@/generated/api/sdk.gen';

const { Title, Text } = Typography;
const { TextArea } = Input;

interface Message {
  id: string;
  type: 'human' | 'ai';
  content: string;
}

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

            if (currentEvent === 'messages') {
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
            }
          }
        }
      }
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || 'An error occurred during streaming execution.');
    } finally {
      setIsStreaming(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
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
      {/* Top Navigation Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          paddingBottom: '16px',
          borderBottom: '1px solid var(--border-color, #dde3ea)',
          marginBottom: '16px',
        }}
      >
        <Space size="middle">
          <Button
            type="text"
            icon={<ArrowLeft size={16} />}
            onClick={onBack}
            style={{ borderRadius: '8px' }}
          >
            Back
          </Button>
          <div>
            <Title level={4} className="font-outfit" style={{ margin: 0, fontWeight: 700 }}>
              Chat: <span style={{ color: '#4f46e5' }}>{assistantId}</span>
            </Title>
            <Text type="secondary" style={{ fontSize: '12px' }}>
              Thread Ref: {threadId || 'No active thread'}
            </Text>
          </div>
        </Space>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {modelOptions?.data?.llm_models && (
            <Select
              value={selectedModel}
              onChange={(value) => setSelectedModel(value)}
              style={{ width: 180 }}
              options={modelOptions.data.llm_models.map((m) => ({ label: m, value: m }))}
              placeholder="Select Model"
              disabled={isStreaming}
            />
          )}
          <Tooltip title="Reset Conversation">
            <Button
              shape="circle"
              icon={<RotateCcw size={16} />}
              onClick={createNewThread}
              disabled={isStreaming}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                border: '1px solid var(--border-color)',
              }}
            />
          </Tooltip>
        </div>
      </div>

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
          messages.map((msg) => {
            const isHuman = msg.type === 'human';
            return (
              <div
                key={msg.id}
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
                        : isDarkMode ? '#1f2937' : '#e5e7eb',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: isHuman ? '#ffffff' : isDarkMode ? '#ffffff' : '#4b5563',
                      boxShadow: isHuman ? '0 2px 8px rgba(79,70,229,0.15)' : 'none',
                      flexShrink: 0,
                    }}
                  >
                    {isHuman ? <User size={16} /> : <Bot size={16} />}
                  </div>

                  {/* Speech Bubble */}
                  <div
                    style={{
                      background: isHuman
                        ? 'linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%)'
                        : isDarkMode ? '#111827' : '#ffffff',
                      color: isHuman ? '#ffffff' : 'inherit',
                      padding: '12px 16px',
                      borderRadius: isHuman ? '16px 4px 16px 16px' : '4px 16px 16px 16px',
                      border: isHuman ? 'none' : '1px solid var(--border-color, #e5e7eb)',
                      boxShadow: '0 2px 10px rgba(0,0,0,0.02)',
                      fontSize: '14px',
                      lineHeight: '1.5',
                    }}
                  >
                    {isHuman ? (
                      <span style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</span>
                    ) : (
                      <MarkdownPreview markdown={msg.content} />
                    )}
                  </div>
                </div>
              </div>
            );
          })
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

      {/* Input Message Area */}
      <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end' }}>
        <TextArea
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Send a message to the graph..."
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={isStreaming}
          style={{
            borderRadius: '12px',
            padding: '12px 16px',
            border: '1px solid var(--border-color, #dde3ea)',
            background: isDarkMode ? '#111827' : '#ffffff',
            boxShadow: 'none',
            fontSize: '14px',
          }}
        />
        <Button
          type="primary"
          icon={<Send size={16} />}
          onClick={handleSend}
          disabled={!inputValue.trim() || isStreaming}
          style={{
            height: '46px',
            width: '46px',
            borderRadius: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%)',
            border: 'none',
            boxShadow: '0 4px 12px rgba(79, 70, 229, 0.2)',
          }}
        />
      </div>
    </div>
  );
};
