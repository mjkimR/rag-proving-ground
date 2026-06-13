import React, { useMemo, useEffect } from 'react';
import { Card, Input, InputNumber, Select, Space, Switch, Typography } from 'antd';
import { useQuery } from '@tanstack/react-query';
import {
  getKnowledgeBasesApiV1KnowledgeBasesGet,
  getProviderOptionsApiV1ProvidersOptionsGet,
} from '@/generated/api/sdk.gen';

const { Text } = Typography;

export interface RagConfigPanelProps {
  selectedKbIds: string[];
  setSelectedKbIds: (ids: string[]) => void;
  retrievalLimit: number;
  setRetrievalLimit: (n: number) => void;
  candidateLimit: number | null;
  setCandidateLimit: (n: number | null) => void;
  rerankerEnabled: boolean;
  setRerankerEnabled: (v: boolean) => void;
  rerankerModel: string | undefined;
  setRerankerModel: (m: string | undefined) => void;
  rerankerTopN: number | null;
  setRerankerTopN: (n: number | null) => void;
  retrievalMode: string | undefined;
  setRetrievalMode: (m: string | undefined) => void;
  sparseModel: string | undefined;
  setSparseModel: (m: string | undefined) => void;
  isStreaming: boolean;
  isDarkMode: boolean;
}

