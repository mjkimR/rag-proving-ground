import React from 'react';
import { Card, Button, Space, Typography, Tag, Modal, Tabs, Radio, Alert } from 'antd';
import { useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, RefreshCw, Cpu, Sliders, Clock, Search, Settings, Info, Trash2, FileText
} from 'lucide-react';
import type { KnowledgeBaseRead } from '@/generated/api/types.gen';
import { useKnowledgeBaseDetail } from '../hooks/useKnowledgeBaseDetail';
import { DocumentUploadCard } from './DocumentUploadCard';
import { DocumentTable } from './DocumentTable';
import { StrategySettingsForm } from './StrategySettingsForm';
import { JobHistoryList } from './JobHistoryList';
import { DocumentSettingsModal } from './DocumentSettingsModal';
import { RetrievalTestTab } from './RetrievalTestTab';
import styles from './KnowledgeBaseDetail.module.css';

const { Title, Text, Paragraph } = Typography;

interface KnowledgeBaseDetailProps {
  kb: KnowledgeBaseRead;
  onBack: () => void;
  onDeleteSelected: () => void;
  onUpdateKbName: (name: string) => void;
  onInspect: (doc: { id: string; hash: string; name: string }) => void;
}

const formatBytes = (bytes: number, decimals = 2) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
};

