import React from 'react';
import { useThemeStore } from '@/stores/themeStore';
import { ChatHub } from './components/ChatHub';
import { ChatDetail } from './components/ChatDetail';

export const Chat: React.FC = () => {
  const { selectedAssistantId, setSelectedAssistantId } = useThemeStore();

  return (
    <div style={{ minHeight: 'calc(100vh - 120px)', padding: '12px 0 24px 0' }}>
      {selectedAssistantId ? (
        <ChatDetail
          assistantId={selectedAssistantId}
          onBack={() => setSelectedAssistantId(null)}
        />
      ) : (
        <ChatHub
          onSelect={(assistant) => setSelectedAssistantId(assistant.id)}
        />
      )}
    </div>
  );
};
