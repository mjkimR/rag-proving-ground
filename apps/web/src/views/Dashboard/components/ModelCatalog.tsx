import React from 'react';
import { Card, Col, Row, Tag, Typography, Spin } from 'antd';
import { Cpu } from 'lucide-react';

interface ModelCatalogProps {
  catalogLoading: boolean;
  llmModels: string[];
  embeddingModels: string[];
  rerankerModels: string[];
  parserProviders: string[];
}

export const ModelCatalog: React.FC<ModelCatalogProps> = ({
  catalogLoading,
  llmModels,
  embeddingModels,
  rerankerModels,
  parserProviders,
}) => {
  return (
    <Card
      title={
        <span className="font-outfit" style={{ fontSize: '16px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Cpu size={18} className="text-primary" style={{ color: 'var(--colorPrimary)' }} />
          AI Model & Ingestion Catalog
        </span>
      }
      variant="borderless"
      className="glass-card"
    >
      <Row gutter={[16, 16]}>
        {/* LLM Models Column */}
        <Col xs={24} sm={12} md={6}>
          <Card size="small" variant="borderless" title={<span className="font-outfit" style={{ fontWeight: 700, fontSize: '14px' }}>Language Models (LLM)</span>} style={{ background: 'rgba(0,0,0,0.015)', border: '1px solid var(--border-color)', borderRadius: '10px' }}>
            {catalogLoading ? <Spin size="small" /> : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {llmModels.length > 0 ? llmModels.map(m => (
                  <Tag color="blue" key={m} style={{ margin: 0, padding: '4px 8px', borderRadius: '6px', fontSize: '13px', fontWeight: 500 }}>{m}</Tag>
                )) : <Typography.Text type="secondary">No LLMs configured</Typography.Text>}
              </div>
            )}
          </Card>
        </Col>
        
        {/* Embedding Models Column */}
        <Col xs={24} sm={12} md={6}>
          <Card size="small" variant="borderless" title={<span className="font-outfit" style={{ fontWeight: 700, fontSize: '14px' }}>Embedding Models</span>} style={{ background: 'rgba(0,0,0,0.015)', border: '1px solid var(--border-color)', borderRadius: '10px' }}>
            {catalogLoading ? <Spin size="small" /> : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {embeddingModels.length > 0 ? embeddingModels.map(m => (
                  <Tag color="green" key={m} style={{ margin: 0, padding: '4px 8px', borderRadius: '6px', fontSize: '13px', fontWeight: 500 }}>{m}</Tag>
                )) : <Typography.Text type="secondary">No embedding models</Typography.Text>}
              </div>
            )}
          </Card>
        </Col>

        {/* Reranker Models Column */}
        <Col xs={24} sm={12} md={6}>
          <Card size="small" variant="borderless" title={<span className="font-outfit" style={{ fontWeight: 700, fontSize: '14px' }}>Reranker Models</span>} style={{ background: 'rgba(0,0,0,0.015)', border: '1px solid var(--border-color)', borderRadius: '10px' }}>
            {catalogLoading ? <Spin size="small" /> : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {rerankerModels.length > 0 ? rerankerModels.map(m => (
                  <Tag color="orange" key={m} style={{ margin: 0, padding: '4px 8px', borderRadius: '6px', fontSize: '13px', fontWeight: 500 }}>{m}</Tag>
                )) : <Typography.Text type="secondary">No reranker models</Typography.Text>}
              </div>
            )}
          </Card>
        </Col>

        {/* Parser Providers Column */}
        <Col xs={24} sm={12} md={6}>
          <Card size="small" variant="borderless" title={<span className="font-outfit" style={{ fontWeight: 700, fontSize: '14px' }}>Parser Engines</span>} style={{ background: 'rgba(0,0,0,0.015)', border: '1px solid var(--border-color)', borderRadius: '10px' }}>
            {catalogLoading ? <Spin size="small" /> : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {parserProviders.length > 0 ? parserProviders.map(p => (
                  <Tag color="purple" key={p} style={{ margin: 0, padding: '4px 8px', borderRadius: '6px', fontSize: '13px', fontWeight: 500, textTransform: 'capitalize' }}>{p}</Tag>
                )) : <Typography.Text type="secondary">No parser engines</Typography.Text>}
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </Card>
  );
};
