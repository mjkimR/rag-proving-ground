import React from 'react';
import { Card, Descriptions, Tag, Alert, Spin } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { getPromptProviderInfoApiV1ProvidersPromptsGet } from '@/generated/api/sdk.gen';
import type { PromptProviderInfo } from '@/generated/api/types.gen';

export const PromptsSection: React.FC = () => {
  const { data, isLoading, error } = useQuery({
    queryKey: ['prompts-config'],
    queryFn: () => getPromptProviderInfoApiV1ProvidersPromptsGet(),
  });

  if (isLoading) {
    return <Spin size="large" />;
  }

  // extract properly, handling standard fetch wrapper shapes
  const responseData = data?.data as PromptProviderInfo | undefined;

  if (error || !responseData) {
    return <Alert type="error" message="Failed to load Prompts config" />;
  }

  return (
    <Card
      bordered={false}
      styles={{ body: { padding: '16px 0' } }}
      title={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span className="font-outfit" style={{ fontSize: '16px', fontWeight: 700 }}>
            Prompt Registry Configuration
          </span>
        </div>
      }
    >
      <Descriptions bordered column={1} size="small">
        <Descriptions.Item label="Current Provider">
          <Tag color="geekblue">{responseData.current_provider}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="Available Providers">
          {responseData.available_providers?.map((p: string) => (
            <Tag key={p}>{p}</Tag>
          ))}
        </Descriptions.Item>
        {responseData.current_provider === 's3' && (
          <Descriptions.Item label="S3 Bucket">
            {responseData.s3_bucket || 'N/A'}
          </Descriptions.Item>
        )}
        {responseData.current_provider === 'langfuse' && (
          <Descriptions.Item label="Langfuse Host">
            {responseData.langfuse_host || 'N/A'}
          </Descriptions.Item>
        )}
        <Descriptions.Item label="Fallback Directory">
          {responseData.fallback_dir || 'N/A'}
        </Descriptions.Item>
      </Descriptions>
    </Card>
  );
};
