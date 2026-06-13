import React, { useEffect, useReducer } from 'react';
import {
  Modal, Form, Input, Select, InputNumber, Switch, Radio, Alert, Space, Typography, Steps, Button
} from 'antd';
import { Settings, Info } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  patchKnowledgeBaseApiV1KnowledgeBasesKnowledgeBaseIdPatch,
  getProviderOptionsApiV1ProvidersOptionsGet
} from '@/generated/api/sdk.gen';
import type { KnowledgeBaseRead, KnowledgeBaseConfigApplyMode, KnowledgeBasePatch } from '@/generated/api/types.gen';
import { PARSER_LABELS } from '@/views/DocumentWorkbench/types';

const { Text, Paragraph } = Typography;

const normalizeExtensions = (
  obj: Record<string, string | null | undefined> | null | undefined
): Record<string, string> => {
  if (!obj) return {};
  return Object.fromEntries(
    Object.entries(obj).filter(([_, v]) => v !== undefined && v !== null && String(v).trim() !== '')
  ) as Record<string, string>;
};

const CONFIG_STEP_FIELDS = [
  [
    'name',
    ['default_parsing_config', 'provider'],
    ['default_parsing_config', 'extension_providers']
  ],
  [
    ['default_chunking_config', 'chunk_size'],
    ['default_chunking_config', 'chunk_overlap'],
    ['default_chunking_config', 'merge_max_chars'],
    ['default_chunking_config', 'breadcrumb_depth'],
    ['default_chunking_config', 'breadcrumb_separator']
  ]
];

interface SettingsModalState {
  currentStep: number;
  showParserOverrides: boolean;
  confirmVisible: boolean;
  pendingValues: KnowledgeBasePatch | null;
  loadType: 'low' | 'high' | 'reembed';
  applyMode: KnowledgeBaseConfigApplyMode;
}

type SettingsModalAction =
  | { type: 'reset' }
  | { type: 'setStep'; value: React.SetStateAction<number> }
  | { type: 'setShowParserOverrides'; value: boolean }
  | { type: 'setConfirmVisible'; value: boolean }
  | { type: 'prepareSave'; pendingValues: KnowledgeBasePatch; loadType: 'low' | 'high' | 'reembed'; applyMode: KnowledgeBaseConfigApplyMode }
  | { type: 'setApplyMode'; value: KnowledgeBaseConfigApplyMode };

const initialSettingsModalState: SettingsModalState = {
  currentStep: 0,
  showParserOverrides: false,
  confirmVisible: false,
  pendingValues: null,
  loadType: 'low',
  applyMode: 'INHERITED_ONLY',
};

const settingsModalReducer = (
  state: SettingsModalState,
  action: SettingsModalAction
): SettingsModalState => {
  switch (action.type) {
    case 'reset':
      return { ...initialSettingsModalState };
    case 'setStep':
      return {
        ...state,
        currentStep: typeof action.value === 'function' ? action.value(state.currentStep) : action.value,
      };
    case 'setShowParserOverrides':
      return { ...state, showParserOverrides: action.value };
    case 'setConfirmVisible':
      return { ...state, confirmVisible: action.value };
    case 'prepareSave':
      return {
        ...state,
        pendingValues: action.pendingValues,
        loadType: action.loadType,
        applyMode: action.applyMode,
        confirmVisible: true,
      };
    case 'setApplyMode':
      return { ...state, applyMode: action.value };
  }
};

interface KnowledgeBaseSettingsModalProps {
  visible: boolean;
  onClose: () => void;
  kb: KnowledgeBaseRead | null;
  onSuccess: (updatedKb: KnowledgeBaseRead) => void;
}

