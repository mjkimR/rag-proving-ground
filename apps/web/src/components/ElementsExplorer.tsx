import { useState, useMemo } from "react";
import type { ParsedElement, BoundingBox, AssetRef, TableGridData, TableCellData } from "@/generated/api/types.gen";
import { ChevronRight, ChevronDown, Folder, FileText, Table, Image, Code } from "lucide-react";
import { sanitizeHtml } from "../lib/sanitize";

export type { ParsedElement, BoundingBox, AssetRef, TableGridData, TableCellData };

interface ElementsExplorerProps {
  elements: ParsedElement[];
  onElementClick?: (element: ParsedElement) => void;
  activeElement?: ParsedElement | null;
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
  code: "var(--badge-code, #8b5cf6)", // Purple/Indigo for Code block
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

  if (element.type === "code") {
    return (
      <pre
        style={{
          fontFamily: "monospace",
          background: "var(--bg-code-preview, #f1f5f9)",
          padding: "8px",
          borderRadius: "4px",
          margin: 0,
          fontSize: "12px",
          overflowX: "auto",
        }}
      >
        <code>{element.content}</code>
      </pre>
    );
  }

  return <>{element.content || <span className="empty-content-label">[Empty Content]</span>}</>;
}

interface ElementDetailsProps {
  element: ParsedElement;
  onCellHover?: (syntheticElement: ParsedElement | null) => void;
}

