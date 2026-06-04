import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Col, Empty, Input, InputNumber, Row, Select, Space, Spin, Switch, Tag, Typography, message } from 'antd';
import { useMutation, useQuery } from '@tanstack/react-query';
import { GitMerge, Search, SlidersHorizontal } from 'lucide-react';
import {
  getKnowledgeBasesApiV1KnowledgeBasesGet,
  getModelCatalogOptionsApiV1ModelCatalogOptionsGet,
  searchMultiKnowledgeBasesApiV1KnowledgeBasesSearchPost,
} from '@/generated/api/sdk.gen';
import type { KnowledgeBaseSearchResponse, RerankerConfig } from '@/generated/api/types.gen';
import { SearchResultCards } from '@/views/Knowledge/components/SearchResultCards';

const { Title, Text, Paragraph } = Typography;

export const Playground: React.FC = () => {
  const [selectedKbIds, setSelectedKbIds] = useState<string[]>([]);
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState<number>(5);
  const [candidateLimit, setCandidateLimit] = useState<number | null>(null);
  const [rerankerEnabled, setRerankerEnabled] = useState(false);
  const [rerankerModel, setRerankerModel] = useState<string | undefined>(undefined);
  const [rerankerTopN, setRerankerTopN] = useState<number | null>(null);

  const kbQuery = useQuery({
    queryKey: ['kbList'],
    queryFn: () => getKnowledgeBasesApiV1KnowledgeBasesGet({ throwOnError: true }),
  });

  const modelQuery = useQuery({
    queryKey: ['configOptions'],
    queryFn: () => getModelCatalogOptionsApiV1ModelCatalogOptionsGet({ throwOnError: true }),
  });

  const knowledgeBases = kbQuery.data?.data?.items || [];
  const rerankerModels = modelQuery.data?.data?.reranker_models || [];
  const hasCatalogRerankerModels = rerankerModels.length > 0 && !rerankerModels.includes('no-model');
  const forcedReranker = selectedKbIds.length >= 2;
  const effectiveRerankerEnabled = forcedReranker || rerankerEnabled;

  useEffect(() => {
    if (!rerankerModel && hasCatalogRerankerModels) {
      setRerankerModel(rerankerModels[0]);
    }
  }, [hasCatalogRerankerModels, rerankerModel, rerankerModels]);

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
    <div style={{ minHeight: 'calc(100vh - 120px)', padding: '12px 0 24px 0' }}>
      <div style={{ marginBottom: '24px' }}>
        <Space align="center" size={12}>
          <div
            style={{
              width: 42,
              height: 42,
              borderRadius: '14px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'linear-gradient(135deg, #0f766e 0%, #2563eb 100%)',
              boxShadow: '0 10px 24px rgba(15, 118, 110, 0.22)',
            }}
          >
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
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
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
                optionFilterProp="label"
              />
              <div style={{ marginTop: '12px' }}>
                <Text type="secondary">
                  {selectedKbIds.length} selected. Two or more KBs force reranking before final ranking.
                </Text>
              </div>
            </Card>

            <Card variant="borderless" className="glass-card" style={{ borderRadius: '16px' }}>
              <Space align="center" style={{ width: '100%', justifyContent: 'space-between', marginBottom: '16px' }}>
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
                  message="Reranker is required for multi-KB search."
                  style={{ marginBottom: '14px' }}
                />
              )}

              <Space direction="vertical" size={12} style={{ width: '100%' }}>
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
                      style={{ width: '100%', marginTop: '6px' }}
                    />
                  ) : (
                    <Input
                      size="large"
                      placeholder="Use default reranker or enter model name"
                      value={rerankerModel}
                      onChange={(event) => setRerankerModel(event.target.value || undefined)}
                      style={{ marginTop: '6px' }}
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
                    style={{ width: '100%', marginTop: '6px' }}
                    size="large"
                  />
                </div>
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
            <Space align="center" style={{ justifyContent: 'space-between', width: '100%', marginBottom: '16px' }}>
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
              <div style={{ textAlign: 'center', padding: '48px 0' }}>
                <Spin size="large" tip="Searching selected Knowledge Bases..." />
              </div>
            ) : searchMutation.data?.data ? (
              <>
                <Text type="secondary" style={{ display: 'block', marginBottom: '16px' }}>
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
