import { useState } from "react";
import type { ChangeEvent } from "react";
import { convertOfficeToPdf } from "../lib/office";

type OfficePreviewProps = {
  onPdfReady: (url: string, name: string) => void;
};

import { OFFICE_CONVERT_URL } from '@/lib/config';

const convertUrl = OFFICE_CONVERT_URL;

export function OfficePreview({ onPdfReady }: OfficePreviewProps) {
  const [status, setStatus] = useState(convertUrl ? "Ready for conversion" : "Set VITE_OFFICE_CONVERT_URL first");
  const [isConverting, setIsConverting] = useState(false);

  async function handleOfficeChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file || !convertUrl) return;

    setIsConverting(true);
    setStatus("Converting with Gotenberg...");

    try {
      const pdf = await convertOfficeToPdf(file, convertUrl);
      const url = URL.createObjectURL(pdf);
      onPdfReady(url, file.name.replace(/\.[^.]+$/, ".pdf"));
      setStatus("Converted to PDF");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Office conversion failed");
    } finally {
      setIsConverting(false);
      event.target.value = "";
    }
  }

  return (
    <div className="office-panel">
      <h2>Office to PDF</h2>
      <p>Office documents will be converted using Gotenberg and displayed in the PDF viewer.</p>
      <label className="office-upload" htmlFor="office-file">
        Select Office file
      </label>
      <input
        accept=".doc,.docx,.ppt,.pptx,.xls,.xlsx,.odt,.odp,.ods"
        disabled={!convertUrl || isConverting}
        id="office-file"
        onChange={handleOfficeChange}
        type="file"
      />
      <code>{status}</code>
    </div>
  );
}
