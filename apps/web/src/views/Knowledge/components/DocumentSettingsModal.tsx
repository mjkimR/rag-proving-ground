import React, { useEffect, useState } from 'react';
import {
  Modal, Form, Select, Input, InputNumber, Switch, Button, Checkbox, Space, Typography, Tag, Divider, Alert
} from 'antd';
import { FileText, RotateCw, Settings2 } from 'lucide-react';
import { useMutation } from '@tanstack/react-query';
import {
  patchKnowledgeBaseDocumentApiV1KnowledgeBaseDocumentsKnowledgeBaseDocumentIdPatch,
  reprocessKnowledgeBaseDocumentApiV1KnowledgeBaseDocumentsKnowledgeBaseDocumentIdReprocessPost
} from '@/generated/api/sdk.gen';
import type {
  KnowledgeBaseDocumentRead, ChunkingConfig, KnowledgeParsingConfig, KnowledgeBaseDocumentReprocessMode
} from '@/generated/api/types.gen';

const { Text } = Typography;

interface DocumentSettingsModalProps {
  visible: boolean;
  onClose: () => void;
  document: KnowledgeBaseDocumentRead | null;
  kbDefaultParsingConfig?: KnowledgeParsingConfig | null;
  kbDefaultChunkingConfig?: ChunkingConfig | null;
  onSuccess: () => void;
}

