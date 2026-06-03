import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";

type MarkdownPreviewProps = {
  markdown: string;
  className?: string;
};

export function MarkdownPreview({ markdown, className = "markdown-preview" }: MarkdownPreviewProps) {
  return (
    <article className={className}>
      <ReactMarkdown rehypePlugins={[rehypeSanitize]} remarkPlugins={[remarkGfm]}>
        {markdown}
      </ReactMarkdown>
    </article>
  );
}
