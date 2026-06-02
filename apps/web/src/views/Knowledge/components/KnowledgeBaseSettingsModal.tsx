import React, { useEffect, useState } from 'react';
import {
  Modal, Form, Input, Select, InputNumber, Switch, Tabs, Radio, Alert, Space, Typography
} from 'antd';
import { Settings, Info } from 'lucide-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { patchKnowledgeBaseApiV1KnowledgeBasesKnowledgeBaseIdPatch } from '@/generated/api/sdk.gen';
import type { KnowledgeBaseRead, KnowledgeBaseConfigApplyMode } from '@/generated/api/types.gen';

const { Text, Paragraph } = Typography;

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
  const [form] = Form.useForm();
  const [activeTab, setActiveTab] = useState('embedding');
  const [confirmVisible, setConfirmVisible] = useState(false);
  const [pendingValues, setPendingValues] = useState<any>(null);
  const [loadType, setLoadType] = useState<'low' | 'high' | 'reembed'>('low');
  const [applyMode, setApplyMode] = useState<KnowledgeBaseConfigApplyMode>('INHERITED_ONLY');

  useEffect(() => {
    if (visible && kb) {
      form.setFieldsValue({
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
      setActiveTab('embedding');
      setConfirmVisible(false);
      setPendingValues(null);
    }
  }, [visible, kb, form]);

  const patchMutation = useMutation({
    mutationFn: (payload: { id: string; body: any }) => {
      return patchKnowledgeBaseApiV1KnowledgeBasesKnowledgeBaseIdPatch({
        path: { knowledge_base_id: payload.id },
        body: payload.body,
        throwOnError: true,
      });
    },
    onSuccess: (response: any) => {
      if (response.data) {
        onSuccess(response.data);
      }
      queryClient.invalidateQueries({ queryKey: ['kbList'] });
      queryClient.invalidateQueries({ queryKey: ['fileList', kb?.id] });
      setConfirmVisible(false);
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

  const handlePreSave = (values: any) => {
    if (!kb) return;

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
      defaultApplyMode = 'FORCE_ALL'; // Forcing re-embedding is often necessary as collection hash changes
    } else if (parsingChanged) {
      computedLoad = 'high';
      defaultApplyMode = 'INHERITED_ONLY';
    } else if (chunkingChanged) {
      computedLoad = 'low';
      defaultApplyMode = 'INHERITED_ONLY';
    }

    setLoadType(computedLoad);
    setApplyMode(defaultApplyMode);
    setPendingValues(values);
    setConfirmVisible(true);
  };

  const handleFinalSave = () => {
    if (!kb || !pendingValues) return;

    const body = {
      name: pendingValues.name,
      embedding_config: pendingValues.embedding_config,
      default_chunking_config: pendingValues.default_chunking_config,
      default_parsing_config: pendingValues.default_parsing_config,
      apply_mode: applyMode,
    };

    patchMutation.mutate({
      id: kb.id,
      body,
    });
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
        okText="Apply Changes"
        onOk={() => form.submit()}
        confirmLoading={patchMutation.isPending}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handlePreSave}
          style={{ marginTop: '16px' }}
        >
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            className="font-outfit"
            items={[
              {
                key: 'embedding',
                label: 'Embedding Settings',
                children: (
                  <div style={{ padding: '8px 4px' }}>
                    <Alert
                      title="Vector Database Physical Indexing"
                      description="Embedding configurations establish a physical collection inside Qdrant. Modifying these values requires all documents to be re-embedded."
                      type="warning"
                      showIcon
                      style={{ marginBottom: '20px' }}
                    />
                    <Form.Item
                      name="name"
                      label="Knowledge Base Name"
                      rules={[{ required: true, message: 'Please enter a name' }]}
                    >
                      <Input placeholder="e.g. legal_documents" />
                    </Form.Item>

                    <Form.Item
                      name={['embedding_config', 'model']}
                      label="Embedding Model"
                      rules={[{ required: true, message: 'Please select or enter an embedding model' }]}
                      tooltip="Must match a LiteLLM embedding model configured on your proxy backend."
                    >
                      <Select>
                        <Select.Option value="text-embedding-3-small">text-embedding-3-small (Default)</Select.Option>
                        <Select.Option value="text-embedding-3-large">text-embedding-3-large</Select.Option>
                        <Select.Option value="text-embedding-ada-002">text-embedding-ada-002</Select.Option>
                        <Select.Option value="bge-large-en-v1.5">bge-large-en-v1.5</Select.Option>
                      </Select>
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
                )
              },
              {
                key: 'parsing',
                label: 'Default Parsing Config',
                children: (
                  <div style={{ padding: '8px 4px' }}>
                    <Paragraph type="secondary">
                      Specify the default parsing framework used to read files. Changes in parsing are resource-heavy (High Load) because documents need to be re-read and analyzed.
                    </Paragraph>
                    <Form.Item
                      name={['default_parsing_config', 'provider']}
                      label="Parsing Provider"
                      rules={[{ required: true }]}
                    >
                      <Select style={{ width: '200px' }}>
                        <Select.Option value="docling">Docling (Recommended)</Select.Option>
                        <Select.Option value="marker">Marker</Select.Option>
                      </Select>
                    </Form.Item>
                  </div>
                )
              },
              {
                key: 'chunking',
                label: 'Default Chunking Config',
                children: (
                  <div style={{ padding: '8px 4px' }}>
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
                )
              }
            ]}
          />
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
        onCancel={() => setConfirmVisible(false)}
        width={500}
        onOk={handleFinalSave}
        confirmLoading={patchMutation.isPending}
        okText="Confirm & Process"
        cancelText="Back to Edit"
      >
        <Space direction="vertical" size="middle" style={{ width: '100%', marginTop: '12px' }}>
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
              onChange={(e) => setApplyMode(e.target.value)}
              style={{ width: '100%' }}
            >
              <Space direction="vertical" style={{ width: '100%' }}>
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
