import React from 'react';
import { Card, Col, Row, Statistic, Table, Tag, Typography, Alert, Space } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { listKnowledgeBasesApiV1KnowledgeGet, healthApiHealthGet } from '@/generated/api/sdk.gen';
import { Database, FileText, Activity, Server, AlertCircle } from 'lucide-react';
import { useThemeStore } from '@/stores/themeStore';

const { Title, Paragraph } = Typography;

export const Dashboard: React.FC = () => {
  const { setActiveTab, setSelectedKnowledgeName } = useThemeStore();

  // 1. Fetch all knowledge bases
  const { data: kbList, isLoading: kbLoading, error: kbError } = useQuery({
    queryKey: ['kbList'],
    queryFn: () => listKnowledgeBasesApiV1KnowledgeGet({ throwOnError: true }),
  });

  // 2. Fetch API Health
  const { data: healthData, isError: isHealthError } = useQuery({
    queryKey: ['apiHealth'],
    queryFn: () => healthApiHealthGet({ throwOnError: true }),
    refetchInterval: 5000,
  });

  const getSystemStatus = () => {
    if (isHealthError) return { text: 'Offline', color: 'red', desc: 'Cannot connect to backend API.' };
    if (!healthData) return { text: 'Connecting...', color: 'orange', desc: 'Resolving connection...' };
    const res = healthData.data as any;
    if (res?.status === 'healthy' || res?.success || res?.status === 'ok') {
      return { text: 'Online', color: 'green', desc: 'System API is fully responsive.' };
    }
    return { text: 'Degraded', color: 'warning', desc: 'System running but with exceptions.' };
  };

  const status = getSystemStatus();

  // Render metrics card
  return (
    <div style={{ padding: '8px 0' }}>
      <Row gutter={[18, 18]}>
        {/* Metric 1: Total KB */}
        <Col xs={24} sm={12} lg={6}>
          <Card bordered={false} hoverable className="glass-card">
            <Statistic
              title={<span className="font-outfit" style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-secondary)' }}>Knowledge Bases</span>}
              value={kbList?.data ? kbList.data.length : 0}
              loading={kbLoading}
              prefix={<Database size={22} color="var(--accent-gradient)" style={{ marginRight: '8px', verticalAlign: 'middle' }} />}
              valueStyle={{ fontWeight: 800, fontSize: '28px', fontFamily: 'Outfit' }}
            />
          </Card>
        </Col>

        {/* Metric 2: System Health */}
        <Col xs={24} sm={12} lg={6}>
          <Card bordered={false} hoverable className="glass-card">
            <Statistic
              title={<span className="font-outfit" style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-secondary)' }}>System Status</span>}
              value={status.text}
              prefix={<Activity size={22} color={status.color === 'green' ? '#10b981' : '#f59e0b'} style={{ marginRight: '8px', verticalAlign: 'middle' }} />}
              valueStyle={{ fontWeight: 800, fontSize: '24px', fontFamily: 'Outfit', color: status.color === 'green' ? '#10b981' : '#f59e0b' }}
            />
          </Card>
        </Col>

        {/* Metric 3: Active Parser */}
        <Col xs={24} sm={12} lg={6}>
          <Card bordered={false} hoverable className="glass-card">
            <Statistic
              title={<span className="font-outfit" style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-secondary)' }}>Parser Engine</span>}
              value="Docling SDK"
              prefix={<Server size={22} color="#8b5cf6" style={{ marginRight: '8px', verticalAlign: 'middle' }} />}
              valueStyle={{ fontWeight: 800, fontSize: '24px', fontFamily: 'Outfit', color: '#8b5cf6' }}
            />
          </Card>
        </Col>

        {/* Metric 4: Platform Version */}
        <Col xs={24} sm={12} lg={6}>
          <Card bordered={false} hoverable className="glass-card">
            <Statistic
              title={<span className="font-outfit" style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-secondary)' }}>Platform Version</span>}
              value="v0.1.0-alpha"
              prefix={<FileText size={22} color="#f59e0b" style={{ marginRight: '8px', verticalAlign: 'middle' }} />}
              valueStyle={{ fontWeight: 800, fontSize: '24px', fontFamily: 'Outfit' }}
            />
          </Card>
        </Col>
      </Row>

      {/* Main Section */}
      <Row gutter={[18, 18]} style={{ marginTop: '24px' }}>
        <Col xs={24} lg={16}>
          <Card
            title={<span className="font-outfit" style={{ fontSize: '16px', fontWeight: 700 }}>Your Knowledge Bases</span>}
            bordered={false}
            className="glass-card"
          >
            {kbError ? (
              <Alert
                message="Error loading knowledge bases"
                description={kbError.toString()}
                type="error"
                showIcon
                icon={<AlertCircle />}
              />
            ) : kbList?.data && kbList.data.length > 0 ? (
              <Table
                dataSource={kbList.data.map((name, index) => ({ key: index, name }))}
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
                    render: (_, record) => <code>s3://local_storage/knowledge/{record.name}/</code>,
                  },
                  {
                    title: 'Action',
                    key: 'action',
                    align: 'right',
                    render: (_, record) => (
                      <Space size="middle">
                        <a
                          onClick={() => {
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
              />
            ) : (
              <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                <Database size={48} style={{ opacity: 0.3, marginBottom: '12px' }} />
                <p style={{ margin: 0, fontSize: '15px', fontWeight: 600 }}>No knowledge bases found.</p>
                <p style={{ margin: '4px 0 0 0', fontSize: '13px' }}>
                  Go to <a onClick={() => setActiveTab('knowledge')}>Knowledge Bases</a> to create your first one.
                </p>
              </div>
            )}
          </Card>
        </Col>

        {/* Sidebar Info Panel */}
        <Col xs={24} lg={8}>
          <Card
            title={<span className="font-outfit" style={{ fontSize: '16px', fontWeight: 700 }}>System Health Info</span>}
            bordered={false}
            className="glass-card"
            style={{ height: '100%' }}
          >
            <Paragraph style={{ color: 'var(--text-secondary)', fontSize: '14px', lineHeight: 1.6 }}>
              This monorepo serves as a sandboxed testing ground for high-fidelity document parsing, semantic chunking, and LLM-compatible retrieval pipelines.
            </Paragraph>

            <Alert
              message={status.text === 'Online' ? 'Active & Ready' : 'Warning'}
              description={status.desc}
              type={status.text === 'Online' ? 'success' : 'warning'}
              showIcon
              style={{ marginTop: '16px' }}
            />

            <div style={{ marginTop: '24px', borderTop: '1px solid var(--border-color)', paddingTop: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '13px' }}>
                <span style={{ fontWeight: 600 }}>RAG-Core Library:</span>
                <Tag color="cyan">Ready</Tag>
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
};
