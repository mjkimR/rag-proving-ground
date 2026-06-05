import React, { useState } from 'react';
import { Spin, Alert } from 'antd';
import { AlertTriangle } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useThemeStore } from '@/stores/themeStore';
import { getModelCatalogOptionsApiV1ModelCatalogOptionsGet } from '@/generated/api/sdk.gen';
import { useChatThread } from '../hooks/useChatThread';
import { useChatStream } from '../hooks/useChatStream';
import { ChatHeader } from '../components/ChatHeader';
import { ChatMessageArea } from '../components/ChatMessageArea';
import { ChatInput } from '../components/ChatInput';
import type { AgentViewProps } from '../types';

export const SimpleChatView: React.FC<AgentViewProps> = ({
  assistantId,
  assistantName,
  onBack,
}) => {
  const { isDarkMode } = useThemeStore();
  const [inputValue, setInputValue] = useState('');
  const [selectedModel, setSelectedModel] = useState<string | undefined>(undefined);

  const { data: modelOptions } = useQuery({
    queryKey: ['modelOptions'],
    queryFn: () => getModelCatalogOptionsApiV1ModelCatalogOptionsGet({ throwOnError: true }),
  });

  const { threadId, isInitializing, errorMsg, resetThread } = useChatThread(assistantId);
  const { messages, isStreaming, sendMessage } = useChatStream({ threadId, assistantId });

  const activeModel = selectedModel ?? modelOptions?.data?.llm_models?.[0];

  const handleSend = () => {
    if (!inputValue.trim() || isStreaming) return;
    const userText = inputValue.trim();
    setInputValue('');
    sendMessage(userText, {
      model_name: activeModel || null,
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
        assistantGraphId="simple_chat"
        threadId={threadId}
        onBack={onBack}
        llmModels={modelOptions?.data?.llm_models}
        selectedModel={activeModel}
        setSelectedModel={setSelectedModel}
        isStreaming={isStreaming}
        onReset={resetThread}
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
