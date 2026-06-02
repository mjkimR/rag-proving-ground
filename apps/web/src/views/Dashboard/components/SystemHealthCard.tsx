import React from 'react';
import { Card, Typography, Alert, Tag } from 'antd';

const { Paragraph } = Typography;

interface SystemHealthCardProps {
  systemStatus: { text: string; color: string; desc: string };
}

export const SystemHealthCard: React.FC<SystemHealthCardProps> = ({
  systemStatus,
}) => {
  return (
    <Card
      title={<span className="font-outfit" style={{ fontSize: '16px', fontWeight: 700 }}>System Health Info</span>}
      variant="borderless"
      className="glass-card"
      style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
      styles={{ body: { flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' } }}
    >
      <div>
        <Paragraph style={{ color: 'var(--text-secondary)', fontSize: '14px', lineHeight: 1.6, marginBottom: '16px' }}>
          This monorepo serves as a sandboxed testing ground for high-fidelity document parsing, semantic chunking, and LLM-compatible retrieval pipelines.
        </Paragraph>

        <Alert
          title={systemStatus.text === 'Online' ? 'Active & Ready' : 'Warning'}
          description={systemStatus.desc}
          type={systemStatus.text === 'Online' ? 'success' : 'warning'}
          showIcon
        />
      </div>

      <div style={{ marginTop: '24px', borderTop: '1px solid var(--border-color)', paddingTop: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '13px' }}>
          <span style={{ fontWeight: 600 }}>RAG-Core Library:</span>
          <Tag color="cyan" style={{ margin: 0 }}>Ready</Tag>
        </div>
      </div>
    </Card>
  );
};
