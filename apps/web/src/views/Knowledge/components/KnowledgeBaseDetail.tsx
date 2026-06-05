import React, { useState, useEffect } from 'react';
import {
  Card, Table, Button, Space, Typography, Upload, Select, Spin, Tag, Empty, Modal, Badge,
  Tooltip, Row, Col, Tabs, Form, Input, InputNumber, Switch, Radio, Alert, message
} from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getKnowledgeBaseDocumentsApiV1KnowledgeBasesKnowledgeBaseIdDocumentsGet,
  uploadKnowledgeBaseDocumentApiV1KnowledgeBasesKnowledgeBaseIdUploadPost,
  deleteKnowledgeBaseDocumentApiV1KnowledgeBaseDocumentsKnowledgeBaseDocumentIdDelete,
  patchKnowledgeBaseApiV1KnowledgeBasesKnowledgeBaseIdPatch,
  deleteKnowledgeBaseApiV1KnowledgeBasesKnowledgeBaseIdDelete,
  getJobProcessHistoriesApiV1JobProcessHistoriesGet,
  getModelCatalogOptionsApiV1ModelCatalogOptionsGet,
} from '@/generated/api/sdk.gen';
import {
  FileText, Trash2, Download, Eye, AlertCircle, UploadCloud, Settings2, Settings,
  ArrowLeft, RefreshCw, Cpu, Sliders, Info, Clock, Search
} from 'lucide-react';
import type {
  KnowledgeBaseRead, KnowledgeBaseDocumentRead, KnowledgeBaseConfigApplyMode, JobProcessHistoryRead
} from '@/generated/api/types.gen';
import { DocumentSettingsModal } from './DocumentSettingsModal';
import { RetrievalTestTab } from './RetrievalTestTab';
import { API_BASE_URL } from '@/lib/config';

const { Title, Text, Paragraph } = Typography;
const { Option } = Select;

const PARSER_LABELS: Record<string, string> = {
  docling: 'Docling (Layout + Tables Analysis)',
};

interface KnowledgeBaseDetailProps {
  kb: KnowledgeBaseRead;
  onBack: () => void;
  onDeleteSelected: () => void;
  onUpdateKbName: (name: string) => void;
  onInspect: (doc: { id: string; hash: string; name: string }) => void;
}

