import { Viewer, Worker } from "@react-pdf-viewer/core";

type PdfPreviewProps = {
  fileName: string;
  fileUrl?: string;
};

const workerUrl = new URL("pdfjs-dist/build/pdf.worker.min.js", import.meta.url).toString();

export function PdfPreview({ fileName, fileUrl }: PdfPreviewProps) {
  if (!fileUrl) {
    return (
      <div className="empty-state">
        <h2>PDF original viewer</h2>
        <p>Select a PDF file from the left to open the original viewer.</p>
      </div>
    );
  }

  return (
    <div className="pdf-frame">
      <div className="preview-toolbar">
        <strong>{fileName}</strong>
      </div>
      <Worker workerUrl={workerUrl}>
        <Viewer fileUrl={fileUrl} />
      </Worker>
    </div>
  );
}
