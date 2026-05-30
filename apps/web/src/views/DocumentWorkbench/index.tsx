import { ChangeEvent, useEffect, useMemo, useState } from "react";
import { PreviewMode } from "./types";
import { ControlPanel } from "./components/ControlPanel";
import { PreviewPanel } from "./components/PreviewPanel";
import { FullscreenComparison } from "./components/FullscreenComparison";

type DocumentWorkbenchProps = {
  copilotEnabled: boolean;
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
  const [isFullscreen, setIsFullscreen] = useState(false);
  
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
    if (mode === "compare-markdown") return "Side-by-side: PDF & Markdown active";
    if (mode === "compare-html") return "Side-by-side: PDF & HTML active";
    if (mode === "compare-elements") return "Side-by-side: PDF & Layout Elements active";
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
      
      // Auto switch to comparison view to show off the results!
      setMode("compare-markdown");
    } catch (err: any) {
      console.error(err);
      setParseError(err.message || "Failed to parse document");
    } finally {
      setIsParsing(false);
    }
  }

  return (
    <div style={{ position: "relative" }}>
      {isFullscreen && (
        <FullscreenComparison
          setIsFullscreen={setIsFullscreen}
          pdfName={pdfName}
          mode={mode}
          setMode={setMode}
          file={file}
          pdfUrl={pdfUrl}
          markdown={markdown}
          html={html}
          parsedDoc={parsedDoc}
        />
      )}

      <section className="workspace">
        <ControlPanel
          setIsFullscreen={setIsFullscreen}
          handleFileChange={handleFileChange}
          provider={provider}
          setProvider={setProvider}
          handleParse={handleParse}
          isParsing={isParsing}
          file={file}
          parseError={parseError}
          mode={mode}
          setMode={setMode}
          markdown={markdown}
          setMarkdown={setMarkdown}
          html={html}
          setHtml={setHtml}
        />

        <PreviewPanel
          copilotEnabled={copilotEnabled}
          activeSummary={activeSummary}
          isParsing={isParsing}
          provider={provider}
          mode={mode}
          setMode={setMode}
          pdfUrl={pdfUrl}
          setPdfUrl={setPdfUrl}
          pdfName={pdfName}
          setPdfName={setPdfName}
          markdown={markdown}
          html={html}
          parsedDoc={parsedDoc}
          file={file}
        />
      </section>
    </div>
  );
}
