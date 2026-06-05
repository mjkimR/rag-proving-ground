import React, { useState } from 'react';
import { Drawer, Spin, Empty } from 'antd';
import { useQuery } from '@tanstack/react-query';
import {
  getKnowledgeBasesApiV1KnowledgeBasesGet,
  getParsedDocumentApiV1KnowledgeBaseDocumentsKnowledgeBaseDocumentIdParsedGet
} from '@/generated/api/sdk.gen';
import { useThemeStore } from '@/stores/themeStore';
import { ElementsExplorer } from '@/components/ElementsExplorer';
import { PdfPreview } from '@/components/PdfPreview';
import { KnowledgeBaseHub } from './components/KnowledgeBaseHub';
import { KnowledgeBaseDetail } from './components/KnowledgeBaseDetail';
import type { KnowledgeBaseRead } from '@/generated/api/types.gen';
import { API_BASE_URL } from '@/lib/config';

export const Knowledge: React.FC = () => {
  const {
    setSelectedKnowledgeName,
    selectedKnowledgeId,
    setSelectedKnowledgeId
  } = useThemeStore();

  const [inspectingFile, setInspectingFile] = useState<{ id: string; hash: string; name: string } | null>(null);
  const [activeElement, setActiveElement] = useState<any>(null);

  // Fetch Knowledge Bases to resolve the active KB configuration
  const { data: kbList, isLoading: kbListLoading } = useQuery({
    queryKey: ['kbList'],
    queryFn: () => getKnowledgeBasesApiV1KnowledgeBasesGet({ throwOnError: true }),
  });

  const activeKb = kbList?.data?.items?.find((item: KnowledgeBaseRead) => item.id === selectedKnowledgeId) || null;

  // Fetch Parsed Document for Inspector Drawer
  const { data: parsedDoc, isLoading: parsedLoading } = useQuery({
    queryKey: ['parsedDoc', inspectingFile?.id],
    queryFn: () => {
      if (!inspectingFile) return Promise.resolve(null);
      return getParsedDocumentApiV1KnowledgeBaseDocumentsKnowledgeBaseDocumentIdParsedGet({
        path: {
          knowledge_base_document_id: inspectingFile.id,
        },
        throwOnError: true,
      });
    },
    enabled: !!inspectingFile,
  });

  // Handle loading state when resolving active KB
  const renderDetailView = () => {
    if (!selectedKnowledgeId) return null;
    
    if (kbListLoading) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '400px' }}>
          <Spin size="large" />
          <p className="font-outfit" style={{ marginTop: '16px', fontWeight: 600 }}>Loading Knowledge Base details...</p>
        </div>
      );
    }

    if (!activeKb) {
      // Fallback: if selected ID is invalid or not found, go back to Hub
      return (
        <div style={{ padding: '24px', textAlign: 'center' }}>
          <Empty description="The selected Knowledge Base could not be found." />
          <button
            onClick={() => {
              setSelectedKnowledgeId(null);
              setSelectedKnowledgeName(null);
            }}
            style={{
              marginTop: '12px',
              padding: '8px 16px',
              background: 'var(--colorPrimary)',
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer'
            }}
          >
            Return to Hub
          </button>
        </div>
      );
    }

    return (
      <KnowledgeBaseDetail
        kb={activeKb}
        onBack={() => {
          setSelectedKnowledgeId(null);
          setSelectedKnowledgeName(null);
        }}
        onDeleteSelected={() => {
          setSelectedKnowledgeId(null);
          setSelectedKnowledgeName(null);
        }}
        onUpdateKbName={(newName) => {
          setSelectedKnowledgeName(newName);
        }}
        onInspect={setInspectingFile}
      />
    );
  };

  return (
    <div style={{ minHeight: 'calc(100vh - 120px)', padding: '12px 0 24px 0' }}>
      {selectedKnowledgeId ? (
        renderDetailView()
      ) : (
        <KnowledgeBaseHub
          onSelect={(kb) => {
            setSelectedKnowledgeId(kb.id);
            setSelectedKnowledgeName(kb.name);
          }}
        />
      )}

      {/* Drawer: Parsed Elements Inspector */}
      <Drawer
        title={
          <span className="font-outfit" style={{ fontWeight: 800 }}>
            Layout Element Inspector: <span style={{ color: 'var(--accent-gradient)', background: 'linear-gradient(90deg, #4f46e5 0%, #00f2fe 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>{inspectingFile?.name}</span>
          </span>
        }
        width="90vw"
        onClose={() => {
          setInspectingFile(null);
          setActiveElement(null);
        }}
        open={!!inspectingFile}
        destroyOnClose
        styles={{ body: { padding: 0, overflow: 'hidden' } }}
      >
        {parsedLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <Spin size="large" />
            <p className="font-outfit" style={{ marginTop: '16px', fontWeight: 600 }}>Loading elements structure...</p>
          </div>
        ) : parsedDoc?.data ? (
          <div className="multi-view-container" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", height: "100%", gap: "16px", padding: "16px", background: "var(--bg-app)" }}>
            {/* Left Side Panel: Original Source */}
            <div className="multi-panel" style={{ height: "100%", background: "#ffffff", border: "1px solid var(--border-color)", borderRadius: "8px", display: "flex", flexDirection: "column", overflow: "hidden" }}>
              <div className="panel-header" style={{ padding: "10px 16px", background: "var(--bg-app)", borderBottom: "1px solid var(--border-color)", fontWeight: 700, fontSize: "13px" }}>PDF / Original Source</div>
              <div className="panel-content" style={{ flex: 1, overflow: "hidden" }}>
                {inspectingFile?.name.toLowerCase().endsWith('.pdf') ? (
                  <PdfPreview
                    fileUrl={`${API_BASE_URL}/api/v1/knowledge_base_documents/${inspectingFile.id}/download`}
                    fileName={inspectingFile.name}
                    activeElement={activeElement}
                    parsedDoc={parsedDoc.data as any}
                  />
                ) : (
                  <div className="non-pdf-info" style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", color: "#64748b", padding: "24px", textAlign: "center" }}>
                    <h3>{inspectingFile?.name}</h3>
                    <p>Comparison is only supported for PDF files.</p>
                  </div>
                )}
              </div>
            </div>

            {/* Right Side Panel: Layout Elements */}
            <div className="multi-panel" style={{ height: "100%", background: "#ffffff", border: "1px solid var(--border-color)", borderRadius: "8px", display: "flex", flexDirection: "column", overflow: "hidden" }}>
              <div className="panel-header" style={{ padding: "10px 16px", background: "var(--bg-app)", borderBottom: "1px solid var(--border-color)", fontWeight: 700, fontSize: "13px" }}>Layout Elements</div>
              <div className="panel-content" style={{ flex: 1, overflow: "hidden" }}>
                <ElementsExplorer
                  elements={
                    ((parsedDoc.data as any).elements || []).map((el: any) => ({
                      ...el,
                      content: el.content || '',
                    }))
                  }
                  onElementClick={setActiveElement}
                />
              </div>
            </div>
          </div>
        ) : (
          <Empty description="No elements data parsed successfully." />
        )}
      </Drawer>
    </div>
  );
};
