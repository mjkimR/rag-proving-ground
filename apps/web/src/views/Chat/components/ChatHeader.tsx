import React from 'react';
import { Button, Space, Typography, Tooltip, Select } from 'antd';
import { ArrowLeft, RotateCcw } from 'lucide-react';

const { Title, Text } = Typography;

interface ChatHeaderProps {
  assistantId: string;
  threadId: string | null;
  onBack: () => void;
  llmModels?: string[];
  selectedModel: string | undefined;
  setSelectedModel: (model: string | undefined) => void;
  isStreaming: boolean;
  onReset: () => void;
}

export const ChatHeader: React.FC<ChatHeaderProps> = ({
  assistantId,
  threadId,
  onBack,
  llmModels,
  selectedModel,
  setSelectedModel,
  isStreaming,
  onReset,
}) => {
  return (
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
        {llmModels && llmModels.length > 0 && (
          <Select
            value={selectedModel}
            onChange={(value) => setSelectedModel(value)}
            style={{ width: 180 }}
            options={llmModels.map((m) => ({ label: m, value: m }))}
            placeholder="Select Model"
            disabled={isStreaming}
          />
        )}
        <Tooltip title="Reset Conversation">
          <Button
            shape="circle"
            icon={<RotateCcw size={16} />}
            onClick={onReset}
            disabled={isStreaming}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '1px solid var(--border-color, #e5e7eb)',
            }}
          />
        </Tooltip>
      </div>
    </div>
  );
};
