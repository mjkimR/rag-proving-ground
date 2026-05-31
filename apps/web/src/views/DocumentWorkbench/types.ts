export type PreviewMode = 
  | "compare-elements" 
  | "compare-markdown" 
  | "compare-html" 
  | "office";

export const modeLabels: Record<PreviewMode, string> = {
  "compare-elements": "Layout Element",
  "compare-markdown": "Markdown",
  "compare-html": "HTML",
  "office": "Office convert",
};
