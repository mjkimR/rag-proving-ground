import React from "react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import { Popover } from "antd";
import { FileText, ArrowRight } from "lucide-react";

import type { Reference } from '@/views/Chat/types';

type MarkdownPreviewProps = {
  markdown: string;
  className?: string;
  references?: Reference[];
  onReferenceClick?: (index: number) => void;
  isDarkMode?: boolean;
};

export function MarkdownPreview({
  markdown,
  className = "markdown-preview",
  references = [],
  onReferenceClick,
  isDarkMode = false,
}: MarkdownPreviewProps) {
  // Pre-process markdown to replace [cite:N] with [N](#ref-N)
  const processedMarkdown = React.useMemo(() => {
    if (!markdown) return "";
    return markdown.replace(/\[cite:(\d+)\]/g, "[$1](#ref-$1)");
  }, [markdown]);

  const customComponents = React.useMemo(() => ({
    a: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => {
      if (href && href.startsWith("#ref-")) {
        const refIndexStr = href.replace("#ref-", "");
        const refIndex = parseInt(refIndexStr, 10);
        
        // Find matching reference in references list
        const ref = references.find((r) => r.index === refIndex);
        
        if (ref) {
          const scorePercent = ref.rerank_score !== null && ref.rerank_score !== undefined
            ? (ref.rerank_score * 100).toFixed(0)
            : (ref.score * 100).toFixed(0);

          const popoverContent = (
            <div style={{ maxWidth: "320px", fontSize: "13px" }}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: "8px", marginBottom: "8px" }}>
                <FileText size={16} style={{ color: "#3b82f6", flexShrink: 0, marginTop: "2px" }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, wordBreak: "break-all", color: isDarkMode ? "#cbd5e1" : "#374151" }}>
                    {ref.source || "Document"}
                  </div>
                  {ref.page !== null && ref.page !== undefined && (
                    <div style={{ fontSize: "11px", color: "#9ca3af" }}>Page {ref.page}</div>
                  )}
                </div>
                <div style={{ flexShrink: 0 }}>
                  <span
                    style={{
                      fontSize: "11px",
                      background: isDarkMode ? "#1e293b" : "#eff6ff",
                      color: "#3b82f6",
                      padding: "2px 6px",
                      borderRadius: "4px",
                      fontWeight: 600,
                    }}
                  >
                    {scorePercent}% match
                  </span>
                </div>
              </div>
              <div
                style={{
                  background: isDarkMode ? "#030712" : "#f9fafb",
                  border: isDarkMode ? "1px solid #1f2937" : "1px solid #e5e7eb",
                  borderRadius: "6px",
                  padding: "8px",
                  fontSize: "12px",
                  color: isDarkMode ? "#9ca3af" : "#4b5563",
                  maxHeight: "120px",
                  overflowY: "auto",
                  whiteSpace: "pre-wrap",
                  marginBottom: "8px",
                  lineHeight: "1.4",
                }}
              >
                {ref.content}
              </div>
              {onReferenceClick && (
                <div
                  onClick={() => onReferenceClick(refIndex)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "flex-end",
                    gap: "4px",
                    color: "#3b82f6",
                    cursor: "pointer",
                    fontWeight: 600,
                    fontSize: "12px",
                    transition: "opacity 0.2s",
                  }}
                  className="popover-action-link"
                >
                  <span>Go to reference</span>
                  <ArrowRight size={12} />
                </div>
              )}
            </div>
          );

          return (
            <Popover
              content={popoverContent}
              title={null}
              trigger="hover"
              placement="top"
              overlayInnerStyle={{
                padding: "12px",
                borderRadius: "10px",
                border: isDarkMode ? "1px solid #1f2937" : "1px solid #e5e7eb",
                background: isDarkMode ? "#0b0f17" : "#ffffff",
                boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
              }}
            >
              <span
                onClick={() => onReferenceClick?.(refIndex)}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  minWidth: "18px",
                  height: "18px",
                  borderRadius: "9px",
                  padding: "0 5px",
                  backgroundColor: isDarkMode ? "#1e293b" : "#eff6ff",
                  color: "#3b82f6",
                  fontSize: "10px",
                  fontWeight: 700,
                  cursor: "pointer",
                  margin: "0 3px",
                  verticalAlign: "baseline",
                  position: "relative",
                  top: "-2px",
                  border: isDarkMode ? "1px solid #3b82f6" : "1px solid #bfdbfe",
                  transition: "all 0.2s ease-in-out",
                  userSelect: "none",
                }}
                className="citation-badge"
              >
                {refIndex}
              </span>
            </Popover>
          );
        }
      }
      return <a href={href} {...props}>{children}</a>;
    }
  }), [references, onReferenceClick, isDarkMode]);

  return (
    <article className={className}>
      <ReactMarkdown
        rehypePlugins={[rehypeSanitize]}
        remarkPlugins={[remarkGfm]}
        components={customComponents}
      >
        {processedMarkdown}
      </ReactMarkdown>
    </article>
  );
}
