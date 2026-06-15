import { useEffect, useState, useRef, useCallback, useMemo } from "react";
import type { ParsedElement } from "./ElementsExplorer";
import type { ParsedPage, BoundingBox } from "@/generated/api/types.gen";
import { Document, Page, pdfjs } from "react-pdf";
import styles from "./PdfPreview.module.css";
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

  const [showSectionBoundaries, setShowSectionBoundaries] = useState(true);

  const childElements = useMemo(() => {
    if (!activeElement || !parsedDoc?.elements || !showSectionBoundaries) return [];

    const elementsList = parsedDoc.elements;
    const result: ParsedElement[] = [];
    const queue = [...(activeElement.children_ids || [])];
    const visited = new Set<string>();

    while (queue.length > 0) {
      const currentId = queue.shift()!;
      if (visited.has(currentId)) continue;
      visited.add(currentId);

      const found = elementsList.find((el) => el.element_id === currentId);
      if (found) {
        result.push(found);
        if (found.children_ids) {
          queue.push(...found.children_ids);
        }
      }
    }
    return result;
  }, [activeElement, parsedDoc, showSectionBoundaries]);

  const getPageInfoByPageNo = useCallback((pageNo: number) => {
    let targetIndex = pageNo - 1;
    let width = 612;
    let height = 792;

    if (parsedDoc && parsedDoc.pages && Array.isArray(parsedDoc.pages)) {
      const page = parsedDoc.pages.find((p) => p.page_no === pageNo);
      if (page) {
        targetIndex = page.page_no - 1;
        if (page.width) width = page.width;
        if (page.height) height = page.height;
      }
    }
    return { targetIndex, width, height };
  }, [parsedDoc]);

  const getPageInfo = useCallback((element: ParsedElement) => {
    let targetIndex = 0;
    let width = 612;
    let height = 792;

    if (parsedDoc && parsedDoc.pages && Array.isArray(parsedDoc.pages)) {
      const page = parsedDoc.pages.find((p) => p.page_id === element.page_id);
      if (page) {
        targetIndex = page.page_no - 1;
        if (page.width) width = page.width;
        if (page.height) height = page.height;
        return { targetIndex, width, height };
      }
    }

    const match = element.page_id ? element.page_id.match(/\d+/) : null;
    if (match && match[0].length < 10) {
      targetIndex = parseInt(match[0], 10) - 1;
    }

    return { targetIndex, width, height };
  }, [parsedDoc]);

  const getHighlightColor = useCallback((element: ParsedElement) => {
    const role = element.logical_role || element.type;
    switch (role?.toLowerCase()) {
      case "heading":
      case "title":
      case "sectionheading":
        return {
          bg: "rgba(99, 102, 241, 0.15)",
          bgChild: "rgba(99, 102, 241, 0.05)",
          border: "#6366f1",
          shadow: "rgba(99, 102, 241, 0.25)",
        };
      case "table":
      case "table_cell":
        return {
          bg: "rgba(16, 185, 129, 0.15)",
          bgChild: "rgba(16, 185, 129, 0.05)",
          border: "#10b981",
          shadow: "rgba(16, 185, 129, 0.25)",
        };
      case "footnote":
      case "caption":
        return {
          bg: "rgba(249, 115, 22, 0.15)",
          bgChild: "rgba(249, 115, 22, 0.05)",
          border: "#f97316",
          shadow: "rgba(249, 115, 22, 0.25)",
        };
      case "image":
      case "picture":
        return {
          bg: "rgba(168, 85, 247, 0.15)",
          bgChild: "rgba(168, 85, 247, 0.05)",
          border: "#a855f7",
          shadow: "rgba(168, 85, 247, 0.25)",
        };
      default:
        return {
          bg: "rgba(79, 70, 229, 0.15)",
          bgChild: "rgba(79, 70, 229, 0.05)",
          border: "#4f46e5",
          shadow: "rgba(79, 70, 229, 0.25)",
        };
    }
  }, []);

  const renderHighlightsForPage = (pageIndex: number) => {
    if (!activeElement) return null;

    const highlights: React.ReactNode[] = [];
    const colors = getHighlightColor(activeElement);

    const addHighlightsForElement = (el: ParsedElement, isChild: boolean, elIdx: string) => {
      const elementColors = getHighlightColor(el);

      const renderSingleBox = (bbox: BoundingBox, pageNo: number, boxKey: string) => {
        const targetPageIndex = pageNo - 1;
        if (pageIndex !== targetPageIndex) return;

        const { width: pageWidth, height: pageHeight } = getPageInfoByPageNo(pageNo);

        const leftPercent = (bbox.left / pageWidth) * 100;
        const topPercent = (bbox.top / pageHeight) * 100;
        const widthPercent = ((bbox.right - bbox.left) / pageWidth) * 100;
        const heightPercent = ((bbox.bottom - bbox.top) / pageHeight) * 100;

        highlights.push(
          <div
            key={boxKey}
            style={{
              position: "absolute",
              left: `calc(${leftPercent}% - 3px)`,
              top: `calc(${topPercent}% - 3px)`,
              width: `calc(${widthPercent}% + 6px)`,
              height: `calc(${heightPercent}% + 6px)`,
              background: isChild ? (elementColors.bgChild || "rgba(79, 70, 229, 0.05)") : colors.bg,
              border: isChild 
                ? `1.5px dashed ${elementColors.border}` 
                : `2px solid ${colors.border}`,
              borderRadius: "4px",
              boxSizing: "border-box",
              pointerEvents: "none",
              zIndex: isChild ? 5 : 10,
              boxShadow: isChild ? "none" : `0 0 6px ${colors.shadow}`,
            }}
          />
        );
      };

      if (el.provenance && el.provenance.length > 0) {
        el.provenance.forEach((prov, idx) => {
          if (!prov.bbox || prov.page_no === undefined || prov.page_no === null) return;
          renderSingleBox(prov.bbox, prov.page_no, `highlight-${elIdx}-${idx}`);
        });
      } else if (el.bbox && el.page_id) {
        const { targetIndex } = getPageInfo(el);
        renderSingleBox(el.bbox, targetIndex + 1, `highlight-${elIdx}-fallback`);
      }
    };

    // 1. Render children highlights first (behind the active element highlight)
    childElements.forEach((childEl: ParsedElement) => {
      if (childEl.element_id === activeElement.element_id) return;
      addHighlightsForElement(childEl, true, childEl.element_id);
    });

    // 2. Render active element highlight
    addHighlightsForElement(activeElement, false, "active");

    return highlights.length > 0 ? <>{highlights}</> : null;
  };

  // Scroll to activeElement bounding box when activeElement changes
  useEffect(() => {
    if (docLoaded && numPages && numPages > 0 && activeElement) {
      let bbox = activeElement.bbox;
      let targetPageIndex = -1;
      let targetPageHeightPoints = 792;

      if (activeElement.provenance && activeElement.provenance.length > 0) {
        const firstProv = activeElement.provenance.find(p => p.bbox && p.page_no !== undefined && p.page_no !== null);
        if (firstProv) {
          bbox = firstProv.bbox;
          targetPageIndex = firstProv.page_no! - 1;
          const pageInfo = getPageInfoByPageNo(firstProv.page_no!);
          targetPageHeightPoints = pageInfo.height;
        }
      }

      if (targetPageIndex === -1 && activeElement.bbox && activeElement.page_id) {
        const pageInfo = getPageInfo(activeElement);
        targetPageIndex = pageInfo.targetIndex;
        targetPageHeightPoints = pageInfo.height;
      }

      if (targetPageIndex < 0 || targetPageIndex >= numPages || !bbox) {
        return;
      }

      // 100ms timeout ensures standard react-pdf render lifecycle finishes layout first
      const timer = setTimeout(() => {
        try {
          const pageWrapper = document.querySelector(`[data-page-index="${targetPageIndex}"]`);
          const container = scrollContainerRef.current;

          if (pageWrapper && container) {
            const bboxTopPercent = bbox.top / targetPageHeightPoints;
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
  }, [activeElement, docLoaded, numPages, getPageInfo, getPageInfoByPageNo]);

  if (!fileUrl) {
    return (
      <div className="empty-state">
        <h2>PDF original viewer</h2>
        <p>Select a PDF file from the left to open the original viewer.</p>
      </div>
    );
  }

  return (
    <div className={styles.pdfFrame}>
      {/* Premium Glassmorphic Toolbar */}
      <div className={styles.toolbar}>
        <div className={styles.fileNameBlock}>
          <span className={styles.fileName}>
            {fileName}
          </span>
          {numPages && (
            <span className={styles.pageCountBadge}>
              {numPages} Pages
            </span>
          )}
        </div>
        
        {/* View Mode Segmented Controls */}
        <div className={styles.viewModeControls}>
          <span className={styles.viewModeLabel}>
            View:
          </span>
          <div className={styles.segmentedControl}>
            <button
              onClick={() => setShowSectionBoundaries(false)}
              title="Show only the selected element outline"
              className={`${styles.segmentedButton} ${!showSectionBoundaries ? styles.segmentedButtonActive : ""}`}
            >
              Selected
            </button>
            <button
              onClick={() => setShowSectionBoundaries(true)}
              title="Show selected element outline and its children sections"
              className={`${styles.segmentedButton} ${showSectionBoundaries ? styles.segmentedButtonActive : ""}`}
            >
              Section + Children
            </button>
          </div>
        </div>

        {/* Zoom Controls */}
        <div className={styles.zoomControls}>
          <button
            onClick={() => setScale(prev => Math.max(0.5, prev - 0.1))}
            title="Zoom Out"
            className={styles.toolbarButton}
          >
            <ZoomOut size={15} />
          </button>
          
          <span className={styles.zoomText}>
            {Math.round(scale * 100)}%
          </span>
          
          <button
            onClick={() => setScale(prev => Math.min(2.5, prev + 0.1))}
            title="Zoom In"
            className={styles.toolbarButton}
          >
            <ZoomIn size={15} />
          </button>
          
          <button
            onClick={() => setScale(0.9)}
            title="Reset Zoom"
            className={styles.toolbarButton}
          >
            <RotateCcw size={15} />
          </button>
        </div>
      </div>

      {/* PDF Viewport Scroll Area */}
      <div
        ref={scrollContainerRef}
        className={styles.viewportScrollArea}
      >
        <Document
          file={fileUrl}
          onLoadSuccess={(pdf) => {
            setDocLoaded(true);
            setNumPages(pdf.numPages);
          }}
          loading={
            <div className={styles.statusContainer}>
              <div className={`spinner ${styles.loadingSpinner}`} />
              <p className={styles.statusText}>Loading PDF...</p>
            </div>
          }
          error={
            <div className={styles.statusContainer}>
              <AlertCircle size={32} color="var(--accent-color)" />
              <p className={styles.errorText}>Failed to load PDF</p>
            </div>
          }
        >
          {Array.from(new Array(numPages || 0), (_, index) => (
            <div
              key={`page_${index + 1}`}
              data-page-index={index}
              className={styles.pageContainer}
            >
              <Page
                pageNumber={index + 1}
                scale={scale}
                renderAnnotationLayer={false}
                renderTextLayer={false}
                loading={
                  <div className={styles.pageLoadingPlaceholder} style={{ width: 612 * scale, height: 792 * scale }}>
                    <div className={`spinner ${styles.loadingSpinner}`} />
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
