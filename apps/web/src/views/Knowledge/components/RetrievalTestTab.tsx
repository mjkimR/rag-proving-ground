import React, { useState } from 'react';
import { Card, Row, Col, Input, InputNumber, Spin, Empty, Typography, message } from 'antd';
import { useMutation } from '@tanstack/react-query';
import { searchKnowledgeBaseApiV1KnowledgeBasesKnowledgeBaseIdSearchPost } from '@/generated/api/sdk.gen';
import type { KnowledgeBaseRead, KnowledgeBaseSearchResponse } from '@/generated/api/types.gen';
import { SearchResultCards } from './SearchResultCards';

const { Title, Text, Paragraph } = Typography;

interface RetrievalTestTabProps {
  kb: KnowledgeBaseRead;
}

export const RetrievalTestTab: React.FC<RetrievalTestTabProps> = ({ kb }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchLimit, setSearchLimit] = useState<number>(5);

  const searchMutation = useMutation({
    mutationFn: (variables: { query: string; limit: number }) => {
      return searchKnowledgeBaseApiV1KnowledgeBasesKnowledgeBaseIdSearchPost({
        path: { knowledge_base_id: kb.id },
        body: {
          query: variables.query,
          limit: variables.limit,
        },
        throwOnError: true,
      });
    },
    onSuccess: (response: { data: KnowledgeBaseSearchResponse }) => {
      message.success(`Search completed. Found ${response.data?.results?.length || 0} chunks.`);
    },
    onError: (e) => {
      console.error('Failed to run retrieval test:', e);
      message.error(e instanceof Error ? e.message : 'Retrieval search failed.');
    }
  });

  return (
    <Card variant="borderless" className="glass-card" style={{ borderRadius: '16px' }}>
      <div style={{ marginBottom: '20px' }}>
        <Title level={4} style={{ margin: 0, fontWeight: 700 }}>Vector Store Retrieval Test</Title>
        <Paragraph type="secondary" style={{ margin: '4px 0 0 0' }}>
          Query the underlying Qdrant vector database directly. Search results will filter for this specific Knowledge Base.
        </Paragraph>
      </div>

      <div style={{
        background: 'rgba(0,0,0,0.015)',
        padding: '20px',
        borderRadius: '12px',
        border: '1px solid var(--border-color)',
        marginBottom: '24px'
      }}>
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} sm={18}>
            <Input.Search
              placeholder="Type query to retrieve similar chunks..."
              allowClear
              enterButton="Retrieve"
              size="large"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onSearch={(value) => {
                if (value.trim()) {
                  searchMutation.mutate({ query: value, limit: searchLimit });
                } else {
                  message.warning('Please enter a query string.');
                }
              }}
              loading={searchMutation.isPending}
            />
          </Col>
          <Col xs={24} sm={6} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '13px', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>Limit:</span>
            <InputNumber
              min={1}
              max={100}
              value={searchLimit}
              onChange={(val) => val && setSearchLimit(val)}
              style={{ width: '100%' }}
              size="large"
            />
          </Col>
        </Row>
      </div>

      {searchMutation.isPending && (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin size="large" description="Retrieving similar vectors..." />
        </div>
      )}

      {!searchMutation.isPending && !searchMutation.data && (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="Enter a query above and click Retrieve to test the vector store."
        />
      )}

      {!searchMutation.isPending && searchMutation.data && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <Text type="secondary">
              Retrieved <strong style={{ color: 'var(--text-primary)' }}>{searchMutation.data.data?.results?.length || 0}</strong> chunks in total.
            </Text>
          </div>

          <SearchResultCards results={searchMutation.data.data?.results || []} />
        </div>
      )}
    </Card>
  );
};
