import { ChangeEvent } from "react";
import { Maximize2 } from "lucide-react";
import { PreviewMode, modeLabels } from "../types";

type ControlPanelProps = {
  setIsFullscreen: (val: boolean) => void;
  handleFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  provider: string;
  setProvider: (provider: string) => void;
  handleParse: () => void;
  isParsing: boolean;
  file: File | null;
  parseError: string | null;
  mode: PreviewMode;
  setMode: (mode: PreviewMode) => void;
  markdown: string;
  setMarkdown: (markdown: string) => void;
  html: string;
  setHtml: (html: string) => void;
};

export function ControlPanel({
  setIsFullscreen,
  handleFileChange,
  provider,
  setProvider,
  handleParse,
  isParsing,
  file,
  parseError,
  mode,
  setMode,
  markdown,
  setMarkdown,
  html,
  setHtml,
}: ControlPanelProps) {
  return (
    <aside className="control-panel" style={{ position: "relative" }}>
      {/* Immersive Full Screen Trigger Button */}
      <button
        type="button"
        onClick={() => setIsFullscreen(true)}
        style={{
          position: "absolute",
          right: "12px",
          top: "12px",
          background: "transparent",
          border: "none",
          color: "var(--text-secondary, #647084)",
          cursor: "pointer",
          padding: "4px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: "4px",
          zIndex: 5,
        }}
        title="View Full Screen Comparison"
      >
        <Maximize2 size={18} />
      </button>

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
  );
}
