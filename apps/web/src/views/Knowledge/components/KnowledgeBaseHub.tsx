import React, { useState } from 'react';
import {
  Card, Table, Button, Input, Tag, Space, Typography, Modal, Form,
  Select, InputNumber, Radio, Switch, Row, Col, Badge, Empty, message, Steps
} from 'antd';
import {
  Plus, Trash2, Database, ArrowRight, Search, Sparkles, Cpu,
  Layers, HardDrive, AlertTriangle, Calendar
} from 'lucide-react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  getKnowledgeBasesApiV1KnowledgeBasesGet,
  createKnowledgeBaseApiV1KnowledgeBasesPost,
  deleteKnowledgeBaseApiV1KnowledgeBasesKnowledgeBaseIdDelete,
  getProviderOptionsApiV1ProvidersOptionsGet
} from '@/generated/api/sdk.gen';
import type { KnowledgeBaseRead } from '@/generated/api/types.gen';
import styles from './KnowledgeBaseHub.module.css';

const { Title, Text, Paragraph } = Typography;

interface CreateFormValues {
  name: string;
  embedding_model?: string;
  distance_metric?: 'cosine' | 'dot' | 'euclid';
  use_colpali?: boolean;
  colpali_model?: string | null;
  parsing_provider?: string;
  extension_providers?: Record<string, string>;
  chunk_size?: number;
  chunk_overlap?: number;
  merge_max_chars?: number;
  breadcrumb_depth?: number;
  include_root_breadcrumb?: boolean;
  breadcrumb_separator?: string;
}

const normalizeExtensions = (obj: Record<string, string | null | undefined> | null | undefined): Record<string, string> => {
  if (!obj) return {};
  return Object.fromEntries(
    Object.entries(obj).filter(([_, v]) => v !== undefined && v !== null && String(v).trim() !== '')
  ) as Record<string, string>;
};

const HUB_STEP_FIELDS = [
  [
    'name',
    'parsing_provider',
    'extension_providers'
  ],
  [
    'chunk_size',
    'chunk_overlap',
    'merge_max_chars',
    'breadcrumb_depth',
    'breadcrumb_separator'
  ]
];

interface KnowledgeBaseHubProps {
  onSelect: (kb: KnowledgeBaseRead) => void;
}

