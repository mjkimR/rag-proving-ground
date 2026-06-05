import React, { useState } from 'react';
import {
  Card, Table, Button, Space, Typography, Upload, Select, Spin, Tag, Empty, Modal, Badge, Tooltip, Row, Col
} from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getKnowledgeBaseDocumentsApiV1KnowledgeBasesKnowledgeBaseIdDocumentsGet,
  uploadKnowledgeBaseDocumentApiV1KnowledgeBasesKnowledgeBaseIdUploadPost,
  deleteKnowledgeBaseDocumentApiV1KnowledgeBaseDocumentsKnowledgeBaseDocumentIdDelete
} from '@/generated/api/sdk.gen';
import {
  FileText, Trash2, Download, Eye, AlertCircle, UploadCloud, Settings2, Settings
} from 'lucide-react';
import type { KnowledgeBaseDocumentRead, KnowledgeParsingConfig, ChunkingConfig } from '@/generated/api/types.gen';
import { API_BASE_URL } from '@/lib/config';
import { DocumentSettingsModal } from './DocumentSettingsModal';

const { Title, Text } = Typography;
const { Option } = Select;

interface DocumentListProps {
  selectedKnowledgeId: string;
  selectedKnowledgeName: string;
  kbDefaultParsingConfig?: KnowledgeParsingConfig | null;
  kbDefaultChunkingConfig?: ChunkingConfig | null;
  onInspect: (doc: { id: string; hash: string; name: string }) => void;
  onOpenSettings: () => void;
}

