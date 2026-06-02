import React from 'react';
import { Card, Table, Alert, Space } from 'antd';
import { Database, AlertCircle } from 'lucide-react';
import { useThemeStore } from '@/stores/themeStore';
import type { GetKnowledgeBasesApiV1KnowledgeBasesGetResponse, KnowledgeBaseRead } from '@/generated/api/types.gen';

interface KnowledgeBasesCardProps {
  kbList: { data: GetKnowledgeBasesApiV1KnowledgeBasesGetResponse } | undefined;
  kbLoading: boolean;
  kbError: Error | null | unknown;
}

export const KnowledgeBasesCard: React.FC<KnowledgeBasesCardProps> = ({
  kbList,
  kbLoading,
  kbError,
}) => {
  const { setActiveTab, setSelectedKnowledgeName, setSelectedKnowledgeId } = useThemeStore();

  return (
    <Card
      title={<span className="font-outfit" style={{ fontSize: '16px', fontWeight: 700 }}>Your Knowledge Bases</span>}
      variant="borderless"
      className="glass-card"
      style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
      styles={{ body: { flex: 1, display: 'flex', flexDirection: 'column', justifyContent: (kbList?.data?.items?.length ?? 0) > 0 ? 'flex-start' : 'center' } }}
    >
      {kbError ? (
        <Alert
          title="Error loading knowledge bases"
          description={kbError.toString()}
          type="error"
          showIcon
          icon={<AlertCircle />}
        />
      ) : kbList?.data?.items && kbList.data.items.length > 0 ? (
        <Table
          dataSource={kbList.data.items}
          rowKey="id"
          columns={[
            {
              title: 'Name',
              dataIndex: 'name',
              key: 'name',
              render: (text) => <span className="font-outfit" style={{ fontWeight: 600, fontSize: '15px' }}>{text}</span>,
            },
            {
              title: 'Storage Path',
              key: 'path',
              render: (_, record: KnowledgeBaseRead) => <code>s3://local_storage/knowledge/{record.name}/</code>,
            },
            {
              title: 'Action',
              key: 'action',
              align: 'right',
              render: (_, record: KnowledgeBaseRead) => (
                <Space size="middle">
                  <a
                    onClick={() => {
                      setSelectedKnowledgeId(record.id);
                      setSelectedKnowledgeName(record.name);
                      setActiveTab('knowledge');
                    }}
                    className="font-outfit"
                    style={{ fontWeight: 700 }}
                  >
                    Manage Bases
                  </a>
                </Space>
              ),
            },
          ]}
          pagination={false}
          size="middle"
          loading={kbLoading}
        />
      ) : (
        <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-secondary)' }}>
          <Database size={48} style={{ opacity: 0.3, marginBottom: '12px' }} />
          <p style={{ margin: 0, fontSize: '15px', fontWeight: 600 }}>No knowledge bases found.</p>
          <p style={{ margin: '4px 0 0 0', fontSize: '13px' }}>
            Go to <a onClick={() => setActiveTab('knowledge')}>Knowledge Bases</a> to create your first one.
          </p>
        </div>
      )}
    </Card>
  );
};