export const KnowledgeBaseHub: React.FC<KnowledgeBaseHubProps> = ({ onSelect }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [showParserOverrides, setShowParserOverrides] = useState(false);
  const [form] = Form.useForm();

  // 1. Fetch Knowledge Bases
  const { data: kbList, isLoading: kbLoading, refetch: refetchKbs } = useQuery({
    queryKey: ['kbList'],
    queryFn: () => getKnowledgeBasesApiV1KnowledgeBasesGet({ throwOnError: true }),
  });

  // Fetch dynamic configuration options
  const { data: configOptions, isLoading: configLoading } = useQuery({
    queryKey: ['configOptions'],
    queryFn: () => getProviderOptionsApiV1ProvidersOptionsGet({ throwOnError: true }),
  });

  const embeddingModels = configOptions?.data?.embedding_models || [];
  const parserProviders = configOptions?.data?.parser_providers || [];

  const items = kbList?.data?.items || [];

  // Filter KBs
  const filteredItems = items.filter((kb) =>
    kb.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Stats calculation
  const totalCount = items.length;
  const readyCount = items.filter(i => i.status === 'READY' || i.status === 'COMPLETED').length;
  const activeModels = Array.from(new Set(items.map(i => i.embedding_config?.model).filter(Boolean)));

  // 2. Create KB Mutation
  const createKbMutation = useMutation({
    mutationFn: (values: CreateFormValues) => {
      const payload = {
        name: values.name.trim().toLowerCase().replace(/\s+/g, '_'),
        embedding_config: {
          model: values.embedding_model || 'text-embedding-3-small',
          distance: values.distance_metric || 'cosine',
          use_colpali: values.use_colpali || false,
          colpali_model: values.colpali_model || null,
        },
        default_parsing_config: {
          provider: values.parsing_provider || 'docling',
          extension_providers: normalizeExtensions(values.extension_providers || {}),
        },
        default_chunking_config: {
          chunk_size: values.chunk_size ?? 1024,
          chunk_overlap: values.chunk_overlap ?? 200,
          merge_max_chars: values.merge_max_chars ?? 4096,
          breadcrumb_depth: values.breadcrumb_depth ?? 2,
          include_root_breadcrumb: values.include_root_breadcrumb ?? true,
          breadcrumb_separator: values.breadcrumb_separator || ' > ',
        }
      };

      return createKnowledgeBaseApiV1KnowledgeBasesPost({
        body: payload,
        throwOnError: true,
      });
    },
    onSuccess: (response: { data?: KnowledgeBaseRead }) => {
      message.success('Knowledge Base created successfully!');
      setCreateModalVisible(false);
      form.resetFields();
      setCurrentStep(0);
      setShowParserOverrides(false);
      refetchKbs();
      if (response.data) {
        onSelect(response.data);
      }
    },
    onError: (e) => {
      console.error('Failed to create knowledge base:', e);
      Modal.error({
        title: 'Creation Failed',
        content: e instanceof Error ? e.message : 'Please check your connection and configuration.',
      });
    }
  });

  // 3. Delete KB Mutation
  const deleteKbMutation = useMutation({
    mutationFn: (kbId: string) => {
      return deleteKnowledgeBaseApiV1KnowledgeBasesKnowledgeBaseIdDelete({
        path: { knowledge_base_id: kbId },
        throwOnError: true,
      });
    },
    onSuccess: () => {
      message.success('Knowledge base deleted successfully.');
      refetchKbs();
    },
    onError: (e) => {
      console.error('Failed to delete knowledge base:', e);
      Modal.error({
        title: 'Delete Failed',
        content: e instanceof Error ? e.message : 'Failed to delete the knowledge base.',
      });
    }
  });

  const handlePrevHub = () => {
    setCurrentStep((prev) => prev - 1);
  };

  const handleNextHub = async () => {
    try {
      const fieldsToValidate = HUB_STEP_FIELDS[currentStep];
      if (fieldsToValidate) {
        await form.validateFields(fieldsToValidate);
      }
      setCurrentStep((prev) => prev + 1);
    } catch (errorInfo) {
      console.warn('Form validation failed:', errorInfo);
    }
  };

  const handleCreate = (values: CreateFormValues) => {
    createKbMutation.mutate(values);
  };

  const handleDelete = (kbId: string, name: string) => {
    Modal.confirm({
      title: 'Delete Knowledge Base',
      content: `Are you sure you want to permanently delete "${name}"? This will physically drop the collection in Qdrant and delete all ingested documents. This action CANNOT be undone.`,
      okText: 'Permanently Delete',
      okType: 'danger',
      onOk: () => deleteKbMutation.mutate(kbId),
    });
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

  return (
    <div style={{ padding: '0 4px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      
      {/* 1. Header Area with dynamic actions */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <Title level={2} className="font-outfit" style={{ margin: 0, fontWeight: 800, display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Database size={28} className="text-primary" style={{ color: 'var(--colorPrimary)' }} />
            Knowledge Base Hub
          </Title>
          <Paragraph type="secondary" style={{ margin: '4px 0 0 0', fontSize: '14px' }}>
            Create, manage, and configure unified document store vector indices.
          </Paragraph>
        </div>
        <Button
          type="primary"
          icon={<Plus size={18} />}
          size="large"
          className={`font-outfit ${styles.shadowButton}`}
          onClick={() => {
            setCreateModalVisible(true);
            setCurrentStep(0);
            setShowParserOverrides(false);
            const defaultEmbed = embeddingModels.includes('text-embedding-3-small') ? 'text-embedding-3-small' : (embeddingModels[0] || '');
            const defaultParser = parserProviders.includes('docling') ? 'docling' : (parserProviders[0] || '');
            form.setFieldsValue({
              embedding_model: defaultEmbed,
              distance_metric: 'cosine',
              parsing_provider: defaultParser,
              chunk_size: 1024,
              chunk_overlap: 200,
              merge_max_chars: 4096,
              breadcrumb_depth: 2,
              breadcrumb_separator: ' > ',
              include_root_breadcrumb: true
            });
          }}
          style={{ height: '46px', borderRadius: '12px', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}
        >
          New Knowledge Base
        </Button>
      </div>

      <Row gutter={[20, 20]}>
        <Col xs={24} sm={8}>
          <Card variant="borderless" className={`glass-card ${styles.cardHoverEffect}`} style={{ borderRadius: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{ padding: '12px', background: 'rgba(79, 70, 229, 0.1)', borderRadius: '12px', color: '#4f46e5' }}>
                <HardDrive size={24} />
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: '13px', display: 'block' }}>Total Collections</Text>
                <Title level={3} style={{ margin: 0, fontWeight: 800, fontFamily: 'Outfit' }}>{totalCount}</Title>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card variant="borderless" className={`glass-card ${styles.cardHoverEffect}`} style={{ borderRadius: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{ padding: '12px', background: 'rgba(16, 185, 129, 0.1)', borderRadius: '12px', color: '#10b981' }}>
                <Layers size={24} />
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: '13px', display: 'block' }}>Healthy Bases</Text>
                <Title level={3} style={{ margin: 0, fontWeight: 800, fontFamily: 'Outfit' }}>{readyCount}</Title>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card variant="borderless" className={`glass-card ${styles.cardHoverEffect}`} style={{ borderRadius: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{ padding: '12px', background: 'rgba(236, 72, 153, 0.1)', borderRadius: '12px', color: '#ec4899' }}>
                <Cpu size={24} />
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: '13px', display: 'block' }}>Active Embeddings</Text>
                <Title level={3} style={{ margin: 0, fontWeight: 800, fontFamily: 'Outfit', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '180px' }} title={activeModels.join(', ')}>
                  {activeModels.length ? activeModels[0] : 'None'}
                </Title>
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      {/* 3. Table View Card */}
      <Card variant="borderless" className="glass-card" style={{ borderRadius: '16px', overflow: 'hidden' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
          <Text strong style={{ fontSize: '16px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            Available Databases <Badge count={filteredItems.length} showZero color="var(--colorPrimary)" style={{ fontWeight: 700 }} />
          </Text>
          
          {/* Search bar */}
          <Input
            placeholder="Search by knowledge base name..."
            prefix={<Search size={16} color="var(--text-secondary)" style={{ marginRight: '6px' }} />}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{ width: '320px', borderRadius: '10px' }}
            allowClear
          />
        </div>

        <Table
          dataSource={filteredItems}
          loading={kbLoading}
          rowKey="id"
          className={styles.customTable}
          pagination={{
            pageSize: 6,
            hideOnSinglePage: true,
          }}
          columns={[
            {
              title: 'Name',
              dataIndex: 'name',
              key: 'name',
              render: (name: string, record: KnowledgeBaseRead) => (
                <Space size="middle" style={{ cursor: 'pointer' }} onClick={() => onSelect(record)}>
                  <div style={{
                    width: '38px',
                    height: '38px',
                    borderRadius: '10px',
                    background: 'linear-gradient(135deg, rgba(79, 70, 229, 0.1) 0%, rgba(0, 242, 254, 0.1) 100%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    border: '1px solid rgba(79, 70, 229, 0.15)'
                  }}>
                    <Database size={18} color="#4f46e5" />
                  </div>
                  <div>
                    <span className="font-outfit" style={{ fontWeight: 700, fontSize: '15px', color: 'var(--text-primary)' }}>{name}</span>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'Outfit' }}>ID: {record.id.slice(0, 8)}...</div>
                  </div>
                </Space>
              ),
            },
            {
              title: 'Status',
              dataIndex: 'status',
              key: 'status',
              render: (status: string) => {
                let color = 'default';
                let pulse = false;
                if (status === 'READY' || status === 'COMPLETED') color = 'success';
                else if (status === 'FAILED') color = 'error';
                else if (status === 'RUNNING') {
                  color = 'processing';
                  pulse = true;
                } else if (status === 'DELETING') color = 'warning';

                return (
                  <Space size={6}>
                    {pulse && <span className={styles.pulseDot} />}
                    <Tag color={color} style={{ fontWeight: 600, borderRadius: '6px', padding: '2px 8px' }}>
                      {status}
                    </Tag>
                  </Space>
                );
              }
            },
            {
              title: 'Vector Model & Similarity',
              key: 'model',
              render: (_, record: KnowledgeBaseRead) => (
                <Space orientation="vertical" size={2}>
                  <Tag color="blue" style={{ fontFamily: 'Outfit', fontWeight: 500, borderRadius: '4px', margin: 0 }}>
                    <Cpu size={11} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
                    {record.embedding_config?.model || 'text-embedding-3-small'}
                  </Tag>
                  <span style={{ fontSize: '11px', color: 'var(--text-secondary)', fontFamily: 'Outfit' }}>
                    Distance: <span style={{ textTransform: 'capitalize', fontWeight: 600 }}>{record.embedding_config?.distance || 'cosine'}</span>
                  </span>
                </Space>
              )
            },
            {
              title: 'Default Parser',
              key: 'parser',
              render: (_, record: KnowledgeBaseRead) => (
                <Tag color="purple" style={{ textTransform: 'capitalize', fontWeight: 500, borderRadius: '6px' }}>
                  <Sparkles size={11} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
                  {record.default_parsing_config?.provider || 'docling'}
                </Tag>
              )
            },
            {
              title: 'Created At',
              dataIndex: 'created_at',
              key: 'created_at',
              render: (date: string) => (
                <Space size={6} style={{ color: 'var(--text-secondary)', fontSize: '13px', fontFamily: 'Outfit' }}>
                  <Calendar size={13} style={{ opacity: 0.7 }} />
                  <span>{formatDate(date)}</span>
                </Space>
              )
            },
            {
              title: 'Actions',
              key: 'actions',
              align: 'right',
              render: (_, record: KnowledgeBaseRead) => (
                <Space size="middle">
                  <Button
                    type="primary"
                    ghost
                    icon={<ArrowRight size={15} />}
                    onClick={() => onSelect(record)}
                    style={{ borderRadius: '8px', display: 'flex', alignItems: 'center', fontWeight: 600 }}
                  >
                    Enter Base
                  </Button>
                  <Button
                    type="text"
                    danger
                    icon={<Trash2 size={16} />}
                    onClick={() => handleDelete(record.id, record.name)}
                    disabled={record.status === 'DELETING'}
                  />
                </Space>
              ),
            },
          ]}
          locale={{
            emptyText: (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={
                  <div style={{ textAlign: 'center', padding: '16px' }}>
                    <Text type="secondary" style={{ fontSize: '14px' }}>No Knowledge Bases Found.</Text>
                    <Paragraph type="secondary" style={{ fontSize: '12px', margin: '4px 0 12px 0' }}>
                      Get started by creating your first vector collection.
                    </Paragraph>
                  </div>
                }
              />
            )
          }}
        />
      </Card>

      {/* 4. Beautiful creation modal */}
      <Modal
        title={
          <span className="font-outfit" style={{ fontSize: '18px', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Database size={20} style={{ color: 'var(--colorPrimary)' }} />
            Create Knowledge Base
          </span>
        }
        open={createModalVisible}
        onCancel={() => {
          setCreateModalVisible(false);
        }}
        footer={[
          <Button key="cancel" onClick={() => setCreateModalVisible(false)}>
            Cancel
          </Button>,
          currentStep > 0 && (
            <Button key="prev" onClick={handlePrevHub}>
              Previous
            </Button>
          ),
          currentStep < 2 && (
            <Button key="next" type="primary" onClick={handleNextHub}>
              Next
            </Button>
          ),
          currentStep === 2 && (
            <Button key="submit" type="primary" onClick={() => form.submit()} loading={createKbMutation.isPending}>
              Create Collection
            </Button>
          ),
        ].filter(Boolean)}
        width={620}
        styles={{ body: { padding: '12px 0' } }}
      >
        <Steps
          current={currentStep}
          size="small"
          style={{ marginBottom: '24px', padding: '0 4px' }}
          items={[
            { title: 'General & Parsing' },
            { title: 'Chunking Strategy' },
            { title: 'Vector Database' }
          ]}
        />
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreate}
          style={{ marginTop: '8px' }}
        >
          <div style={{ padding: '0 4px' }}>
            
            {/* Step 0: General & Parsing */}
            <div style={{ display: currentStep === 0 ? 'block' : 'none' }}>
              <Form.Item
                name="name"
                label="Collection Name"
                rules={[
                  { required: true, message: 'Please enter a name for the database' },
                  { pattern: /^[a-zA-Z0-9_\-\s]+$/, message: 'Only alphanumeric characters, spaces, hyphens, and underscores are allowed' }
                ]}
                tooltip="The collection name must be unique. Spaces will be replaced with underscores, and converted to lowercase."
              >
                <Input placeholder="e.g. Legal Documents or financial_report_2026" className="font-outfit" size="large" />
              </Form.Item>

              <Form.Item
                name="parsing_provider"
                label="Default Document Parser"
                rules={[{ required: true }]}
                tooltip="The default parser provider used for file ingestion. Docling is highly accurate with PDFs, tables, and complex documents."
              >
                <Select
                  size="large"
                  loading={configLoading}
                  options={parserProviders.map((provider) => ({
                    value: provider,
                    label: `${provider.charAt(0).toUpperCase() + provider.slice(1)} ${provider === 'docling' ? '(Deep Layout)' : ''}`
                  }))}
                />
              </Form.Item>

              <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--border-color)' }}>
                <Button
                  type="link"
                  onClick={() => setShowParserOverrides(!showParserOverrides)}
                  style={{ padding: 0, display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600, fontSize: '13px', marginBottom: '12px' }}
                >
                  {showParserOverrides ? 'Hide Extension-Specific Parser Overrides' : 'Show Extension-Specific Parser Overrides'}
                </Button>
                {showParserOverrides && (
                  <div>
                    <Text strong style={{ display: 'block', marginBottom: '8px', fontSize: '13px' }}>
                      Extension-Specific Parser Overrides
                    </Text>
                    <Paragraph type="secondary" style={{ fontSize: '12px', marginBottom: '16px' }}>
                      Optionally override the default parser for specific file types.
                    </Paragraph>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      {['.pdf', '.docx', '.txt', '.html', '.md'].map((ext) => (
                        <Form.Item
                          key={ext}
                          name={['extension_providers', ext]}
                          label={`Files ending in ${ext}`}
                          style={{ marginBottom: '8px' }}
                        >
                          <Select
                            placeholder="Use Default Parser"
                            allowClear
                            loading={configLoading}
                            size="small"
                            options={parserProviders.map((provider) => ({
                              value: provider,
                              label: provider.charAt(0).toUpperCase() + provider.slice(1)
                            }))}
                          />
                        </Form.Item>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Step 1: Chunking Strategy */}
            <div style={{ display: currentStep === 1 ? 'block' : 'none' }}>
              <Paragraph type="secondary" style={{ fontSize: '13px', marginBottom: '16px' }}>
                Configure how the documents will be split into chunks during ingestion.
              </Paragraph>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="chunk_size"
                    label="Chunk Size (Characters)"
                    rules={[{ required: true }]}
                  >
                    <InputNumber min={100} max={10000} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="chunk_overlap"
                    label="Chunk Overlap"
                    rules={[{ required: true }]}
                  >
                    <InputNumber min={0} max={2000} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="merge_max_chars"
                    label="Merge Max Characters"
                    rules={[{ required: true }]}
                  >
                    <InputNumber min={100} max={20000} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="breadcrumb_depth"
                    label="Breadcrumb Depth"
                    rules={[{ required: true }]}
                  >
                    <InputNumber min={0} max={10} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="breadcrumb_separator"
                    label="Separator"
                    rules={[{ required: true }]}
                  >
                    <Input style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="include_root_breadcrumb"
                    label="Include Root Breadcrumb"
                    valuePropName="checked"
                  >
                    <Switch />
                  </Form.Item>
                </Col>
              </Row>
            </div>

            {/* Step 2: Vector Database */}
            <div style={{ display: currentStep === 2 ? 'block' : 'none' }}>
              <Row gutter={16}>
                <Col span={24}>
                  <Form.Item
                    name="embedding_model"
                    label="Embedding Model"
                    rules={[{ required: true }]}
                    tooltip="The vectorizer model used to compute chunk embeddings. Must match LiteLLM configurations."
                  >
                    <Select
                      size="large"
                      loading={configLoading}
                      options={embeddingModels.map((model) => ({
                        value: model,
                        label: model
                      }))}
                    />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="use_colpali"
                    label="Use ColPali (Vision RAG)"
                    valuePropName="checked"
                    tooltip="Enable ColPali to use multi-vector vision representation. This processes document pages as images."
                  >
                    <Switch />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item noStyle shouldUpdate={(prevValues, currentValues) => prevValues.use_colpali !== currentValues.use_colpali}>
                    {({ getFieldValue }) => {
                      const useColpali = getFieldValue('use_colpali');
                      if (useColpali) {
                        return (
                          <Form.Item
                            name="colpali_model"
                            label="ColPali Model"
                            rules={[{ required: true, message: 'Please select a ColPali model' }]}
                            tooltip="Multi-vector vision model for page image embeddings."
                          >
                            <Select
                              size="large"
                              placeholder="Select ColPali model"
                              options={[
                                { value: 'vidore/colpali-v1.2-merged', label: 'vidore/colpali-v1.2-merged (Default)' },
                                { value: 'vidore/colpali-v1.3-merged', label: 'vidore/colpali-v1.3-merged' },
                                { value: 'vidore/colSmol-500M-merged', label: 'vidore/colSmol-500M-merged' }
                              ]}
                            />
                          </Form.Item>
                        );
                      }
                      return null;
                    }}
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item
                name="distance_metric"
                label="Distance Similarity Metric"
                rules={[{ required: true }]}
              >
                <Radio.Group optionType="button" buttonStyle="solid" style={{ width: '100%' }}>
                  <Row gutter={8} style={{ width: '100%', margin: 0 }}>
                    <Col span={8} style={{ padding: '0 4px' }}><Radio.Button value="cosine" style={{ width: '100%', textAlign: 'center', borderRadius: '8px' }}>Cosine</Radio.Button></Col>
                    <Col span={8} style={{ padding: '0 4px' }}><Radio.Button value="dot" style={{ width: '100%', textAlign: 'center', borderRadius: '8px' }}>Dot Product</Radio.Button></Col>
                    <Col span={8} style={{ padding: '0 4px' }}><Radio.Button value="euclid" style={{ width: '100%', textAlign: 'center', borderRadius: '8px' }}>Euclidean</Radio.Button></Col>
                  </Row>
                </Radio.Group>
              </Form.Item>

              {/* Warning Alert */}
              <div style={{ marginTop: '20px' }}>
                <AlertTriangle size={15} style={{ color: '#faad14', verticalAlign: 'middle', marginRight: '6px', display: 'inline-block' }} />
                <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  Creating a database maps directly to a high-performance collection inside Qdrant and sets up permanent defaults.
                </span>
              </div>
            </div>

          </div>
        </Form>
      </Modal>

    </div>
  );
};
