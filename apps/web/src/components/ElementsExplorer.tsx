import { useState } from "react";

export interface BoundingBox {
  left: number;
  top: number;
  right: number;
  bottom: number;
  coord_origin?: string;
}

export interface AssetRef {
  uri?: string;
  path?: string;
  mimetype?: string;
  width?: number;
  height?: number;
  dpi?: number;
}

export interface ParsedElement {
  element_id: string;
  type: string;
  format: string;
  content: string;
  page_id?: string;
  order: number;
  level?: number;
  bbox?: BoundingBox;
  parent_id?: string;
  children_ids: string[];
  ignored?: boolean;
  asset?: AssetRef;
  metadata: Record<string, any>;
}

interface ElementsExplorerProps {
  elements: ParsedElement[];
  onElementClick?: (element: ParsedElement) => void;
}

// Element badge color configurations mapping element types to CSS variables and fallback hex codes
const ELEMENT_COLORS: Record<string, string> = {
  heading: "var(--badge-heading, #6366f1)", // Indigo
  table: "var(--badge-table, #10b981)", // Emerald
  image: "var(--badge-image, #f59e0b)", // Amber
  list: "var(--badge-list, #06b6d4)", // Cyan
  list_item: "var(--badge-list, #06b6d4)", // Cyan
  equation: "var(--badge-equation, #ec4899)", // Pink
  footnote: "var(--badge-caption, #8b5cf6)", // Purple
  caption: "var(--badge-caption, #8b5cf6)", // Purple
  page_header: "var(--badge-layout, #9ca3af)", // Warm Gray
  page_footer: "var(--badge-layout, #9ca3af)", // Warm Gray
  section_index: "var(--badge-index, #f43f5e)", // Rose
};

const getTypeColor = (type: string): string => {
  return ELEMENT_COLORS[type.toLowerCase()] || "var(--badge-default, #6b7280)"; // Gray
};

interface ElementPreviewProps {
  element: ParsedElement;
}

export function ElementPreview({ element }: ElementPreviewProps) {
  if (element.format === "html") {
    return (
      <div className="table-placeholder-label">
        [HTML Table Element - Click to inspect HTML source]
      </div>
    );
  }

  if (element.type === "image") {
    return (
      <div
        className="image-placeholder-label"
        style={{
          color: "var(--badge-image, #f59e0b)",
          fontWeight: 600,
          fontStyle: "italic",
        }}
      >
        🖼️ [Image Element {element.asset?.uri ? `- ${element.asset.uri}` : ""}]
      </div>
    );
  }

  return <>{element.content || <span className="empty-content-label">[Empty Content]</span>}</>;
}

interface ElementDetailsProps {
  element: ParsedElement;
}

