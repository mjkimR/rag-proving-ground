import { useCopilotAction } from "@copilotkit/react-core";
import { HtmlPreview } from "../../../components/HtmlPreview";
import { MarkdownPreview } from "../../../components/MarkdownPreview";
import { OfficePreview } from "../../../components/OfficePreview";
import { PdfPreview } from "../../../components/PdfPreview";
import { ElementsExplorer } from "../../../components/ElementsExplorer";
import type { PreviewMode } from "../types";
import type { ParsedElement } from "../../../components/ElementsExplorer";
import type { ParsedPage } from "@/generated/api/types.gen";

function PreviewCopilotAction({ activeSummary }: { activeSummary: string }) {
  useCopilotAction({
    name: "getActivePreviewSummary",
    description: "Returns the currently selected preview mode and a short state summary.",
    parameters: [],
    handler: async () => activeSummary,
  });

  return null;
}

type PreviewPanelProps = {
  copilotEnabled: boolean;
  activeSummary: string;
  isParsing: boolean;
  provider: string;
  mode: PreviewMode;
  setMode: (mode: PreviewMode) => void;
  pdfUrl?: string;
  setPdfUrl: (url: string) => void;
  pdfName: string;
  setPdfName: (name: string) => void;
  markdown: string;
  html: string;
  parsedDoc: { elements?: ParsedElement[]; pages?: ParsedPage[] } | null | undefined;
  file: File | null;
  activeElement: ParsedElement | null | undefined;
  setActiveElement: (el: ParsedElement) => void;
};

export function PreviewPanel({
  copilotEnabled,
  activeSummary,
  isParsing,
  provider,
  mode,
  setMode,
  pdfUrl,
  setPdfUrl,
  pdfName,
  setPdfName,
  markdown,
  html,
  parsedDoc,
  file,
  activeElement,
  setActiveElement,
}: PreviewPanelProps) {
  return (
    <section className="preview-panel" aria-live="polite" style={{ position: "relative" }}>
      {copilotEnabled && <PreviewCopilotAction activeSummary={activeSummary} />}
      
      {isParsing && (
        <div className="parsing-loader">
          <div className="spinner"></div>
          <h3>Analyzing & Parsing Document...</h3>
          <p>Using <strong>{provider}</strong> engine to reconstruct layout and extract text schemas.</p>
        </div>
      )}

      {!isParsing && (
        <>
          {mode === "office" && (
            <OfficePreview onPdfReady={(url, name) => {
              if (pdfUrl) URL.revokeObjectURL(pdfUrl);
              setPdfUrl(url);
              setPdfName(name);
              setMode("compare-elements");
            }} />
          )}
          
          {mode.startsWith("compare-") && (
            <div className="multi-view-container" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", height: "100%", gap: "16px", padding: "16px", background: "var(--bg-app)" }}>
              {/* Left Side Panel: Original Source */}
              <div className="multi-panel" style={{ height: "100%" }}>
                <div className="panel-header">PDF / Original Source</div>
                <div className="panel-content">
                  {file?.type === "application/pdf" ? (
                    <PdfPreview fileUrl={pdfUrl} fileName={pdfName} activeElement={activeElement} parsedDoc={parsedDoc} />
                  ) : (
                    <div className="non-pdf-info">
                      <h3>{file ? file.name : "No file selected"}</h3>
                      <p>Type: {file ? file.type || "unknown" : "N/A"}</p>
                      <p>Size: {file ? `${(file.size / 1024).toFixed(1)} KB` : "N/A"}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Right Side Panel: selected compare mode */}
              <div className="multi-panel" style={{ height: "100%" }}>
                <div className="panel-header">
                  {mode === "compare-markdown" ? "Parsed Markdown" : mode === "compare-html" ? "Parsed HTML" : "Layout Elements"}
                </div>
                <div className="panel-content">
                  {mode === "compare-markdown" && <MarkdownPreview markdown={markdown} />}
                  {mode === "compare-html" && <HtmlPreview html={html} />}
                  {mode === "compare-elements" && (
                    parsedDoc?.elements ? (
                      <ElementsExplorer 
                        elements={parsedDoc.elements} 
                        onElementClick={setActiveElement} 
                        activeElement={activeElement} 
                      />
                    ) : (
                      <div className="no-elements-multi">Run parser to inspect layout elements.</div>
                    )
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
