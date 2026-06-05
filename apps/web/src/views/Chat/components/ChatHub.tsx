import React from 'react';
import { Card, Button, Row, Col, Spin, Empty, Tag, Typography } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { MessageSquare, Bot, Cpu, Calendar } from 'lucide-react';
import { useThemeStore } from '@/stores/themeStore';

const { Title, Paragraph, Text } = Typography;

interface Assistant {
  assistant_id: string;
  name: string;
  description: string;
  graph_id: string;
  version: number;
  created_at: string;
  metadata?: {
    title?: string;
    tags?: string[];
    icon?: string;
  };
}

interface ChatHubProps {
  onSelect: (assistant: { id: string; name: string; graphId: string }) => void;
}

import { AEGRA_API_URL } from '@/lib/config';

export const ChatHub: React.FC<ChatHubProps> = ({ onSelect }) => {
  const { isDarkMode } = useThemeStore();

  const { data: assistants, isLoading, error } = useQuery<Assistant[]>({
    queryKey: ['aegraAssistants'],
    queryFn: async () => {
      const res = await fetch(`${AEGRA_API_URL}/assistants/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        throw new Error('Failed to fetch Aegra assistants');
      }
      return res.json();
    },
    refetchInterval: 10000, // Refresh list every 10 seconds to catch new graphs
  });

  if (isLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '400px' }}>
        <Spin size="large" />
        <p className="font-outfit" style={{ marginTop: '16px', fontWeight: 600, color: isDarkMode ? '#f3f4f6' : '#1f2937' }}>
          Scanning active Aegra graphs...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', background: isDarkMode ? '#1f2937' : '#ffffff', borderRadius: '16px', border: '1px solid var(--border-color)' }}>
        <Empty
          description={
            <span style={{ color: '#ef4444', fontWeight: 600 }}>
              Failed to connect to Aegra Server at {AEGRA_API_URL}.
            </span>
          }
        />
        <p style={{ color: '#6b7280', fontSize: '14px', marginTop: '8px' }}>
          Please make sure your Aegra server (port 2026) is running and healthy.
        </p>
      </div>
    );
  }

  return (
    <div style={{ padding: '0 24px' }}>
      <div style={{ marginBottom: '32px' }}>
        <Title level={2} className="font-outfit" style={{ margin: 0, fontWeight: 800 }}>
          Served Graphs Playground
        </Title>
        <Paragraph style={{ color: '#6b7280', fontSize: '15px', marginTop: '8px' }}>
          Select an active graph registered on your Aegra serving endpoint to test interactions and streaming outputs.
        </Paragraph>
      </div>

      {!assistants || assistants.length === 0 ? (
        <Empty description="No served graphs or assistants found in aegra.json config." />
      ) : (
        <Row gutter={[24, 24]}>
          {assistants.map((assistant) => {
            const meta = assistant.metadata || {};

            return (
              <Col xs={24} sm={12} lg={8} key={assistant.assistant_id}>
                <Card
                  hoverable
                  className="gradient-card-hover"
                  style={{
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    borderRadius: '16px',
                    background: isDarkMode ? '#111827' : '#ffffff',
                    border: '1px solid var(--border-color, #dde3ea)',
                    boxShadow: '0 4px 20px rgba(0,0,0,0.03)',
                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    overflow: 'hidden',
                  }}
                  styles={{
                    body: {
                      padding: '24px',
                      display: 'flex',
                      flexDirection: 'column',
                      height: '100%',
                      flex: 1,
                    }
                  }}
                >
                  {/* Card Header Info */}
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '20px' }}>
                    <div
                      style={{
                        background: 'linear-gradient(135deg, #4f46e5 0%, #00f2fe 100%)',
                        width: '46px',
                        height: '46px',
                        borderRadius: '12px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        boxShadow: '0 6px 16px rgba(79, 70, 229, 0.15)',
                      }}
                    >
                      {meta.icon === 'Workflow' ? (
                        <Cpu color="#ffffff" size={24} />
                      ) : (
                        <Bot color="#ffffff" size={24} />
                      )}
                    </div>
                    <Tag color="purple" style={{ margin: 0, borderRadius: '6px', fontWeight: 600 }}>
                      v{assistant.version}
                    </Tag>
                  </div>

                  {/* Assistant Details */}
                  <div style={{ flex: 1 }}>
                    <Title level={4} className="font-outfit" style={{ margin: '0 0 8px 0', fontWeight: 700 }}>
                      {meta.title || assistant.name}
                    </Title>

                    {/* Meta Tags */}
                    {meta.tags && meta.tags.length > 0 && (
                      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginBottom: '12px' }}>
                        {meta.tags.map((tag: string) => (
                          <Tag key={tag} color="blue" style={{ borderRadius: '4px', fontSize: '11px', marginRight: 0 }}>
                            {tag}
                          </Tag>
                        ))}
                      </div>
                    )}

                    <Paragraph style={{ color: '#6b7280', fontSize: '13px', margin: '0 0 16px 0', minHeight: '40px', overflow: 'hidden' }}>
                      {assistant.description || 'No description provided.'}
                    </Paragraph>
                  </div>

                  {/* Info Badges */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '20px', borderTop: '1px solid var(--border-color)', paddingTop: '16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#6b7280', fontSize: '12px' }}>
                      <Cpu size={14} />
                      <Text type="secondary">Graph Key: </Text>
                      <Text strong style={{ fontSize: '12px' }}>{assistant.graph_id}</Text>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#6b7280', fontSize: '12px' }}>
                      <Calendar size={14} />
                      <Text type="secondary">Created: </Text>
                      <Text style={{ fontSize: '12px' }}>{new Date(assistant.created_at).toLocaleDateString()}</Text>
                    </div>
                  </div>

                  {/* Launch Button */}
                  <Button
                    type="primary"
                    icon={<MessageSquare size={16} />}
                    onClick={() => onSelect({ id: assistant.assistant_id, name: assistant.name, graphId: assistant.graph_id })}
                    style={{
                      width: '100%',
                      height: '42px',
                      borderRadius: '10px',
                      fontWeight: 600,
                      background: 'linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%)',
                      border: 'none',
                      boxShadow: '0 4px 12px rgba(79, 70, 229, 0.2)',
                    }}
                  >
                    Enter Chat
                  </Button>
                </Card>
              </Col>
            );
          })}
        </Row>
      )}
    </div>
  );
};
