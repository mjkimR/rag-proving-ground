import React from 'react';
import {
  Card, Typography, Steps, Form, Input, InputNumber, Select,
  Button, Row, Col, Switch, Radio, Alert
} from 'antd';
import type { FormInstance } from 'antd';
import { PARSER_LABELS } from '@/views/DocumentWorkbench/types';

const { Title, Paragraph, Text } = Typography;

interface StrategySettingsFormProps {
  settingsForm: FormInstance;
  currentStep: number;
  showParserOverrides: boolean;
  setShowParserOverrides: (show: boolean) => void;
  parserProviders: string[];
  embeddingModels: string[];
  sparseEmbeddingModels?: string[];
  configLoading: boolean;
  patchKbMutationPending: boolean;
  handlePreSaveConfig: (values: Record<string, unknown>) => void;
  handlePrevConfig: () => void;
  handleNextConfig: () => void;
}

export const StrategySettingsForm: React.FC<StrategySettingsFormProps> = ({
  settingsForm,
  currentStep,
  showParserOverrides,
  setShowParserOverrides,
  parserProviders,
  embeddingModels,
  sparseEmbeddingModels,
  configLoading,
  patchKbMutationPending,
  handlePreSaveConfig,
  handlePrevConfig,
  handleNextConfig,
}) => {
  return (
    <Card variant="borderless" className="glass-card" style={{ borderRadius: '16px' }}>
      <div style={{ marginBottom: '20px' }}>
        <Title level={4} style={{ margin: 0, fontWeight: 700 }}>Strategy Configurations</Title>
        <Paragraph type="secondary" style={{ margin: '4px 0 0 0' }}>
          Adjust parsing mechanisms, boundary semantic chunks, and vector embedding sizes. Updates propagate to documents based on your selected strategy.
        </Paragraph>
      </div>

      <Steps
        current={currentStep}
        size="small"
        style={{ marginBottom: '24px', maxWidth: '780px' }}
        items={[
          { title: 'General & Parsing' },
          { title: 'Chunking Strategy' },
          { title: 'Vector Database' }
        ]}
      />

      <Form
        form={settingsForm}
        layout="vertical"
        onFinish={handlePreSaveConfig}
        style={{ maxWidth: '780px' }}
      >
        {/* Step 0: General & Parsing */}
        <div style={{ display: currentStep === 0 ? 'block' : 'none' }}>
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
            label="Default Parsing Provider"
            rules={[{ required: true }]}
          >
            <Select
              size="large"
              style={{ width: '260px' }}
              loading={configLoading}
              options={parserProviders.map((provider) => ({
                value: provider,
                label: PARSER_LABELS[provider] || (provider.charAt(0).toUpperCase() + provider.slice(1))
              }))}
            />
          </Form.Item>

          <div style={{ marginTop: '20px', marginBottom: '24px' }}>
            <Button
              type="link"
              onClick={() => setShowParserOverrides(!showParserOverrides)}
              style={{ padding: 0, display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600, fontSize: '13px', marginBottom: '12px' }}
            >
              {showParserOverrides ? 'Hide Extension-Specific Parser Overrides' : 'Show Extension-Specific Parser Overrides'}
            </Button>
            {showParserOverrides && (
              <div>
                <Text strong style={{ display: 'block', marginBottom: '8px' }}>
                  Extension-Specific Overrides
                </Text>
                <Paragraph type="secondary" style={{ fontSize: '13px', marginBottom: '16px' }}>
                  Optionally override the default parser for specific file types.
                </Paragraph>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', maxWidth: '600px' }}>
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
          <Title level={5} style={{ margin: '0 0 12px 0', borderBottom: '1px solid var(--border-color)', paddingBottom: '6px' }}>Chunking & Boundary Splitting Defaults</Title>
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
        </div>

        {/* Step 2: Vector Database */}
        <div style={{ display: currentStep === 2 ? 'block' : 'none' }}>
          <Title level={5} style={{ margin: '0 0 12px 0', borderBottom: '1px solid var(--border-color)', paddingBottom: '6px' }}>Vector Database Physical Indexing</Title>
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

          <Row gutter={20}>
            <Col span={12}>
              <Form.Item
                name={['embedding_config', 'use_colpali']}
                label="Use ColPali (Vision RAG)"
                valuePropName="checked"
                tooltip="Enable ColPali to use multi-vector vision representation. This processes document pages as images."
              >
                <Switch />
              </Form.Item>
            </Col>
            <Col span={12}>
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

          <Row gutter={20}>
            <Col span={12}>
              <Form.Item
                name={['embedding_config', 'retrieval_mode']}
                label="Retrieval Mode"
                rules={[{ required: true }]}
                tooltip="Retrieval mode for knowledge base search (e.g. dense, keyword-based sparse, or combined hybrid)."
              >
                <Radio.Group size="large" optionType="button" buttonStyle="solid" style={{ width: '100%' }}>
                  <Radio.Button value="dense" style={{ width: '33.33%', textAlign: 'center' }}>Dense</Radio.Button>
                  <Radio.Button value="sparse" style={{ width: '33.33%', textAlign: 'center' }}>Sparse</Radio.Button>
                  <Radio.Button value="hybrid" style={{ width: '33.33%', textAlign: 'center' }}>Hybrid</Radio.Button>
                </Radio.Group>
              </Form.Item>
            </Col>
            <Col span={12}>
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
                          size="large"
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
            </Col>
          </Row>
        </div>

        <div style={{ marginTop: '30px', display: 'flex', gap: '12px' }}>
          {currentStep > 0 && (
            <Button size="large" onClick={handlePrevConfig} style={{ borderRadius: '10px' }}>
              Previous
            </Button>
          )}
          {currentStep < 2 ? (
            <Button type="primary" size="large" onClick={handleNextConfig} style={{ borderRadius: '10px' }}>
              Next
            </Button>
          ) : (
            <Button
              type="primary"
              size="large"
              onClick={() => settingsForm.submit()}
              loading={patchKbMutationPending}
              style={{ padding: '0 40px', height: '46px', borderRadius: '10px', fontWeight: 600 }}
            >
              Save Strategy Configuration
            </Button>
          )}
        </div>
      </Form>
    </Card>
  );
};
