import React, { useState } from 'react';
import { 
  Card, Table, Button, Space, Input, List, Row, Col, Typography, 
  Upload, Select, Spin, Drawer, Tag, Empty, Modal, Badge, Tooltip 
} from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  listKnowledgeBasesApiV1KnowledgeGet, 
  listKnowledgeFilesApiV1KnowledgeKnowledgeNameFilesGet,
  uploadDocumentApiV1KnowledgeKnowledgeNameUploadPost,
  deleteDocumentApiV1KnowledgeKnowledgeNameFilesFileMd5Delete,
  getParsedDocumentApiV1KnowledgeKnowledgeNameFilesFileMd5ParsedGet
} from '@/generated/api/sdk.gen';
import { 
  Database, Plus, UploadCloud, FileText, Trash2, Download, Eye, AlertCircle, FileDigit 
} from 'lucide-react';
import { useThemeStore } from '@/stores/themeStore';
import { ElementsExplorer } from '@/components/ElementsExplorer';

const { Title, Text, Paragraph } = Typography;
const { Option } = Select;

export const Knowledge: React.FC = () => {
  const queryClient = useQueryClient();
  const { selectedKnowledgeName, setSelectedKnowledgeName } = useThemeStore();
  const [newKbName, setNewKbName] = useState('');
  const [parserProvider, setParserProvider] = useState('docling');
  const [isUploading, setIsUploading] = useState(false);
  const [inspectingFile, setInspectingFile] = useState<{ md5: string; name: string } | null>(null);

  // 1. Fetch Knowledge Bases
  const { data: kbList, isLoading: kbLoading, refetch: refetchKbs } = useQuery({
    queryKey: ['kbList'],
    queryFn: () => listKnowledgeBasesApiV1KnowledgeGet({ throwOnError: true }),
  });

  // 2. Fetch Knowledge Files
  const { data: fileList, isLoading: filesLoading, refetch: refetchFiles } = useQuery({
    queryKey: ['fileList', selectedKnowledgeName],
    queryFn: () => {
      if (!selectedKnowledgeName) return Promise.resolve({ data: [] as any });
      return listKnowledgeFilesApiV1KnowledgeKnowledgeNameFilesGet({
        path: { knowledge_name: selectedKnowledgeName },
        throwOnError: true,
      });
    },
    enabled: !!selectedKnowledgeName,
  });

  // 3. Fetch Parsed Document for Inspector
  const { data: parsedDoc, isLoading: parsedLoading } = useQuery({
    queryKey: ['parsedDoc', selectedKnowledgeName, inspectingFile?.md5],
    queryFn: () => {
      if (!selectedKnowledgeName || !inspectingFile) return Promise.resolve(null);
      return getParsedDocumentApiV1KnowledgeKnowledgeNameFilesFileMd5ParsedGet({
        path: {
          knowledge_name: selectedKnowledgeName,
          file_md5: inspectingFile.md5,
        },
        throwOnError: true,
      });
    },
    enabled: !!selectedKnowledgeName && !!inspectingFile,
  });

  // 4. Delete file mutation
  const deleteMutation = useMutation({
    mutationFn: (fileMd5: string) => {
      return deleteDocumentApiV1KnowledgeKnowledgeNameFilesFileMd5Delete({
        path: {
          knowledge_name: selectedKnowledgeName!,
          file_md5: fileMd5,
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
    setSelectedKnowledgeName(name);
    setNewKbName('');
    // S3 directories are created dynamically on first upload, so we just set active state!
  };

  const handleUpload = async (file: File) => {
    if (!selectedKnowledgeName) return;
    setIsUploading(true);
    try {
      await uploadDocumentApiV1KnowledgeKnowledgeNameUploadPost({
        path: {
          knowledge_name: selectedKnowledgeName,
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
        title: 'Document Parsing Failed',
        content: e instanceof Error ? e.message : 'Please check your backend connection or Docling parser logs.',
        icon: <AlertCircle color="#ef4444" />,
      });
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = (fileMd5: string) => {
    Modal.confirm({
      title: 'Delete Document',
      content: 'Are you sure you want to delete this document and all its parsed elements from the knowledge base?',
      okText: 'Yes, Delete',
      okType: 'danger',
      onOk: () => deleteMutation.mutate(fileMd5),
    });
  };

  const handleDownload = (fileMd5: string) => {
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8389';
    window.open(`${apiBaseUrl}/api/v1/knowledge/${selectedKnowledgeName}/files/${fileMd5}/download`, '_blank');
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
            dataSource={kbList?.data || []}
            renderItem={(item) => (
              <List.Item
                style={{
                  padding: '12px 16px',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  marginBottom: '6px',
                  background: selectedKnowledgeName === item ? 'rgba(79, 70, 229, 0.08)' : 'transparent',
                  border: selectedKnowledgeName === item ? '1px solid rgba(79, 70, 229, 0.2)' : '1px solid transparent',
                  transition: 'all 0.2s ease',
                }}
                onClick={() => setSelectedKnowledgeName(item)}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Database size={16} color={selectedKnowledgeName === item ? 'var(--accent-gradient)' : 'var(--text-secondary)'} />
                  <span className="font-outfit" style={{ fontWeight: selectedKnowledgeName === item ? 700 : 500 }}>{item}</span>
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
        {selectedKnowledgeName ? (
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
                      <Option value="docling">Docling (Sleek)</Option>
                      <Option value="marker">Marker (Text)</Option>
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
                        Docling Parsing in progress...
                      </p>
                      <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary)' }}>
                        Layout detection, table parsing, and semantic tagging running on backend.
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
                dataSource={fileList?.data || []}
                loading={filesLoading}
                rowKey="md5_hash"
                columns={[
                  {
                    title: 'Filename',
                    dataIndex: 'filename',
                    key: 'filename',
                    render: (text) => (
                      <Space>
                        <FileText size={16} color="var(--text-secondary)" />
                        <span className="font-outfit" style={{ fontWeight: 600 }}>{text}</span>
                      </Space>
                    ),
                  },
                  {
                    title: 'MD5 Hash',
                    dataIndex: 'md5_hash',
                    key: 'md5',
                    render: (text) => (
                      <Tooltip title={text}>
                        <code>{text.slice(0, 8)}...</code>
                      </Tooltip>
                    ),
                  },
                  {
                    title: 'Elements',
                    dataIndex: 'element_count',
                    key: 'elements',
                    align: 'center',
                    render: (count) => <Badge count={count} showZero color="#4f46e5" style={{ fontWeight: 700 }} />,
                  },
                  {
                    title: 'Size',
                    dataIndex: 'size_bytes',
                    key: 'size',
                    render: (bytes) => formatBytes(bytes),
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
                          onClick={() => setInspectingFile({ md5: record.md5_hash, name: record.filename })}
                        >
                          Inspect
                        </Button>
                        <Button 
                          type="text" 
                          icon={<Download size={16} />} 
                          onClick={() => handleDownload(record.md5_hash)}
                        />
                        <Button 
                          type="text" 
                          danger
                          icon={<Trash2 size={16} />} 
                          onClick={() => handleDelete(record.md5_hash)}
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
        width={720}
        onClose={() => setInspectingFile(null)}
        open={!!inspectingFile}
        destroyOnClose
      >
        {parsedLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <Spin size="large" />
            <p className="font-outfit" style={{ marginTop: '16px', fontWeight: 600 }}>Loading elements structure...</p>
          </div>
        ) : parsedDoc?.data ? (
          <ElementsExplorer 
            elements={
              (parsedDoc.data.elements || []).map((el: any) => ({
                ...el,
                content: el.content || '',
              }))
            } 
          />
        ) : (
          <Empty description="No elements data parsed successfully." />
        )}
      </Drawer>
    </Row>
  );
};
