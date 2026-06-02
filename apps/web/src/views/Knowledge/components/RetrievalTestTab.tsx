import React, { useState } from 'react';
import { Card, Row, Col, Input, InputNumber, Spin, Empty, Space, Badge, Tag, Tooltip, Typography, message } from 'antd';
import { useMutation } from '@tanstack/react-query';
import { searchKnowledgeBaseApiV1KnowledgeBasesKnowledgeBaseIdSearchPost } from '@/generated/api/sdk.gen';
import type { KnowledgeBaseRead, KnowledgeBaseSearchResultItem, KnowledgeBaseSearchResponse } from '@/generated/api/types.gen';
import { Info } from 'lucide-react';

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

  const getScoreColor = (score: number) => {
    if (score > 0.8) return 'success';
    if (score > 0.6) return 'processing';
    if (score > 0.4) return 'warning';
    return 'error';
  };

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
          <Spin size="large" tip="Retrieving similar vectors..." />
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

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {searchMutation.data.data?.results?.map((result: KnowledgeBaseSearchResultItem, idx: number) => {
              const metadata = result.metadata as Record<string, any> | undefined;
              const pageIds = metadata?.page_ids;

              return (
                <Card
                  key={result.chunk_id}
                  size="small"
                  variant="borderless"
                  style={{
                    background: '#ffffff',
                    border: '1px solid var(--border-color)',
                    borderRadius: '12px',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.02)'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '8px', marginBottom: '12px' }}>
                    <Space size="middle" align="center" style={{ flexWrap: 'wrap' }}>
                      <Badge
                        count={`Chunk #${idx + 1}`}
                        style={{ backgroundColor: 'var(--border-color)', color: 'var(--text-secondary)', fontWeight: 600 }}
                      />
                      <Text type="secondary" style={{ fontSize: '12px' }}>
                        Document ID: <span style={{ fontFamily: 'monospace', background: 'rgba(0,0,0,0.03)', padding: '2px 6px', borderRadius: '4px' }}>{result.doc_id || 'N/A'}</span>
                      </Text>
                      {Array.isArray(pageIds) && pageIds.length > 0 && (
                        <Text type="secondary" style={{ fontSize: '12px' }}>
                          Pages: <span style={{ fontWeight: 600 }}>{pageIds.join(', ')}</span>
                        </Text>
                      )}
                    </Space>
                    <Tag
                      color={getScoreColor(result.score)}
                      style={{ fontWeight: 700, borderRadius: '6px', padding: '2px 8px', fontSize: '13px', margin: 0 }}
                    >
                      Score: {(result.score * 100).toFixed(1)}%
                    </Tag>
                  </div>

                  <div style={{
                    background: 'rgba(0,0,0,0.01)',
                    padding: '12px 16px',
                    borderRadius: '8px',
                    border: '1px dashed var(--border-color)',
                    maxHeight: '300px',
                    overflowY: 'auto'
                  }}>
                    <pre style={{
                      margin: 0,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      fontFamily: 'inherit',
                      fontSize: '13px',
                      color: 'var(--text-primary)',
                      lineHeight: '1.6'
                    }}>
                      {result.content}
                    </pre>
                  </div>

                  {metadata && Object.keys(metadata).length > 0 && (
                    <div style={{ marginTop: '12px', borderTop: '1px solid rgba(0,0,0,0.04)', paddingTop: '10px' }}>
                      <Tooltip title={JSON.stringify(metadata, null, 2)}>
                        <Text type="secondary" style={{ fontSize: '11px', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                          <Info size={12} />
                          <span>Hover to view metadata</span>
                        </Text>
                      </Tooltip>
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        </div>
      )}
    </Card>
  );
};
