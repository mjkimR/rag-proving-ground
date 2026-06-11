import { useEffect, useMemo, useState } from "react";
import type { ChangeEvent } from "react";
import type { PreviewMode } from "./types";
import { ControlPanel } from "./components/ControlPanel";
import { PreviewPanel } from "./components/PreviewPanel";
import { FullscreenComparison } from "./components/FullscreenComparison";
import { 
  getProviderOptionsApiV1ProvidersOptionsGet,
  documentParseApiV1DocParseParsePost 
} from "@/generated/api";
import type { ParsedElement } from "../../components/ElementsExplorer";
import type { ParsedPage } from "@/generated/api/types.gen";

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

function getErrorMessage(err: unknown, fallback: string) {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  if (
    typeof err === "object" &&
    err !== null &&
    "message" in err &&
    typeof err.message === "string"
  ) {
    return err.message;
  }
  return fallback;
}

export function DocumentWorkbench({ copilotEnabled }: DocumentWorkbenchProps) {
  const [mode, setMode] = useState<PreviewMode>("compare-elements");
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
  const [parsedDoc, setParsedDoc] = useState<{ elements?: ParsedElement[]; pages?: ParsedPage[]; metadata?: Record<string, unknown> } | null>(null);
  const [activeElement, setActiveElement] = useState<ParsedElement | null>(null);
  const [ignoreCache, setIgnoreCache] = useState<boolean>(false);
  const [parserProviders, setParserProviders] = useState<string[]>(["docling"]);

  useEffect(() => {
    getProviderOptionsApiV1ProvidersOptionsGet({ throwOnError: true })
      .then((res) => {
        if (res.data?.parser_providers) {
          setParserProviders(res.data.parser_providers);
        }
      })
      .catch((err) => console.error("Failed to fetch parser providers:", err));
  }, []);

  const activeSummary = useMemo(() => {
    if (mode === "compare-markdown") return "Side-by-side: PDF & Markdown active";
    if (mode === "compare-html") return "Side-by-side: PDF & HTML active";
    if (mode === "compare-elements") return `Side-by-side: PDF & Layout Elements active (${parsedDoc?.elements?.length || 0} elements)`;
    return "Office preview: convert via Gotenberg first";
  }, [mode, parsedDoc]);

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
      setMode("compare-elements");
    } else {
      setMode("compare-markdown");
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
      const response = await documentParseApiV1DocParseParsePost({
        body: {
          file,
          provider: provider || null,
          ignore_cache: ignoreCache,
        },
        throwOnError: true,
      });

      const data = response.data;
      if (!data) {
        throw new Error("No data returned from parser");
      }
      setParsedDoc(data);
      setMarkdown(data.markdown || data.text || "");
      setHtml(data.html || "");
      
      // Auto switch to comparison view to show off the results!
      setMode("compare-elements");
    } catch (err) {
      console.error(err);
      setParseError(getErrorMessage(err, "Failed to parse document"));
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
          activeElement={activeElement}
          setActiveElement={setActiveElement}
        />
      )}

      <section className="workspace">
        <ControlPanel
          setIsFullscreen={setIsFullscreen}
          handleFileChange={handleFileChange}
          provider={provider}
          setProvider={setProvider}
          parserProviders={parserProviders}
          handleParse={handleParse}
          isParsing={isParsing}
          file={file}
          parseError={parseError}
          mode={mode}
          setMode={setMode}
          ignoreCache={ignoreCache}
          setIgnoreCache={setIgnoreCache}
          parsedDocMetadata={parsedDoc?.metadata}
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
          activeElement={activeElement}
          setActiveElement={setActiveElement}
        />
      </section>
    </div>
  );
}
