import { useCopilotAction } from "@copilotkit/react-core";
import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { HtmlPreview } from "./HtmlPreview";
import { MarkdownPreview } from "./MarkdownPreview";
import { OfficePreview } from "./OfficePreview";
import { PdfPreview } from "./PdfPreview";

type PreviewMode = "pdf" | "markdown" | "html" | "office";

type DocumentWorkbenchProps = {
  copilotEnabled: boolean;
};

const modeLabels: Record<PreviewMode, string> = {
  pdf: "PDF",
  markdown: "Markdown",
  html: "HTML",
  office: "Office",
};

const initialMarkdown = `# RAG preview

- GitHub Flavored Markdown 지원
- table, task list, link sanitize 적용

| Field | Value |
| --- | --- |
| Parser | Docling |
| Preview | react-markdown |
`;

const initialHtml = `<article>
  <h2>HTML preview</h2>
  <p>DOMPurify로 sanitize 후 sandbox iframe에서 렌더링합니다.</p>
  <button onclick="alert('blocked')">inline handler removed</button>
</article>`;

export function DocumentWorkbench({ copilotEnabled }: DocumentWorkbenchProps) {
  const [mode, setMode] = useState<PreviewMode>("pdf");
  const [pdfUrl, setPdfUrl] = useState<string>();
  const [pdfName, setPdfName] = useState("No PDF selected");
  const [markdown, setMarkdown] = useState(initialMarkdown);
  const [html, setHtml] = useState(initialHtml);

  const activeSummary = useMemo(() => {
    if (mode === "pdf") return `PDF preview: ${pdfName}`;
    if (mode === "markdown") return `Markdown preview: ${markdown.length} chars`;
    if (mode === "html") return `HTML preview: ${html.length} chars`;
    return "Office preview: convert via Gotenberg first";
  }, [html.length, markdown.length, mode, pdfName]);

  useEffect(() => {
    return () => {
      if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    };
  }, [pdfUrl]);

  function handlePdfChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    setPdfUrl(URL.createObjectURL(file));
    setPdfName(file.name);
    setMode("pdf");
  }

  return (
    <section className="workspace">
      <aside className="control-panel">
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

        <label className="field-label" htmlFor="pdf-file">
          PDF original
        </label>
        <input accept="application/pdf" id="pdf-file" onChange={handlePdfChange} type="file" />

        <label className="field-label" htmlFor="markdown-source">
          Markdown source
        </label>
        <textarea id="markdown-source" onChange={(event) => setMarkdown(event.target.value)} value={markdown} />

        <label className="field-label" htmlFor="html-source">
          HTML source
        </label>
        <textarea id="html-source" onChange={(event) => setHtml(event.target.value)} value={html} />
      </aside>

      <section className="preview-panel" aria-live="polite">
        {copilotEnabled && <PreviewCopilotAction activeSummary={activeSummary} />}
        {mode === "pdf" && <PdfPreview fileUrl={pdfUrl} fileName={pdfName} />}
        {mode === "markdown" && <MarkdownPreview markdown={markdown} />}
        {mode === "html" && <HtmlPreview html={html} />}
        {mode === "office" && <OfficePreview onPdfReady={(url, name) => {
          if (pdfUrl) URL.revokeObjectURL(pdfUrl);
          setPdfUrl(url);
          setPdfName(name);
          setMode("pdf");
        }} />}
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
