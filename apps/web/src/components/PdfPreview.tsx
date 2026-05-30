import { useEffect, useState } from "react";
import { Viewer, Worker } from "@react-pdf-viewer/core";
import { defaultLayoutPlugin } from "@react-pdf-viewer/default-layout";
import { highlightPlugin, RenderHighlightsProps } from "@react-pdf-viewer/highlight";
import "@react-pdf-viewer/core/lib/styles/index.css";
import "@react-pdf-viewer/default-layout/lib/styles/index.css";
import "@react-pdf-viewer/highlight/lib/styles/index.css";

type PdfPreviewProps = {
  fileName: string;
  fileUrl?: string;
  activeElement?: any;
  parsedDoc?: any;
};

const workerUrl = new URL("pdfjs-dist/build/pdf.worker.min.js", import.meta.url).toString();

export function PdfPreview({ fileName, fileUrl, activeElement, parsedDoc }: PdfPreviewProps) {
  const [docLoaded, setDocLoaded] = useState(false);
  const [numPages, setNumPages] = useState(0);

  const defaultLayoutPluginInstance = defaultLayoutPlugin();

  const getPageInfo = (element: any) => {
    let targetIndex = 0;
    let width = 612;
    let height = 792;
    
    if (parsedDoc && parsedDoc.pages && Array.isArray(parsedDoc.pages)) {
      const page = parsedDoc.pages.find((p: any) => p.page_id === element.page_id);
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
  };

  const renderHighlights = (props: RenderHighlightsProps) => {
    if (!activeElement || !activeElement.bbox || !activeElement.page_id) return <></>;

    const { targetIndex, width: pdfPageWidthPoints, height: pdfPageHeightPoints } = getPageInfo(activeElement);

    if (props.pageIndex !== targetIndex) return <></>;

    const { bbox } = activeElement;

    const leftPercent = (bbox.left / pdfPageWidthPoints) * 100;
    let topPercent = (bbox.top / pdfPageHeightPoints) * 100;
    
    const isBottomLeftOrigin = bbox.coord_origin === "BottomLeft";
    if (isBottomLeftOrigin) {
      topPercent = ((pdfPageHeightPoints - bbox.top) / pdfPageHeightPoints) * 100;
    }
    
    const widthPercent = ((bbox.right - bbox.left) / pdfPageWidthPoints) * 100;
    const heightPercent = ((bbox.bottom - bbox.top) / pdfPageHeightPoints) * 100;
    const absHeightPercent = Math.abs(heightPercent);

    const finalTopPercent = isBottomLeftOrigin ? topPercent - absHeightPercent : topPercent;

    return (
      <div
        style={{
          position: "absolute",
          left: `${leftPercent}%`,
          top: `${finalTopPercent}%`,
          width: `${widthPercent}%`,
          height: `${absHeightPercent}%`,
          background: "rgba(255, 99, 71, 0.25)",
          border: "2px solid tomato",
          borderRadius: "4px",
          pointerEvents: "none",
          zIndex: 100,
        }}
      />
    );
  };

  const highlightPluginInstance = highlightPlugin({
    renderHighlights,
  });

  const { jumpToHighlightArea } = highlightPluginInstance;

  useEffect(() => {
    // Only attempt to jump if the document is fully loaded and we have pages
    if (docLoaded && numPages > 0 && activeElement && activeElement.page_id && activeElement.bbox) {
      const { targetIndex, width: pdfPageWidthPoints, height: pdfPageHeightPoints } = getPageInfo(activeElement);
      
      // Ensure target index is within bounds to prevent "Invalid page request" error
      if (targetIndex < 0 || targetIndex >= numPages) {
        console.warn(`Highlight target page ${targetIndex} is out of bounds (0 - ${numPages - 1})`);
        return;
      }

      const { bbox } = activeElement;

      const leftPercent = (bbox.left / pdfPageWidthPoints) * 100;
      let topPercent = (bbox.top / pdfPageHeightPoints) * 100;
      
      const isBottomLeftOrigin = bbox.coord_origin === "BottomLeft";
      if (isBottomLeftOrigin) {
        topPercent = ((pdfPageHeightPoints - bbox.top) / pdfPageHeightPoints) * 100;
      }
      const finalTopPercent = isBottomLeftOrigin ? topPercent - Math.abs(((bbox.bottom - bbox.top) / pdfPageHeightPoints) * 100) : topPercent;

      // Small delay ensures viewer layout is settled before jumping
      const timer = setTimeout(() => {
        try {
          jumpToHighlightArea({
            pageIndex: targetIndex,
            left: leftPercent,
            top: finalTopPercent,
            width: ((bbox.right - bbox.left) / pdfPageWidthPoints) * 100,
            height: Math.abs(((bbox.bottom - bbox.top) / pdfPageHeightPoints) * 100),
          });
        } catch (e) {
          console.warn("Failed to jump to highlight area", e);
        }
      }, 50);

      return () => clearTimeout(timer);
    }
  }, [activeElement, jumpToHighlightArea, docLoaded, numPages, parsedDoc]);

  if (!fileUrl) {
    return (
      <div className="empty-state">
        <h2>PDF original viewer</h2>
        <p>Select a PDF file from the left to open the original viewer.</p>
      </div>
    );
  }

  return (
    <div className="pdf-frame" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <Worker workerUrl={workerUrl}>
        <Viewer 
          fileUrl={fileUrl} 
          plugins={[defaultLayoutPluginInstance, highlightPluginInstance]} 
          defaultScale={0.9}
          onDocumentLoad={(e) => {
            setDocLoaded(true);
            setNumPages(e.doc.numPages);
          }}
        />
      </Worker>
    </div>
  );
}
