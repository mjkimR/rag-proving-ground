import { sanitizeHtml } from "../lib/sanitize";
import styles from "./HtmlPreview.module.css";

type HtmlPreviewProps = {
  html: string;
};

export function HtmlPreview({ html }: HtmlPreviewProps) {
  return (
    <iframe
      className={styles.htmlPreview}
      sandbox=""
      srcDoc={sanitizeHtml(html)}
      title="Sanitized HTML preview"
    />
  );
}
