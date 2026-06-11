import { useEffect, useState, useRef, useCallback } from "react";
import type { ParsedElement } from "./ElementsExplorer";
import type { ParsedPage } from "@/generated/api/types.gen";
import { Document, Page, pdfjs } from "react-pdf";
import pdfWorkerSrc from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { ZoomIn, ZoomOut, RotateCcw, AlertCircle } from "lucide-react";

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorkerSrc;

type PdfPreviewProps = {
  fileName: string;
  fileUrl?: string;
  activeElement?: ParsedElement | null;
  parsedDoc?: { elements?: ParsedElement[]; pages?: ParsedPage[] } | null;
};

export function PdfPreview({ fileName, fileUrl, activeElement, parsedDoc }: PdfPreviewProps) {
  const [docLoaded, setDocLoaded] = useState(false);
  const [numPages, setNumPages] = useState<number | null>(null);
  const [scale, setScale] = useState(0.9);
  
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const getPageInfo = useCallback((element: ParsedElement) => {
    let targetIndex = 0;
    let width = 612;
    let height = 792;

    if (parsedDoc && parsedDoc.pages && Array.isArray(parsedDoc.pages)) {
      const page = parsedDoc.pages.find((p) => p.page_id === element.page_id);
      if (page) {
        // page_no is 1-indexed in Docling
        targetIndex = page.page_no - 1;
        if (page.width) width = page.width;
        if (page.height) height = page.height;
        return { targetIndex, width, height };
      }
    }

    // Fallback if parsedDoc not provided or page_id not found
    const match = element.page_id ? element.page_id.match(/\d+/) : null;
    if (match && match[0].length < 10) {
      targetIndex = parseInt(match[0], 10) - 1;
    }

    return { targetIndex, width, height };
  }, [parsedDoc]);

  const renderHighlightsForPage = (pageIndex: number) => {
    if (!activeElement || !activeElement.bbox || !activeElement.page_id) return null;

    const { targetIndex, width: pdfPageWidthPoints, height: pdfPageHeightPoints } = getPageInfo(activeElement);

    if (pageIndex !== targetIndex) return null;

    const { bbox } = activeElement;

    // Backend normalizes all bbox to TOPLEFT origin, so no Y-axis inversion needed
    const leftPercent = (bbox.left / pdfPageWidthPoints) * 100;
    const topPercent = (bbox.top / pdfPageHeightPoints) * 100;
    const widthPercent = ((bbox.right - bbox.left) / pdfPageWidthPoints) * 100;
    const heightPercent = ((bbox.bottom - bbox.top) / pdfPageHeightPoints) * 100;

    return (
      <div
        style={{
          position: "absolute",
          left: `calc(${leftPercent}% - 3px)`,
          top: `calc(${topPercent}% - 3px)`,
          width: `calc(${widthPercent}% + 6px)`,
          height: `calc(${heightPercent}% + 6px)`,
          background: "var(--highlight-bg, rgba(79, 70, 229, 0.15))",
          border: "2px solid var(--accent-color, #4f46e5)",
          borderRadius: "4px",
          boxSizing: "border-box",
          pointerEvents: "none",
          zIndex: 10,
          boxShadow: "0 0 6px rgba(79, 70, 229, 0.25)",
        }}
      />
    );
  };

  // Scroll to activeElement bounding box when activeElement changes
  useEffect(() => {
    if (docLoaded && numPages && numPages > 0 && activeElement && activeElement.page_id && activeElement.bbox) {
      const { targetIndex, height: pdfPageHeightPoints } = getPageInfo(activeElement);

      if (targetIndex < 0 || targetIndex >= numPages) {
        console.warn(`Highlight target page ${targetIndex} is out of bounds (0 - ${numPages - 1})`);
        return;
      }

      const bbox = activeElement.bbox;
      if (!bbox) return;

      // 100ms timeout ensures standard react-pdf render lifecycle finishes layout first
      const timer = setTimeout(() => {
        try {
          const pageWrapper = document.querySelector(`[data-page-index="${targetIndex}"]`);
          const container = scrollContainerRef.current;
          
          if (pageWrapper && container) {
            const bboxTopPercent = bbox.top / pdfPageHeightPoints;
            const pageHeight = pageWrapper.clientHeight;
            const scrollOffsetInPage = pageHeight * bboxTopPercent;

            const elementTop = (pageWrapper as HTMLElement).offsetTop;
            // Center vertically within viewport by subtracting ~35% of visible container height
            const viewportOffset = container.clientHeight * 0.35;
            const targetScrollTop = Math.max(0, elementTop + scrollOffsetInPage - viewportOffset);

            container.scrollTo({
              top: targetScrollTop,
              behavior: "smooth",
            });
          }
        } catch (e) {
          console.warn("Failed to jump to highlight area", e);
        }
      }, 100);

      return () => clearTimeout(timer);
    }

    return undefined;
  }, [activeElement, docLoaded, numPages, getPageInfo]);

  if (!fileUrl) {
    return (
      <div className="empty-state">
        <h2>PDF original viewer</h2>
        <p>Select a PDF file from the left to open the original viewer.</p>
      </div>
    );
  }

  return (
    <div className="pdf-frame" style={{ height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      {/* Premium Glassmorphic Toolbar */}
      <div 
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          background: "var(--bg-card)",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
          borderBottom: "1px solid var(--border-color)",
          padding: "8px 16px",
          zIndex: 10,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: 0 }}>
          <span 
            style={{ 
              fontSize: "14px", 
              fontWeight: 700, 
              color: "var(--text-primary)",
              textOverflow: "ellipsis",
              overflow: "hidden",
              whiteSpace: "nowrap"
            }}
          >
            {fileName}
          </span>
          {numPages && (
            <span 
              style={{ 
                fontSize: "11px", 
                color: "var(--text-secondary)", 
                background: "var(--border-color)", 
                padding: "2px 6px", 
                borderRadius: "4px",
                whiteSpace: "nowrap"
              }}
            >
              {numPages} Pages
            </span>
          )}
        </div>
        
        {/* Zoom Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <button
            onClick={() => setScale(prev => Math.max(0.5, prev - 0.1))}
            title="Zoom Out"
            style={{
              background: "transparent",
              border: "1px solid var(--border-color)",
              borderRadius: "6px",
              padding: "6px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--text-secondary)",
              transition: "all 0.2s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = "var(--accent-color)";
              e.currentTarget.style.color = "var(--text-primary)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = "var(--border-color)";
              e.currentTarget.style.color = "var(--text-secondary)";
            }}
          >
            <ZoomOut size={15} />
          </button>
          
          <span style={{ fontSize: "12px", fontWeight: 600, minWidth: "40px", textAlign: "center", color: "var(--text-primary)" }}>
            {Math.round(scale * 100)}%
          </span>
          
          <button
            onClick={() => setScale(prev => Math.min(2.5, prev + 0.1))}
            title="Zoom In"
            style={{
              background: "transparent",
              border: "1px solid var(--border-color)",
              borderRadius: "6px",
              padding: "6px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--text-secondary)",
              transition: "all 0.2s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = "var(--accent-color)";
              e.currentTarget.style.color = "var(--text-primary)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = "var(--border-color)";
              e.currentTarget.style.color = "var(--text-secondary)";
            }}
          >
            <ZoomIn size={15} />
          </button>
          
          <button
            onClick={() => setScale(0.9)}
            title="Reset Zoom"
            style={{
              background: "transparent",
              border: "1px solid var(--border-color)",
              borderRadius: "6px",
              padding: "6px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--text-secondary)",
              transition: "all 0.2s",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = "var(--accent-color)";
              e.currentTarget.style.color = "var(--text-primary)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = "var(--border-color)";
              e.currentTarget.style.color = "var(--text-secondary)";
            }}
          >
            <RotateCcw size={15} />
          </button>
        </div>
      </div>

      {/* PDF Viewport Scroll Area */}
      <div
        ref={scrollContainerRef}
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "24px 16px",
          background: "var(--bg-app)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "24px",
          position: "relative",
        }}
      >
        <Document
          file={fileUrl}
          onLoadSuccess={(pdf) => {
            setDocLoaded(true);
            setNumPages(pdf.numPages);
          }}
          loading={
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "12px", padding: "48px" }}>
              <div className="spinner" />
              <p style={{ color: "var(--text-secondary)", fontSize: "13px" }}>Loading PDF...</p>
            </div>
          }
          error={
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "12px", padding: "48px", color: "var(--text-secondary)" }}>
              <AlertCircle size={32} color="var(--accent-color)" />
              <p style={{ fontSize: "13px", fontWeight: 600 }}>Failed to load PDF</p>
            </div>
          }
        >
          {Array.from(new Array(numPages || 0), (_, index) => (
            <div
              key={`page_${index + 1}`}
              data-page-index={index}
              style={{
                position: "relative",
                boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.05)",
                borderRadius: "8px",
                overflow: "hidden",
                border: "1px solid var(--border-color)",
                background: "#ffffff",
                transition: "transform 0.2s ease",
              }}
            >
              <Page
                pageNumber={index + 1}
                scale={scale}
                renderAnnotationLayer={false}
                renderTextLayer={false}
                loading={
                  <div style={{ width: 612 * scale, height: 792 * scale, background: "#f8fafc", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <div className="spinner" style={{ width: "24px", height: "24px", borderWidth: "2px" }} />
                  </div>
                }
              />
              {renderHighlightsForPage(index)}
            </div>
          ))}
        </Document>
      </div>
    </div>
  );
}