export const DocumentList: React.FC<DocumentListProps> = ({
  selectedKnowledgeId,
  selectedKnowledgeName,
  kbDefaultParsingConfig,
  kbDefaultChunkingConfig,
  onInspect,
  onOpenSettings
}) => {
  const queryClient = useQueryClient();
  const [parserProvider, setParserProvider] = useState('docling');
  const [isUploading, setIsUploading] = useState(false);
  const [selectedDocForSettings, setSelectedDocForSettings] = useState<KnowledgeBaseDocumentRead | null>(null);

  // 1. Fetch Knowledge Files
  const { data: fileList, isLoading: filesLoading, refetch: refetchFiles } = useQuery({
    queryKey: ['fileList', selectedKnowledgeId],
    queryFn: () => {
      return getKnowledgeBaseDocumentsApiV1KnowledgeBasesKnowledgeBaseIdDocumentsGet({
        path: { knowledge_base_id: selectedKnowledgeId },
        throwOnError: true,
      });
    },
    enabled: !!selectedKnowledgeId,
  });

  // 2. Upload file mutation
  const handleUpload = async (file: File) => {
    setIsUploading(true);
    try {
      await uploadKnowledgeBaseDocumentApiV1KnowledgeBasesKnowledgeBaseIdUploadPost({
        path: {
          knowledge_base_id: selectedKnowledgeId,
        },
        body: {
          file: file,
          provider: parserProvider,
        },
        throwOnError: true,
      });
      refetchFiles();
      queryClient.invalidateQueries({ queryKey: ['kbList'] });
    } catch (e) {
      console.error('File parsing/upload failed:', e);
      Modal.error({
        title: 'Document Ingestion Failed',
        content: e instanceof Error ? e.message : 'Please check your backend connection, Docling parser logs, or LLM config.',
        icon: <AlertCircle color="#ef4444" />,
      });
    } finally {
      setIsUploading(false);
    }
  };

  // 3. Delete file mutation
  const deleteMutation = useMutation({
    mutationFn: (docId: string) => {
      return deleteKnowledgeBaseDocumentApiV1KnowledgeBaseDocumentsKnowledgeBaseDocumentIdDelete({
        path: {
          knowledge_base_document_id: docId,
        },
        throwOnError: true,
      });
    },
    onSuccess: () => {
      refetchFiles();
      queryClient.invalidateQueries({ queryKey: ['kbList'] });
    },
  });

  const handleDelete = (docId: string) => {
    Modal.confirm({
      title: 'Delete Document',
      content: 'Are you sure you want to delete this document and all its parsed elements/chunks from the knowledge base?',
      okText: 'Yes, Delete',
      okType: 'danger',
      onOk: () => deleteMutation.mutate(docId),
    });
  };

  const handleDownload = (docId: string) => {
    window.open(`${API_BASE_URL}/api/v1/knowledge_base_documents/${docId}/download`, '_blank');
  };

  const formatBytes = (bytes: number, decimals = 2) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  };

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {/* Header & Upload panel */}
      <Card variant="borderless" className="glass-card">
        <Row align="middle" justify="space-between" gutter={[16, 16]}>
          <Col>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Title level={4} className="font-outfit" style={{ margin: 0 }}>
                KB: <span style={{ color: 'var(--accent-gradient)' }}>{selectedKnowledgeName}</span>
              </Title>
              <Button
                type="text"
                shape="circle"
                icon={<Settings size={16} color="var(--text-secondary)" />}
                onClick={onOpenSettings}
                title="Knowledge Base Settings"
              />
            </div>
            <Text type="secondary">Upload and parse documents into this knowledge base.</Text>
          </Col>
          <Col>
            <Space size="middle">
              <Text strong>Parser Provider:</Text>
              <Select
                defaultValue="docling"
                style={{ width: 140 }}
                onChange={(val) => setParserProvider(val)}
                className="font-outfit"
              >
                <Option value="docling">Docling</Option>
                <Option value="marker">Marker</Option>
              </Select>
            </Space>
          </Col>
        </Row>

        <div style={{ marginTop: '20px' }}>
          <Upload.Dragger
            customRequest={({ file }) => handleUpload(file as File)}
            showUploadList={false}
            disabled={isUploading}
          >
            {isUploading ? (
              <div style={{ padding: '24px 0' }}>
                <Spin size="large" />
                <p className="font-outfit" style={{ marginTop: '16px', fontWeight: 600, fontSize: '15px' }}>
                  Docling Ingestion in progress...
                </p>
                <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary)' }}>
                  Layout detection, parsing, chunking and embedding are running in background.
                </p>
              </div>
            ) : (
              <div style={{ padding: '24px 0' }}>
                <p style={{ display: 'flex', justifyContent: 'center' }}>
                  <UploadCloud size={40} color="#4f46e5" />
                </p>
                <p className="font-outfit" style={{ fontWeight: 700, fontSize: '15px', margin: '12px 0 4px 0' }}>
                  Click or drag files to this area to upload and parse
                </p>
                <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary)' }}>
                  Supports PDF, HTML, MD, DOCX, TXT. File size limit: 10MB.
                </p>
              </div>
            )}
          </Upload.Dragger>
        </div>
      </Card>

      {/* Documents List Table */}
      <Card
        variant="borderless"
        className="glass-card"
        title={<span className="font-outfit" style={{ fontSize: '15px', fontWeight: 700 }}>Knowledge Documents</span>}
      >
        <Table
          dataSource={fileList?.data?.items || []}
          loading={filesLoading}
          rowKey="id"
          columns={[
            {
              title: 'Filename',
              dataIndex: 'name',
              key: 'filename',
              render: (text) => (
                <Space>
                  <FileText size={16} color="var(--text-secondary)" />
                  <span className="font-outfit" style={{ fontWeight: 600 }}>{text}</span>
                </Space>
              ),
            },
            {
              title: 'Status',
              dataIndex: 'status',
              key: 'status',
              render: (status: string) => {
                let color = 'default';
                if (status === 'COMPLETED') color = 'success';
                else if (status === 'FAILED') color = 'error';
                else if (['PARSING', 'CHUNKING', 'EMBEDDING'].includes(status)) color = 'processing';
                else if (['PENDING_REPARSE', 'PENDING_RECHUNK', 'PENDING_REEMBED'].includes(status)) color = 'warning';
                return (
                  <Tag color={color}>
                    {status}
                  </Tag>
                );
              }
            },
            {
              title: 'Strategy',
              key: 'strategy',
              render: (_, record: KnowledgeBaseDocumentRead) => {
                const hasParsingOverride = !!record.parsing_config;
                const hasChunkingOverride = !!record.chunking_config;

                if (hasParsingOverride || hasChunkingOverride) {
                  const overrides = [];
                  if (hasParsingOverride) overrides.push(`Parsing: ${record.parsing_config?.provider}`);
                  if (hasChunkingOverride) overrides.push(`Chunking: size=${record.chunking_config?.chunk_size}`);

                  return (
                    <Tooltip title={`Overrides set: ${overrides.join(', ')}`}>
                      <Tag color="purple" style={{ cursor: 'help' }}>Custom Override</Tag>
                    </Tooltip>
                  );
                }

                return (
                  <Tooltip title="Inheriting default settings from Knowledge Base">
                    <Tag color="blue" style={{ cursor: 'help' }}>Inherited</Tag>
                  </Tooltip>
                );
              }
            },
            {
              title: 'File Hash',
              dataIndex: 'file_hash',
              key: 'hash',
              render: (text) => (
                <Tooltip title={text}>
                  <code>{text ? text.slice(0, 8) : ''}...</code>
                </Tooltip>
              ),
            },
            {
              title: 'Elements',
              key: 'elements',
              align: 'center',
              render: (_, record: any) => {
                const count = record.document_info?.element_count ?? 0;
                return <Badge count={count} showZero color="#4f46e5" style={{ fontWeight: 700 }} />;
              },
            },
            {
              title: 'Size',
              key: 'size',
              render: (_, record: any) => {
                const bytes = record.document_info?.size_bytes ?? 0;
                return formatBytes(bytes);
              },
            },
            {
              title: 'Actions',
              key: 'actions',
              align: 'right',
              render: (_, record: KnowledgeBaseDocumentRead) => (
                <Space size="middle">
                  <Button
                    type="text"
                    icon={<Eye size={16} />}
                    onClick={() => onInspect({ id: record.id, hash: record.file_hash, name: record.name })}
                    disabled={record.status !== 'COMPLETED'}
                  >
                    Inspect
                  </Button>
                  <Button
                    type="text"
                    icon={<Settings2 size={16} />}
                    onClick={() => setSelectedDocForSettings(record)}
                  >
                    Settings
                  </Button>
                  <Button
                    type="text"
                    icon={<Download size={16} />}
                    onClick={() => handleDownload(record.id)}
                  />
                  <Button
                    type="text"
                    danger
                    icon={<Trash2 size={16} />}
                    onClick={() => handleDelete(record.id)}
                  />
                </Space>
              ),
            },
          ]}
          locale={{
            emptyText: <Empty description="No documents uploaded yet. Upload your first file above!" />
          }}
        />
      </Card>

      {/* Document Settings Modal */}
      <DocumentSettingsModal
        visible={!!selectedDocForSettings}
        onClose={() => setSelectedDocForSettings(null)}
        document={selectedDocForSettings}
        kbDefaultParsingConfig={kbDefaultParsingConfig}
        kbDefaultChunkingConfig={kbDefaultChunkingConfig}
        onSuccess={() => {
          refetchFiles();
          queryClient.invalidateQueries({ queryKey: ['kbList'] });
        }}
      />
    </Space>
  );
};
