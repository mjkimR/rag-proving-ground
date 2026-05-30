import { useState } from "react";

export interface BoundingBox {
  left: number;
  top: number;
  right: number;
  bottom: number;
  coord_origin?: string;
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
  metadata: Record<string, any>;
}

interface ElementsExplorerProps {
  elements: ParsedElement[];
  onElementClick?: (element: ParsedElement) => void;
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

  const getTypeColor = (type: string) => {
    switch (type.toLowerCase()) {
      case "heading":
        return "var(--badge-heading, #6366f1)"; // Indigo
      case "table":
        return "var(--badge-table, #10b981)"; // Emerald
      case "image":
        return "var(--badge-image, #f59e0b)"; // Amber
      case "list":
      case "list_item":
        return "var(--badge-list, #06b6d4)"; // Cyan
      case "equation":
        return "var(--badge-equation, #ec4899)"; // Pink
      case "footnote":
      case "caption":
        return "var(--badge-caption, #8b5cf6)"; // Purple
      default:
        return "var(--badge-default, #6b7280)"; // Gray
    }
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
                className={`element-card ${isExpanded ? "expanded" : ""}`}
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
                      📍 Show in PDF
                    </button>
                  )}
                </div>

                <div className="element-content-preview">
                  {el.type === "table" ? (
                    <div className="table-placeholder-label">
                      [HTML Table Element - Click to inspect HTML source]
                    </div>
                  ) : (
                    el.content || <span className="empty-content-label">[Empty Content]</span>
                  )}
                </div>

                {isExpanded && (
                  <div className="element-details" onClick={(e) => e.stopPropagation()}>
                    <div className="details-grid">
                      <div>
                        <strong>ID:</strong> <code>{el.element_id}</code>
                      </div>
                      <div>
                        <strong>Format:</strong> <code>{el.format}</code>
                      </div>
                      {el.bbox && (
                        <div className="bbox-details">
                          <strong>Bounding Box:</strong>
                          <div className="bbox-coords">
                            L: {el.bbox.left.toFixed(1)}, T: {el.bbox.top.toFixed(1)}, R: {el.bbox.right.toFixed(1)}, B: {el.bbox.bottom.toFixed(1)}
                          </div>
                        </div>
                      )}
                      {el.parent_id && (
                        <div>
                          <strong>Parent ID:</strong> <code>{el.parent_id}</code>
                        </div>
                      )}
                      {el.children_ids.length > 0 && (
                        <div>
                          <strong>Children IDs:</strong>{" "}
                          <code>{el.children_ids.join(", ")}</code>
                        </div>
                      )}
                    </div>
                    {Object.keys(el.metadata).length > 0 && (
                      <div className="element-metadata-block">
                        <strong>Metadata:</strong>
                        <pre>{JSON.stringify(el.metadata, null, 2)}</pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
