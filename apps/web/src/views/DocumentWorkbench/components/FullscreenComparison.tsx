import { modeLabels } from "../types";
import type { PreviewMode } from "../types";
import { HtmlPreview } from "../../../components/HtmlPreview";
import { MarkdownPreview } from "../../../components/MarkdownPreview";
import { PdfPreview } from "../../../components/PdfPreview";
import { ElementsExplorer } from "../../../components/ElementsExplorer";
import type { ParsedElement } from "../../../components/ElementsExplorer";
import type { ParsedPage } from "@/generated/api/types.gen";

type FullscreenComparisonProps = {
  setIsFullscreen: (val: boolean) => void;
  pdfName: string;
  mode: PreviewMode;
  setMode: (mode: PreviewMode) => void;
  file: File | null;
  pdfUrl?: string;
  markdown: string;
  html: string;
  parsedDoc: { elements?: ParsedElement[]; pages?: ParsedPage[] } | null | undefined;
  activeElement: ParsedElement | null | undefined;
  setActiveElement: (el: ParsedElement) => void;
};

export function FullscreenComparison({
  setIsFullscreen,
  pdfName,
  mode,
  setMode,
  file,
  pdfUrl,
  markdown,
  html,
  parsedDoc,
  activeElement,
  setActiveElement,
}: FullscreenComparisonProps) {
  return (
    <div
      style={{
        position: "fixed",
        left: 0,
        top: 0,
        width: "100vw",
        height: "100vh",
        zIndex: 9999,
        background: "var(--bg-app, #f6f7f9)",
        display: "flex",
        flexDirection: "column",
        padding: "0",
      }}
    >
      {/* Immersive Fullscreen Header */}
      <div
        style={{
          height: "60px",
          padding: "0 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "var(--colorBgContainer, #ffffff)",
          borderBottom: "1px solid var(--border-color, #dde3ea)",
          boxShadow: "0 2px 8px rgba(0, 0, 0, 0.05)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <span style={{ fontWeight: 800, fontSize: "16px", color: "var(--text-primary)" }}>
            Immersive Comparison Workspace
          </span>
          <span style={{ color: "var(--text-secondary)", fontSize: "13px" }}>
            File: <strong>{pdfName}</strong>
          </span>
        </div>

        {/* Mode switcher tabs inside fullscreen modal */}
        <div className="mode-tabs" style={{ display: "flex", gap: "4px", background: "#eef1f5", padding: "4px", borderRadius: "8px", width: "420px" }} aria-label="Fullscreen type">
          {(["compare-elements", "compare-markdown", "compare-html"] as PreviewMode[]).map((nextMode) => (
            <button
              aria-pressed={mode === nextMode}
              className="mode-tab"
              key={nextMode}
              onClick={() => setMode(nextMode)}
              type="button"
              style={{ flex: 1, minHeight: "30px", fontSize: "11px" }}
            >
              {modeLabels[nextMode]}
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={() => setIsFullscreen(false)}
          style={{
            background: "var(--accent-color, #4f46e5)",
            color: "#ffffff",
            border: "none",
            borderRadius: "8px",
            padding: "8px 16px",
            fontWeight: 700,
            cursor: "pointer",
            boxShadow: "0 4px 12px rgba(79, 70, 229, 0.25)",
            transition: "all 0.2s",
          }}
        >
          Exit Full Screen
        </button>
      </div>

      {/* Fullscreen split screen grid */}
      <div style={{ flex: 1, height: "calc(100vh - 60px)", overflow: "hidden" }}>
        <div className="multi-view-container" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", height: "100%", gap: "16px", padding: "20px", background: "var(--bg-app)" }}>
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
      </div>
    </div>
  );
}
