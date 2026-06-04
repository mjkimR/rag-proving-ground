import React from 'react';
import { Badge, Card, Empty, Space, Tag, Tooltip, Typography } from 'antd';
import { Info } from 'lucide-react';
import type { KnowledgeBaseSearchResultItem } from '@/generated/api/types.gen';
import { formatShortId } from '@/lib/format';

const { Text } = Typography;

interface SearchResultCardsProps {
  results: KnowledgeBaseSearchResultItem[];
  emptyDescription?: string;
}

export const SearchResultCards: React.FC<SearchResultCardsProps> = ({
  results,
  emptyDescription = 'No chunks matched this query.',
}) => {
  if (!results.length) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={emptyDescription} />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {results.map((result, idx) => (
        <SearchResultCard key={result.chunk_id} result={result} index={idx} />
      ))}
    </div>
  );
};

interface SearchResultCardProps {
  result: KnowledgeBaseSearchResultItem;
  index: number;
}

const SearchResultCard: React.FC<SearchResultCardProps> = ({ result, index }) => {
  const metadata = result.metadata as Record<string, unknown> | undefined;
  const pageIds = metadata?.page_ids;

  return (
    <Card
      size="small"
      variant="borderless"
      style={{
        background: '#ffffff',
        border: '1px solid var(--border-color)',
        borderRadius: '12px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.02)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '8px', marginBottom: '12px' }}>
        <Space size="middle" align="center" style={{ flexWrap: 'wrap' }}>
          <Badge
            count={`Chunk #${index + 1}`}
            style={{ backgroundColor: 'var(--border-color)', color: 'var(--text-secondary)', fontWeight: 600 }}
          />
          <Text type="secondary" style={{ fontSize: '12px' }}>
            KB:{' '}
            <span style={{ fontFamily: 'monospace', background: 'rgba(0,0,0,0.03)', padding: '2px 6px', borderRadius: '4px' }}>
              {formatShortId(result.knowledge_base_id)}
            </span>
          </Text>
          <Text type="secondary" style={{ fontSize: '12px' }}>
            Document:{' '}
            <span style={{ fontFamily: 'monospace', background: 'rgba(0,0,0,0.03)', padding: '2px 6px', borderRadius: '4px' }}>
              {result.doc_id || 'N/A'}
            </span>
          </Text>
          {Array.isArray(pageIds) && pageIds.length > 0 && (
            <Text type="secondary" style={{ fontSize: '12px' }}>
              Pages: <span style={{ fontWeight: 600 }}>{pageIds.join(', ')}</span>
            </Text>
          )}
        </Space>
        <Space size={6} wrap>
          <ScoreTag label="Final" score={result.score} />
          <ScoreTag label="Vector" score={result.vector_score} />
          {typeof result.rerank_score === 'number' && <ScoreTag label="Rerank" score={result.rerank_score} />}
        </Space>
      </div>

      <div
        style={{
          background: 'rgba(0,0,0,0.01)',
          padding: '12px 16px',
          borderRadius: '8px',
          border: '1px dashed var(--border-color)',
          maxHeight: '300px',
          overflowY: 'auto',
        }}
      >
        <pre
          style={{
            margin: 0,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            fontFamily: 'inherit',
            fontSize: '13px',
            color: 'var(--text-primary)',
            lineHeight: '1.6',
          }}
        >
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
};

interface ScoreTagProps {
  label: string;
  score: number;
}

const ScoreTag: React.FC<ScoreTagProps> = ({ label, score }) => (
  <Tag
    color={getScoreColor(score)}
    style={{ fontWeight: 700, borderRadius: '6px', padding: '2px 8px', fontSize: '13px', margin: 0 }}
  >
    {label}: {(score * 100).toFixed(1)}%
  </Tag>
);

const getScoreColor = (score: number) => {
  if (score > 0.8) return 'success';
  if (score > 0.6) return 'processing';
  if (score > 0.4) return 'warning';
  return 'error';
};