export const DocumentSettingsModal: React.FC<DocumentSettingsModalProps> = ({
  visible,
  onClose,
  document,
  kbDefaultParsingConfig,
  kbDefaultChunkingConfig,
  onSuccess
}) => {
  const [form] = Form.useForm();
  const [overrideParsing, setOverrideParsing] = useState(false);
  const [overrideChunking, setOverrideChunking] = useState(false);
  const [reprocessMode, setReprocessMode] = useState<KnowledgeBaseDocumentReprocessMode>('AUTO');

  useEffect(() => {
    if (visible && document) {
      const hasParsingOverride = !!document.parsing_config;
      const hasChunkingOverride = !!document.chunking_config;

      setOverrideParsing(hasParsingOverride);
      setOverrideChunking(hasChunkingOverride);

      form.setFieldsValue({
        parsing_config: {
          provider: document.parsing_config?.provider || kbDefaultParsingConfig?.provider || 'docling',
        },
        chunking_config: {
          chunk_size: document.chunking_config?.chunk_size ?? kbDefaultChunkingConfig?.chunk_size ?? 1024,
          chunk_overlap: document.chunking_config?.chunk_overlap ?? kbDefaultChunkingConfig?.chunk_overlap ?? 200,
          merge_max_chars: document.chunking_config?.merge_max_chars ?? kbDefaultChunkingConfig?.merge_max_chars ?? 4096,
          breadcrumb_depth: document.chunking_config?.breadcrumb_depth ?? kbDefaultChunkingConfig?.breadcrumb_depth ?? 2,
          include_root_breadcrumb: document.chunking_config?.include_root_breadcrumb ?? kbDefaultChunkingConfig?.include_root_breadcrumb ?? true,
          breadcrumb_separator: document.chunking_config?.breadcrumb_separator || kbDefaultChunkingConfig?.breadcrumb_separator || ' > ',
        }
      });
    }
  }, [visible, document, kbDefaultParsingConfig, kbDefaultChunkingConfig, form]);

  // Patch mutation
  const patchMutation = useMutation({
    mutationFn: (payload: { id: string; body: any }) => {
      return patchKnowledgeBaseDocumentApiV1KnowledgeBaseDocumentsKnowledgeBaseDocumentIdPatch({
        path: { knowledge_base_document_id: payload.id },
        body: payload.body,
        throwOnError: true,
      });
    },
    onSuccess: () => {
      onSuccess();
      onClose();
    },
    onError: (e) => {
      console.error('Failed to update document settings:', e);
      Modal.error({
        title: 'Update Failed',
        content: e instanceof Error ? e.message : 'Please check your connection and settings.',
      });
    }
  });

  // Reprocess mutation
  const reprocessMutation = useMutation({
    mutationFn: (payload: { id: string; mode: KnowledgeBaseDocumentReprocessMode }) => {
      return reprocessKnowledgeBaseDocumentApiV1KnowledgeBaseDocumentsKnowledgeBaseDocumentIdReprocessPost({
        path: { knowledge_base_document_id: payload.id },
        body: { mode: payload.mode },
        throwOnError: true,
      });
    },
    onSuccess: () => {
      Modal.success({
        title: 'Reprocessing Started',
        content: `Document re-ingestion has been triggered in the background using ${reprocessMode} mode.`,
      });
      onSuccess();
      onClose();
    },
    onError: (e) => {
      console.error('Failed to trigger reprocessing:', e);
      Modal.error({
        title: 'Reprocess Failed',
        content: e instanceof Error ? e.message : 'Failed to trigger reprocessing for this document.',
      });
    }
  });

  const handleSave = (values: any) => {
    if (!document) return;

    // Resolve what needs to be saved
    const body = {
      parsing_config: overrideParsing ? values.parsing_config : null,
      chunking_config: overrideChunking ? values.chunking_config : null,
    };

    patchMutation.mutate({
      id: document.id,
      body,
    });
  };

  const handleReprocess = () => {
    if (!document) return;
    reprocessMutation.mutate({
      id: document.id,
      mode: reprocessMode,
    });
  };

  const handleResetToDefault = () => {
    if (!document) return;
    Modal.confirm({
      title: 'Reset to Defaults',
      content: 'Are you sure you want to discard all custom overrides for this document? It will re-inherit all configurations from the Knowledge Base.',
      okText: 'Yes, Reset',
      onOk: () => {
        patchMutation.mutate({
          id: document.id,
          body: {
            parsing_config: null,
            chunking_config: null,
          }
        });
      }
    });
  };

  return (
    <Modal
      title={
        <span className="font-outfit" style={{ fontSize: '18px', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Settings2 size={20} className="text-primary" />
          Document Configuration
        </span>
      }
      open={visible}
      onCancel={onClose}
      width={600}
      footer={[
        <Button key="cancel" onClick={onClose}>
          Cancel
        </Button>,
        <Button
          key="reset"
          danger
          onClick={handleResetToDefault}
          disabled={!document?.parsing_config && !document?.chunking_config}
        >
          Reset to Defaults
        </Button>,
        <Button
          key="save"
          type="primary"
          onClick={() => form.submit()}
          loading={patchMutation.isPending}
        >
          Save Configuration
        </Button>
      ]}
    >
      {document && (
        <div style={{ marginTop: '16px' }}>
          {/* Doc Header Details */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'var(--bg-app)', padding: '12px 16px', borderRadius: '8px', marginBottom: '20px' }}>
            <FileText size={24} color="var(--text-secondary)" />
            <div style={{ flex: 1, minWidth: 0 }}>
              <Text strong style={{ display: 'block', wordBreak: 'break-all' }}>{document.name}</Text>
              <Text type="secondary" style={{ fontSize: '12px' }}>
                Status: <Tag color={document.status === 'COMPLETED' ? 'success' : document.status === 'FAILED' ? 'error' : 'processing'}>{document.status}</Tag>
              </Text>
            </div>
          </div>

          <Form form={form} layout="vertical" onFinish={handleSave}>
            {/* 1. Parsing Configuration Section */}
            <div style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <Text strong style={{ fontSize: '14px' }}>Parsing Strategy</Text>
                <Checkbox
                  checked={overrideParsing}
                  onChange={(e) => setOverrideParsing(e.target.checked)}
                >
                  Override default provider
                </Checkbox>
              </div>

              {overrideParsing ? (
                <div style={{ padding: '12px 16px', border: '1px solid var(--border-color)', borderRadius: '8px', background: '#fff' }}>
                  <Form.Item
                    name={['parsing_config', 'provider']}
                    label="Override Provider"
                    rules={[{ required: true }]}
                    style={{ marginBottom: 0 }}
                  >
                    <Select>
                      <Select.Option value="docling">Docling</Select.Option>
                      <Select.Option value="native_text">Native Text</Select.Option>
                      <Select.Option value="marker">Marker</Select.Option>
                    </Select>

                  </Form.Item>
                </div>
              ) : (
                <div style={{ padding: '8px 12px', background: 'rgba(0,0,0,0.02)', borderRadius: '6px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                  Inheriting Parsing Provider: <strong style={{ color: 'var(--text-primary)' }}>{kbDefaultParsingConfig?.provider || 'docling'}</strong>
                </div>
              )}
            </div>

            {/* 2. Chunking Configuration Section */}
            <div style={{ marginBottom: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <Text strong style={{ fontSize: '14px' }}>Chunking Strategy</Text>
                <Checkbox
                  checked={overrideChunking}
                  onChange={(e) => setOverrideChunking(e.target.checked)}
                >
                  Override default chunking
                </Checkbox>
              </div>

              {overrideChunking ? (
                <div style={{ padding: '16px', border: '1px solid var(--border-color)', borderRadius: '8px', background: '#fff' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                    <Form.Item
                      name={['chunking_config', 'chunk_size']}
                      label="Chunk Size"
                      rules={[{ required: true }]}
                    >
                      <InputNumber style={{ width: '100%' }} min={100} />
                    </Form.Item>

                    <Form.Item
                      name={['chunking_config', 'chunk_overlap']}
                      label="Chunk Overlap"
                      rules={[{ required: true }]}
                    >
                      <InputNumber style={{ width: '100%' }} min={0} />
                    </Form.Item>

                    <Form.Item
                      name={['chunking_config', 'merge_max_chars']}
                      label="Merge Max Characters"
                      rules={[{ required: true }]}
                    >
                      <InputNumber style={{ width: '100%' }} min={100} />
                    </Form.Item>

                    <Form.Item
                      name={['chunking_config', 'breadcrumb_depth']}
                      label="Breadcrumb Depth"
                      rules={[{ required: true }]}
                    >
                      <InputNumber style={{ width: '100%' }} min={0} />
                    </Form.Item>
                  </div>

                  <Form.Item
                    name={['chunking_config', 'breadcrumb_separator']}
                    label="Breadcrumb Separator"
                    rules={[{ required: true }]}
                  >
                    <Input style={{ width: '120px' }} />
                  </Form.Item>

                  <Form.Item
                    name={['chunking_config', 'include_root_breadcrumb']}
                    label="Include Root Breadcrumb"
                    valuePropName="checked"
                    style={{ marginBottom: 0 }}
                  >
                    <Switch />
                  </Form.Item>
                </div>
              ) : (
                <div style={{ padding: '12px', background: 'rgba(0,0,0,0.02)', borderRadius: '6px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <div>Inheriting default Chunking settings from KB:</div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', fontWeight: 600, color: 'var(--text-primary)' }}>
                      <span>Size: {kbDefaultChunkingConfig?.chunk_size ?? 1024} chars</span>
                      <span>Overlap: {kbDefaultChunkingConfig?.chunk_overlap ?? 200} chars</span>
                      <span>Max Merge: {kbDefaultChunkingConfig?.merge_max_chars ?? 4096}</span>
                      <span>Breadcrumb Depth: {kbDefaultChunkingConfig?.breadcrumb_depth ?? 2}</span>
                    </div>
                  </Space>
                </div>
              )}
            </div>
          </Form>

          {/* 3. Reprocessing Trigger Section */}
          <Divider orientation={"left" as any} style={{ margin: '12px 0' }}>
            <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Reprocessing Actions</span>
          </Divider>

          <Alert
            title="Need to apply config updates immediately?"
            description="If you have already overridden the config or changed default configurations, you can trigger reprocessing for this document below."
            type="info"
            showIcon
            style={{ marginBottom: '16px' }}
          />

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'rgba(0,0,0,0.01)', border: '1px dashed var(--border-color)', padding: '12px 16px', borderRadius: '8px' }}>
            <Space direction="vertical" size={2}>
              <Text strong style={{ fontSize: '13px' }}>Manual Reprocess Mode</Text>
              <Select
                value={reprocessMode}
                onChange={setReprocessMode}
                style={{ width: 140 }}
                className="font-outfit"
              >
                <Select.Option value="AUTO">Auto Detect</Select.Option>
                <Select.Option value="REPARSE">Re-parse & Re-index</Select.Option>
                <Select.Option value="RECHUNK">Re-chunk Only</Select.Option>
                <Select.Option value="REEMBED">Re-embed Only</Select.Option>
              </Select>
            </Space>

            <Button
              type="primary"
              icon={<RotateCw size={14} />}
              onClick={handleReprocess}
              loading={reprocessMutation.isPending}
            >
              Reprocess Document
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
};