export const KnowledgeBaseDetail: React.FC<KnowledgeBaseDetailProps> = ({
  kb,
  onBack,
  onDeleteSelected,
  onUpdateKbName,
  onInspect
}) => {
  const queryClient = useQueryClient();
  
  const {
    activeTab,
    setActiveTab,
    configLoading,
    embeddingModels,
    parserProviders,
    sparseEmbeddingModels,
    parserProvider,
    setParserProvider,
    isUploading,
    selectedDocForSettings,
    setSelectedDocForSettings,
    settingsForm,
    currentStep,
    showParserOverrides,
    setShowParserOverrides,
    configConfirmVisible,
    setConfigConfirmVisible,
    configLoadType,
    applyMode,
    setApplyMode,
    fileList,
    filesLoading,
    refetchFiles,
    parseHistory,
    parsingHistLoading,
    chunkHistory,
    chunkingHistLoading,
    embedHistory,
    embeddingHistLoading,
    handleUpload,
    handleDeleteDoc,
    handleDownload,
    handleDeleteKb,
    handlePreSaveConfig,
    handleFinalSaveConfig,
    handlePrevConfig,
    handleNextConfig,
    handleRefreshAll,
    patchKbMutation,
    refetchParseHist,
    refetchChunkHist,
    refetchEmbedHist,
  } = useKnowledgeBaseDetail({
    kb,
    onDeleteSelected,
    onUpdateKbName,
  });

  const docs = fileList?.data?.items || [];
  const completedDocs = docs.filter(d => d.status === 'COMPLETED').length;
  const processingDocs = docs.filter(d => ['PARSING', 'CHUNKING', 'EMBEDDING'].includes(d.status || '')).length;
  const failedDocs = docs.filter(d => d.status === 'FAILED').length;
  const totalSizeBytes = docs.reduce((acc, curr) => acc + ((curr.document_info as { size_bytes?: number } | null)?.size_bytes || 0), 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* 1. Detail Header Panel */}
      <Card variant="borderless" className="glass-card header-panel" style={{ borderRadius: '16px', padding: '6px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px', marginBottom: '16px' }}>
          
          <Space orientation="vertical" size={2}>
            {/* Back Button */}
            <Button
              type="text"
              icon={<ArrowLeft size={16} />}
              onClick={onBack}
              style={{ padding: 0, height: 'auto', display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)', marginBottom: '8px' }}
            >
              Back to Hub
            </Button>
            
            <Space align="center" size={12}>
              <div style={{
                width: '42px',
                height: '42px',
                borderRadius: '12px',
                background: 'linear-gradient(135deg, rgba(79, 70, 229, 0.15) 0%, rgba(0, 242, 254, 0.15) 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                border: '1px solid rgba(79, 70, 229, 0.2)'
              }}>
                <Settings size={20} color="#4f46e5" />
              </div>
              <div>
                <Title level={3} className="font-outfit" style={{ margin: 0, fontWeight: 800 }}>
                  KB: <span style={{ color: 'var(--accent-gradient)', background: 'linear-gradient(90deg, #4f46e5 0%, #00f2fe 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>{kb.name}</span>
                </Title>
                <Text type="secondary" style={{ fontSize: '12px', fontFamily: 'Outfit' }}>ID: {kb.id}</Text>
              </div>
            </Space>
          </Space>

          {/* Quick actions row */}
          <Space size="middle">
            <Button
              icon={<RefreshCw size={14} />}
              onClick={handleRefreshAll}
              style={{ borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              Refresh Status
            </Button>
            <Button
              type="primary"
              danger
              ghost
              icon={<Trash2 size={15} />}
              onClick={handleDeleteKb}
              style={{ borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              Drop Collection
            </Button>
          </Space>
        </div>

        {/* 2. Metadata Stats Bar */}
        <div className="meta-strip" style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '12px',
          background: 'rgba(0,0,0,0.015)',
          padding: '16px',
          borderRadius: '12px',
          border: '1px solid var(--border-color)'
        }}>
          <div>
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Store Status</span>
            <Tag color={kb.status === 'READY' || kb.status === 'COMPLETED' ? 'success' : 'processing'} style={{ fontWeight: 700, borderRadius: '4px', margin: '4px 0 0 0' }}>
              {kb.status}
            </Tag>
          </div>
          <div>
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Ingested files</span>
            <span className="font-outfit" style={{ fontSize: '16px', fontWeight: 700, display: 'block', marginTop: '2px' }}>
              {docs.length} <span style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>({completedDocs} Ready / {processingDocs} Active)</span>
            </span>
          </div>
          <div>
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Total Store Size</span>
            <span className="font-outfit" style={{ fontSize: '16px', fontWeight: 700, display: 'block', marginTop: '2px' }}>{formatBytes(totalSizeBytes)}</span>
          </div>
          <div>
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'block', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Embedding configuration</span>
            <span className="font-outfit" style={{ fontSize: '13px', fontWeight: 600, display: 'block', marginTop: '2px', wordBreak: 'break-all' }}>
              <Cpu size={12} style={{ marginRight: '4px', display: 'inline-block', verticalAlign: 'middle' }} />
              {kb.embedding_config?.model || 'text-embedding-3-small'} ({kb.embedding_config?.distance || 'cosine'})
            </span>
          </div>
        </div>
      </Card>

      {/* 3. Core Detail Tabs */}
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        type="card"
        className={styles.kbTabs}
        items={[
          {
            key: '1',
            label: (
              <span style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 12px', fontWeight: 600 }}>
                <FileText size={16} />
                <span>Documents & Upload ({docs.length})</span>
              </span>
            ),
            children: (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <DocumentUploadCard
                  parserProvider={parserProvider}
                  setParserProvider={setParserProvider}
                  parserProviders={parserProviders}
                  configLoading={configLoading}
                  isUploading={isUploading}
                  handleUpload={handleUpload}
                />
                <DocumentTable
                  docs={docs}
                  filesLoading={filesLoading}
                  failedDocs={failedDocs}
                  onInspect={onInspect}
                  setSelectedDocForSettings={setSelectedDocForSettings}
                  handleDeleteDoc={handleDeleteDoc}
                  handleDownload={handleDownload}
                />
              </div>
            )
          },
          {
            key: '2',
            label: (
              <span style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 12px', fontWeight: 600 }}>
                <Sliders size={16} />
                <span>Strategy Settings</span>
              </span>
            ),
            children: (
              <StrategySettingsForm
                kb={kb}
                settingsForm={settingsForm}
                currentStep={currentStep}
                showParserOverrides={showParserOverrides}
                setShowParserOverrides={setShowParserOverrides}
                parserProviders={parserProviders}
                embeddingModels={embeddingModels}
                sparseEmbeddingModels={sparseEmbeddingModels}
                configLoading={configLoading}
                patchKbMutationPending={patchKbMutation.isPending}
                handlePreSaveConfig={handlePreSaveConfig}
                handlePrevConfig={handlePrevConfig}
                handleNextConfig={handleNextConfig}
              />
            )
          },
          {
            key: '3',
            label: (
              <span style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 12px', fontWeight: 600 }}>
                <Clock size={16} />
                <span>Execution Logs & History</span>
              </span>
            ),
            children: (
              <JobHistoryList
                parseHistory={parseHistory}
                parsingHistLoading={parsingHistLoading}
                chunkHistory={chunkHistory}
                chunkingHistLoading={chunkingHistLoading}
                embedHistory={embedHistory}
                embeddingHistLoading={embeddingHistLoading}
                refetchParseHist={refetchParseHist}
                refetchChunkHist={refetchChunkHist}
                refetchEmbedHist={refetchEmbedHist}
              />
            )
          },
          {
            key: '4',
            label: (
              <span style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 12px', fontWeight: 600 }}>
                <Search size={16} />
                <span>Retrieval Test</span>
              </span>
            ),
            children: (
              <RetrievalTestTab kb={kb} />
            )
          }
        ]}
      />

      {/* 4. Single Document settings override modal */}
      <DocumentSettingsModal
        visible={!!selectedDocForSettings}
        onClose={() => setSelectedDocForSettings(null)}
        document={selectedDocForSettings}
        kbDefaultParsingConfig={kb.default_parsing_config}
        kbDefaultChunkingConfig={kb.default_chunking_config}
        onSuccess={() => {
          refetchFiles();
          queryClient.invalidateQueries({ queryKey: ['kbList'] });
        }}
      />

      {/* 5. Strategy adjustment confirmation modal */}
      <Modal
        title={
          <span className="font-outfit" style={{ fontSize: '16px', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Info size={18} className="text-warning" style={{ color: '#faad14' }} />
            Apply Strategy Settings
          </span>
        }
        open={configConfirmVisible}
        onCancel={() => setConfigConfirmVisible(false)}
        width={500}
        onOk={handleFinalSaveConfig}
        confirmLoading={patchKbMutation.isPending}
        okText="Confirm and Propagate"
        cancelText="Back to Edit"
        style={{ borderRadius: '12px' }}
      >
        <Space orientation="vertical" size="middle" style={{ width: '100%', marginTop: '12px' }}>
          
          {configLoadType === 'reembed' && (
            <Alert
              title="Full Collection Re-Embedding Required"
              description="Restructuring vector model dimensions or distance metrics requires building a new physics vector namespace. All files inside this database MUST be re-embedded."
              type="error"
              showIcon
            />
          )}

          {configLoadType === 'high' && (
            <Alert
              title="High Workload Detected"
              description="Altering default parsing providers requires parsing workers to download raw documents and run OCR / element extractions again, which takes processing bandwidth."
              type="warning"
              showIcon
            />
          )}

          {configLoadType === 'low' && (
            <Alert
              title="Low Load Strategy Adjustment"
              description="Only character split bounds or breadcrumbs adjusted. Fast propagation because worker nodes bypass layout extraction and process cached document trees."
              type="success"
              showIcon
            />
          )}

          <div>
            <Text strong className="font-outfit" style={{ display: 'block', marginBottom: '8px', fontSize: '13px' }}>
              Select strategy propagation scope for this database:
            </Text>
            <Radio.Group
              value={applyMode}
              onChange={(e) => setApplyMode(e.target.value)}
              style={{ width: '100%' }}
            >
              <Space orientation="vertical" style={{ width: '100%' }}>
                <Radio
                  value="NEW_ONLY"
                  disabled={configLoadType === 'reembed'}
                  style={{ display: 'flex', alignItems: 'start' }}
                >
                  <div style={{ marginLeft: '4px' }}>
                    <Text strong style={{ fontSize: '13px' }}>New Uploads Only</Text>
                    <Paragraph type="secondary" style={{ margin: 0, fontSize: '12px' }}>
                      Keep all current database entries intact. Only documents uploaded starting now inherit this updated strategy.
                    </Paragraph>
                  </div>
                </Radio>
                <Radio value="INHERITED_ONLY" style={{ display: 'flex', alignItems: 'start' }}>
                  <div style={{ marginLeft: '4px' }}>
                    <Text strong style={{ fontSize: '13px' }}>Reprocess Inherited Items</Text>
                    <Paragraph type="secondary" style={{ margin: 0, fontSize: '12px' }}>
                      Only reprocess documents that do not have active overrides (inheriting database defaults).
                    </Paragraph>
                  </div>
                </Radio>
                <Radio value="FORCE_ALL" style={{ display: 'flex', alignItems: 'start' }}>
                  <div style={{ marginLeft: '4px' }}>
                    <Text strong style={{ fontSize: '13px' }}>Force Propagate (Discard Overrides)</Text>
                    <Paragraph type="secondary" style={{ margin: 0, fontSize: '12px' }}>
                      Overwrite custom document settings and enforce this strategy across every file in this database.
                    </Paragraph>
                  </div>
                </Radio>
              </Space>
            </Radio.Group>
          </div>
        </Space>
      </Modal>

    </div>
  );
};
