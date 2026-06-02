import React from 'react';
import { Col, Row } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { getKnowledgeBasesApiV1KnowledgeBasesGet, healthApiHealthGet, getModelCatalogOptionsApiV1ModelCatalogOptionsGet } from '@/generated/api/sdk.gen';

import { DashboardStats } from './components/DashboardStats';
import { KnowledgeBasesCard } from './components/KnowledgeBasesCard';
import { SystemHealthCard } from './components/SystemHealthCard';
import { ModelCatalog } from './components/ModelCatalog';

export const Dashboard: React.FC = () => {
  // 1. Fetch all knowledge bases
  const { data: kbList, isLoading: kbLoading, error: kbError } = useQuery({
    queryKey: ['kbList'],
    queryFn: () => getKnowledgeBasesApiV1KnowledgeBasesGet({ throwOnError: true }),
  });

  // 2. Fetch API Health
  const { data: healthData, isError: isHealthError } = useQuery({
    queryKey: ['apiHealth'],
    queryFn: () => healthApiHealthGet({ throwOnError: true }),
    refetchInterval: 5000,
  });

  // 3. Fetch Model Catalog Options
  const { data: configOptions, isLoading: catalogLoading } = useQuery({
    queryKey: ['configOptions'],
    queryFn: () => getModelCatalogOptionsApiV1ModelCatalogOptionsGet({ throwOnError: true }),
  });

  const embeddingModels = configOptions?.data?.embedding_models || [];
  const llmModels = configOptions?.data?.llm_models || [];
  const rerankerModels = configOptions?.data?.reranker_models || [];
  const parserProviders = configOptions?.data?.parser_providers || [];

  const getSystemStatus = () => {
    if (isHealthError) return { text: 'Offline', color: 'red', desc: 'Cannot connect to backend API.' };
    if (!healthData) return { text: 'Connecting...', color: 'orange', desc: 'Resolving connection...' };
    const res = healthData.data as any;
    if (res?.status === 'healthy' || res?.success || res?.status === 'ok') {
      return { text: 'Online', color: 'green', desc: 'System API is fully responsive.' };
    }
    return { text: 'Degraded', color: 'warning', desc: 'System running but with exceptions.' };
  };

  const status = getSystemStatus();

  return (
    <div style={{ padding: '8px 0' }}>
      <DashboardStats
        kbCount={kbList?.data?.items ? kbList.data.items.length : 0}
        kbLoading={kbLoading}
        systemStatus={status}
      />

      {/* Main Section */}
      <Row gutter={[18, 18]} style={{ marginTop: '24px' }}>
        <Col xs={24} lg={16}>
          <KnowledgeBasesCard
            kbList={kbList}
            kbLoading={kbLoading}
            kbError={kbError}
          />
        </Col>

        {/* Sidebar Info Panel */}
        <Col xs={24} lg={8}>
          <SystemHealthCard systemStatus={status} />
        </Col>
      </Row>

      {/* Model Catalog Section */}
      <div style={{ marginTop: '24px' }}>
        <ModelCatalog
          catalogLoading={catalogLoading}
          llmModels={llmModels}
          embeddingModels={embeddingModels}
          rerankerModels={rerankerModels}
          parserProviders={parserProviders}
        />
      </div>
    </div>
  );
};

