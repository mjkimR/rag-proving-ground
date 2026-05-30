import { useCopilotAction } from "@copilotkit/react-core";
import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { HtmlPreview } from "./HtmlPreview";
import { MarkdownPreview } from "./MarkdownPreview";
import { OfficePreview } from "./OfficePreview";
import { PdfPreview } from "./PdfPreview";
import { ElementsExplorer } from "./ElementsExplorer";

type PreviewMode = "pdf" | "markdown" | "html" | "elements" | "multi" | "office";

type DocumentWorkbenchProps = {
  copilotEnabled: boolean;
};

const modeLabels: Record<PreviewMode, string> = {
  pdf: "PDF Original",
  markdown: "Parsed Markdown",
  html: "Parsed HTML",
  elements: "Layout Elements",
  multi: "Multi-View Dashboard",
  office: "Office Convert",
};

const initialMarkdown = `# RAG Preview
Upload a document and click **Parse Document** to view the parsed outputs in different formats!

- Rich layout parsing
- Semantic element classification
- Table structure extraction
`;

const initialHtml = `<article>
  <h2>Document Parse Workbench</h2>
  <p>Select a document, choose your parser provider, and compare the outputs side-by-side.</p>
</article>`;

export function DocumentWorkbench({ copilotEnabled }: DocumentWorkbenchProps) {
  const [mode, setMode] = useState<PreviewMode>("pdf");
  const [file, setFile] = useState<File | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string>();
  const [pdfName, setPdfName] = useState("No file selected");
  const [markdown, setMarkdown] = useState(initialMarkdown);
  const [html, setHtml] = useState(initialHtml);
  
  // Parser states
  const [provider, setProvider] = useState<string>("docling");
  const [isParsing, setIsParsing] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [parsedDoc, setParsedDoc] = useState<any>(null);

  const activeSummary = useMemo(() => {
    if (mode === "pdf") return `PDF preview: ${pdfName}`;
    if (mode === "markdown") return `Markdown preview: ${markdown.length} chars`;
    if (mode === "html") return `HTML preview: ${html.length} chars`;
    if (mode === "elements") return `Layout elements count: ${parsedDoc?.elements?.length || 0}`;
    if (mode === "multi") return "Multi-View Dashboard active";
    return "Office preview: convert via Gotenberg first";
  }, [html.length, markdown.length, mode, pdfName, parsedDoc]);

  useEffect(() => {
    return () => {
      if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    };
  }, [pdfUrl]);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0];
    if (!selectedFile) return;

    setFile(selectedFile);
    setPdfName(selectedFile.name);
    setParseError(null);

    // If it's a PDF, set the local preview URL
    if (selectedFile.type === "application/pdf") {
      if (pdfUrl) URL.revokeObjectURL(pdfUrl);
      setPdfUrl(URL.createObjectURL(selectedFile));
      setMode("pdf");
    } else {
      setMode("markdown");
    }
  }

  async function handleParse() {
    if (!file) {
      setParseError("Please select a file to parse first.");
      return;
    }

    setIsParsing(true);
    setParseError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      if (provider) {
        formData.append("provider", provider);
      }

      const response = await fetch("/api/v1/doc_parse/parse", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: "Unknown error" }));
        throw new Error(errorData.detail || `Server error: ${response.status}`);
      }

      const data = await response.json();
      setParsedDoc(data);
      setMarkdown(data.markdown || data.text || "");
      setHtml(data.html || "");
      
      // Auto switch to multi-view to show off the results!
      setMode("multi");
    } catch (err: any) {
      console.error(err);
      setParseError(err.message || "Failed to parse document");
    } finally {
      setIsParsing(false);
    }
  }

  return (
    <section className="workspace">
      <aside className="control-panel">
        <label className="field-label" htmlFor="doc-file">
          Select Document
        </label>
        <input 
          accept=".pdf,.html,.htm,.md,.docx,.txt" 
          id="doc-file" 
          onChange={handleFileChange} 
          type="file" 
        />

        <div className="parser-settings-block">
          <label className="field-label" htmlFor="parser-provider">
            Parser Provider
          </label>
          <select 
            id="parser-provider" 
            value={provider} 
            onChange={(e) => setProvider(e.target.value)}
            className="provider-select"
          >
            <option value="docling">Docling Serve (AI Parser)</option>
          </select>

          <button 
            type="button" 
            className="parse-btn" 
            onClick={handleParse}
            disabled={isParsing || !file}
          >
            {isParsing ? "Parsing document..." : "Parse Document"}
          </button>
        </div>

        {parseError && (
          <div className="parse-error-banner" role="alert">
            <strong>Error:</strong> {parseError}
          </div>
        )}

        <hr className="divider" />

        <div className="mode-tabs" aria-label="Preview type">
          {(Object.keys(modeLabels) as PreviewMode[]).map((nextMode) => (
            <button
              aria-pressed={mode === nextMode}
              className="mode-tab"
              key={nextMode}
              onClick={() => setMode(nextMode)}
              type="button"
            >
              {modeLabels[nextMode]}
            </button>
          ))}
        </div>

        <label className="field-label" htmlFor="markdown-source">
          Markdown Source (editable)
        </label>
        <textarea 
          id="markdown-source" 
          onChange={(event) => setMarkdown(event.target.value)} 
          value={markdown} 
        />

        <label className="field-label" htmlFor="html-source">
          HTML Source (editable)
        </label>
        <textarea 
          id="html-source" 
          onChange={(event) => setHtml(event.target.value)} 
          value={html} 
        />
      </aside>

      <section className="preview-panel" aria-live="polite">
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
            {mode === "pdf" && <PdfPreview fileUrl={pdfUrl} fileName={pdfName} />}
            {mode === "markdown" && <MarkdownPreview markdown={markdown} />}
            {mode === "html" && <HtmlPreview html={html} />}
            {mode === "elements" && (
              parsedDoc?.elements ? (
                <ElementsExplorer elements={parsedDoc.elements} />
              ) : (
                <div className="empty-state">
                  <h2>No structured elements parsed yet</h2>
                  <p>Upload a document and run the parser to see layout elements.</p>
                </div>
              )
            )}
            {mode === "office" && (
              <OfficePreview onPdfReady={(url, name) => {
                if (pdfUrl) URL.revokeObjectURL(pdfUrl);
                setPdfUrl(url);
                setPdfName(name);
                setMode("pdf");
              }} />
            )}
            {mode === "multi" && (
              <div className="multi-view-container">
                <div className="multi-grid">
                  {/* Panel 1: Original File Source */}
                  <div className="multi-panel">
                    <div className="panel-header">PDF / Original Source</div>
                    <div className="panel-content">
                      {file?.type === "application/pdf" ? (
                        <PdfPreview fileUrl={pdfUrl} fileName={pdfName} />
                      ) : (
                        <div className="non-pdf-info">
                          <h3>{file ? file.name : "No file selected"}</h3>
                          <p>Type: {file ? file.type || "unknown" : "N/A"}</p>
                          <p>Size: {file ? `${(file.size / 1024).toFixed(1)} KB` : "N/A"}</p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Panel 2: Parsed HTML */}
                  <div className="multi-panel">
                    <div className="panel-header">Parsed HTML</div>
                    <div className="panel-content">
                      <HtmlPreview html={html} />
                    </div>
                  </div>

                  {/* Panel 3: Parsed Markdown */}
                  <div className="multi-panel">
                    <div className="panel-header">Parsed Markdown</div>
                    <div className="panel-content">
                      <MarkdownPreview markdown={markdown} />
                    </div>
                  </div>

                  {/* Panel 4: Layout Elements */}
                  <div className="multi-panel">
                    <div className="panel-header">Layout Elements</div>
                    <div className="panel-content">
                      {parsedDoc?.elements ? (
                        <ElementsExplorer elements={parsedDoc.elements} />
                      ) : (
                        <div className="no-elements-multi">Run parser to inspect layout elements.</div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </section>
    </section>
  );
}

function PreviewCopilotAction({ activeSummary }: { activeSummary: string }) {
  useCopilotAction({
    name: "getActivePreviewSummary",
    description: "Returns the currently selected preview mode and a short state summary.",
    parameters: [],
    handler: async () => activeSummary,
  });

  return null;
}

