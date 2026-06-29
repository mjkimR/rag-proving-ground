import React, { useState } from 'react';
import { Card, Descriptions, Tag, Alert, Spin, Button, List, Modal, Typography, message, Space, Row, Col } from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getPromptProviderInfoApiV1ProvidersPromptsGet,
  invalidateCacheApiV1ProvidersPromptsCacheInvalidatePost,
  listFallbackTemplatesApiV1ProvidersPromptsTemplatesGet
} from '@/generated/api/sdk.gen';
import type { PromptProviderInfo, FallbackTemplateInfo, InvalidateCacheResponse } from '@/generated/api/types.gen';
import { RefreshCw, FileText, Layers, Server } from 'lucide-react';

const { Text, Title, Paragraph } = Typography;

export const Prompts: React.FC = () => {
  const queryClient = useQueryClient();
  const [selectedTemplate, setSelectedTemplate] = useState<FallbackTemplateInfo | null>(null);

  // Queries
  const {
    data: configData,
    isLoading: isConfigLoading,
    error: configError
  } = useQuery({
    queryKey: ['prompts-config'],
    queryFn: () => getPromptProviderInfoApiV1ProvidersPromptsGet(),
  });

  const {
    data: templatesData,
    isLoading: isTemplatesLoading,
    error: templatesError
  } = useQuery({
    queryKey: ['prompts-templates'],
    queryFn: () => listFallbackTemplatesApiV1ProvidersPromptsTemplatesGet(),
  });

  // Mutation for Cache Invalidation
  const invalidateCacheMutation = useMutation({
    mutationFn: () => invalidateCacheApiV1ProvidersPromptsCacheInvalidatePost(),
    onSuccess: (res: { data?: InvalidateCacheResponse }) => {
      const data = res?.data;
      if (data?.success) {
        message.success(data.message || 'Prompt cache invalidated successfully.');
      } else {
        message.error(data?.message || 'Failed to invalidate prompt cache.');
      }
      queryClient.invalidateQueries({ queryKey: ['prompts-config'] });
    },
    onError: (err: { message?: string }) => {
      message.error(err?.message || 'Failed to invalidate prompt cache.');
    }
  });

  const isLoading = isConfigLoading || isTemplatesLoading;
  const hasError = configError || templatesError;

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <Spin size="large" tip="Loading Prompt Registry & Templates..." />
      </div>
    );
  }

  // Extract response data
  const config = configData?.data as PromptProviderInfo | undefined;
  const templates = (templatesData?.data || []) as FallbackTemplateInfo[];

  if (hasError || !config) {
    return (
      <Alert
        type="error"
        message="System Connection Error"
        description="Could not connect to backend prompts provider configuration service. Please check if your backend FastAPI application is running."
        showIcon
      />
    );
  }

  const getProviderColor = (prov: string) => {
    switch (prov.toLowerCase()) {
      case 's3':
        return 'orange';
      case 'langfuse':
        return 'purple';
      case 'local':
        return 'blue';
      default:
        return 'default';
    }
  };

  return (
    <div style={{ padding: '4px 0 24px 0' }}>
      
      {/* Upper header section */}
      <div style={{ marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Title level={4} style={{ margin: 0, fontWeight: 700 }} className="font-outfit">
            Prompt Template Registry
          </Title>
          <Paragraph type="secondary" style={{ margin: '4px 0 0 0' }}>
            Manage core LLM instruction templates, invalidate cache for updates, and explore fallback backups.
          </Paragraph>
        </div>
        
        <Button
          type="primary"
          icon={<RefreshCw size={14} className={invalidateCacheMutation.isPending ? 'animate-spin' : ''} />}
          loading={invalidateCacheMutation.isPending}
          onClick={() => invalidateCacheMutation.mutate()}
          style={{
            background: 'linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%)',
            border: 'none',
            borderRadius: '8px',
            height: '40px',
            fontWeight: 600,
            boxShadow: '0 4px 12px rgba(79, 70, 229, 0.2)'
          }}
        >
          Invalidate Prompt Cache
        </Button>
      </div>

      <Row gutter={[24, 24]}>
        {/* Left Column: Registry config */}
        <Col xs={24} lg={10}>
          <Card
            bordered={false}
            className="shadow-sm"
            style={{ borderRadius: '12px' }}
            title={
              <Space>
                <Server size={18} className="text-indigo-600" />
                <span style={{ fontWeight: 700, fontSize: '15px' }} className="font-outfit">
                  Adapter Settings
                </span>
              </Space>
            }
          >
            <Descriptions bordered column={1} size="middle" style={{ background: '#fff' }}>
              <Descriptions.Item label="Active Provider">
                <Tag color={getProviderColor(config.current_provider)} style={{ fontWeight: 700, padding: '4px 12px', fontSize: '13px', borderRadius: '6px' }}>
                  {config.current_provider.toUpperCase()}
                </Tag>
              </Descriptions.Item>
              
              <Descriptions.Item label="Available adapters">
                <Space>
                  {config.available_providers?.map((p: string) => (
                    <Tag key={p} color={getProviderColor(p)} style={{ fontWeight: 500 }}>
                      {p}
                    </Tag>
                  ))}
                </Space>
              </Descriptions.Item>

              {config.current_provider === 's3' && (
                <Descriptions.Item label="S3 Bucket">
                  <Text code className="font-mono">{config.s3_bucket || 'N/A'}</Text>
                </Descriptions.Item>
              )}

              {config.current_provider === 'langfuse' && (
                <Descriptions.Item label="Langfuse Host">
                  <Text code className="font-mono">{config.langfuse_host || 'N/A'}</Text>
                </Descriptions.Item>
              )}

              <Descriptions.Item label="Fallback Directory">
                <Text code className="font-mono" style={{ fontSize: '12px', wordBreak: 'break-all', display: 'inline-block', padding: '4px 6px', background: '#f8fafc', borderRadius: '4px', border: '1px solid #e2e8f0' }}>
                  {config.fallback_dir || 'N/A'}
                </Text>
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>

        {/* Right Column: Templates Explorer */}
        <Col xs={24} lg={14}>
          <Card
            bordered={false}
            className="shadow-sm"
            style={{ borderRadius: '12px' }}
            title={
              <Space>
                <Layers size={18} className="text-indigo-600" />
                <span style={{ fontWeight: 700, fontSize: '15px' }} className="font-outfit">
                  Backup Templates Explorer
                </span>
              </Space>
            }
          >
            <List
              itemLayout="horizontal"
              dataSource={templates}
              locale={{ emptyText: 'No fallback template files found.' }}
              renderItem={(item) => (
                <List.Item
                  actions={[
                    <Button
                      key="view"
                      type="link"
                      icon={<FileText size={15} />}
                      onClick={() => setSelectedTemplate(item)}
                      style={{ color: '#4f46e5', fontWeight: 600 }}
                    >
                      Inspect
                    </Button>
                  ]}
                >
                  <List.Item.Meta
                    avatar={
                      <div style={{ padding: '8px', background: '#eef2ff', borderRadius: '8px', color: '#4f46e5', display: 'flex', alignItems: 'center' }}>
                        <FileText size={18} />
                      </div>
                    }
                    title={<span style={{ fontWeight: 600, fontSize: '14px' }}>{item.name}</span>}
                    description={
                      <Space style={{ marginTop: '2px' }}>
                        <Tag color={item.format === 'yaml' ? 'blue' : 'cyan'} style={{ borderRadius: '4px', fontSize: '11px', fontWeight: 600 }}>
                          {item.format.toUpperCase()}
                        </Tag>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>

      {/* Template Content Viewer Modal */}
      <Modal
        title={
          <Space>
            <FileText size={18} className="text-indigo-600" />
            <span style={{ fontWeight: 700, fontSize: '16px' }} className="font-outfit">
              {selectedTemplate ? `${selectedTemplate.name}.${selectedTemplate.format}` : 'Template Viewer'}
            </span>
          </Space>
        }
        open={!!selectedTemplate}
        onCancel={() => setSelectedTemplate(null)}
        footer={[
          <Button key="close" type="primary" onClick={() => setSelectedTemplate(null)} style={{ background: '#4f46e5', border: 'none', borderRadius: '6px' }}>
            Close
          </Button>
        ]}
        width={800}
        destroyOnClose
      >
        {selectedTemplate && (
          <div style={{ marginTop: '16px' }}>
            <div style={{ marginBottom: '12px' }}>
              <Text type="secondary">
                This config is loaded into the pipeline when S3 or Langfuse services are unreachable.
              </Text>
            </div>
            <pre
              style={{
                background: '#0f172a',
                color: '#e2e8f0',
                padding: '16px',
                borderRadius: '8px',
                overflowX: 'auto',
                fontSize: '13px',
                fontFamily: 'SFMono-Regular, Consolas, "Liberation Mono", Menlo, Courier, monospace',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
                maxHeight: '520px',
                border: '1px solid #1e293b'
              }}
            >
              {selectedTemplate.content}
            </pre>
          </div>
        )}
      </Modal>

    </div>
  );
};

export default Prompts;