export const RagConfigPanel: React.FC<RagConfigPanelProps> = ({
  selectedKbIds,
  setSelectedKbIds,
  retrievalLimit,
  setRetrievalLimit,
  candidateLimit,
  setCandidateLimit,
  rerankerEnabled,
  setRerankerEnabled,
  rerankerModel,
  setRerankerModel,
  rerankerTopN,
  setRerankerTopN,
  retrievalMode,
  setRetrievalMode,
  sparseModel,
  setSparseModel,
  isStreaming,
  isDarkMode,
}) => {
  const { data: modelOptions } = useQuery({
    queryKey: ['modelOptions'],
    queryFn: () => getProviderOptionsApiV1ProvidersOptionsGet({ throwOnError: true }),
  });

  const kbQuery = useQuery({
    queryKey: ['chatKbList'],
    queryFn: () => getKnowledgeBasesApiV1KnowledgeBasesGet({ throwOnError: true }),
  });

  const kbOptions = useMemo(
    () => {
      const knowledgeBases = kbQuery.data?.data?.items || [];
      return knowledgeBases.map((kb) => ({
        label: `${kb.name} (${kb.status})`,
        value: kb.id,
      }));
    },
    [kbQuery.data?.data?.items],
  );

  const rerankerModels = useMemo(
    () => modelOptions?.data?.reranker_models || [],
    [modelOptions?.data?.reranker_models]
  );
  const sparseEmbeddingModels = useMemo(
    () => modelOptions?.data?.sparse_embedding_models || [],
    [modelOptions?.data?.sparse_embedding_models]
  );
  const hasCatalogRerankerModels = rerankerModels.length > 0 && !rerankerModels.includes('no-model');
  const forcedReranker = selectedKbIds.length >= 2;
  const effectiveRerankerEnabled = forcedReranker || rerankerEnabled;

  useEffect(() => {
    if (!rerankerModel && hasCatalogRerankerModels) {
      setRerankerModel(rerankerModels[0]);
    }
  }, [hasCatalogRerankerModels, rerankerModel, rerankerModels, setRerankerModel]);

  return (
    <Card
      size="small"
      style={{
        marginBottom: '16px',
        borderRadius: '12px',
        background: isDarkMode ? '#111827' : '#ffffff',
        border: '1px solid var(--border-color, #e5e7eb)',
      }}
    >
      <Space orientation="vertical" size={12} style={{ width: '100%' }}>
        <Space orientation="vertical" size={6} style={{ width: '100%' }}>
          <Text strong>Knowledge Bases</Text>
          <Select
            mode="multiple"
            placeholder="Select Knowledge Bases to retrieve context from"
            loading={kbQuery.isLoading}
            options={kbOptions}
            value={selectedKbIds}
            onChange={setSelectedKbIds}
            style={{ width: '100%' }}
            showSearch={{
              filterOption: (input, option) => (option?.label ?? '').toString().toLowerCase().includes(input.toLowerCase())
            }}
            disabled={isStreaming}
          />
        </Space>

        <Space wrap size={12} style={{ width: '100%' }}>
          <Space orientation="vertical" size={6}>
            <Text strong>Limit</Text>
            <InputNumber
              min={1}
              max={100}
              value={retrievalLimit}
              onChange={(value) => value && setRetrievalLimit(value)}
              disabled={isStreaming}
            />
          </Space>
          <Space orientation="vertical" size={6}>
            <Text strong>Candidate Limit</Text>
            <InputNumber
              min={1}
              max={500}
              value={candidateLimit}
              onChange={(value) => setCandidateLimit(value)}
              placeholder="Auto"
              disabled={isStreaming}
            />
          </Space>
          <Space orientation="vertical" size={6}>
            <Text strong>Reranker</Text>
            <Switch
              checked={effectiveRerankerEnabled}
              disabled={isStreaming || forcedReranker}
              onChange={setRerankerEnabled}
              checkedChildren="On"
              unCheckedChildren="Off"
            />
          </Space>
          <Space orientation="vertical" size={6} style={{ minWidth: 220 }}>
            <Text strong>Reranker Model</Text>
            {hasCatalogRerankerModels ? (
              <Select
                showSearch
                allowClear
                placeholder="Default reranker"
                loading={!modelOptions}
                options={rerankerModels.map((model) => ({ label: model, value: model }))}
                value={rerankerModel}
                onChange={setRerankerModel}
                disabled={isStreaming || !effectiveRerankerEnabled}
                style={{ width: '100%' }}
              />
            ) : (
              <Input
                placeholder="Default reranker or model name"
                value={rerankerModel}
                onChange={(event) => setRerankerModel(event.target.value || undefined)}
                disabled={isStreaming || !effectiveRerankerEnabled}
              />
            )}
          </Space>
          <Space orientation="vertical" size={6}>
            <Text strong>Top N</Text>
            <InputNumber
              min={1}
              max={100}
              value={rerankerTopN}
              onChange={(value) => setRerankerTopN(value)}
              placeholder="Limit"
              disabled={isStreaming || !effectiveRerankerEnabled}
            />
          </Space>
          <Space orientation="vertical" size={6} style={{ minWidth: 160 }}>
            <Text strong>Retrieval Mode</Text>
            <Select
              allowClear
              placeholder="KB default"
              options={[
                { value: 'dense', label: 'Dense Only' },
                { value: 'sparse', label: 'Sparse Only' },
                { value: 'hybrid', label: 'Hybrid (Dense+Sparse)' }
              ]}
              value={retrievalMode}
              onChange={(value) => {
                setRetrievalMode(value || undefined);
                if (value !== 'sparse' && value !== 'hybrid') {
                  setSparseModel(undefined);
                }
              }}
              disabled={isStreaming}
              style={{ width: '100%' }}
            />
          </Space>
          {(retrievalMode === 'sparse' || retrievalMode === 'hybrid') && (
            <Space orientation="vertical" size={6} style={{ minWidth: 220 }}>
              <Text strong>Sparse Model Override</Text>
              <Select
                allowClear
                placeholder="KB default"
                loading={!modelOptions}
                options={sparseEmbeddingModels.map((model) => ({
                  label: model === 'en-bm25'
                    ? 'English BM25 (en-bm25)'
                    : model === 'ko-kiwi-bm25'
                    ? 'Korean Kiwi BM25 (ko-kiwi-bm25)'
                    : model,
                  value: model
                }))}
                value={sparseModel}
                onChange={setSparseModel}
                disabled={isStreaming}
                style={{ width: '100%' }}
              />
            </Space>
          )}
        </Space>

        {forcedReranker && (
          <Text type="secondary" style={{ fontSize: '12px' }}>
            Multi-KB RAG requires reranking before final context selection.
          </Text>
        )}
      </Space>
    </Card>
  );
};
