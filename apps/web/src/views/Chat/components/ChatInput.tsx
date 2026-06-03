import React, { useRef, useEffect } from 'react';
import { Input, Button } from 'antd';
import { Send } from 'lucide-react';

const { TextArea } = Input;

interface ChatInputProps {
  inputValue: string;
  setInputValue: (val: string) => void;
  onSend: () => void;
  isStreaming: boolean;
  isDarkMode: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  inputValue,
  setInputValue,
  onSend,
  isStreaming,
  isDarkMode,
}) => {
  const inputRef = useRef<any>(null);

  // Auto-focus the input field when streaming finishes or on mount
  useEffect(() => {
    if (isStreaming) return;

    const timer = setTimeout(() => {
      inputRef.current?.focus();
    }, 50);
    return () => clearTimeout(timer);
  }, [isStreaming]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end' }}>
      <TextArea
        ref={inputRef}
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
        onClick={onSend}
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
  );
};