export const KnowledgeBaseSettingsModal: React.FC<KnowledgeBaseSettingsModalProps> = ({
  visible,
  onClose,
  kb,
  onSuccess
}) => {
  const queryClient = useQueryClient();

  // Fetch dynamic configuration options
  const { data: configOptions, isLoading: configLoading } = useQuery({
    queryKey: ['configOptions'],
    queryFn: () => getProviderOptionsApiV1ProvidersOptionsGet({ throwOnError: true }),
    enabled: visible,
  });

  const embeddingModels = configOptions?.data?.embedding_models || [];
  const parserProviders = configOptions?.data?.parser_providers || [];
  const sparseEmbeddingModels = configOptions?.data?.sparse_embedding_models || [];
  const [form] = Form.useForm();
  const [{
    currentStep,
    showParserOverrides,
    confirmVisible,
    pendingValues,
    loadType,
    applyMode,
  }, dispatchSettings] = useReducer(settingsModalReducer, initialSettingsModalState);

  useEffect(() => {
    dispatchSettings({ type: 'reset' });
  }, [visible, kb?.id]);

  useEffect(() => {
    if (visible && kb) {
      form.setFieldsValue({
        name: kb.name,
        embedding_config: {
          model: kb.embedding_config?.model || 'text-embedding-3-small',
          distance: kb.embedding_config?.distance || 'cosine',
          use_colpali: kb.embedding_config?.use_colpali || false,
          colpali_model: kb.embedding_config?.colpali_model || 'vidore/colpali-v1.2-merged',
          retrieval_mode: kb.embedding_config?.retrieval_mode || 'dense',
          sparse_model: kb.embedding_config?.sparse_model || 'en-bm25',
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
          extension_providers: kb.default_parsing_config?.extension_providers || {},
        }
      });
    }
  }, [visible, kb, form]);

  const patchMutation = useMutation({
    mutationFn: (payload: { id: string; body: KnowledgeBasePatch }) => {
      return patchKnowledgeBaseApiV1KnowledgeBasesKnowledgeBaseIdPatch({
        path: { knowledge_base_id: payload.id },
        body: payload.body,
        throwOnError: true,
      });
    },
    onSuccess: (response: { data: KnowledgeBaseRead }) => {
      if (response.data) {
        onSuccess(response.data);
      }
      queryClient.invalidateQueries({ queryKey: ['kbList'] });
      queryClient.invalidateQueries({ queryKey: ['fileList', kb?.id] });
      dispatchSettings({ type: 'setConfirmVisible', value: false });
      onClose();
    },
    onError: (e) => {
      console.error('Failed to update knowledge base settings:', e);
      Modal.error({
        title: 'Update Failed',
        content: e instanceof Error ? e.message : 'Please check your connection and settings.',
      });
    }
  });

  const handlePreSave = (values: KnowledgeBasePatch) => {
    if (!kb) return;

    // Detect what has changed
    const embeddingChanged =
      kb.embedding_config?.model !== values.embedding_config?.model ||
      kb.embedding_config?.distance !== values.embedding_config?.distance ||
      kb.embedding_config?.use_colpali !== values.embedding_config?.use_colpali ||
      kb.embedding_config?.colpali_model !== values.embedding_config?.colpali_model ||
      kb.embedding_config?.retrieval_mode !== values.embedding_config?.retrieval_mode ||
      kb.embedding_config?.sparse_model !== values.embedding_config?.sparse_model;

    const parsingChanged =
      kb.default_parsing_config?.provider !== values.default_parsing_config?.provider ||
      JSON.stringify(normalizeExtensions(kb.default_parsing_config?.extension_providers)) !==
        JSON.stringify(normalizeExtensions(values.default_parsing_config?.extension_providers));

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
      defaultApplyMode = 'FORCE_ALL'; // Forcing re-embedding is often necessary as collection hash changes
    } else if (parsingChanged) {
      computedLoad = 'high';
      defaultApplyMode = 'INHERITED_ONLY';
    } else if (chunkingChanged) {
      computedLoad = 'low';
      defaultApplyMode = 'INHERITED_ONLY';
    }

    dispatchSettings({
      type: 'prepareSave',
      pendingValues: values,
      loadType: computedLoad,
      applyMode: defaultApplyMode,
    });
  };

  const handleFinalSave = () => {
    if (!kb || !pendingValues) return;

    const body = {
      name: pendingValues.name,
      embedding_config: pendingValues.embedding_config,
      default_chunking_config: pendingValues.default_chunking_config,
      default_parsing_config: {
        ...pendingValues.default_parsing_config,
        extension_providers: normalizeExtensions(pendingValues.default_parsing_config?.extension_providers)
      },
      apply_mode: applyMode,
    };

    patchMutation.mutate({
      id: kb.id,
      body,
    });
  };

  const handlePrev = () => {
    dispatchSettings({ type: 'setStep', value: (prev) => prev - 1 });
  };

  const handleNext = async () => {
    try {
      const fieldsToValidate = CONFIG_STEP_FIELDS[currentStep];
      if (fieldsToValidate) {
        await form.validateFields(fieldsToValidate);
      }
      dispatchSettings({ type: 'setStep', value: (prev) => prev + 1 });
    } catch (errorInfo) {
      console.warn('Form validation failed:', errorInfo);
    }
  };

  return (
    <>
      <Modal
        title={
          <span className="font-outfit" style={{ fontSize: '18px', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Settings size={20} className="text-primary" />
            Knowledge Base Settings: <span style={{ color: 'var(--accent-gradient)' }}>{kb?.name}</span>
          </span>
        }
        open={visible && !confirmVisible}
        onCancel={onClose}
        width={680}
        footer={[
          <Button key="cancel" onClick={onClose}>
            Cancel
          </Button>,
          currentStep > 0 && (
            <Button key="prev" onClick={handlePrev}>
              Previous
            </Button>
          ),
          currentStep < 2 && (
            <Button key="next" type="primary" onClick={handleNext}>
              Next
            </Button>
          ),
          currentStep === 2 && (
            <Button key="submit" type="primary" onClick={() => form.submit()} loading={patchMutation.isPending}>
              Apply Changes
            </Button>
          ),
        ].filter(Boolean)}
      >
        <Steps
          current={currentStep}
          size="small"
          style={{ marginBottom: '24px', marginTop: '16px' }}
          items={[
            { title: 'General & Parsing' },
            { title: 'Chunking Strategy' },
            { title: 'Vector Database' }
          ]}
        />
        <Form
          form={form}
          layout="vertical"
          onFinish={handlePreSave}
          style={{ marginTop: '16px' }}
        >
          {/* Step 0: General & Parsing */}
          <div style={{ display: currentStep === 0 ? 'block' : 'none' }}>
            <Paragraph type="secondary">
              Configure the default parsing settings used to read uploaded files. Altering parser configurations on existing documents requires re-parsing them (High Load).
            </Paragraph>
            <Form.Item
              name="name"
              label="Knowledge Base Name"
              rules={[{ required: true, message: 'Please enter a name' }]}
            >
              <Input placeholder="e.g. legal_documents" />
            </Form.Item>

            <Form.Item
              name={['default_parsing_config', 'provider']}
              label="Default Parsing Provider"
              rules={[{ required: true }]}
            >
              <Select
                style={{ width: '200px' }}
                loading={configLoading}
                options={parserProviders.map((provider) => ({
                  value: provider,
                  label: PARSER_LABELS[provider] || (provider.charAt(0).toUpperCase() + provider.slice(1))
                }))}
              />
            </Form.Item>

            <div style={{ marginTop: '20px' }}>
              <Button
                type="link"
                onClick={() => dispatchSettings({ type: 'setShowParserOverrides', value: !showParserOverrides })}
                style={{ padding: 0, display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600, fontSize: '13px', marginBottom: '12px' }}
              >
                {showParserOverrides ? 'Hide Extension-Specific Parser Overrides' : 'Show Extension-Specific Parser Overrides'}
              </Button>
              {showParserOverrides && (
                <div>
                  <Text strong className="font-outfit" style={{ display: 'block', marginBottom: '8px' }}>
                    Extension-Specific Overrides
                  </Text>
                  <Paragraph type="secondary" style={{ fontSize: '12px', marginBottom: '16px' }}>
                    Optionally override the default parser for specific file types.
                  </Paragraph>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                    {['.pdf', '.docx', '.txt', '.html', '.md'].map((ext) => (
                      <Form.Item
                        key={ext}
                        name={['default_parsing_config', 'extension_providers', ext]}
                        label={`Files ending in ${ext}`}
                        style={{ marginBottom: '12px' }}
                      >
                        <Select
                          placeholder="Use Default Provider"
                          allowClear
                          loading={configLoading}
                          options={parserProviders.map((provider) => ({
                            value: provider,
                            label: PARSER_LABELS[provider] || (provider.charAt(0).toUpperCase() + provider.slice(1))
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
            <Paragraph type="secondary">
              Determine how parsed documents are split into manageable chunks for semantic indexing. Modifying chunking settings only (Low Load) is computationally fast since parsing is cached.
            </Paragraph>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <Form.Item
                name={['default_chunking_config', 'chunk_size']}
                label="Chunk Size (Characters)"
                rules={[{ required: true }]}
              >
                <InputNumber style={{ width: '100%' }} min={100} max={10000} />
              </Form.Item>

              <Form.Item
                name={['default_chunking_config', 'chunk_overlap']}
                label="Chunk Overlap (Characters)"
                rules={[{ required: true }]}
              >
                <InputNumber style={{ width: '100%' }} min={0} max={2000} />
              </Form.Item>

              <Form.Item
                name={['default_chunking_config', 'merge_max_chars']}
                label="Merge Max Characters"
                rules={[{ required: true }]}
              >
                <InputNumber style={{ width: '100%' }} min={100} max={20000} />
              </Form.Item>

              <Form.Item
                name={['default_chunking_config', 'breadcrumb_depth']}
                label="Breadcrumb Prefix Depth"
                rules={[{ required: true }]}
              >
                <InputNumber style={{ width: '100%' }} min={0} max={10} />
              </Form.Item>
            </div>

            <Form.Item
              name={['default_chunking_config', 'breadcrumb_separator']}
              label="Breadcrumb Separator"
              rules={[{ required: true }]}
            >
              <Input style={{ width: '120px' }} />
            </Form.Item>

            <Form.Item
              name={['default_chunking_config', 'include_root_breadcrumb']}
              label="Include Root Breadcrumb"
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
          </div>

          {/* Step 2: Vector Database */}
          <div style={{ display: currentStep === 2 ? 'block' : 'none' }}>
            <Alert
              title="Vector Database Physical Indexing"
              description="Embedding configurations establish a physical collection inside Qdrant. Modifying these values requires all documents to be re-embedded."
              type="warning"
              showIcon
              style={{ marginBottom: '20px' }}
            />
            
            <Form.Item
              name={['embedding_config', 'model']}
              label="Embedding Model"
              rules={[{ required: true, message: 'Please select or enter an embedding model' }]}
              tooltip="Must match a LiteLLM embedding model configured on your proxy backend."
            >
              <Select
                loading={configLoading}
                options={embeddingModels.map((model) => ({
                  value: model,
                  label: `${model} ${model === 'text-embedding-3-small' ? '(Default)' : ''}`
                }))}
              />
            </Form.Item>

            <Form.Item
              name={['embedding_config', 'use_colpali']}
              label="Use ColPali (Vision RAG)"
              valuePropName="checked"
              tooltip="Enable ColPali to use multi-vector vision representation. This processes document pages as images."
            >
              <Switch />
            </Form.Item>

            <Form.Item noStyle shouldUpdate={(prevValues, currentValues) => prevValues.embedding_config?.use_colpali !== currentValues.embedding_config?.use_colpali}>
              {({ getFieldValue }) => {
                const useColpali = getFieldValue(['embedding_config', 'use_colpali']);
                if (useColpali) {
                  return (
                    <Form.Item
                      name={['embedding_config', 'colpali_model']}
                      label="ColPali Model"
                      rules={[{ required: true, message: 'Please select a ColPali model' }]}
                    >
                      <Select
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

            <Form.Item
              name={['embedding_config', 'retrieval_mode']}
              label="Retrieval Mode"
              rules={[{ required: true }]}
              tooltip="Retrieval mode for knowledge base search (e.g. dense, keyword-based sparse, or combined hybrid)."
            >
              <Radio.Group optionType="button" buttonStyle="solid">
                <Radio.Button value="dense">Dense</Radio.Button>
                <Radio.Button value="sparse">Sparse (Keyword)</Radio.Button>
                <Radio.Button value="hybrid">Hybrid (Dense + Sparse)</Radio.Button>
              </Radio.Group>
            </Form.Item>

            <Form.Item noStyle shouldUpdate={(prevValues, currentValues) => prevValues.embedding_config?.retrieval_mode !== currentValues.embedding_config?.retrieval_mode}>
              {({ getFieldValue }) => {
                const retrievalMode = getFieldValue(['embedding_config', 'retrieval_mode']);
                if (retrievalMode === 'sparse' || retrievalMode === 'hybrid') {
                  return (
                    <Form.Item
                      name={['embedding_config', 'sparse_model']}
                      label="Sparse Embedding Model"
                      rules={[{ required: true, message: 'Please select a sparse model' }]}
                      tooltip="Model used for sparse retrieval (keyword search)."
                    >
                      <Select
                        placeholder="Select sparse model"
                        options={
                          sparseEmbeddingModels && sparseEmbeddingModels.length > 0
                            ? sparseEmbeddingModels.map((model) => ({
                                value: model,
                                label: model === 'en-bm25'
                                  ? 'English BM25 (en-bm25)'
                                  : model === 'ko-kiwi-bm25'
                                  ? 'Korean Kiwi BM25 (ko-kiwi-bm25)'
                                  : model
                              }))
                            : [
                                { value: 'en-bm25', label: 'English BM25 (en-bm25)' },
                                { value: 'ko-kiwi-bm25', label: 'Korean Kiwi BM25 (ko-kiwi-bm25)' }
                              ]
                        }
                      />
                    </Form.Item>
                  );
                }
                return null;
              }}
            </Form.Item>

            <Form.Item
              name={['embedding_config', 'distance']}
              label="Distance Metric"
              rules={[{ required: true }]}
            >
              <Radio.Group optionType="button" buttonStyle="solid">
                <Radio.Button value="cosine">Cosine Similarity</Radio.Button>
                <Radio.Button value="dot">Dot Product</Radio.Button>
                <Radio.Button value="euclid">Euclidean Distance</Radio.Button>
              </Radio.Group>
            </Form.Item>
          </div>
        </Form>
      </Modal>

      {/* Confirmation Step / Sub-Modal for choosing Apply Strategy */}
      <Modal
        title={
          <span className="font-outfit" style={{ fontSize: '16px', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Info size={18} className="text-warning" />
            Apply Settings Strategy
          </span>
        }
        open={confirmVisible}
        onCancel={() => dispatchSettings({ type: 'setConfirmVisible', value: false })}
        width={500}
        onOk={handleFinalSave}
        confirmLoading={patchMutation.isPending}
        okText="Confirm & Process"
        cancelText="Back to Edit"
      >
        <Space orientation="vertical" size="middle" style={{ width: '100%', marginTop: '12px' }}>
          {loadType === 'reembed' && (
            <Alert
              title="Re-Embedding Required"
              description="You changed embedding model/distance settings. All existing documents in this knowledge base must be re-embedded to match the new vector structure."
              type="error"
              showIcon
            />
          )}

          {loadType === 'high' && (
            <Alert
              title="High Load Processing Detected"
              description="Parsing configurations changed. Re-parsing PDF files runs heavy layout extraction and OCR, which will take time to process."
              type="warning"
              showIcon
            />
          )}

          {loadType === 'low' && (
            <Alert
              title="Low Load Processing Detected"
              description="Only chunking configs changed. Reprocessing will bypass parsing and execute rapidly using existing cached layouts."
              type="success"
              showIcon
            />
          )}

          <div>
            <Text strong className="font-outfit" style={{ display: 'block', marginBottom: '8px' }}>
              Choose how to apply this config update to existing documents:
            </Text>
            <Radio.Group
              value={applyMode}
              onChange={(e) => dispatchSettings({ type: 'setApplyMode', value: e.target.value })}
              style={{ width: '100%' }}
            >
              <Space orientation="vertical" style={{ width: '100%' }}>
                <Radio
                  value="NEW_ONLY"
                  disabled={loadType === 'reembed'}
                  style={{ display: 'flex', alignItems: 'start' }}
                >
                  <div>
                    <Text strong>New Documents Only</Text>
                    <Paragraph type="secondary" style={{ margin: 0, fontSize: '12px' }}>
                      Keep all existing documents untouched. Only new documents uploaded from now on will inherit these settings.
                    </Paragraph>
                  </div>
                </Radio>
                <Radio value="INHERITED_ONLY" style={{ display: 'flex', alignItems: 'start' }}>
                  <div>
                    <Text strong>Reprocess Inherited Documents</Text>
                    <Paragraph type="secondary" style={{ margin: 0, fontSize: '12px' }}>
                      Only reprocess documents that inherit from the KB (i.e. documents without custom overrides).
                    </Paragraph>
                  </div>
                </Radio>
                <Radio value="FORCE_ALL" style={{ display: 'flex', alignItems: 'start' }}>
                  <div>
                    <Text strong>Force Apply to All Documents</Text>
                    <Paragraph type="secondary" style={{ margin: 0, fontSize: '12px' }}>
                      Reset any custom overrides on all documents and force-reprocess all files in the knowledge base.
                    </Paragraph>
                  </div>
                </Radio>
              </Space>
            </Radio.Group>
          </div>
        </Space>
      </Modal>
    </>
  );
};
