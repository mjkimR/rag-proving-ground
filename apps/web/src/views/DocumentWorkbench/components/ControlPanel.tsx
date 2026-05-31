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
  ignoreCache: boolean;
  setIgnoreCache: (val: boolean) => void;
  parsedDocMetadata?: {
    cache_hit?: boolean;
    parse_duration_sec?: number;
  };
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
  ignoreCache,
  setIgnoreCache,
  parsedDocMetadata,
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
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <label className="field-label" htmlFor="parser-provider" style={{ marginTop: 0 }}>
            Parser Provider
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "var(--text-secondary, #647084)", fontWeight: "500", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={ignoreCache}
              onChange={(e) => setIgnoreCache(e.target.checked)}
              style={{ cursor: "pointer", width: "14px", height: "14px", accentColor: "var(--accent-color)" }}
            />
            Ignore Cache
          </label>
        </div>
        <select
          id="parser-provider"
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
          className="provider-select"
        >
          <option value="docling">Docling Serve</option>
        </select>

        <button
          type="button"
          className="parse-btn"
          onClick={handleParse}
          disabled={isParsing || !file}
        >
          {isParsing ? "Parsing document..." : "Parse Document"}
        </button>

        {parsedDocMetadata && (
          <div style={{
            marginTop: "4px",
            padding: "10px 12px",
            borderRadius: "8px",
            background: "var(--bg-app, #f8fafc)",
            border: "1px solid var(--border-color, #cbd5e1)",
            fontSize: "12px",
            display: "flex",
            flexDirection: "column",
            gap: "6px"
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ color: "var(--text-secondary, #647084)", fontWeight: "500" }}>Cache Status</span>
              <span style={{
                fontWeight: "700",
                color: parsedDocMetadata.cache_hit ? "#10b981" : "#3b82f6",
                backgroundColor: parsedDocMetadata.cache_hit ? "rgba(16, 185, 129, 0.1)" : "rgba(59, 130, 246, 0.1)",
                padding: "2px 6px",
                borderRadius: "4px",
                fontSize: "10px",
                letterSpacing: "0.05em"
              }}>
                {parsedDocMetadata.cache_hit ? "CACHE HIT" : "CACHE MISS"}
              </span>
            </div>
            {parsedDocMetadata.parse_duration_sec !== undefined && (
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ color: "var(--text-secondary, #647084)", fontWeight: "500" }}>Parse Duration</span>
                <span style={{ fontWeight: "600", color: "var(--text-primary, #1e293b)" }}>
                  {parsedDocMetadata.parse_duration_sec.toFixed(2)}s
                </span>
              </div>
            )}
          </div>
        )}
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
    </aside>
  );
}
