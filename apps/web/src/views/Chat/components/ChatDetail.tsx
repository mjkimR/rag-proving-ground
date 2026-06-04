import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Spin, Alert, Card, Input, InputNumber, Select, Space, Switch, Typography, message } from 'antd';
import { AlertTriangle, Bot } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useThemeStore } from '@/stores/themeStore';
import {
  getKnowledgeBasesApiV1KnowledgeBasesGet,
  getModelCatalogOptionsApiV1ModelCatalogOptionsGet,
} from '@/generated/api/sdk.gen';
import type { RerankerConfig } from '@/generated/api/types.gen';
import { ChatHeader } from './ChatHeader';
import { ChatInput } from './ChatInput';
import { ChatMessageItem, type Message } from './ChatMessageItem';

interface ChatDetailProps {
  assistantId: string;
  assistantName?: string | null;
  assistantGraphId?: string | null;
  onBack: () => void;
}

const AEGRA_API_URL = import.meta.env.VITE_AEGRA_URL || 'http://localhost:2026';
const THINKING_CONTENT_BLOCK_TYPES = new Set(['thinking', 'reasoning']);
const { Text } = Typography;

interface MessageContentDelta {
  content: string;
  thinking: string;
}

const emptyDelta = (): MessageContentDelta => ({ content: '', thinking: '' });

const isRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === 'object' && value !== null
);

const mergeDelta = (left: MessageContentDelta, right: MessageContentDelta): MessageContentDelta => ({
  content: left.content + right.content,
  thinking: left.thinking + right.thinking,
});

const extractString = (value: unknown): string => (
  typeof value === 'string' ? value : ''
);

const extractMessageContentDelta = (content: unknown): MessageContentDelta => {
  if (typeof content === 'string') {
    return { content, thinking: '' };
  }

  if (Array.isArray(content)) {
    return content.reduce(
      (delta, item) => mergeDelta(delta, extractMessageContentDelta(item)),
      emptyDelta(),
    );
  }

  if (!isRecord(content)) {
    return emptyDelta();
  }

  const blockType = typeof content.type === 'string' ? content.type : undefined;
  if (blockType && THINKING_CONTENT_BLOCK_TYPES.has(blockType)) {
    return {
      content: '',
      thinking: extractString(content.thinking)
        || extractString(content.reasoning)
        || extractString(content.text)
        || extractMessageContentDelta(content.content).content,
    };
  }

  if (typeof content.text === 'string') {
    return { content: content.text, thinking: '' };
  }

  if (typeof content.content === 'string' || Array.isArray(content.content)) {
    return extractMessageContentDelta(content.content);
  }

  return emptyDelta();
};