export const KnowledgeBaseDetail: React.FC<KnowledgeBaseDetailProps> = ({
  kb,
  onBack,
  onDeleteSelected,
  onUpdateKbName,
  onInspect
}) => {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState('1');

  // Fetch dynamic configuration options
  const { data: configOptions, isLoading: configLoading } = useQuery({
    queryKey: ['configOptions'],
    queryFn: () => getModelCatalogOptionsApiV1ModelCatalogOptionsGet({ throwOnError: true }),
  });

  const embeddingModels = configOptions?.data?.embedding_models || [];
  const parserProviders = configOptions?.data?.parser_providers || [];

  const [parserProvider, setParserProvider] = useState('docling');
  const [isUploading, setIsUploading] = useState(false);
  const [selectedDocForSettings, setSelectedDocForSettings] = useState<KnowledgeBaseDocumentRead | null>(null);
  // Configuration settings form states
  const [settingsForm] = Form.useForm();
  const [configConfirmVisible, setConfigConfirmVisible] = useState(false);
  const [pendingConfigValues, setPendingConfigValues] = useState<any>(null);
  const [configLoadType, setConfigLoadType] = useState<'low' | 'high' | 'reembed'>('low');
  const [applyMode, setApplyMode] = useState<KnowledgeBaseConfigApplyMode>('INHERITED_ONLY');

  // --- QUERY 1: Fetch documents in KB ---
  const { data: fileList, isLoading: filesLoading, refetch: refetchFiles } = useQuery({
    queryKey: ['fileList', kb.id],
    queryFn: () => {
      return getKnowledgeBaseDocumentsApiV1KnowledgeBasesKnowledgeBaseIdDocumentsGet({
        path: { knowledge_base_id: kb.id },
        throwOnError: true,
      });
    },
    enabled: !!kb.id,
  });

  // --- QUERIES FOR HISTORY (TAB 3) ---
  const { data: parseHistory, isLoading: parsingHistLoading, refetch: refetchParseHist } = useQuery({
    queryKey: ['parsingHistory', kb.id],
    queryFn: () => getJobProcessHistoriesApiV1JobProcessHistoriesGet({
      query: { resource_type: 'knowledge_base_document', stage: 'parsing', limit: 20 },
      throwOnError: true,
    }),
    enabled: activeTab === '3',
  });

  const { data: chunkHistory, isLoading: chunkingHistLoading, refetch: refetchChunkHist } = useQuery({
    queryKey: ['chunkingHistory', kb.id],
    queryFn: () => getJobProcessHistoriesApiV1JobProcessHistoriesGet({
      query: { resource_type: 'knowledge_base_document', stage: 'chunking', limit: 20 },
      throwOnError: true,
    }),
    enabled: activeTab === '3',
  });

  const { data: embedHistory, isLoading: embeddingHistLoading, refetch: refetchEmbedHist } = useQuery({
    queryKey: ['embeddingHistory', kb.id],
    queryFn: () => getJobProcessHistoriesApiV1JobProcessHistoriesGet({
      query: { resource_type: 'knowledge_base_document', stage: 'embedding', limit: 20 },
      throwOnError: true,
    }),
    enabled: activeTab === '3',
  });

  // Setup form default values when KB changes
  useEffect(() => {
    if (kb) {
      settingsForm.setFieldsValue({
        name: kb.name,
        embedding_config: {
          model: kb.embedding_config?.model || 'text-embedding-3-small',
          distance: kb.embedding_config?.distance || 'cosine',
        },
        default_chunking_config: {
          chunk_size: kb.default_chunking_config?.chunk_size ?? 1024,
          chunk_overlap: kb.default_chunking_config?.chunk_overlap ?? 200,
          merge_max_chars: kb.default_chunking_config?.merge_max_chars ?? 4096,
          breadcrumb_depth: kb.default_chunking_config?.breadcrumb_depth ?? 2,
          include_root_breadcrumb: kb.default_chunking_config?.include_root_breadcrumb ?? true,
          breadcrumb_separator: kb.default_chunking_config?.breadcrumb_separator || ' > ',
        },
        default_parsing_config: {
          provider: kb.default_parsing_config?.provider || 'docling',
        }
      });
    }
  }, [kb, settingsForm]);

  useEffect(() => {
    if (parserProviders.length > 0 && !parserProviders.includes(parserProvider)) {
      setParserProvider(parserProviders[0]);
    }
  }, [parserProviders, parserProvider]);

  // --- MUTATION: Upload Document ---
  const handleUpload = async (file: File) => {
    setIsUploading(true);
    try {
      await uploadKnowledgeBaseDocumentApiV1KnowledgeBasesKnowledgeBaseIdUploadPost({
        path: {
          knowledge_base_id: kb.id,
        },
        body: {
          file: file,
          provider: parserProvider,
        },
        throwOnError: true,
      });
      message.success(`Document "${file.name}" uploaded and queued for processing!`);
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

  // --- MUTATION: Delete Document ---
  const deleteDocMutation = useMutation({
    mutationFn: (docId: string) => {
      return deleteKnowledgeBaseDocumentApiV1KnowledgeBaseDocumentsKnowledgeBaseDocumentIdDelete({
        path: {
          knowledge_base_document_id: docId,
        },
        throwOnError: true,
      });
    },
    onSuccess: () => {
      message.success('Document deleted successfully.');
      refetchFiles();
      queryClient.invalidateQueries({ queryKey: ['kbList'] });
    },
    onError: (e) => {
      message.error(e instanceof Error ? e.message : 'Failed to delete document.');
    }
  });

  const handleDeleteDoc = (docId: string) => {
    Modal.confirm({
      title: 'Delete Document',
      content: 'Are you sure you want to delete this document and all its parsed elements/chunks from the database?',
      okText: 'Yes, Delete',
      okType: 'danger',
      onOk: () => deleteDocMutation.mutate(docId),
    });
  };

  const handleDownload = (docId: string) => {
    window.open(`${API_BASE_URL}/api/v1/knowledge_base_documents/${docId}/download`, '_blank');
  };

  // --- MUTATION: Delete KB ---
  const deleteKbMutation = useMutation({
    mutationFn: () => {
      return deleteKnowledgeBaseApiV1KnowledgeBasesKnowledgeBaseIdDelete({
        path: { knowledge_base_id: kb.id },
        throwOnError: true,
      });
    },
    onSuccess: () => {
      message.success('Knowledge Base deleted.');
      onDeleteSelected();
    },
    onError: (e) => {
      message.error(e instanceof Error ? e.message : 'Failed to delete collection.');
    }
  });

  const handleDeleteKb = () => {
    Modal.confirm({
      title: 'Delete Knowledge Base',
      content: `Are you sure you want to permanently delete "${kb.name}"? This deletes all raw files, layouts, and vector embeddings in Qdrant.`,
      okText: 'Delete Everything',
      okType: 'danger',
      onOk: () => deleteKbMutation.mutate(),
    });
  };

  // --- MUTATION: Patch KB Settings ---
  const patchKbMutation = useMutation({
    mutationFn: (payload: { body: any }) => {
      return patchKnowledgeBaseApiV1KnowledgeBasesKnowledgeBaseIdPatch({
        path: { knowledge_base_id: kb.id },
        body: payload.body,
        throwOnError: true,
      });
    },
    onSuccess: (response: any) => {
      message.success('Strategy configurations applied successfully!');
      if (response.data) {
        onUpdateKbName(response.data.name);
      }
      queryClient.invalidateQueries({ queryKey: ['kbList'] });
      refetchFiles();
      setConfigConfirmVisible(false);
    },
    onError: (e) => {
      console.error('Failed to update knowledge base settings:', e);
      Modal.error({
        title: 'Update Failed',
        content: e instanceof Error ? e.message : 'Please check your connection and settings.',
      });
    }
  });

  const handlePreSaveConfig = (values: any) => {
    // Detect what has changed
    const embeddingChanged =
      kb.embedding_config?.model !== values.embedding_config?.model ||
      kb.embedding_config?.distance !== values.embedding_config?.distance;

    const parsingChanged =
      kb.default_parsing_config?.provider !== values.default_parsing_config?.provider;

    const chunkingChanged =
      kb.default_chunking_config?.chunk_size !== values.default_chunking_config?.chunk_size ||
      kb.default_chunking_config?.chunk_overlap !== values.default_chunking_config?.chunk_overlap ||
      kb.default_chunking_config?.merge_max_chars !== values.default_chunking_config?.merge_max_chars ||
      kb.default_chunking_config?.breadcrumb_depth !== values.default_chunking_config?.breadcrumb_depth ||
      kb.default_chunking_config?.include_root_breadcrumb !== values.default_chunking_config?.include_root_breadcrumb ||
      kb.default_chunking_config?.breadcrumb_separator !== values.default_chunking_config?.breadcrumb_separator;

    let computedLoad: 'low' | 'high' | 'reembed' = 'low';
    let defaultApplyMode: KnowledgeBaseConfigApplyMode = 'INHERITED_ONLY';

    if (embeddingChanged) {
      computedLoad = 'reembed';
      defaultApplyMode = 'FORCE_ALL';
    } else if (parsingChanged) {
      computedLoad = 'high';
      defaultApplyMode = 'INHERITED_ONLY';
    } else if (chunkingChanged) {
      computedLoad = 'low';
      defaultApplyMode = 'INHERITED_ONLY';
    }

    setConfigLoadType(computedLoad);
    setApplyMode(defaultApplyMode);
    setPendingConfigValues(values);
    setConfigConfirmVisible(true);
  };

  const handleFinalSaveConfig = () => {
    if (!pendingConfigValues) return;

    const body = {
      name: pendingConfigValues.name,
      embedding_config: pendingConfigValues.embedding_config,
      default_chunking_config: pendingConfigValues.default_chunking_config,
      default_parsing_config: pendingConfigValues.default_parsing_config,
      apply_mode: applyMode,
    };

    patchKbMutation.mutate({ body });
  };

  const handleRefreshAll = () => {
    if (activeTab === '1') {
      refetchFiles();
      message.success('Document status refreshed.');
    } else if (activeTab === '3') {
      refetchParseHist();
      refetchChunkHist();
      refetchEmbedHist();
      message.success('Processing logs refreshed.');
    }
  };

  // Helper formatting size bytes
  const formatBytes = (bytes: number, decimals = 2) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  };

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

  // Helpers to calculate stats inside documents
  const docs = fileList?.data?.items || [];
  const completedDocs = docs.filter(d => d.status === 'COMPLETED').length;
  const processingDocs = docs.filter(d => ['PARSING', 'CHUNKING', 'EMBEDDING'].includes(d.status || '')).length;
  const failedDocs = docs.filter(d => d.status === 'FAILED').length;
  const totalSizeBytes = docs.reduce((acc, curr: any) => acc + (curr.document_info?.size_bytes || 0), 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* 1. Detail Header Panel */}
      <Card variant="borderless" className="glass-card header-panel" style={{ borderRadius: '16px', padding: '6px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px', marginBottom: '16px' }}>
          
          <Space direction="vertical" size={2}>
            {/* Back Button */}
            <Button
              type="text"
              icon={<ArrowLeft size={16} />}
              onClick={onBack}
              style={{ padding: 0, height: 'auto', display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)', marginBottom: '8px' }}
            >
              Back to Hub
            </Button>
            
            <Space align="center" size={12}>
              <div style={{
                width: '42px',
                height: '42px',
                borderRadius: '12px',
                background: 'linear-gradient(135deg, rgba(79, 70, 229, 0.15) 0%, rgba(0, 242, 254, 0.15) 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                border: '1px solid rgba(79, 70, 229, 0.2)'
              }}>
                <Settings size={20} color="#4f46e5" />
              </div>
              <div>
                <Title level={3} className="font-outfit" style={{ margin: 0, fontWeight: 800 }}>
                  KB: <span style={{ color: 'var(--accent-gradient)', background: 'linear-gradient(90deg, #4f46e5 0%, #00f2fe 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>{kb.name}</span>
                </Title>
                <Text type="secondary" style={{ fontSize: '12px', fontFamily: 'Outfit' }}>ID: {kb.id}</Text>
              </div>
            </Space>
          </Space>

          {/* Quick actions row */}
          <Space size="middle">
            <Button
              icon={<RefreshCw size={14} />}
              onClick={handleRefreshAll}
              style={{ borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              Refresh Status
            </Button>
            <Button
              type="primary"
              danger
              ghost
              icon={<Trash2 size={15} />}
              onClick={handleDeleteKb}
              style={{ borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              Drop Collection
            </Button>
          </Space>
        </div>

        {/* 2. Metadata Stats Bar */}
        <div className="meta-strip" style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '12px',
          background: 'rgba(0,0,0,0.015)',
          padding: '16px',
          borderRadius: '12px',
          border: '1px solid var(--border-color)'
        }}>
          <div>
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Store Status</span>
            <Tag color={kb.status === 'READY' || kb.status === 'COMPLETED' ? 'success' : 'processing'} style={{ fontWeight: 700, borderRadius: '4px', margin: '4px 0 0 0' }}>
              {kb.status}
            </Tag>
          </div>
          <div>
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Ingested files</span>
            <span className="font-outfit" style={{ fontSize: '16px', fontWeight: 700, display: 'block', marginTop: '2px' }}>
              {docs.length} <span style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>({completedDocs} Ready / {processingDocs} Active)</span>
            </span>
          </div>
          <div>
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Total Store Size</span>
            <span className="font-outfit" style={{ fontSize: '16px', fontWeight: 700, display: 'block', marginTop: '2px' }}>{formatBytes(totalSizeBytes)}</span>
          </div>
          <div>
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Embedding configuration</span>
            <span className="font-outfit" style={{ fontSize: '13px', fontWeight: 600, display: 'block', marginTop: '2px', wordBreak: 'break-all' }}>
              <Cpu size={12} style={{ marginRight: '4px', display: 'inline-block', verticalAlign: 'middle' }} />
              {kb.embedding_config?.model || 'text-embedding-3-small'} ({kb.embedding_config?.distance || 'cosine'})
            </span>
          </div>
        </div>
      </Card>

      {/* 3. Core Detail Tabs */}
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        type="card"
        className="kb-tabs"
        items={[
          {
            key: '1',
            label: (
              <span style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 12px', fontWeight: 600 }}>
                <FileText size={16} />
                <span>Documents & Upload ({docs.length})</span>
              </span>
            ),
            children: (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                
                {/* Drag and Drop Uploader */}
                <Card variant="borderless" className="glass-card" style={{ borderRadius: '16px' }}>
                  <Row align="middle" justify="space-between" gutter={[16, 16]}>
                    <Col>
                      <Title level={5} className="font-outfit" style={{ margin: 0, fontWeight: 700 }}>
                        Upload Document Stream
                      </Title>
                      <Text type="secondary" style={{ fontSize: '13px' }}>Configure default ingestion pipelines and drop documents to initiate embedding extraction.</Text>
                    </Col>
                    <Col>
                      <Space size="middle">
                        <Text strong style={{ fontSize: '13px' }}>Ingestion Parser:</Text>
                        <Select
                          value={parserProvider}
                          style={{ width: 150 }}
                          onChange={(val) => setParserProvider(val)}
                          className="font-outfit"
                          size="middle"
                          loading={configLoading}
                        >
                          {parserProviders.map((provider) => (
                            <Option key={provider} value={provider}>
                              {provider.charAt(0).toUpperCase() + provider.slice(1)} Parser
                            </Option>
                          ))}
                        </Select>
                      </Space>
                    </Col>
                  </Row>

                  <div style={{ marginTop: '16px' }}>
                    <Upload.Dragger
                      customRequest={({ file }) => handleUpload(file as File)}
                      showUploadList={false}
                      disabled={isUploading}
                      style={{ borderRadius: '12px', background: 'rgba(0,0,0,0.005)' }}
                    >
                      {isUploading ? (
                        <div style={{ padding: '24px 0' }}>
                          <Spin size="large" />
                          <p className="font-outfit" style={{ marginTop: '16px', fontWeight: 700, fontSize: '15px', color: 'var(--colorPrimary)' }}>
                            Worker node extracting document layouts...
                          </p>
                          <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary)' }}>
                            Deep layout analysis, OCR, semantic character boundary chunking, and Qdrant index embeddings running.
                          </p>
                        </div>
                      ) : (
                        <div style={{ padding: '24px 0' }}>
                          <p style={{ display: 'flex', justifyContent: 'center', marginBottom: '12px' }}>
                            <UploadCloud size={44} color="var(--colorPrimary)" style={{ opacity: 0.8 }} />
                          </p>
                          <p className="font-outfit" style={{ fontWeight: 700, fontSize: '15px', margin: '0 0 4px 0' }}>
                            Drag and drop target files or click to choose from local disk
                          </p>
                          <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary)' }}>
                            Supports PDF, DOCX, Markdown, HTML, Plain Text (Limit: 10MB)
                          </p>
                        </div>
                      )}
                    </Upload.Dragger>
                  </div>
                </Card>

                {/* Documents list table */}
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
                        render: (status: string) => {
                          let color = 'default';
                          if (status === 'COMPLETED') color = 'success';
                          else if (status === 'FAILED') color = 'error';
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
                        render: (_, record: any) => {
                          const count = record.document_info?.element_count ?? 0;
                          return <Badge count={count} showZero color="#4f46e5" style={{ fontWeight: 700 }} />;
                        },
                      },
                      {
                        title: 'File Size',
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

              </div>
            )
          },
          {
            key: '2',
            label: (
              <span style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 12px', fontWeight: 600 }}>
                <Sliders size={16} />
                <span>Strategy Settings</span>
              </span>
            ),
            children: (
              <Card variant="borderless" className="glass-card" style={{ borderRadius: '16px' }}>
                <div style={{ marginBottom: '20px' }}>
                  <Title level={4} style={{ margin: 0, fontWeight: 700 }}>Strategy Configurations</Title>
                  <Paragraph type="secondary" style={{ margin: '4px 0 0 0' }}>
                    Adjust parsing mechanisms, boundary semantic chunks, and vector embedding sizes. Updates propagate to documents based on your selected strategy.
                  </Paragraph>
                </div>

                <Form
                  form={settingsForm}
                  layout="vertical"
                  onFinish={handlePreSaveConfig}
                  style={{ maxWidth: '780px' }}
                >
                  <Title level={5} style={{ margin: '0 0 12px 0', borderBottom: '1px solid var(--border-color)', paddingBottom: '6px' }}>General Configuration</Title>
                  <Form.Item
                    name="name"
                    label="Knowledge Base Name"
                    rules={[{ required: true, message: 'Please enter a name' }]}
                    tooltip="Alphanumeric unique identifier."
                  >
                    <Input size="large" />
                  </Form.Item>

                  <Title level={5} style={{ margin: '24px 0 12px 0', borderBottom: '1px solid var(--border-color)', paddingBottom: '6px' }}>Parsing Default Strategy</Title>
                  <Paragraph type="secondary" style={{ fontSize: '13px' }}>
                    Parsing provider defines how files are parsed and extracted. Modifying this config acts as a heavy load operation, as files will need to be re-read.
                  </Paragraph>
                  <Form.Item
                    name={['default_parsing_config', 'provider']}
                    label="Parsing Provider"
                    rules={[{ required: true }]}
                  >
                    <Select size="large" style={{ width: '260px' }} loading={configLoading}>
                      {parserProviders.map((provider) => (
                        <Select.Option key={provider} value={provider}>
                          {PARSER_LABELS[provider] || (provider.charAt(0).toUpperCase() + provider.slice(1))}
                        </Select.Option>
                      ))}
                    </Select>
                  </Form.Item>

                  <Title level={5} style={{ margin: '24px 0 12px 0', borderBottom: '1px solid var(--border-color)', paddingBottom: '6px' }}>Chunking & Boundary Splitting Defaults</Title>
                  <Paragraph type="secondary" style={{ fontSize: '13px' }}>
                    Calculates characters split overlap and breadcrumb header tracking for parent retrieval optimization. Modifying chunking defaults is light load because layout objects are cached.
                  </Paragraph>
                  
                  <Row gutter={20}>
                    <Col span={12}>
                      <Form.Item
                        name={['default_chunking_config', 'chunk_size']}
                        label="Chunk Size (Characters)"
                        rules={[{ required: true }]}
                      >
                        <InputNumber size="large" style={{ width: '100%' }} min={100} max={10000} />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item
                        name={['default_chunking_config', 'chunk_overlap']}
                        label="Chunk Overlap (Characters)"
                        rules={[{ required: true }]}
                      >
                        <InputNumber size="large" style={{ width: '100%' }} min={0} max={2000} />
                      </Form.Item>
                    </Col>
                  </Row>

                  <Row gutter={20}>
                    <Col span={12}>
                      <Form.Item
                        name={['default_chunking_config', 'merge_max_chars']}
                        label="Merge Max Characters"
                        rules={[{ required: true }]}
                      >
                        <InputNumber size="large" style={{ width: '100%' }} min={100} max={20000} />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item
                        name={['default_chunking_config', 'breadcrumb_depth']}
                        label="Breadcrumb Depth prefix"
                        rules={[{ required: true }]}
                        tooltip="Traverses headings hierarchy tree upward to inject breadcrumbs as text prefix for precise indexing context."
                      >
                        <InputNumber size="large" style={{ width: '100%' }} min={0} max={10} />
                      </Form.Item>
                    </Col>
                  </Row>

                  <Row gutter={20}>
                    <Col span={12}>
                      <Form.Item
                        name={['default_chunking_config', 'breadcrumb_separator']}
                        label="Separator"
                        rules={[{ required: true }]}
                      >
                        <Input size="large" style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item
                        name={['default_chunking_config', 'include_root_breadcrumb']}
                        label="Include Root Breadcrumb Heading"
                        valuePropName="checked"
                      >
                        <Switch />
                      </Form.Item>
                    </Col>
                  </Row>

                  <Title level={5} style={{ margin: '24px 0 12px 0', borderBottom: '1px solid var(--border-color)', paddingBottom: '6px' }}>Vector Database Physical Indexing</Title>
                  <Alert
                    title="Index Restructure Warning"
                    description="Embedding adjustments require creating a physically separate namespace/collection inside Qdrant. Restructuring this will necessitate re-embedding all existing files."
                    type="warning"
                    showIcon
                    style={{ marginBottom: '16px' }}
                  />

                  <Row gutter={20}>
                    <Col span={12}>
                      <Form.Item
                        name={['embedding_config', 'model']}
                        label="Embedding Model"
                        rules={[{ required: true }]}
                      >
                        <Select size="large" loading={configLoading}>
                          {embeddingModels.map((model) => (
                            <Select.Option key={model} value={model}>
                              {model}
                            </Select.Option>
                          ))}
                        </Select>
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item
                        name={['embedding_config', 'distance']}
                        label="Distance Similarity Metric"
                        rules={[{ required: true }]}
                      >
                        <Radio.Group size="large" optionType="button" buttonStyle="solid" style={{ width: '100%' }}>
                          <Radio.Button value="cosine" style={{ width: '33.33%', textAlign: 'center' }}>Cosine</Radio.Button>
                          <Radio.Button value="dot" style={{ width: '33.33%', textAlign: 'center' }}>Dot</Radio.Button>
                          <Radio.Button value="euclid" style={{ width: '33.33%', textAlign: 'center' }}>Euclidean</Radio.Button>
                        </Radio.Group>
                      </Form.Item>
                    </Col>
                  </Row>

                  <div style={{ marginTop: '30px', display: 'flex', justifyContent: 'flex-start' }}>
                    <Button
                      type="primary"
                      size="large"
                      onClick={() => settingsForm.submit()}
                      loading={patchKbMutation.isPending}
                      style={{ padding: '0 40px', height: '46px', borderRadius: '10px', fontWeight: 600 }}
                    >
                      Save Strategy Configuration
                    </Button>
                  </div>
                </Form>
              </Card>
            )
          },
          {
            key: '3',
            label: (
              <span style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 12px', fontWeight: 600 }}>
                <Clock size={16} />
                <span>Execution Logs & History</span>
              </span>
            ),
            children: (
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
                    onClick={() => {
                      refetchParseHist();
                      refetchChunkHist();
                      refetchEmbedHist();
                      message.success('Processing history reloaded.');
                    }}
                  >
                    Reload History
                  </Button>
                </div>

                <Tabs
                  defaultActiveKey="parse-hist"
                  className="sub-history-tabs"
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
            )
          },
          {
            key: '4',
            label: (
              <span style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 12px', fontWeight: 600 }}>
                <Search size={16} />
                <span>Retrieval Test</span>
              </span>
            ),
            children: (
              <RetrievalTestTab kb={kb} />
            )
          }
        ]}
      />

      {/* 4. Single Document settings override modal */}
      <DocumentSettingsModal
        visible={!!selectedDocForSettings}
        onClose={() => setSelectedDocForSettings(null)}
        document={selectedDocForSettings}
        kbDefaultParsingConfig={kb.default_parsing_config}
        kbDefaultChunkingConfig={kb.default_chunking_config}
        onSuccess={() => {
          refetchFiles();
          queryClient.invalidateQueries({ queryKey: ['kbList'] });
        }}
      />

      {/* 5. Strategy adjustment confirmation modal */}
      <Modal
        title={
          <span className="font-outfit" style={{ fontSize: '16px', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Info size={18} className="text-warning" style={{ color: '#faad14' }} />
            Apply Strategy Settings
          </span>
        }
        open={configConfirmVisible}
        onCancel={() => setConfigConfirmVisible(false)}
        width={500}
        onOk={handleFinalSaveConfig}
        confirmLoading={patchKbMutation.isPending}
        okText="Confirm and Propagate"
        cancelText="Back to Edit"
        style={{ borderRadius: '12px' }}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%', marginTop: '12px' }}>
          
          {configLoadType === 'reembed' && (
            <Alert
              title="Full Collection Re-Embedding Required"
              description="Restructuring vector model dimensions or distance metrics requires building a new physics vector namespace. All files inside this database MUST be re-embedded."
              type="error"
              showIcon
            />
          )}

          {configLoadType === 'high' && (
            <Alert
              title="High Workload Detected"
              description="Altering default parsing providers requires parsing workers to download raw documents and run OCR / element extractions again, which takes processing bandwidth."
              type="warning"
              showIcon
            />
          )}

          {configLoadType === 'low' && (
            <Alert
              title="Low Load Strategy Adjustment"
              description="Only character split bounds or breadcrumbs adjusted. Fast propagation because worker nodes bypass layout extraction and process cached document trees."
              type="success"
              showIcon
            />
          )}

          <div>
            <Text strong className="font-outfit" style={{ display: 'block', marginBottom: '8px', fontSize: '13px' }}>
              Select strategy propagation scope for this database:
            </Text>
            <Radio.Group
              value={applyMode}
              onChange={(e) => setApplyMode(e.target.value)}
              style={{ width: '100%' }}
            >
              <Space direction="vertical" style={{ width: '100%' }}>
                <Radio
                  value="NEW_ONLY"
                  disabled={configLoadType === 'reembed'}
                  style={{ display: 'flex', alignItems: 'start' }}
                >
                  <div style={{ marginLeft: '4px' }}>
                    <Text strong style={{ fontSize: '13px' }}>New Uploads Only</Text>
                    <Paragraph type="secondary" style={{ margin: 0, fontSize: '12px' }}>
                      Keep all current database entries intact. Only documents uploaded starting now inherit this updated strategy.
                    </Paragraph>
                  </div>
                </Radio>
                <Radio value="INHERITED_ONLY" style={{ display: 'flex', alignItems: 'start' }}>
                  <div style={{ marginLeft: '4px' }}>
                    <Text strong style={{ fontSize: '13px' }}>Reprocess Inherited Items</Text>
                    <Paragraph type="secondary" style={{ margin: 0, fontSize: '12px' }}>
                      Only reprocess documents that do not have active overrides (inheriting database defaults).
                    </Paragraph>
                  </div>
                </Radio>
                <Radio value="FORCE_ALL" style={{ display: 'flex', alignItems: 'start' }}>
                  <div style={{ marginLeft: '4px' }}>
                    <Text strong style={{ fontSize: '13px' }}>Force Propagate (Discard Overrides)</Text>
                    <Paragraph type="secondary" style={{ margin: 0, fontSize: '12px' }}>
                      Overwrite custom document settings and enforce this strategy across every file in this database.
                    </Paragraph>
                  </div>
                </Radio>
              </Space>
            </Radio.Group>
          </div>
        </Space>
      </Modal>

      <style dangerouslySetInnerHTML={{ __html: `
        .kb-tabs .ant-tabs-nav {
          margin-bottom: 16px !important;
        }
        .kb-tabs .ant-tabs-tab {
          background: rgba(0,0,0,0.01) !important;
          border: 1px solid var(--border-color) !important;
          border-radius: 8px 8px 0 0 !important;
          transition: all 0.2s ease !important;
        }
        .kb-tabs .ant-tabs-tab-active {
          background: #ffffff !important;
          border-bottom-color: #ffffff !important;
        }
        .sub-history-tabs .ant-tabs-nav {
          margin-bottom: 12px !important;
        }
      `}} />

    </div>
  );
};
