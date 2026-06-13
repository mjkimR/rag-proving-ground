import React, { useMemo, useState } from 'react';
import { Alert, Button, Card, Col, Empty, Input, InputNumber, Row, Select, Space, Spin, Switch, Tag, Typography, message } from 'antd';
import { useMutation, useQuery } from '@tanstack/react-query';
import { GitMerge, Search, SlidersHorizontal } from 'lucide-react';
import {
  getKnowledgeBasesApiV1KnowledgeBasesGet,
  getProviderOptionsApiV1ProvidersOptionsGet,
  searchMultiKnowledgeBasesApiV1KnowledgeBasesSearchPost,
} from '@/generated/api/sdk.gen';
import type { KnowledgeBaseSearchResponse, RerankerConfig } from '@/generated/api/types.gen';
import { SearchResultCards } from '@/views/Knowledge/components/SearchResultCards';
import styles from './Playground.module.css';

const { Title, Text, Paragraph } = Typography;

export const Playground: React.FC = () => {
  const [selectedKbIds, setSelectedKbIds] = useState<string[]>([]);
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState<number>(5);
  const [candidateLimit, setCandidateLimit] = useState<number | null>(null);
  const [rerankerEnabled, setRerankerEnabled] = useState(false);
  const [selectedRerankerModel, setRerankerModel] = useState<string | undefined>(undefined);
  const [rerankerTopN, setRerankerTopN] = useState<number | null>(null);
  const [retrievalMode, setRetrievalMode] = useState<'dense' | 'sparse' | 'hybrid' | undefined>(undefined);
  const [sparseModelOverride, setSparseModelOverride] = useState<string | undefined>(undefined);

  const kbQuery = useQuery({
    queryKey: ['kbList'],
    queryFn: () => getKnowledgeBasesApiV1KnowledgeBasesGet({ throwOnError: true }),
  });

  const modelQuery = useQuery({
    queryKey: ['configOptions'],
    queryFn: () => getProviderOptionsApiV1ProvidersOptionsGet({ throwOnError: true }),
  });

  const knowledgeBases = useMemo(() => kbQuery.data?.data?.items || [], [kbQuery.data]);
  const rerankerModels = useMemo(() => modelQuery.data?.data?.reranker_models || [], [modelQuery.data]);
  const sparseEmbeddingModels = useMemo(() => modelQuery.data?.data?.sparse_embedding_models || [], [modelQuery.data]);
  const hasCatalogRerankerModels = rerankerModels.length > 0 && !rerankerModels.includes('no-model');
  const forcedReranker = selectedKbIds.length >= 2;
  const effectiveRerankerEnabled = forcedReranker || rerankerEnabled;

  const rerankerModel = selectedRerankerModel !== undefined
    ? selectedRerankerModel
    : (hasCatalogRerankerModels ? rerankerModels[0] : undefined);

  const kbOptions = useMemo(
    () =>
      knowledgeBases.map((kb) => ({
        label: `${kb.name} (${kb.status})`,
        value: kb.id,
      })),
    [knowledgeBases],
  );

  const searchMutation = useMutation({
    mutationFn: () => {
      const rerankerConfig: RerankerConfig | undefined = effectiveRerankerEnabled
        ? {
            model: rerankerModel?.trim() || undefined,
            top_n: rerankerTopN || undefined,
          }
        : undefined;

      return searchMultiKnowledgeBasesApiV1KnowledgeBasesSearchPost({
        body: {
          query,
          knowledge_base_ids: selectedKbIds,
          limit,
          candidate_limit: candidateLimit || undefined,
          reranker_config: rerankerConfig,
          retrieval_mode: retrievalMode,
          sparse_model: sparseModelOverride,
        },
        throwOnError: true,
      });
    },
    onSuccess: (response: { data: KnowledgeBaseSearchResponse }) => {
      message.success(`Search completed. Found ${response.data.results.length} chunks.`);
    },
    onError: (e) => {
      console.error('Failed to run multi-KB search:', e);
      message.error(e instanceof Error ? e.message : 'Multi-KB search failed.');
    },
  });

  const runSearch = () => {
    if (!query.trim()) {
      message.warning('Please enter a query string.');
      return;
    }
    if (!selectedKbIds.length) {
      message.warning('Select at least one Knowledge Base.');
      return;
    }
    searchMutation.mutate();
  };

  return (
    <div className={styles.container}>
      <div style={{ marginBottom: '24px' }}>
        <Space align="center" size={12}>
          <div className={styles.headerIcon}>
            <GitMerge size={20} color="#fff" />
          </div>
          <div>
            <Title level={2} style={{ margin: 0, fontWeight: 800 }}>
              Multi-KB Retrieval Playground
            </Title>
            <Paragraph type="secondary" style={{ margin: '4px 0 0 0' }}>
              Search one or more Knowledge Bases and inspect vector versus reranker scoring.
            </Paragraph>
          </div>
        </Space>
      </div>

      <Row gutter={[18, 18]}>
        <Col xs={24} xl={9}>
          <Space orientation="vertical" size={16} style={{ width: '100%' }}>
            <Card variant="borderless" className="glass-card" style={{ borderRadius: '16px' }}>
              <Title level={4} style={{ marginTop: 0 }}>
                Knowledge Bases
              </Title>
              <Select
                mode="multiple"
                size="large"
                placeholder="Select Knowledge Bases"
                loading={kbQuery.isLoading}
                options={kbOptions}
                value={selectedKbIds}
                onChange={setSelectedKbIds}
                style={{ width: '100%' }}
                showSearch={{
                  filterOption: (input, option) => (option?.label ?? '').toString().toLowerCase().includes(input.toLowerCase())
                }}
              />
              <div style={{ marginTop: '12px' }}>
                <Text type="secondary">
                  {selectedKbIds.length} selected. Two or more KBs force reranking before final ranking.
                </Text>
              </div>
            </Card>

            <Card variant="borderless" className="glass-card" style={{ borderRadius: '16px' }}>
              <Space align="center" className={styles.cardHeader}>
                <Space>
                  <SlidersHorizontal size={18} />
                  <Title level={4} style={{ margin: 0 }}>
                    Reranker
                  </Title>
                </Space>
                <Switch
                  checked={effectiveRerankerEnabled}
                  disabled={forcedReranker}
                  onChange={setRerankerEnabled}
                />
              </Space>

              {forcedReranker && (
                <Alert
                  showIcon
                  type="info"
                  title="Reranker is required for multi-KB search."
                  style={{ marginBottom: '14px' }}
                />
              )}

              <Space orientation="vertical" size={12} style={{ width: '100%' }}>
                <div>
                  <Text strong>Model</Text>
                  {hasCatalogRerankerModels ? (
                    <Select
                      showSearch
                      allowClear
                      size="large"
                      placeholder="Use default reranker or select model"
                      loading={modelQuery.isLoading}
                      options={rerankerModels.map((model) => ({ label: model, value: model }))}
                      value={rerankerModel}
                      onChange={setRerankerModel}
                      className={styles.fieldWrapper}
                    />
                  ) : (
                    <Input
                      size="large"
                      placeholder="Use default reranker or enter model name"
                      value={rerankerModel}
                      onChange={(event) => setRerankerModel(event.target.value || undefined)}
                      className={styles.fieldWrapper}
                    />
                  )}
                </div>
                <div>
                  <Text strong>Top N</Text>
                  <InputNumber
                    min={1}
                    max={100}
                    value={rerankerTopN}
                    onChange={(value) => setRerankerTopN(value)}
                    placeholder="Backend default"
                    className={styles.fieldWrapper}
                    size="large"
                  />
                </div>
              </Space>
            </Card>

            <Card variant="borderless" className="glass-card" style={{ borderRadius: '16px' }}>
              <Space align="center" className={styles.cardHeader}>
                <Space>
                  <SlidersHorizontal size={18} />
                  <Title level={4} style={{ margin: 0 }}>
                    Retrieval Overrides
                  </Title>
                </Space>
              </Space>

              <Space orientation="vertical" size={12} style={{ width: '100%' }}>
                <div>
                  <Text strong style={{ display: 'block', marginBottom: '6px' }}>Retrieval Mode</Text>
                  <Select
                    size="large"
                    placeholder="Use KB default mode"
                    allowClear
                    options={[
                      { value: 'dense', label: 'Dense Only' },
                      { value: 'sparse', label: 'Sparse Only' },
                      { value: 'hybrid', label: 'Hybrid (Dense + Sparse)' }
                    ]}
                    value={retrievalMode}
                    onChange={(value) => {
                      setRetrievalMode(value || undefined);
                      if (value !== 'sparse' && value !== 'hybrid') {
                        setSparseModelOverride(undefined);
                      }
                    }}
                    style={{ width: '100%' }}
                  />
                </div>

                {(retrievalMode === 'sparse' || retrievalMode === 'hybrid') && (
                  <div>
                    <Text strong style={{ display: 'block', marginBottom: '6px' }}>Sparse Model Override</Text>
                    <Select
                      size="large"
                      placeholder="Use KB default sparse model"
                      allowClear
                      loading={modelQuery.isLoading}
                      options={sparseEmbeddingModels.map((model) => ({
                        value: model,
                        label: model === 'en-bm25'
                          ? 'English BM25 (en-bm25)'
                          : model === 'ko-kiwi-bm25'
                          ? 'Korean Kiwi BM25 (ko-kiwi-bm25)'
                          : model
                      }))}
                      value={sparseModelOverride}
                      onChange={setSparseModelOverride}
                      style={{ width: '100%' }}
                    />
                  </div>
                )}
              </Space>
            </Card>
          </Space>
        </Col>

        <Col xs={24} xl={15}>
          <Card variant="borderless" className="glass-card" style={{ borderRadius: '16px', marginBottom: '18px' }}>
            <Title level={4} style={{ marginTop: 0 }}>
              Search Panel
            </Title>
            <Input.TextArea
              placeholder="Ask a question that should retrieve evidence from selected KBs..."
              rows={4}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onPressEnter={(e) => {
                if ((e.metaKey || e.ctrlKey) && !searchMutation.isPending) {
                  runSearch();
                }
              }}
            />
            <Row gutter={[12, 12]} style={{ marginTop: '14px' }}>
              <Col xs={24} md={8}>
                <Text strong>Limit</Text>
                <InputNumber
                  min={1}
                  max={100}
                  value={limit}
                  onChange={(value) => value && setLimit(value)}
                  style={{ width: '100%', marginTop: '6px' }}
                  size="large"
                />
              </Col>
              <Col xs={24} md={8}>
                <Text strong>Candidate Limit</Text>
                <InputNumber
                  min={1}
                  max={500}
                  value={candidateLimit}
                  onChange={(value) => setCandidateLimit(value)}
                  placeholder="Auto"
                  style={{ width: '100%', marginTop: '6px' }}
                  size="large"
                />
              </Col>
              <Col xs={24} md={8} style={{ display: 'flex', alignItems: 'end' }}>
                <Button
                  type="primary"
                  size="large"
                  icon={<Search size={18} />}
                  loading={searchMutation.isPending}
                  onClick={runSearch}
                  style={{ width: '100%', fontWeight: 700 }}
                >
                  Search
                </Button>
              </Col>
            </Row>
          </Card>

          <Card variant="borderless" className="glass-card" style={{ borderRadius: '16px' }}>
            <Space align="center" className={styles.cardHeader}>
              <div>
                <Title level={4} style={{ margin: 0 }}>
                  Results
                </Title>
                <Text type="secondary">Merged chunks show final, vector, and rerank scores separately.</Text>
              </div>
              <Tag color={effectiveRerankerEnabled ? 'processing' : 'default'}>
                {effectiveRerankerEnabled ? 'Rerank enabled' : 'Vector only'}
              </Tag>
            </Space>

            {searchMutation.isPending ? (
              <div className={styles.spinnerContainer}>
                <Spin size="large" description="Searching selected Knowledge Bases..." />
              </div>
            ) : searchMutation.data?.data ? (
              <>
                <Text type="secondary" className={styles.resultCount}>
                  Retrieved <strong style={{ color: 'var(--text-primary)' }}>{searchMutation.data.data.total}</strong> chunks.
                </Text>
                <SearchResultCards results={searchMutation.data.data.results} />
              </>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Configure a search and run it to inspect merged retrieval results." />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};
