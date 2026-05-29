import { sanitizeHtml } from "../lib/sanitize";

type HtmlPreviewProps = {
  html: string;
};

export function HtmlPreview({ html }: HtmlPreviewProps) {
  return (
    <iframe
      className="html-preview"
      sandbox=""
      srcDoc={sanitizeHtml(html)}
      title="Sanitized HTML preview"
    />
  );
}