export function ElementDetails({ element }: ElementDetailsProps) {
  return (
    <div className="element-details" onClick={(e) => e.stopPropagation()}>
      <div className="details-grid">
        <div>
          <strong>ID:</strong> <code>{element.element_id}</code>
        </div>
        <div>
          <strong>Format:</strong> <code>{element.format}</code>
        </div>
        {element.bbox && (
          <div className="bbox-details">
            <strong>Bounding Box:</strong>
            <div className="bbox-coords">
              L: {element.bbox.left.toFixed(1)}, T: {element.bbox.top.toFixed(1)}, R: {element.bbox.right.toFixed(1)}, B: {element.bbox.bottom.toFixed(1)}
            </div>
          </div>
        )}
        {element.parent_id && (
          <div>
            <strong>Parent ID:</strong> <code>{element.parent_id}</code>
          </div>
        )}
        {element.children_ids.length > 0 && (
          <div>
            <strong>Children IDs:</strong>{" "}
            <code>{element.children_ids.join(", ")}</code>
          </div>
        )}
      </div>
      {element.format === "html" && element.content && (
        <div className="html-element-render-container" style={{ marginTop: "12px", marginBottom: "12px" }}>
          <strong>Table Preview:</strong>
          <div className="html-element-render" dangerouslySetInnerHTML={{ __html: element.content }} />
        </div>
      )}
      {element.type === "image" && element.asset && (
        <div
          className="element-image-details"
          style={{
            marginTop: "12px",
            border: "1px solid var(--border-color, #dde3ea)",
            borderRadius: "6px",
            padding: "10px",
            background: "var(--bg-app, #f8fafc)",
            color: "var(--text-primary)",
          }}
        >
          <strong>Image Asset Details:</strong>
          <div style={{ marginTop: "6px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px", fontSize: "11px" }}>
            {element.asset.uri && (
              <div>
                <strong>URI:</strong> <code>{element.asset.uri}</code>
              </div>
            )}
            {element.asset.path && (
              <div>
                <strong>Storage Path:</strong> <code>{element.asset.path}</code>
              </div>
            )}
            {element.asset.mimetype && <div><strong>Mime-Type:</strong> {element.asset.mimetype}</div>}
            {(element.asset.width || element.asset.height) && (
              <div>
                <strong>Dimensions:</strong> {element.asset.width || "?"} x {element.asset.height || "?"}
              </div>
            )}
            {element.asset.dpi && <div><strong>Resolution:</strong> {element.asset.dpi} DPI</div>}
          </div>
        </div>
      )}
      {Object.keys(element.metadata).length > 0 && (
        <div className="element-metadata-block">
          <strong>Metadata:</strong>
          <pre>{JSON.stringify(element.metadata, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

export function ElementsExplorer({ elements, onElementClick }: ElementsExplorerProps) {
  const [selectedType, setSelectedType] = useState<string>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Get unique element types for the filter bar
  const elementTypes = ["all", ...Array.from(new Set(elements.map((el) => el.type)))];

  // Filter & sort elements by order
  const sortedElements = [...elements].sort((a, b) => a.order - b.order);
  const filteredElements =
    selectedType === "all" ? sortedElements : sortedElements.filter((el) => el.type === selectedType);

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  return (
    <div className="elements-explorer">
      <div className="explorer-header">
        <h3>Structured Layout Elements ({filteredElements.length})</h3>

        {/* Sleek element filter bar */}
        <div className="filter-tags" role="group" aria-label="Filter elements by type">
          {elementTypes.map((type) => (
            <button
              key={type}
              onClick={() => setSelectedType(type)}
              className={`filter-tag ${selectedType === type ? "active" : ""}`}
              type="button"
            >
              {type.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      <div className="elements-list">
        {filteredElements.length === 0 ? (
          <div className="no-elements">No elements matches the filter.</div>
        ) : (
          filteredElements.map((el) => {
            const isExpanded = expandedId === el.element_id;
            return (
              <div
                key={el.element_id}
                className={`element-card ${isExpanded ? "expanded" : ""} ${el.ignored ? "ignored" : ""}`}
                onClick={() => toggleExpand(el.element_id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    toggleExpand(el.element_id);
                  }
                }}
              >
                <div className="element-meta">
                  <span
                    className="element-type-badge"
                    style={{ backgroundColor: getTypeColor(el.type) }}
                  >
                    {el.type}
                  </span>
                  {el.ignored && (
                    <span className="element-ignored-badge" title="This layout element is boilerplate and ignored during semantic chunking">
                      🚫 Ignored
                    </span>
                  )}
                  <span className="element-order">Order #{el.order}</span>
                  {el.page_id && <span className="element-page">Page {el.page_id.split("-").pop() || el.page_id}</span>}
                  {el.level !== undefined && el.level !== null && (
                    <span className="element-level">Lvl {el.level}</span>
                  )}
                  {el.page_id && el.bbox && (
                    <button
                      className="show-in-pdf-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (onElementClick) onElementClick(el);
                      }}
                      style={{
                        marginLeft: "auto",
                        background: "var(--accent-color, #4f46e5)",
                        color: "white",
                        border: "none",
                        borderRadius: "4px",
                        padding: "2px 8px",
                        fontSize: "12px",
                        cursor: "pointer",
                      }}
                    >
                      Show in PDF
                    </button>
                  )}
                </div>

                <div className="element-content-preview">
                  <ElementPreview element={el} />
                </div>

                {isExpanded && <ElementDetails element={el} />}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