export function ElementDetails({ element, onCellHover }: ElementDetailsProps) {
  const renderTableGrid = (tableData: TableGridData) => {
    const { row_count, col_count, cells } = tableData;
    if (!cells || cells.length === 0) return <div style={{ fontSize: "11px", color: "var(--text-secondary)" }}>No cells metadata found.</div>;

    const grid: (TableCellData | "" | null)[][] = Array.from({ length: row_count }, () =>
      Array.from({ length: col_count }, () => "")
    );

    cells.forEach((cell: TableCellData) => {
      const row = cell.row_index;
      const col = cell.col_index;
      if (row < 0 || col < 0 || row >= row_count || col >= col_count) return;

      grid[row][col] = cell;

      const rowSpan = cell.row_span || 1;
      const colSpan = cell.col_span || 1;
      for (let r = row; r < Math.min(row + rowSpan, row_count); r++) {
        for (let c = col; c < Math.min(col + colSpan, col_count); c++) {
          if (r !== row || c !== col) {
            grid[r][c] = null;
          }
        }
      }
    });

    const handleCellMouseEnter = (cell: TableCellData) => {
      if (!cell.bbox) return;

      let pageNo = 1;
      const match = element.page_id ? element.page_id.match(/\d+/) : null;
      if (match && match[0].length < 10) {
        pageNo = parseInt(match[0], 10);
      }

      const syntheticElement: ParsedElement = {
        element_id: `${element.element_id}-cell-${cell.row_index}-${cell.col_index}`,
        type: "paragraph",
        format: "text",
        content: cell.content,
        page_id: element.page_id,
        order: element.order,
        bbox: cell.bbox,
        provenance: [{ page_no: pageNo, bbox: cell.bbox }],
        logical_role: "table_cell",
      };

      if (onCellHover) {
        onCellHover(syntheticElement);
      }
    };

    const handleCellMouseLeave = () => {
      if (onCellHover) {
        onCellHover(null);
      }
    };

    return (
      <div 
        style={{ 
          overflowX: "auto", 
          marginTop: "8px", 
          border: "1px solid var(--border-color, #dde3ea)", 
          borderRadius: "6px",
          background: "var(--bg-app, #f8fafc)"
        }}
      >
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "11px" }}>
          <tbody>
            {grid.map((row, rIdx) => (
              <tr key={`row-${rIdx}`} style={{ borderBottom: "1px solid var(--border-color, #dde3ea)" }}>
                {row.map((cell, cIdx) => {
                  if (cell === null) return null;
                  if (cell === "") {
                    return (
                      <td 
                        key={`empty-${rIdx}-${cIdx}`} 
                        style={{ border: "1px solid var(--border-color, #dde3ea)", padding: "4px" }} 
                      />
                    );
                  }

                  const isHeader = cell.cell_type === "header";
                  const CellTag = isHeader ? "th" : "td";

                  return (
                    <CellTag
                      key={`cell-${rIdx}-${cIdx}`}
                      rowSpan={cell.row_span}
                      colSpan={cell.col_span}
                      onMouseEnter={(e) => {
                        handleCellMouseEnter(cell);
                        if (cell.bbox) {
                          e.currentTarget.style.backgroundColor = "rgba(16, 185, 129, 0.1)";
                        }
                      }}
                      onMouseLeave={(e) => {
                        handleCellMouseLeave();
                        e.currentTarget.style.backgroundColor = isHeader ? "var(--bg-card-secondary, #f1f5f9)" : "var(--bg-card, #ffffff)";
                      }}
                      style={{
                        border: "1px solid var(--border-color, #dde3ea)",
                        padding: "6px",
                        background: isHeader ? "var(--bg-card-secondary, #f1f5f9)" : "var(--bg-card, #ffffff)",
                        color: "var(--text-primary)",
                        fontWeight: isHeader ? 700 : 400,
                        textAlign: isHeader ? "center" : "left",
                        cursor: cell.bbox ? "crosshair" : "default",
                        transition: "all 0.15s ease",
                      }}
                    >
                      {cell.content}
                    </CellTag>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="element-details" onClick={(e) => e.stopPropagation()}>
      <div className="details-grid">
        <div>
          <strong>ID:</strong> <code>{element.element_id}</code>
        </div>
        <div>
          <strong>Format:</strong> <code>{element.format}</code>
        </div>
        {element.logical_role && (
          <div>
            <strong>Logical Role:</strong> <code style={{ color: "var(--badge-heading, #6366f1)", fontWeight: "bold" }}>{element.logical_role}</code>
          </div>
        )}
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
        {element.children_ids && element.children_ids.length > 0 && (
          <div>
            <strong>Children IDs:</strong>{" "}
            <code>{element.children_ids.join(", ")}</code>
          </div>
        )}
      </div>
      {element.type === "table" && element.table_data && (
        <div className="table-grid-inspector-container" style={{ marginTop: "12px", marginBottom: "12px" }}>
          <strong style={{ fontSize: "12px", color: "var(--text-primary)" }}>Table Grid Inspector (Hover cells to highlight in PDF):</strong>
          {renderTableGrid(element.table_data)}
        </div>
      )}
      {element.format === "html" && element.content && (
        <div className="html-element-render-container" style={{ marginTop: "12px", marginBottom: "12px" }}>
          <strong>HTML Preview:</strong>
          <div className="html-element-render" dangerouslySetInnerHTML={{ __html: sanitizeHtml(element.content) }} />
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
      {element.metadata && Object.keys(element.metadata).length > 0 && (
        <div className="element-metadata-block">
          <strong>Metadata:</strong>
          <pre>{JSON.stringify(element.metadata, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

interface TreeNodeProps {
  element: ParsedElement;
  elementMap: Map<string, ParsedElement>;
  onElementClick?: (element: ParsedElement) => void;
  onCellHover?: (syntheticElement: ParsedElement | null) => void;
  expandedIds: Set<string>;
  toggleExpand: (id: string) => void;
  activeId?: string | null;
}

function TreeNodeComponent({
  element,
  elementMap,
  onElementClick,
  onCellHover,
  expandedIds,
  toggleExpand,
  activeId,
}: TreeNodeProps) {
  const [showDetails, setShowDetails] = useState(false);
  const isExpanded = expandedIds.has(element.element_id);
  const isActive = activeId === element.element_id;

  const childrenIds = element.children_ids || [];
  const children = childrenIds
    .map((id) => elementMap.get(id))
    .filter((el): el is ParsedElement => !!el)
    .sort((a, b) => a.order - b.order);

  const hasChildren = children.length > 0;

  const getIcon = () => {
    if (element.type === "heading") return <Folder size={15} style={{ color: "var(--badge-heading, #6366f1)", marginRight: "4px" }} />;
    if (element.type === "table") return <Table size={15} style={{ color: "var(--badge-table, #10b981)", marginRight: "4px" }} />;
    if (element.type === "image") return <Image size={15} style={{ color: "var(--badge-image, #f59e0b)", marginRight: "4px" }} />;
    if (element.type === "code") return <Code size={15} style={{ color: "var(--badge-code, #8b5cf6)", marginRight: "4px" }} />;
    return <FileText size={15} style={{ color: "var(--text-secondary)", marginRight: "4px" }} />;
  };

  const handleCardClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (element.type === "heading" && hasChildren) {
      toggleExpand(element.element_id);
    }
    if (onElementClick) {
      onElementClick(element);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <div
        onClick={handleCardClick}
        className={`element-card ${isActive ? "expanded" : ""} ${element.ignored ? "ignored" : ""}`}
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          padding: "10px 12px",
          marginBottom: "4px",
          borderRadius: "6px",
          border: isActive ? "2px solid var(--accent-color, #4f46e5)" : "1px solid var(--border-color, #dde3ea)",
          cursor: "pointer",
          background: isActive ? "var(--bg-card-active, #f5f3ff)" : "var(--bg-card, #ffffff)",
          boxShadow: isActive ? "0 2px 8px rgba(79, 70, 229, 0.15)" : "none",
          transition: "all 0.15s ease",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
          {hasChildren && (
            <span
              onClick={(e) => {
                e.stopPropagation();
                toggleExpand(element.element_id);
              }}
              style={{ 
                display: "flex", 
                alignItems: "center", 
                cursor: "pointer", 
                color: "var(--text-secondary)",
                padding: "2px",
                borderRadius: "4px",
                transition: "background 0.2s"
              }}
            >
              {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </span>
          )}
          {getIcon()}
          
          <span
            className="element-type-badge"
            style={{
              backgroundColor: getTypeColor(element.type),
              fontSize: "9px",
              padding: "1px 5px",
              borderRadius: "3px",
              color: "white",
              fontWeight: 600,
              textTransform: "uppercase"
            }}
          >
            {element.type}
          </span>

          {element.logical_role && (
            <span
              style={{
                fontSize: "9px",
                padding: "1px 5px",
                borderRadius: "3px",
                color: "var(--badge-heading, #6366f1)",
                background: "rgba(99, 102, 241, 0.1)",
                fontWeight: 600,
              }}
            >
              {element.logical_role}
            </span>
          )}

          {element.ignored && (
            <span className="element-ignored-badge" style={{ fontSize: "9px", padding: "1px 5px" }}>
              🚫 Ignored
            </span>
          )}

          <span style={{ fontSize: "9px", color: "var(--text-secondary)", marginLeft: "auto" }}>
            Order #{element.order}
          </span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setShowDetails((prev) => !prev);
            }}
            style={{
              background: showDetails ? "var(--accent-color, #4f46e5)" : "transparent",
              color: showDetails ? "white" : "var(--text-secondary)",
              border: "1px solid " + (showDetails ? "var(--accent-color, #4f46e5)" : "var(--border-color, #dde3ea)"),
              borderRadius: "4px",
              padding: "2px 6px",
              fontSize: "9px",
              fontWeight: 600,
              cursor: "pointer",
              transition: "all 0.2s",
            }}
          >
            {showDetails ? "Hide" : "Details"}
          </button>
        </div>

        <div className="element-content-preview" style={{ fontSize: "12px", color: "var(--text-primary)" }}>
          <ElementPreview element={element} />
        </div>

        {showDetails && (
          <ElementDetails 
            element={element} 
            onCellHover={onCellHover} 
          />
        )}
      </div>

      {hasChildren && isExpanded && (
        <div
          style={{
            paddingLeft: "12px",
            marginLeft: "8px",
            borderLeft: "1px dashed var(--border-color, #dde3ea)",
            display: "flex",
            flexDirection: "column",
            gap: "2px",
            marginTop: "2px",
            marginBottom: "4px",
          }}
        >
          {children.map((child) => (
            <TreeNodeComponent
              key={child.element_id}
              element={child}
              elementMap={elementMap}
              onElementClick={onElementClick}
              onCellHover={onCellHover}
              expandedIds={expandedIds}
              toggleExpand={toggleExpand}
              activeId={activeId}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface FlatElementCardProps {
  element: ParsedElement;
  isActive: boolean;
  onElementClick?: (element: ParsedElement) => void;
}

function FlatElementCard({ element, isActive, onElementClick }: FlatElementCardProps) {
  const [showDetails, setShowDetails] = useState(false);

  const handleCardClick = () => {
    if (onElementClick) {
      onElementClick(element);
    }
  };

  return (
    <div
      className={`element-card ${showDetails ? "expanded" : ""} ${element.ignored ? "ignored" : ""}`}
      onClick={handleCardClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          handleCardClick();
        }
      }}
      style={{
        border: isActive ? "2px solid var(--accent-color, #4f46e5)" : "1px solid var(--border-color, #dde3ea)",
        background: isActive ? "var(--bg-card-active, #f5f3ff)" : "var(--bg-card, #ffffff)",
        padding: "10px 12px",
        borderRadius: "6px",
        cursor: "pointer",
        transition: "all 0.15s ease",
      }}
    >
      <div className="element-meta" style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
        <span
          className="element-type-badge"
          style={{ backgroundColor: getTypeColor(element.type), fontSize: "9px" }}
        >
          {element.type}
        </span>
        {element.ignored && (
          <span className="element-ignored-badge" style={{ fontSize: "9px" }}>
            🚫 Ignored
          </span>
        )}
        <span className="element-order" style={{ fontSize: "9px" }}>Order #{element.order}</span>
        {element.page_id && (
          <span className="element-page" style={{ fontSize: "9px" }}>
            Page {element.page_id.split("-").pop() || element.page_id}
          </span>
        )}
        {element.level !== undefined && element.level !== null && (
          <span className="element-level" style={{ fontSize: "9px" }}>Lvl {element.level}</span>
        )}
        
        <button
          onClick={(e) => {
            e.stopPropagation();
            setShowDetails(prev => !prev);
          }}
          style={{
            marginLeft: "auto",
            background: showDetails ? "var(--accent-color, #4f46e5)" : "transparent",
            color: showDetails ? "white" : "var(--text-secondary)",
            border: "1px solid " + (showDetails ? "var(--accent-color, #4f46e5)" : "var(--border-color, #dde3ea)"),
            borderRadius: "4px",
            padding: "2px 8px",
            fontSize: "9px",
            fontWeight: 600,
            cursor: "pointer",
            transition: "all 0.2s",
          }}
        >
          {showDetails ? "Hide" : "Details"}
        </button>
      </div>

      <div className="element-content-preview" style={{ fontSize: "12px", color: "var(--text-primary)", marginTop: "6px" }}>
        <ElementPreview element={element} />
      </div>

      {showDetails && (
        <ElementDetails
          element={element}
          onCellHover={(syntheticEl) => {
            if (onElementClick) {
              onElementClick(syntheticEl || element);
            }
          }}
        />
      )}
    </div>
  );
}

export function ElementsExplorer({ elements, onElementClick, activeElement }: ElementsExplorerProps) {
  const [viewMode, setViewMode] = useState<"tree" | "flat">("tree");
  const [selectedType, setSelectedType] = useState<string>("all");
  const [selectedRole, setSelectedRole] = useState<string>("all");
  const [expandedTreeIds, setExpandedTreeIds] = useState<Set<string>>(new Set());
  const [hideIgnored, setHideIgnored] = useState<boolean>(false);

  const [prevActiveElement, setPrevActiveElement] = useState<ParsedElement | null>(null);

  // Sync active element from parent component to auto-expand tree path (derived state update during render)
  if (activeElement !== prevActiveElement) {
    setPrevActiveElement(activeElement || null);
    if (activeElement) {
      const next = new Set(expandedTreeIds);
      let curr: string | undefined | null = activeElement.parent_id;
      while (curr) {
        next.add(curr);
        const parentEl = elements.find((el) => el.element_id === curr);
        curr = parentEl?.parent_id;
      }
      setExpandedTreeIds(next);
    }
  }

  const toggleTreeExpand = (id: string) => {
    setExpandedTreeIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const elementTypes = useMemo(() => ["all", ...Array.from(new Set(elements.map((el) => el.type)))], [elements]);

  const logicalRoles = useMemo(() => {
    const roles = new Set<string>();
    elements.forEach((el) => {
      if (el.logical_role) {
        roles.add(el.logical_role);
      }
    });
    return ["all", ...Array.from(roles)];
  }, [elements]);

  const sortedElements = useMemo(() => [...elements].sort((a, b) => a.order - b.order), [elements]);

  const elementMap = useMemo(() => new Map(elements.map((el) => [el.element_id, el])), [elements]);

  // Tree roots logic
  const roots = useMemo(() => {
    const list = hideIgnored ? sortedElements.filter((el) => !el.ignored) : sortedElements;
    const elementIds = new Set(list.map((el) => el.element_id));
    return list.filter((el) => !el.parent_id || !elementIds.has(el.parent_id));
  }, [sortedElements, hideIgnored]);

  // Flat list filters
  const typeFilteredElements = useMemo(() =>
    selectedType === "all" ? sortedElements : sortedElements.filter((el) => el.type === selectedType),
    [sortedElements, selectedType]
  );

  const roleFilteredElements = useMemo(() =>
    selectedRole === "all" ? typeFilteredElements : typeFilteredElements.filter((el) => el.logical_role === selectedRole),
    [typeFilteredElements, selectedRole]
  );

  const filteredElements = useMemo(() =>
    hideIgnored ? roleFilteredElements.filter((el) => !el.ignored) : roleFilteredElements,
    [roleFilteredElements, hideIgnored]
  );


  const activeId = activeElement?.element_id;

  return (
    <div className="elements-explorer" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div className="explorer-header" style={{ flexShrink: 0, paddingBottom: "12px", borderBottom: "1px solid var(--border-color, #dde3ea)" }}>
        {/* Toggle Mode Tabs */}
        <div style={{ display: "flex", gap: "4px", background: "var(--bg-app, #f8fafc)", padding: "4px", borderRadius: "8px", marginBottom: "12px" }}>
          <button
            onClick={() => setViewMode("tree")}
            style={{
              flex: 1,
              padding: "6px 12px",
              borderRadius: "6px",
              border: "none",
              background: viewMode === "tree" ? "var(--bg-card, #ffffff)" : "transparent",
              color: viewMode === "tree" ? "var(--accent-color, #4f46e5)" : "var(--text-secondary)",
              fontWeight: 700,
              fontSize: "11px",
              cursor: "pointer",
              boxShadow: viewMode === "tree" ? "0 2px 4px rgba(0,0,0,0.05)" : "none",
              transition: "all 0.15s ease",
            }}
          >
            Tree Outline
          </button>
          <button
            onClick={() => setViewMode("flat")}
            style={{
              flex: 1,
              padding: "6px 12px",
              borderRadius: "6px",
              border: "none",
              background: viewMode === "flat" ? "var(--bg-card, #ffffff)" : "transparent",
              color: viewMode === "flat" ? "var(--accent-color, #4f46e5)" : "var(--text-secondary)",
              fontWeight: 700,
              fontSize: "11px",
              cursor: "pointer",
              boxShadow: viewMode === "flat" ? "0 2px 4px rgba(0,0,0,0.05)" : "none",
              transition: "all 0.15s ease",
            }}
          >
            Filter List
          </button>
        </div>

        {/* Global Toolbar */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
          <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-secondary)" }}>
            {viewMode === "tree" ? `Outline Roots (${roots.length})` : `Matched Elements (${filteredElements.length})`}
          </span>

          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            {/* Flat list filters */}
            {viewMode === "flat" && logicalRoles.length > 1 && (
              <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                <span style={{ fontSize: "11px", color: "var(--text-secondary)" }}>Role:</span>
                <select
                  value={selectedRole}
                  onChange={(e) => setSelectedRole(e.target.value)}
                  style={{
                    fontSize: "11px",
                    background: "var(--bg-card, #ffffff)",
                    border: "1px solid var(--border-color, #dde3ea)",
                    borderRadius: "4px",
                    padding: "2px 4px",
                    color: "var(--text-primary)",
                    outline: "none",
                  }}
                >
                  {logicalRoles.map((role) => (
                    <option key={role} value={role}>
                      {role === "all" ? "All Roles" : role}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Elegant Toggle Switch for Hiding Ignored Elements */}
            <label className="ignored-toggle-container">
              <input
                type="checkbox"
                checked={hideIgnored}
                onChange={(e) => setHideIgnored(e.target.checked)}
              />
              <span className="ignored-switch" />
              <span className="ignored-toggle-label">Hide Ignored</span>
            </label>
          </div>
        </div>

        {/* Sleek element filter bar (Only for flat list mode) */}
        {viewMode === "flat" && (
          <div className="filter-tags" style={{ marginTop: "10px", display: "flex", gap: "4px", overflowX: "auto" }}>
            {elementTypes.map((type) => (
              <button
                key={type}
                onClick={() => setSelectedType(type)}
                className={`filter-tag ${selectedType === type ? "active" : ""}`}
                type="button"
                style={{ fontSize: "10px", padding: "3px 8px" }}
              >
                {type}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Body scroll area */}
      <div 
        className="elements-list" 
        style={{ 
          flex: 1, 
          overflowY: "auto", 
          paddingTop: "12px", 
          display: "flex", 
          flexDirection: "column", 
          gap: "8px" 
        }}
      >
        {viewMode === "tree" ? (
          roots.length === 0 ? (
            <div className="no-elements">No structural outline roots found.</div>
          ) : (
            roots.map((el) => (
              <TreeNodeComponent
                key={el.element_id}
                element={el}
                elementMap={elementMap}
                onElementClick={onElementClick}
                onCellHover={(syntheticEl) => {
                  if (onElementClick) {
                    onElementClick(syntheticEl || el);
                  }
                }}
                expandedIds={expandedTreeIds}
                toggleExpand={toggleTreeExpand}
                activeId={activeId}
              />
            ))
          )
        ) : filteredElements.length === 0 ? (
          <div className="no-elements">No elements matched the filters.</div>
        ) : (
          filteredElements.map((el) => {
            const isActive = activeId === el.element_id;
            return (
              <FlatElementCard
                key={el.element_id}
                element={el}
                isActive={isActive}
                onElementClick={onElementClick}
              />
            );
          })
        )}
      </div>
    </div>
  );
}
