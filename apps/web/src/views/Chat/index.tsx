import React from 'react';
import { useThemeStore } from '@/stores/themeStore';
import { ChatHub } from './components/ChatHub';
import { ChatDetail } from './components/ChatDetail';

export const Chat: React.FC = () => {
  const {
    selectedAssistantId,
    selectedAssistantName,
    selectedAssistantGraphId,
    setSelectedAssistant,
  } = useThemeStore();

  return (
    <div style={{ minHeight: 'calc(100vh - 120px)', padding: '12px 0 24px 0' }}>
      {selectedAssistantId ? (
        <ChatDetail
          assistantId={selectedAssistantId}
          assistantName={selectedAssistantName}
          assistantGraphId={selectedAssistantGraphId}
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
