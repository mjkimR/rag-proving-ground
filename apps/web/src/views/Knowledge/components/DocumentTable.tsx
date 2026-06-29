import React from 'react';
import { Card, Table, Space, Tag, Tooltip, Badge, Button, Empty, Typography } from 'antd';
import { FileText, Eye, Settings2, Download, Trash2 } from 'lucide-react';
import type { KnowledgeBaseDocumentRead } from '@/generated/api/types.gen';

const { Text } = Typography;

interface DocumentTableProps {
  docs: KnowledgeBaseDocumentRead[];
  filesLoading: boolean;
  failedDocs: number;
  onInspect: (doc: { id: string; hash: string; name: string }) => void;
  setSelectedDocForSettings: (doc: KnowledgeBaseDocumentRead) => void;
  handleDeleteDoc: (docId: string) => void;
  handleDownload: (docId: string) => void;
}

const formatBytes = (bytes: number, decimals = 2) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
};

export const DocumentTable: React.FC<DocumentTableProps> = ({
  docs,
  filesLoading,
  failedDocs,
  onInspect,
  setSelectedDocForSettings,
  handleDeleteDoc,
  handleDownload,
}) => {
  return (
    <Card variant="borderless" className="glass-card" style={{ borderRadius: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <Text strong style={{ fontSize: '15px' }}>Database Contents</Text>
        {failedDocs > 0 && (
          <Badge status="error" text={`${failedDocs} ingestion failures detected.`} />
        )}
      </div>

      <Table
        dataSource={docs}
        loading={filesLoading}
        rowKey="id"
        pagination={{
          pageSize: 10,
          hideOnSinglePage: true,
        }}
        columns={[
          {
            title: 'Filename',
            dataIndex: 'name',
            key: 'filename',
            render: (text) => (
              <Space>
                <FileText size={15} color="var(--text-secondary)" />
                <span className="font-outfit" style={{ fontWeight: 600, fontSize: '13.5px' }}>{text}</span>
              </Space>
            ),
          },
          {
            title: 'Status',
            dataIndex: 'status',
            key: 'status',
            render: (status: string, record: KnowledgeBaseDocumentRead) => {
              let color = 'default';
              if (status === 'COMPLETED') color = 'success';
              else if (status === 'FAILED') {
                return (
                  <Tooltip title={record.error_message || 'Ingestion failed with an unknown error.'}>
                    <Tag color="error" style={{ borderRadius: '4px', fontWeight: 600, cursor: 'help' }}>
                      {status}
                    </Tag>
                  </Tooltip>
                );
              }
              else if (['PARSING', 'CHUNKING', 'EMBEDDING'].includes(status)) color = 'processing';
              else if (['PENDING_REPARSE', 'PENDING_RECHUNK', 'PENDING_REEMBED'].includes(status)) color = 'warning';
              return (
                <Tag color={color} style={{ borderRadius: '4px', fontWeight: 600 }}>
                  {status}
                </Tag>
              );
            }
          },
          {
            title: 'Strategy Type',
            key: 'strategy',
            render: (_, record: KnowledgeBaseDocumentRead) => {
              const hasParsingOverride = !!record.parsing_config;
              const hasChunkingOverride = !!record.chunking_config;

              if (hasParsingOverride || hasChunkingOverride) {
                return (
                  <Tooltip title={`Parsing override: ${record.parsing_config?.provider || 'none'}, Chunking size: ${record.chunking_config?.chunk_size || 'default'}`}>
                    <Tag color="purple" style={{ cursor: 'help', fontWeight: 500 }}>Custom Override</Tag>
                  </Tooltip>
                );
              }
              return (
                <Tooltip title="Inheriting unified parent settings from Knowledge Base configuration">
                  <Tag color="blue" style={{ cursor: 'help', fontWeight: 500 }}>Inherited Defaults</Tag>
                </Tooltip>
              );
            }
          },
          {
            title: 'Parsed Elements',
            key: 'elements',
            align: 'center',
            render: (_, record: KnowledgeBaseDocumentRead) => {
              const count = (record.document_info as { element_count?: number } | null)?.element_count ?? 0;
              return <Badge count={count} showZero color="#4f46e5" style={{ fontWeight: 700 }} />;
            },
          },
          {
            title: 'File Size',
            key: 'size',
            render: (_, record: KnowledgeBaseDocumentRead) => {
              const bytes = (record.document_info as { size_bytes?: number } | null)?.size_bytes ?? 0;
              return formatBytes(bytes);
            },
          },
          {
            title: 'Actions',
            key: 'actions',
            align: 'right',
            render: (_, record: KnowledgeBaseDocumentRead) => (
              <Space size="small">
                <Button
                  type="text"
                  size="small"
                  icon={<Eye size={14} />}
                  onClick={() => onInspect({ id: record.id, hash: record.file_hash, name: record.name })}
                  disabled={record.status !== 'COMPLETED'}
                  style={{ display: 'flex', alignItems: 'center' }}
                >
                  Inspect Layout
                </Button>
                <Button
                  type="text"
                  size="small"
                  icon={<Settings2 size={14} />}
                  onClick={() => setSelectedDocForSettings(record)}
                  style={{ display: 'flex', alignItems: 'center' }}
                >
                  Overrides
                </Button>
                <Button
                  type="text"
                  size="small"
                  icon={<Download size={14} />}
                  onClick={() => handleDownload(record.id)}
                />
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<Trash2 size={14} />}
                  onClick={() => handleDeleteDoc(record.id)}
                  disabled={record.status === 'DELETING'}
                />
              </Space>
            ),
          },
        ]}
        locale={{
          emptyText: <Empty description="No documents uploaded to this collection yet. Ingest your first document above!" />
        }}
      />
    </Card>
  );
};
