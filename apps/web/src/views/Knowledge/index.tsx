import React, { useState } from 'react';
import {
  Card, Table, Button, Space, Input, List, Row, Col, Typography,
  Upload, Select, Spin, Drawer, Tag, Empty, Modal, Badge, Tooltip
} from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getKnowledgeBasesApiV1KnowledgeBasesGet,
  createKnowledgeBaseApiV1KnowledgeBasesPost,
  deleteKnowledgeBaseApiV1KnowledgeBasesKnowledgeBaseIdDelete,
  getKnowledgeBaseDocumentsApiV1KnowledgeBasesKnowledgeBaseIdDocumentsGet,
  uploadKnowledgeBaseDocumentApiV1KnowledgeBasesKnowledgeBaseIdUploadPost,
  deleteKnowledgeBaseDocumentApiV1KnowledgeBaseDocumentsKnowledgeBaseDocumentIdDelete,
  getParsedDocumentApiV1KnowledgeBaseDocumentsKnowledgeBaseDocumentIdParsedGet
} from '@/generated/api/sdk.gen';
import {
  Database, Plus, UploadCloud, FileText, Trash2, Download, Eye, AlertCircle
} from 'lucide-react';
import { useThemeStore } from '@/stores/themeStore';
import { ElementsExplorer } from '@/components/ElementsExplorer';
import { PdfPreview } from '@/components/PdfPreview';

const { Title, Text, Paragraph } = Typography;
const { Option } = Select;

