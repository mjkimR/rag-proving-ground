import React from 'react';
import { Card, Typography, Button, Tabs, Table, Tooltip, Badge, Tag, message } from 'antd';
import { RefreshCw } from 'lucide-react';
import type { JobProcessHistoryRead } from '@/generated/api/types.gen';
import styles from './KnowledgeBaseDetail.module.css';

const { Title, Paragraph, Text } = Typography;

interface JobHistoryListProps {
  parseHistory: { data?: { items?: JobProcessHistoryRead[] } } | null | undefined;
  parsingHistLoading: boolean;
  chunkHistory: { data?: { items?: JobProcessHistoryRead[] } } | null | undefined;
  chunkingHistLoading: boolean;
  embedHistory: { data?: { items?: JobProcessHistoryRead[] } } | null | undefined;
  embeddingHistLoading: boolean;
  refetchParseHist: () => void;
  refetchChunkHist: () => void;
  refetchEmbedHist: () => void;
}

const formatDate = (dateString: string) => {
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return dateString;
  }
};

const getHistoryMetric = (record: JobProcessHistoryRead, key: string) => {
  const value = record.metrics?.[key];
  return typeof value === 'number' ? value : undefined;
};

export const JobHistoryList: React.FC<JobHistoryListProps> = ({
  parseHistory,
  parsingHistLoading,
  chunkHistory,
  chunkingHistLoading,
  embedHistory,
  embeddingHistLoading,
  refetchParseHist,
  refetchChunkHist,
  refetchEmbedHist,
}) => {
  const handleReload = () => {
    refetchParseHist();
    refetchChunkHist();
    refetchEmbedHist();
    message.success('Processing history reloaded.');
  };

  return (
    <Card variant="borderless" className="glass-card" style={{ borderRadius: '16px' }}>
      <div style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap' }}>
        <div>
          <Title level={4} style={{ margin: 0, fontWeight: 700 }}>Database Processing Logs</Title>
          <Paragraph type="secondary" style={{ margin: '4px 0 0 0' }}>
            Real-time feedback audits from parsing workers, boundary chunkers, and embedding vector indexing.
          </Paragraph>
        </div>
        <Button
          icon={<RefreshCw size={14} />}
          onClick={handleReload}
        >
          Reload History
        </Button>
      </div>

      <Tabs
        defaultActiveKey="parse-hist"
        className={styles.subHistoryTabs}
        items={[
          {
            key: 'parse-hist',
            label: `1. Parsing Workers (${parseHistory?.data?.items?.length || 0})`,
            children: (
              <Table
                dataSource={parseHistory?.data?.items || []}
                loading={parsingHistLoading}
                rowKey="id"
                size="small"
                pagination={{ pageSize: 8 }}
                columns={[
                  { title: 'Date', dataIndex: 'created_at', render: (d) => formatDate(d) },
                  { title: 'Provider', dataIndex: 'provider', render: (p) => <Tag color="purple">{p}</Tag> },
                  {
                    title: 'Status',
                    dataIndex: 'outcome',
                    render: (s) => (
                      <Tag color={s === 'SUCCESS' || s === 'COMPLETED' ? 'success' : 'error'} style={{ fontWeight: 600 }}>
                        {s}
                      </Tag>
                    )
                  },
                  {
                    title: 'Duration',
                    dataIndex: 'duration_seconds',
                    render: (d) => d ? `${d.toFixed(2)}s` : '-'
                  },
                  {
                    title: 'Details / Error',
                    dataIndex: 'error_message',
                    render: (err) => err ? (
                      <Tooltip title={err}>
                        <Text type="danger" style={{ fontSize: '11px', display: 'inline-block', maxWidth: '300px', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                          {err}
                        </Text>
                      </Tooltip>
                    ) : <span style={{ color: 'var(--text-secondary)', fontSize: '11px' }}>Process Clean</span>
                  }
                ]}
              />
            )
          },
          {
            key: 'chunk-hist',
            label: `2. Chunk Splits (${chunkHistory?.data?.items?.length || 0})`,
            children: (
              <Table
                dataSource={chunkHistory?.data?.items || []}
                loading={chunkingHistLoading}
                rowKey="id"
                size="small"
                pagination={{ pageSize: 8 }}
                columns={[
                  { title: 'Date', dataIndex: 'created_at', render: (d) => formatDate(d) },
                  { title: 'Stage', dataIndex: 'stage', render: (s) => <Tag color="blue">{s}</Tag> },
                  {
                    title: 'Chunks Created',
                    render: (_, record: JobProcessHistoryRead) => getHistoryMetric(record, 'chunk_count') ?? '-'
                  },
                  {
                    title: 'Status',
                    dataIndex: 'outcome',
                    render: (s) => (
                      <Tag color={s === 'SUCCESS' || s === 'COMPLETED' ? 'success' : 'error'} style={{ fontWeight: 600 }}>
                        {s}
                      </Tag>
                    )
                  },
                  {
                    title: 'Duration',
                    dataIndex: 'duration_seconds',
                    render: (d) => d ? `${d.toFixed(2)}s` : '-'
                  },
                  {
                    title: 'Details / Error',
                    dataIndex: 'error_message',
                    render: (err) => err ? (
                      <Tooltip title={err}>
                        <Text type="danger" style={{ fontSize: '11px', display: 'inline-block', maxWidth: '300px', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                          {err}
                        </Text>
                      </Tooltip>
                    ) : <span style={{ color: 'var(--text-secondary)', fontSize: '11px' }}>Split Successful</span>
                  }
                ]}
              />
            )
          },
          {
            key: 'embed-hist',
            label: `3. Vector Embeds (${embedHistory?.data?.items?.length || 0})`,
            children: (
              <Table
                dataSource={embedHistory?.data?.items || []}
                loading={embeddingHistLoading}
                rowKey="id"
                size="small"
                pagination={{ pageSize: 8 }}
                columns={[
                  { title: 'Date', dataIndex: 'created_at', render: (d) => formatDate(d) },
                  { title: 'Model Name', dataIndex: 'model_name', render: (m) => <Tag color="pink">{m}</Tag> },
                  {
                    title: 'Vectors Indexed',
                    render: (_, record: JobProcessHistoryRead) => (
                      <Badge
                        count={getHistoryMetric(record, 'vector_count') ?? 0}
                        showZero
                        color="#4f46e5"
                        style={{ fontWeight: 700 }}
                      />
                    )
                  },
                  {
                    title: 'Status',
                    dataIndex: 'outcome',
                    render: (s) => (
                      <Tag color={s === 'SUCCESS' || s === 'COMPLETED' ? 'success' : 'error'} style={{ fontWeight: 600 }}>
                        {s}
                      </Tag>
                    )
                  },
                  {
                    title: 'Duration',
                    dataIndex: 'duration_seconds',
                    render: (d) => d ? `${d.toFixed(2)}s` : '-'
                  },
                  {
                    title: 'Details / Error',
                    dataIndex: 'error_message',
                    render: (err) => err ? (
                      <Tooltip title={err}>
                        <Text type="danger" style={{ fontSize: '11px', display: 'inline-block', maxWidth: '300px', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                          {err}
                        </Text>
                      </Tooltip>
                    ) : <span style={{ color: 'var(--text-secondary)', fontSize: '11px' }}>Index Complete</span>
                  }
                ]}
              />
            )
          }
        ]}
      />
    </Card>
  );
};
