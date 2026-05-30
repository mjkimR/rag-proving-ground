export type PreviewMode = 
  | "pdf" 
  | "markdown" 
  | "html" 
  | "elements" 
  | "compare-markdown" 
  | "compare-html" 
  | "compare-elements" 
  | "office";

export const modeLabels: Record<PreviewMode, string> = {
  pdf: "PDF Original",
  markdown: "Parsed Markdown",
  html: "Parsed HTML",
  elements: "Layout Elements",
  "compare-markdown": "Original - Markdown",
  "compare-html": "Original - HTML",
  "compare-elements": "Original - Layout Element",
  office: "Office Convert",
};
