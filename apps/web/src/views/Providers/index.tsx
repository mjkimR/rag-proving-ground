import React, { useState } from 'react';
import {
  Tabs,
  Table,
  Button,
  Switch,
  Tag,
  Space,
  Modal,
  Form,
  Input,
  message,
  Card,
  Tooltip,
  Alert,
  Empty,
  Popconfirm
} from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Server,
  Cpu,
  RefreshCw,
  Play,
  Edit,
  Star,
  CheckCircle,
  XCircle,
  Plus
} from 'lucide-react';
import {
  getAiModelsApiV1AiModelsGet,
  syncAiModelsApiV1AiModelsSyncPost,
  testAiModelApiV1AiModelsAiModelIdTestPost,
  patchAiModelApiV1AiModelsAiModelIdPatch,
  createAiModelApiV1AiModelsPost,
  deleteAiModelApiV1AiModelsAiModelIdDelete,
  getDocumentParsersApiV1DocumentParsersGet,
  syncDocumentParsersApiV1DocumentParsersSyncPost,
  testDocumentParserApiV1DocumentParsersDocumentParserIdTestPost,
  patchDocumentParserApiV1DocumentParsersDocumentParserIdPatch,
  createDocumentParserApiV1DocumentParsersPost,
  deleteDocumentParserApiV1DocumentParsersDocumentParserIdDelete
} from '@/generated/api/sdk.gen';
import {
  MessageSquare
} from 'lucide-react';
import { PromptsSection } from './PromptsSection';
import type {
  AiModelRead,
  AiModelCreate,
  AiModelPatch,
  DocumentParserRead,
  DocumentParserCreate,
  DocumentParserPatch
} from '@/generated/api/types.gen';

