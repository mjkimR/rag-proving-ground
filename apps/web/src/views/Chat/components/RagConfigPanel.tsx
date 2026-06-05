import React, { useMemo, useEffect } from 'react';
import { Card, Input, InputNumber, Select, Space, Switch, Typography } from 'antd';
import { useQuery } from '@tanstack/react-query';
import {
  getKnowledgeBasesApiV1KnowledgeBasesGet,
  getModelCatalogOptionsApiV1ModelCatalogOptionsGet,
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
  isStreaming,
  isDarkMode,
}) => {
  const { data: modelOptions } = useQuery({
    queryKey: ['modelOptions'],
    queryFn: () => getModelCatalogOptionsApiV1ModelCatalogOptionsGet({ throwOnError: true }),
  });

  const kbQuery = useQuery({
    queryKey: ['chatKbList'],
    queryFn: () => getKnowledgeBasesApiV1KnowledgeBasesGet({ throwOnError: true }),
  });

  const knowledgeBases = kbQuery.data?.data?.items || [];
  const kbOptions = useMemo(
    () =>
      knowledgeBases.map((kb) => ({
        label: `${kb.name} (${kb.status})`,
        value: kb.id,
      })),
    [knowledgeBases],
  );

  const rerankerModels = modelOptions?.data?.reranker_models || [];
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
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Space direction="vertical" size={6} style={{ width: '100%' }}>
          <Text strong>Knowledge Bases</Text>
          <Select
            mode="multiple"
            placeholder="Select Knowledge Bases to retrieve context from"
            loading={kbQuery.isLoading}
            options={kbOptions}
            value={selectedKbIds}
            onChange={setSelectedKbIds}
            style={{ width: '100%' }}
            optionFilterProp="label"
            disabled={isStreaming}
          />
        </Space>

        <Space wrap size={12} style={{ width: '100%' }}>
          <Space direction="vertical" size={6}>
            <Text strong>Limit</Text>
            <InputNumber
              min={1}
              max={100}
              value={retrievalLimit}
              onChange={(value) => value && setRetrievalLimit(value)}
              disabled={isStreaming}
            />
          </Space>
          <Space direction="vertical" size={6}>
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
          <Space direction="vertical" size={6}>
            <Text strong>Reranker</Text>
            <Switch
              checked={effectiveRerankerEnabled}
              disabled={isStreaming || forcedReranker}
              onChange={setRerankerEnabled}
              checkedChildren="On"
              unCheckedChildren="Off"
            />
          </Space>
          <Space direction="vertical" size={6} style={{ minWidth: 220 }}>
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
          <Space direction="vertical" size={6}>
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
