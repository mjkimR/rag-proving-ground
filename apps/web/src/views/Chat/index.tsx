import React from 'react';
import { useThemeStore } from '@/stores/themeStore';
import { ChatHub } from './components/ChatHub';
import { SimpleChatView } from './agents/SimpleChatView';
import { SimpleRagView } from './agents/SimpleRagView';
import type { AgentViewProps } from './types';

const viewMap: Record<string, React.FC<AgentViewProps>> = {
  simple_chat: SimpleChatView,
  simple_rag: SimpleRagView,
};

export const Chat: React.FC = () => {
  const {
    selectedAssistantId,
    selectedAssistantName,
    selectedAssistantGraphId,
    setSelectedAssistant,
  } = useThemeStore();

  const View = viewMap[selectedAssistantGraphId ?? ''] ?? SimpleChatView;

  return (
    <div className="chat-layout-wrapper">
      {selectedAssistantId ? (
        <View
          assistantId={selectedAssistantId}
          assistantName={selectedAssistantName}
          onBack={() => setSelectedAssistant(null)}
        />
      ) : (
        <ChatHub
          onSelect={(assistant) => setSelectedAssistant(assistant)}
        />
      )}
    </div>
  );
};