export const ChatDetail: React.FC<ChatDetailProps> = ({ assistantId, assistantName, assistantGraphId, onBack }) => {
  const { isDarkMode } = useThemeStore();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [threadId, setThreadId] = useState<string | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const [isStreaming, setIsStreaming] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string | undefined>(undefined);
  const [selectedKbIds, setSelectedKbIds] = useState<string[]>([]);
  const [retrievalLimit, setRetrievalLimit] = useState<number>(5);
  const [candidateLimit, setCandidateLimit] = useState<number | null>(null);
  const [rerankerEnabled, setRerankerEnabled] = useState(false);
  const [rerankerModel, setRerankerModel] = useState<string | undefined>(undefined);
  const [rerankerTopN, setRerankerTopN] = useState<number | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isRagAssistant = assistantGraphId === 'simple_rag' || assistantName === 'simple_rag' || assistantId === 'simple_rag';

  const { data: modelOptions } = useQuery({
    queryKey: ['modelOptions'],
    queryFn: () => getModelCatalogOptionsApiV1ModelCatalogOptionsGet({ throwOnError: true }),
  });

  const kbQuery = useQuery({
    queryKey: ['chatKbList'],
    queryFn: () => getKnowledgeBasesApiV1KnowledgeBasesGet({ throwOnError: true }),
    enabled: isRagAssistant,
  });

  const knowledgeBases = kbQuery.data?.data?.items || [];
  const kbOptions = useMemo(
    () =>
      knowledgeBases.map((kb) => ({
        label: `${kb.name} (${kb.status})`,
        value: kb.id,
      })),
    [knowledgeBases],
  );
  const rerankerModels = modelOptions?.data?.reranker_models || [];
  const hasCatalogRerankerModels = rerankerModels.length > 0 && !rerankerModels.includes('no-model');
  const forcedReranker = selectedKbIds.length >= 2;
  const effectiveRerankerEnabled = forcedReranker || rerankerEnabled;

  useEffect(() => {
    if (modelOptions?.data?.llm_models && modelOptions.data.llm_models.length > 0 && !selectedModel) {
      setSelectedModel(modelOptions.data.llm_models[0]);
    }
  }, [modelOptions, selectedModel]);

  useEffect(() => {
    if (!rerankerModel && hasCatalogRerankerModels) {
      setRerankerModel(rerankerModels[0]);
    }
  }, [hasCatalogRerankerModels, rerankerModel, rerankerModels]);

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
    if (isRagAssistant && selectedKbIds.length === 0) {
      message.warning('Select at least one Knowledge Base for RAG chat.');
      return;
    }
    if (isRagAssistant && effectiveRerankerEnabled && rerankerTopN && rerankerTopN < retrievalLimit) {
      message.warning('Reranker Top N must be greater than or equal to the retrieval limit.');
      return;
    }

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
      const rerankerConfig: RerankerConfig | undefined = isRagAssistant && effectiveRerankerEnabled
        ? {
            model: rerankerModel?.trim() || undefined,
            top_n: rerankerTopN || undefined,
          }
        : undefined;
      const configurable = {
        model_name: selectedModel || null,
        ...(isRagAssistant
          ? {
              knowledge_base_ids: selectedKbIds,
              limit: retrievalLimit,
              candidate_limit: candidateLimit || undefined,
              reranker_config: rerankerConfig,
            }
          : {}),
      };

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
            configurable,
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
                    let chunkDelta = extractMessageContentDelta(msgChunk.content);
                    if (!chunkDelta.thinking && isRecord(msgChunk.additional_kwargs)) {
                      chunkDelta = {
                        ...chunkDelta,
                        thinking: extractString(msgChunk.additional_kwargs.reasoning_content),
                      };
                    }
                    if (!chunkDelta.content && !chunkDelta.thinking) continue;

                    const chunkId = msgChunk.id || `ai-${Date.now()}`;

                    setMessages((prev) => {
                      const existingIndex = prev.findIndex((m) => m.id === chunkId);
                      if (existingIndex > -1) {
                        const updated = [...prev];
                        updated[existingIndex] = {
                          ...updated[existingIndex],
                          content: updated[existingIndex].content + chunkDelta.content,
                          thinking: `${updated[existingIndex].thinking || ''}${chunkDelta.thinking}`,
                        };
                        return updated;
                      } else {
                        return [
                          ...prev,
                          {
                            id: chunkId,
                            type: 'ai',
                            content: chunkDelta.content,
                            thinking: chunkDelta.thinking || undefined,
                          },
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
        assistantName={assistantName}
        assistantGraphId={assistantGraphId}
        threadId={threadId}
        onBack={onBack}
        llmModels={modelOptions?.data?.llm_models}
        selectedModel={selectedModel}
        setSelectedModel={setSelectedModel}
        isStreaming={isStreaming}
        onReset={createNewThread}
      />

      {isRagAssistant && (
        <Card
          size="small"
          style={{
            marginBottom: '16px',
            borderRadius: '12px',
            background: isDarkMode ? '#111827' : '#ffffff',
            border: '1px solid var(--border-color, #e5e7eb)',
          }}
        >
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Space direction="vertical" size={6} style={{ width: '100%' }}>
              <Text strong>Knowledge Bases</Text>
              <Select
                mode="multiple"
                placeholder="Select Knowledge Bases to retrieve context from"
                loading={kbQuery.isLoading}
                options={kbOptions}
                value={selectedKbIds}
                onChange={setSelectedKbIds}
                style={{ width: '100%' }}
                optionFilterProp="label"
                disabled={isStreaming}
              />
            </Space>

            <Space wrap size={12} style={{ width: '100%' }}>
              <Space direction="vertical" size={6}>
                <Text strong>Limit</Text>
                <InputNumber
                  min={1}
                  max={100}
                  value={retrievalLimit}
                  onChange={(value) => value && setRetrievalLimit(value)}
                  disabled={isStreaming}
                />
              </Space>
              <Space direction="vertical" size={6}>
                <Text strong>Candidate Limit</Text>
                <InputNumber
                  min={1}
                  max={500}
                  value={candidateLimit}
                  onChange={(value) => setCandidateLimit(value)}
                  placeholder="Auto"
                  disabled={isStreaming}
                />
              </Space>
              <Space direction="vertical" size={6}>
                <Text strong>Reranker</Text>
                <Switch
                  checked={effectiveRerankerEnabled}
                  disabled={isStreaming || forcedReranker}
                  onChange={setRerankerEnabled}
                  checkedChildren="On"
                  unCheckedChildren="Off"
                />
              </Space>
              <Space direction="vertical" size={6} style={{ minWidth: 220 }}>
                <Text strong>Reranker Model</Text>
                {hasCatalogRerankerModels ? (
                  <Select
                    showSearch
                    allowClear
                    placeholder="Default reranker"
                    loading={!modelOptions}
                    options={rerankerModels.map((model) => ({ label: model, value: model }))}
                    value={rerankerModel}
                    onChange={setRerankerModel}
                    disabled={isStreaming || !effectiveRerankerEnabled}
                    style={{ width: '100%' }}
                  />
                ) : (
                  <Input
                    placeholder="Default reranker or model name"
                    value={rerankerModel}
                    onChange={(event) => setRerankerModel(event.target.value || undefined)}
                    disabled={isStreaming || !effectiveRerankerEnabled}
                  />
                )}
              </Space>
              <Space direction="vertical" size={6}>
                <Text strong>Top N</Text>
                <InputNumber
                  min={1}
                  max={100}
                  value={rerankerTopN}
                  onChange={(value) => setRerankerTopN(value)}
                  placeholder="Limit"
                  disabled={isStreaming || !effectiveRerankerEnabled}
                />
              </Space>
            </Space>

            {forcedReranker && (
              <Text type="secondary" style={{ fontSize: '12px' }}>
                Multi-KB RAG requires reranking before final context selection.
              </Text>
            )}
          </Space>
        </Card>
      )}

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
