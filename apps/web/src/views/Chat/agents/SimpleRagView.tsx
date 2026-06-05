import React, { useState } from 'react';
import { Spin, Alert, message } from 'antd';
import { AlertTriangle } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useThemeStore } from '@/stores/themeStore';
import { getModelCatalogOptionsApiV1ModelCatalogOptionsGet } from '@/generated/api/sdk.gen';
import type { RerankerConfig } from '@/generated/api/types.gen';
import { useChatThread } from '../hooks/useChatThread';
import { useChatStream } from '../hooks/useChatStream';
import { ChatHeader } from '../components/ChatHeader';
import { RagConfigPanel } from '../components/RagConfigPanel';
import { ChatMessageArea } from '../components/ChatMessageArea';
import { ChatInput } from '../components/ChatInput';
import type { AgentViewProps } from '../types';

export const SimpleRagView: React.FC<AgentViewProps> = ({
  assistantId,
  assistantName,
  onBack,
}) => {
  const { isDarkMode } = useThemeStore();
  const [inputValue, setInputValue] = useState('');
  const [selectedModel, setSelectedModel] = useState<string | undefined>(undefined);

  // RAG configurations
  const [selectedKbIds, setSelectedKbIds] = useState<string[]>([]);
  const [retrievalLimit, setRetrievalLimit] = useState<number>(5);
  const [candidateLimit, setCandidateLimit] = useState<number | null>(null);
  const [rerankerEnabled, setRerankerEnabled] = useState(false);
  const [rerankerModel, setRerankerModel] = useState<string | undefined>(undefined);
  const [rerankerTopN, setRerankerTopN] = useState<number | null>(null);

  const { data: modelOptions } = useQuery({
    queryKey: ['modelOptions'],
    queryFn: () => getModelCatalogOptionsApiV1ModelCatalogOptionsGet({ throwOnError: true }),
  });

  const { threadId, isInitializing, errorMsg, resetThread } = useChatThread(assistantId);
  const { messages, isStreaming, sendMessage } = useChatStream({ threadId, assistantId });

  const activeModel = selectedModel ?? modelOptions?.data?.llm_models?.[0];

  const handleSend = () => {
    if (!inputValue.trim() || isStreaming) return;

    if (selectedKbIds.length === 0) {
      message.warning('Select at least one Knowledge Base for RAG chat.');
      return;
    }

    const forcedReranker = selectedKbIds.length >= 2;
    const effectiveRerankerEnabled = forcedReranker || rerankerEnabled;

    if (effectiveRerankerEnabled && rerankerTopN && rerankerTopN < retrievalLimit) {
      message.warning('Reranker Top N must be greater than or equal to the retrieval limit.');
      return;
    }

    const userText = inputValue.trim();
    setInputValue('');

    const rerankerConfig: RerankerConfig | undefined = effectiveRerankerEnabled
      ? {
          model: rerankerModel?.trim() || undefined,
          top_n: rerankerTopN || undefined,
        }
      : undefined;

    sendMessage(userText, {
      model_name: activeModel || null,
      knowledge_base_ids: selectedKbIds,
      limit: retrievalLimit,
      candidate_limit: candidateLimit || undefined,
      reranker_config: rerankerConfig,
    });
  };

  if (isInitializing) {
    return (
      <div className="chat-loading-container">
        <Spin size="large" />
        <p className="font-outfit chat-loading-text">
          Opening safe secure channel to Aegra...
        </p>
      </div>
    );
  }

  return (
    <div className="chat-view-container">
      <ChatHeader
        assistantId={assistantId}
        assistantName={assistantName}
        assistantGraphId="simple_rag"
        threadId={threadId}
        onBack={onBack}
        llmModels={modelOptions?.data?.llm_models}
        selectedModel={activeModel}
        setSelectedModel={setSelectedModel}
        isStreaming={isStreaming}
        onReset={resetThread}
      />

      <RagConfigPanel
        selectedKbIds={selectedKbIds}
        setSelectedKbIds={setSelectedKbIds}
        retrievalLimit={retrievalLimit}
        setRetrievalLimit={setRetrievalLimit}
        candidateLimit={candidateLimit}
        setCandidateLimit={setCandidateLimit}
        rerankerEnabled={rerankerEnabled}
        setRerankerEnabled={setRerankerEnabled}
        rerankerModel={rerankerModel}
        setRerankerModel={setRerankerModel}
        rerankerTopN={rerankerTopN}
        setRerankerTopN={setRerankerTopN}
        isStreaming={isStreaming}
        isDarkMode={isDarkMode}
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

      <ChatMessageArea
        messages={messages}
        isStreaming={isStreaming}
        isDarkMode={isDarkMode}
      />

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