export const Providers: React.FC = () => {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState('models');

  // Modal states
  const [isModelModalOpen, setIsModelModalOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<AiModelRead | null>(null);
  const [isParserModalOpen, setIsParserModalOpen] = useState(false);
  const [editingParser, setEditingParser] = useState<DocumentParserRead | null>(null);

  // Test states
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  const [form] = Form.useForm();

  // Queries
  const { data: modelsData, isLoading: modelsLoading } = useQuery({
    queryKey: ['aiModels'],
    queryFn: () => getAiModelsApiV1AiModelsGet({
      query: { limit: 100 },
      throwOnError: true
    }),
  });

  const { data: parsersData, isLoading: parsersLoading } = useQuery({
    queryKey: ['documentParsers'],
    queryFn: () => getDocumentParsersApiV1DocumentParsersGet({
      query: { limit: 100 },
      throwOnError: true
    }),
  });

  // Mutations
  const syncModelsMutation = useMutation({
    mutationFn: () => syncAiModelsApiV1AiModelsSyncPost({ throwOnError: true }),
    onSuccess: () => {
      message.success('Successfully synchronized AI Models from gateway.');
      queryClient.invalidateQueries({ queryKey: ['aiModels'] });
    },
    onError: (err: unknown) => {
      const errMsg = (err as Error & { message?: string })?.message || String(err);
      message.error(`Sync failed: ${errMsg}`);
    }
  });

  const syncParsersMutation = useMutation({
    mutationFn: () => syncDocumentParsersApiV1DocumentParsersSyncPost({ throwOnError: true }),
    onSuccess: () => {
      message.success('Successfully synchronized Document Parsers.');
      queryClient.invalidateQueries({ queryKey: ['documentParsers'] });
    },
    onError: (err: unknown) => {
      const errMsg = (err as Error & { message?: string })?.message || String(err);
      message.error(`Sync failed: ${errMsg}`);
    }
  });

  const saveModelMutation = useMutation({
    mutationFn: ({ id, data }: { id: string | null; data: AiModelCreate | AiModelPatch }) => {
      if (id) {
        return patchAiModelApiV1AiModelsAiModelIdPatch({
          path: { ai_model_id: id },
          body: data as AiModelPatch,
          throwOnError: true
        });
      } else {
        return createAiModelApiV1AiModelsPost({
          body: data as AiModelCreate,
          throwOnError: true
        });
      }
    },
    onSuccess: () => {
      message.success('Model settings saved.');
      setIsModelModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ['aiModels'] });
    },
    onError: (err: unknown) => {
      const errMsg = (err as Error & { message?: string })?.message || String(err);
      message.error(`Failed to save model: ${errMsg}`);
    }
  });

  const deleteModelMutation = useMutation({
    mutationFn: (id: string) => deleteAiModelApiV1AiModelsAiModelIdDelete({
      path: { ai_model_id: id },
      throwOnError: true
    }),
    onSuccess: () => {
      message.success('Model deleted successfully.');
      queryClient.invalidateQueries({ queryKey: ['aiModels'] });
    },
    onError: (err: unknown) => {
      const errMsg = (err as Error & { message?: string })?.message || String(err);
      message.error(`Delete failed: ${errMsg}`);
    }
  });

  const saveParserMutation = useMutation({
    mutationFn: ({ id, data }: { id: string | null; data: DocumentParserCreate | DocumentParserPatch }) => {
      if (id) {
        return patchDocumentParserApiV1DocumentParsersDocumentParserIdPatch({
          path: { document_parser_id: id },
          body: data as DocumentParserPatch,
          throwOnError: true
        });
      } else {
        return createDocumentParserApiV1DocumentParsersPost({
          body: data as DocumentParserCreate,
          throwOnError: true
        });
      }
    },
    onSuccess: () => {
      message.success('Parser settings saved.');
      setIsParserModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ['documentParsers'] });
    },
    onError: (err: unknown) => {
      const errMsg = (err as Error & { message?: string })?.message || String(err);
      message.error(`Failed to save parser: ${errMsg}`);
    }
  });

  const deleteParserMutation = useMutation({
    mutationFn: (id: string) => deleteDocumentParserApiV1DocumentParsersDocumentParserIdDelete({
      path: { document_parser_id: id },
      throwOnError: true
    }),
    onSuccess: () => {
      message.success('Parser deleted successfully.');
      queryClient.invalidateQueries({ queryKey: ['documentParsers'] });
    },
    onError: (err: unknown) => {
      const errMsg = (err as Error & { message?: string })?.message || String(err);
      message.error(`Delete failed: ${errMsg}`);
    }
  });

  const testModelMutation = useMutation({
    mutationFn: (id: string) => testAiModelApiV1AiModelsAiModelIdTestPost({
      path: { ai_model_id: id },
      throwOnError: true
    }),
    onMutate: (id) => {
      setTestingId(id);
      setTestResult(null);
    },
    onSuccess: (res: { data: unknown }) => {
      const data = res.data as { success: boolean; message: string };
      setTestResult({
        success: data.success,
        message: data.message
      });
      if (data.success) {
        message.success('Connection test succeeded!');
      } else {
        message.warning('Connection test failed.');
      }
    },
    onError: (err: unknown) => {
      const errMsg = (err as Error & { message?: string })?.message || String(err);
      setTestResult({
        success: false,
        message: `Connection error: ${errMsg}`
      });
      message.error('Connection test failed.');
    },
    onSettled: () => {
      setTestingId(null);
    }
  });

  const testParserMutation = useMutation({
    mutationFn: (id: string) => testDocumentParserApiV1DocumentParsersDocumentParserIdTestPost({
      path: { document_parser_id: id },
      throwOnError: true
    }),
    onMutate: (id) => {
      setTestingId(id);
      setTestResult(null);
    },
    onSuccess: (res: { data: unknown }) => {
      const data = res.data as { success: boolean; message: string };
      setTestResult({
        success: data.success,
        message: data.message
      });
      if (data.success) {
        message.success('Parser test succeeded!');
      } else {
        message.warning('Parser test failed.');
      }
    },
    onError: (err: unknown) => {
      const errMsg = (err as Error & { message?: string })?.message || String(err);
      setTestResult({
        success: false,
        message: `Parser error: ${errMsg}`
      });
      message.error('Parser test failed.');
    },
    onSettled: () => {
      setTestingId(null);
    }
  });

  // Toggle active helper
  const handleToggleModelActive = (model: AiModelRead, active: boolean) => {
    saveModelMutation.mutate({
      id: model.id,
      data: { is_active: active }
    });
  };

  const handleToggleParserActive = (parser: DocumentParserRead, active: boolean) => {
    saveParserMutation.mutate({
      id: parser.id,
      data: { is_active: active }
    });
  };

  // Set default helper
  const handleSetModelDefault = (model: AiModelRead) => {
    saveModelMutation.mutate({
      id: model.id,
      data: { is_default: true }
    });
  };

  const handleSetParserDefault = (parser: DocumentParserRead) => {
    saveParserMutation.mutate({
      id: parser.id,
      data: { is_default: true }
    });
  };

  // Open Edit modals
  const handleOpenModelEdit = (model: AiModelRead | null) => {
    setEditingModel(model);
    setTestResult(null);
    if (model) {
      form.setFieldsValue({
        name: model.name,
        provider: model.provider,
        model_type: model.model_type,
        is_active: model.is_active,
        is_default: model.is_default,
        extra_metadata: JSON.stringify(model.extra_metadata || {}, null, 2)
      });
    } else {
      form.resetFields();
      form.setFieldsValue({
        is_active: true,
        is_default: false,
        extra_metadata: '{}'
      });
    }
    setIsModelModalOpen(true);
  };

  const handleOpenParserEdit = (parser: DocumentParserRead | null) => {
    setEditingParser(parser);
    setTestResult(null);
    if (parser) {
      form.setFieldsValue({
        name: parser.name,
        is_active: parser.is_active,
        is_default: parser.is_default,
        connection_info: JSON.stringify(parser.connection_info || {}, null, 2),
        extra_metadata: JSON.stringify(parser.extra_metadata || {}, null, 2)
      });
    } else {
      form.resetFields();
      form.setFieldsValue({
        is_active: true,
        is_default: false,
        connection_info: '{}',
        extra_metadata: '{}'
      });
    }
    setIsParserModalOpen(true);
  };

  // Save submit handlers
  const handleModelSubmit = (values: Record<string, string>) => {
    try {
      const extraMeta = JSON.parse(values.extra_metadata || '{}') as Record<string, unknown>;
      saveModelMutation.mutate({
        id: editingModel ? editingModel.id : null,
        data: {
          ...values,
          connection_info: {},
          extra_metadata: extraMeta
        }
      });
    } catch {
      message.error('Invalid JSON in metadata.');
    }
  };

  const handleParserSubmit = (values: Record<string, string>) => {
    try {
      const connInfo = JSON.parse(values.connection_info || '{}') as Record<string, unknown>;
      const extraMeta = JSON.parse(values.extra_metadata || '{}') as Record<string, unknown>;
      saveParserMutation.mutate({
        id: editingParser ? editingParser.id : null,
        data: {
          ...values,
          connection_info: connInfo,
          extra_metadata: extraMeta
        }
      });
    } catch {
      message.error('Invalid JSON in connection parameters or metadata.');
    }
  };

  // UI Table column configs
  const modelColumns = [
    {
      title: 'Model Name',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: AiModelRead) => (
        <Space>
          <span style={{ fontWeight: 600 }}>{text}</span>
          {record.is_default && (
            <Tooltip title="Default Model">
              <Star size={16} fill="#eab308" color="#eab308" />
            </Tooltip>
          )}
        </Space>
      )
    },
    {
      title: 'Provider',
      dataIndex: 'provider',
      key: 'provider',
      render: (text: string) => <Tag color="default">{text.toUpperCase()}</Tag>
    },
    {
      title: 'Type',
      dataIndex: 'model_type',
      key: 'model_type',
      render: (text: string) => {
        let color = 'blue';
        if (text === 'embedding') color = 'green';
        if (text === 'reranker') color = 'purple';
        return <Tag color={color}>{text.toUpperCase()}</Tag>;
      }
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active: boolean, record: AiModelRead) => (
        <Switch
          checked={active}
          onChange={(checked) => handleToggleModelActive(record, checked)}
          size="small"
        />
      )
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: unknown, record: AiModelRead) => (
        <Space size="middle">
          <Button
            type="text"
            icon={<Edit size={15} />}
            onClick={() => handleOpenModelEdit(record)}
            title="Edit Settings"
          />
          <Button
            type="text"
            icon={<Play size={15} />}
            loading={testingId === record.id}
            onClick={() => testModelMutation.mutate(record.id)}
            title="Test Connection"
          />
          {!record.is_default && record.is_active && (
            <Button
              type="text"
              icon={<Star size={15} />}
              onClick={() => handleSetModelDefault(record)}
              title="Set as Default"
            />
          )}
          <Popconfirm
            title="Delete AI Model"
            description="Are you sure you want to delete this model configuration?"
            onConfirm={() => deleteModelMutation.mutate(record.id)}
            okText="Yes"
            cancelText="No"
          >
            <Button type="text" danger icon={<XCircle size={15} />} title="Delete" />
          </Popconfirm>
        </Space>
      )
    }
  ];

  const parserColumns = [
    {
      title: 'Parser Name',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: DocumentParserRead) => (
        <Space>
          <span style={{ fontWeight: 600 }}>{text}</span>
          {record.is_default && (
            <Tooltip title="Default Parser">
              <Star size={16} fill="#eab308" color="#eab308" />
            </Tooltip>
          )}
        </Space>
      )
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active: boolean, record: DocumentParserRead) => (
        <Switch
          checked={active}
          onChange={(checked) => handleToggleParserActive(record, checked)}
          size="small"
        />
      )
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: unknown, record: DocumentParserRead) => (
        <Space size="middle">
          <Button
            type="text"
            icon={<Edit size={15} />}
            onClick={() => handleOpenParserEdit(record)}
            title="Edit Settings"
          />
          <Button
            type="text"
            icon={<Play size={15} />}
            loading={testingId === record.id}
            onClick={() => testParserMutation.mutate(record.id)}
            title="Test Parser"
          />
          {!record.is_default && record.is_active && (
            <Button
              type="text"
              icon={<Star size={15} />}
              onClick={() => handleSetParserDefault(record)}
              title="Set as Default"
            />
          )}
          <Popconfirm
            title="Delete Document Parser"
            description="Are you sure you want to delete this parser configuration?"
            onConfirm={() => deleteParserMutation.mutate(record.id)}
            okText="Yes"
            cancelText="No"
          >
            <Button type="text" danger icon={<XCircle size={15} />} title="Delete" />
          </Popconfirm>
        </Space>
      )
    }
  ];

  const tabItems = [
    {
      key: 'models',
      label: (
        <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Cpu size={16} /> AI Models
        </span>
      ),
      children: (
        <Card
          bordered={false}
          styles={{ body: { padding: '16px 0' } }}
          title={
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="font-outfit" style={{ fontSize: '16px', fontWeight: 700 }}>
                Configured Gateway & Local Models
              </span>
              <Space>
                <Button
                  icon={<Plus size={16} />}
                  onClick={() => handleOpenModelEdit(null)}
                >
                  Add Custom Model
                </Button>
                <Button
                  type="primary"
                  icon={<RefreshCw size={16} />}
                  loading={syncModelsMutation.isPending}
                  onClick={() => syncModelsMutation.mutate()}
                  style={{
                    background: 'linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%)',
                    border: 'none',
                    boxShadow: '0 2px 8px rgba(79, 70, 229, 0.15)'
                  }}
                >
                  Sync from LiteLLM
                </Button>
              </Space>
            </div>
          }
        >
          <Table
            dataSource={modelsData?.data?.items || []}
            columns={modelColumns}
            loading={modelsLoading}
            rowKey="id"
            pagination={{ pageSize: 10 }}
            locale={{ emptyText: <Empty description="No models registered. Run sync or add a custom model." /> }}
          />
        </Card>
      )
    },
    {
      key: 'parsers',
      label: (
        <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Server size={16} /> Document Parsers
        </span>
      ),
      children: (
        <Card
          bordered={false}
          styles={{ body: { padding: '16px 0' } }}
          title={
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="font-outfit" style={{ fontSize: '16px', fontWeight: 700 }}>
                Registered Chunk & Document Parsers
              </span>
              <Space>
                <Button
                  icon={<Plus size={16} />}
                  onClick={() => handleOpenParserEdit(null)}
                >
                  Add Custom Parser
                </Button>
                <Button
                  type="primary"
                  icon={<RefreshCw size={16} />}
                  loading={syncParsersMutation.isPending}
                  onClick={() => syncParsersMutation.mutate()}
                  style={{
                    background: 'linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%)',
                    border: 'none',
                    boxShadow: '0 2px 8px rgba(79, 70, 229, 0.15)'
                  }}
                >
                  Sync Parser Registry
                </Button>
              </Space>
            </div>
          }
        >
          <Table
            dataSource={parsersData?.data?.items || []}
            columns={parserColumns}
            loading={parsersLoading}
            rowKey="id"
            pagination={{ pageSize: 10 }}
            locale={{ emptyText: <Empty description="No document parsers registered." /> }}
          />
        </Card>
      )
    },
    {
      key: 'prompts',
      label: (
        <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <MessageSquare size={16} /> Prompts
        </span>
      ),
      children: <PromptsSection />
    }
  ];

  return (
    <div style={{ padding: '4px 0 24px 0' }}>
      {testResult && (
        <div style={{ marginBottom: '20px' }}>
          <Alert
            message={testResult.success ? 'Diagnostic Test Succeeded' : 'Diagnostic Test Failed'}
            description={testResult.message}
            type={testResult.success ? 'success' : 'error'}
            showIcon
            closable
            onClose={() => setTestResult(null)}
            icon={testResult.success ? <CheckCircle size={20} /> : <XCircle size={20} />}
          />
        </div>
      )}

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={tabItems}
        size="large"
        style={{ background: 'transparent' }}
      />

      {/* Model config modal */}
      <Modal
        title={editingModel ? 'Edit AI Model Settings' : 'Add Custom AI Model'}
        open={isModelModalOpen}
        onCancel={() => setIsModelModalOpen(false)}
        onOk={() => form.submit()}
        width={650}
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleModelSubmit}
          style={{ marginTop: '16px' }}
        >
          <Form.Item
            name="name"
            label="Model ID/Name (Logical identifier)"
            rules={[{ required: true, message: 'Please enter model identifier.' }]}
          >
            <Input placeholder="e.g. custom-gpt-4o" disabled={!!editingModel} />
          </Form.Item>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <Form.Item
              name="provider"
              label="Provider"
              rules={[{ required: true, message: 'Please enter provider name.' }]}
            >
              <Input placeholder="e.g. openai, gemini, ollama" />
            </Form.Item>

            <Form.Item
              name="model_type"
              label="Model Type"
              rules={[{ required: true, message: 'Please select model type.' }]}
            >
              <select
                style={{
                  width: '100%',
                  height: '32px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-color, #d9d9d9)',
                  padding: '0 8px'
                }}
              >
                <option value="llm">LLM (Chat / Generation)</option>
                <option value="embedding">Embedding</option>
                <option value="reranker">Reranker</option>
              </select>
            </Form.Item>
          </div>

          <Form.Item
            name="extra_metadata"
            label="Extra Metadata (JSON Object)"
            extra="Custom variables, description, capabilities description, etc."
          >
            <Input.TextArea rows={4} placeholder="{}" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Parser config modal */}
      <Modal
        title={editingParser ? 'Edit Document Parser Settings' : 'Add Custom Parser'}
        open={isParserModalOpen}
        onCancel={() => setIsParserModalOpen(false)}
        onOk={() => form.submit()}
        width={650}
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleParserSubmit}
          style={{ marginTop: '16px' }}
        >
          <Form.Item
            name="name"
            label="Parser Name"
            rules={[{ required: true, message: 'Please enter parser name.' }]}
          >
            <Input placeholder="e.g. marker" disabled={!!editingParser} />
          </Form.Item>

          <Form.Item
            name="connection_info"
            label="Connection Config (JSON Object)"
            extra="Custom configs like 'base_url', 'timeout', 'max_page_chars', etc."
            rules={[{ required: true, message: 'Please enter connection config.' }]}
          >
            <Input.TextArea rows={5} placeholder="{}" />
          </Form.Item>

          <Form.Item
            name="extra_metadata"
            label="Extra Metadata (JSON Object)"
            extra="Capabilities tags, version etc."
          >
            <Input.TextArea rows={4} placeholder="{}" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};