export const Knowledge: React.FC = () => {
  const queryClient = useQueryClient();
  const {
    selectedKnowledgeName,
    setSelectedKnowledgeName,
    selectedKnowledgeId,
    setSelectedKnowledgeId
  } = useThemeStore();
  const [newKbName, setNewKbName] = useState('');
  const [parserProvider, setParserProvider] = useState('docling');
  const [isUploading, setIsUploading] = useState(false);
  const [inspectingFile, setInspectingFile] = useState<{ id: string; md5: string; name: string } | null>(null);
  const [activeElement, setActiveElement] = useState<any>(null);

  // 1. Fetch Knowledge Bases
  const { data: kbList, isLoading: kbLoading, refetch: refetchKbs } = useQuery({
    queryKey: ['kbList'],
    queryFn: () => getKnowledgeBasesApiV1KnowledgeBasesGet({ throwOnError: true }),
  });

  // Auto-select the first KB if nothing is selected
  React.useEffect(() => {
    if (!selectedKnowledgeId && kbList?.data?.items?.length) {
      const firstKb = kbList.data.items[0];
      setSelectedKnowledgeId(firstKb.id);
      setSelectedKnowledgeName(firstKb.name);
    }
  }, [kbList, selectedKnowledgeId, setSelectedKnowledgeId, setSelectedKnowledgeName]);

  // 2. Fetch Knowledge Files
  const { data: fileList, isLoading: filesLoading, refetch: refetchFiles } = useQuery({
    queryKey: ['fileList', selectedKnowledgeId],
    queryFn: () => {
      if (!selectedKnowledgeId) return Promise.resolve({ data: { items: [] } as any });
      return getKnowledgeBaseDocumentsApiV1KnowledgeBasesKnowledgeBaseIdDocumentsGet({
        path: { knowledge_base_id: selectedKnowledgeId },
        throwOnError: true,
      });
    },
    enabled: !!selectedKnowledgeId,
  });

  // 3. Fetch Parsed Document for Inspector
  const { data: parsedDoc, isLoading: parsedLoading } = useQuery({
    queryKey: ['parsedDoc', inspectingFile?.id],
    queryFn: () => {
      if (!inspectingFile) return Promise.resolve(null);
      return getParsedDocumentApiV1KnowledgeBaseDocumentsKnowledgeBaseDocumentIdParsedGet({
        path: {
          knowledge_base_document_id: inspectingFile.id,
        },
        throwOnError: true,
      });
    },
    enabled: !!inspectingFile,
  });

  // 4. Create KB Mutation
  const createKbMutation = useMutation({
    mutationFn: (name: string) => {
      return createKnowledgeBaseApiV1KnowledgeBasesPost({
        body: { name },
        throwOnError: true,
      });
    },
    onSuccess: (response: any) => {
      const created = response.data;
      if (created) {
        setSelectedKnowledgeId(created.id);
        setSelectedKnowledgeName(created.name);
      }
      refetchKbs();
    },
    onError: (e) => {
      console.error('Failed to create knowledge base:', e);
      Modal.error({
        title: 'Failed to Create Knowledge Base',
        content: e instanceof Error ? e.message : 'Please check your connection.',
      });
    }
  });

  // 5. Delete KB Mutation
  const deleteKbMutation = useMutation({
    mutationFn: (kbId: string) => {
      return deleteKnowledgeBaseApiV1KnowledgeBasesKnowledgeBaseIdDelete({
        path: { knowledge_base_id: kbId },
        throwOnError: true,
      });
    },
    onSuccess: () => {
      refetchKbs();
      setSelectedKnowledgeId(null);
      setSelectedKnowledgeName(null);
    },
    onError: (e) => {
      console.error('Failed to delete knowledge base:', e);
      Modal.error({
        title: 'Delete Failed',
        content: e instanceof Error ? e.message : 'Failed to delete the knowledge base.',
      });
    }
  });

  // 6. Delete file mutation
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

  const handleCreateKb = () => {
    if (!newKbName.trim()) return;
    const name = newKbName.trim().toLowerCase().replace(/\s+/g, '_');
    createKbMutation.mutate(name);
    setNewKbName('');
  };

  const handleDeleteKb = (kbId: string, name: string) => {
    Modal.confirm({
      title: 'Delete Knowledge Base',
      content: `Are you sure you want to delete "${name}"? This will permanently delete all documents and parsed vectors inside it.`,
      okText: 'Yes, Delete',
      okType: 'danger',
      onOk: () => deleteKbMutation.mutate(kbId),
    });
  };

  const handleUpload = async (file: File) => {
    if (!selectedKnowledgeId) return;
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
      refetchKbs();
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
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8389';
    window.open(`${apiBaseUrl}/api/v1/knowledge_base_documents/${docId}/download`, '_blank');
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
    <Row gutter={[24, 24]}>
      {/* Sidebar: Knowledge Bases List */}
      <Col xs={24} md={7}>
        <Card
          bordered={false}
          className="glass-card"
          title={<span className="font-outfit" style={{ fontSize: '15px', fontWeight: 700 }}>Knowledge Bases</span>}
        >
          <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
            <Input
              placeholder="e.g. legal_docs"
              value={newKbName}
              onChange={(e) => setNewKbName(e.target.value)}
              onPressEnter={handleCreateKb}
              className="font-outfit"
            />
            <Button
              type="primary"
              icon={<Plus size={16} />}
              onClick={handleCreateKb}
            />
          </div>

          <List
            loading={kbLoading}
            dataSource={kbList?.data?.items || []}
            renderItem={(item: any) => (
              <List.Item
                style={{
                  padding: '12px 16px',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  marginBottom: '6px',
                  background: selectedKnowledgeId === item.id ? 'rgba(79, 70, 229, 0.08)' : 'transparent',
                  border: selectedKnowledgeId === item.id ? '1px solid rgba(79, 70, 229, 0.2)' : '1px solid transparent',
                  transition: 'all 0.2s ease',
                }}
                onClick={() => {
                  setSelectedKnowledgeId(item.id);
                  setSelectedKnowledgeName(item.name);
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', width: '100%', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <Database size={16} color={selectedKnowledgeId === item.id ? 'var(--accent-gradient)' : 'var(--text-secondary)'} />
                    <span className="font-outfit" style={{ fontWeight: selectedKnowledgeId === item.id ? 700 : 500 }}>{item.name}</span>
                  </div>
                  <Button
                    type="text"
                    size="small"
                    danger
                    icon={<Trash2 size={14} />}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteKb(item.id, item.name);
                    }}
                  />
                </div>
              </List.Item>
            )}
            locale={{
              emptyText: <Empty description="No bases found. Create one above!" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            }}
          />
        </Card>
      </Col>

      {/* Main Area: Files upload & table list */}
      <Col xs={24} md={17}>
        {selectedKnowledgeId ? (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {/* Header & Upload panel */}
            <Card bordered={false} className="glass-card">
              <Row align="middle" justify="space-between" gutter={[16, 16]}>
                <Col>
                  <Title level={4} className="font-outfit" style={{ margin: 0 }}>
                    KB: <span style={{ color: 'var(--accent-gradient)' }}>{selectedKnowledgeName}</span>
                  </Title>
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
              bordered={false}
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
                      return (
                        <Tag color={color}>
                          {status}
                        </Tag>
                      );
                    }
                  },
                  {
                    title: 'MD5 Hash',
                    dataIndex: 'file_md5',
                    key: 'md5',
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
                    render: (_, record: any) => (
                      <Space size="middle">
                        <Button
                          type="text"
                          icon={<Eye size={16} />}
                          onClick={() => setInspectingFile({ id: record.id, md5: record.file_md5, name: record.name })}
                          disabled={record.status !== 'COMPLETED'}
                        >
                          Inspect
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
          </Space>
        ) : (
          <Card bordered={false} className="glass-card" style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '400px' }}>
            <div style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>
              <Database size={56} style={{ opacity: 0.25, marginBottom: '16px' }} />
              <Title level={4} className="font-outfit" style={{ margin: 0, fontWeight: 700 }}>Select a Knowledge Base</Title>
              <Paragraph style={{ marginTop: '8px', maxWidth: '360px', margin: '8px auto 0 auto' }}>
                Please select an existing knowledge base from the sidebar, or create a brand new one to get started!
              </Paragraph>
            </div>
          </Card>
        )}
      </Col>

      {/* Drawer: Parsed Elements Inspector */}
      <Drawer
        title={
          <span className="font-outfit" style={{ fontWeight: 800 }}>
            Layout Element Inspector: <span style={{ color: 'var(--accent-gradient)' }}>{inspectingFile?.name}</span>
          </span>
        }
        width="90vw"
        onClose={() => {
          setInspectingFile(null);
          setActiveElement(null);
        }}
        open={!!inspectingFile}
        destroyOnClose
        styles={{ body: { padding: 0, overflow: 'hidden' } }}
      >
        {parsedLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <Spin size="large" />
            <p className="font-outfit" style={{ marginTop: '16px', fontWeight: 600 }}>Loading elements structure...</p>
          </div>
        ) : parsedDoc?.data ? (
          <div className="multi-view-container" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", height: "100%", gap: "16px", padding: "16px", background: "var(--bg-app)" }}>
            {/* Left Side Panel: Original Source */}
            <div className="multi-panel" style={{ height: "100%", background: "#ffffff", border: "1px solid var(--border-color)", borderRadius: "8px", display: "flex", flexDirection: "column", overflow: "hidden" }}>
              <div className="panel-header" style={{ padding: "10px 16px", background: "var(--bg-app)", borderBottom: "1px solid var(--border-color)", fontWeight: 700, fontSize: "13px" }}>PDF / Original Source</div>
              <div className="panel-content" style={{ flex: 1, overflow: "hidden" }}>
                {inspectingFile?.name.toLowerCase().endsWith('.pdf') ? (
                  <PdfPreview
                    fileUrl={`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8389'}/api/v1/knowledge_base_documents/${inspectingFile.id}/download`}
                    fileName={inspectingFile.name}
                    activeElement={activeElement}
                    parsedDoc={parsedDoc.data as any}
                  />
                ) : (
                  <div className="non-pdf-info" style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", color: "#64748b", padding: "24px", textAlign: "center" }}>
                    <h3>{inspectingFile?.name}</h3>
                    <p>Comparison is only supported for PDF files.</p>
                  </div>
                )}
              </div>
            </div>

            {/* Right Side Panel: Layout Elements */}
            <div className="multi-panel" style={{ height: "100%", background: "#ffffff", border: "1px solid var(--border-color)", borderRadius: "8px", display: "flex", flexDirection: "column", overflow: "hidden" }}>
              <div className="panel-header" style={{ padding: "10px 16px", background: "var(--bg-app)", borderBottom: "1px solid var(--border-color)", fontWeight: 700, fontSize: "13px" }}>Layout Elements</div>
              <div className="panel-content" style={{ flex: 1, overflow: "hidden" }}>
                <ElementsExplorer
                  elements={
                    ((parsedDoc.data as any).elements || []).map((el: any) => ({
                      ...el,
                      content: el.content || '',
                    }))
                  }
                  onElementClick={setActiveElement}
                />
              </div>
            </div>
          </div>
        ) : (
          <Empty description="No elements data parsed successfully." />
        )}
      </Drawer>
    </Row>
  );
};
