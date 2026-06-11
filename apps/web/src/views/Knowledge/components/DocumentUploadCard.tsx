import React from 'react';
import { Card, Row, Col, Typography, Space, Select, Upload, Spin } from 'antd';
import { UploadCloud } from 'lucide-react';

const { Title, Text } = Typography;

interface DocumentUploadCardProps {
  parserProvider: string;
  setParserProvider: (val: string) => void;
  parserProviders: string[];
  configLoading: boolean;
  isUploading: boolean;
  handleUpload: (file: File) => Promise<void>;
}

export const DocumentUploadCard: React.FC<DocumentUploadCardProps> = ({
  parserProvider,
  setParserProvider,
  parserProviders,
  configLoading,
  isUploading,
  handleUpload,
}) => {
  return (
    <Card variant="borderless" className="glass-card" style={{ borderRadius: '16px' }}>
      <Row align="middle" justify="space-between" gutter={[16, 16]}>
        <Col>
          <Title level={5} className="font-outfit" style={{ margin: 0, fontWeight: 700 }}>
            Upload Document Stream
          </Title>
          <Text type="secondary" style={{ fontSize: '13px' }}>
            Configure default ingestion pipelines and drop documents to initiate embedding extraction.
          </Text>
        </Col>
        <Col>
          <Space size="middle">
            <Text strong style={{ fontSize: '13px' }}>Ingestion Parser:</Text>
            <Select
              value={parserProvider}
              style={{ width: 150 }}
              onChange={(val) => setParserProvider(val)}
              className="font-outfit"
              size="middle"
              loading={configLoading}
              options={parserProviders.map((provider) => ({
                value: provider,
                label: `${provider.charAt(0).toUpperCase() + provider.slice(1)} Parser`
              }))}
            />
          </Space>
        </Col>
      </Row>

      <div style={{ marginTop: '16px' }}>
        <Upload.Dragger
          customRequest={({ file }) => handleUpload(file as File)}
          showUploadList={false}
          disabled={isUploading}
          style={{ borderRadius: '12px', background: 'rgba(0,0,0,0.005)' }}
        >
          {isUploading ? (
            <div style={{ padding: '24px 0' }}>
              <Spin size="large" />
              <p className="font-outfit" style={{ marginTop: '16px', fontWeight: 700, fontSize: '15px', color: 'var(--colorPrimary)' }}>
                Worker node extracting document layouts...
              </p>
              <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary)' }}>
                Deep layout analysis, OCR, semantic character boundary chunking, and Qdrant index embeddings running.
              </p>
            </div>
          ) : (
            <div style={{ padding: '24px 0' }}>
              <p style={{ display: 'flex', justifyContent: 'center', marginBottom: '12px' }}>
                <UploadCloud size={44} color="var(--colorPrimary)" style={{ opacity: 0.8 }} />
              </p>
              <p className="font-outfit" style={{ fontWeight: 700, fontSize: '15px', margin: '0 0 4px 0' }}>
                Drag and drop target files or click to choose from local disk
              </p>
              <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary)' }}>
                Supports PDF, DOCX, Markdown, HTML, Plain Text (Limit: 10MB)
              </p>
            </div>
          )}
        </Upload.Dragger>
      </div>
    </Card>
  );
};
