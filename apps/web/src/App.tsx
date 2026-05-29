import { CopilotKit } from "@copilotkit/react-core";
import { CopilotSidebar } from "@copilotkit/react-ui";
import { DocumentWorkbench } from "./components/DocumentWorkbench";

const copilotRuntimeUrl = import.meta.env.VITE_COPILOT_RUNTIME_URL as string | undefined;

export function App() {
  const content = (
    <main className="app-shell">
      <section className="app-header">
        <div>
          <p className="eyebrow">RAG Experiment</p>
          <h1>Document preview workspace</h1>
        </div>
        <div className="status-pill">{copilotRuntimeUrl ? "Copilot connected" : "Copilot runtime not set"}</div>
      </section>

      <DocumentWorkbench copilotEnabled={Boolean(copilotRuntimeUrl)} />
    </main>
  );

  if (!copilotRuntimeUrl) {
    return content;
  }

  return (
    <CopilotKit runtimeUrl={copilotRuntimeUrl}>
      <CopilotSidebar
        defaultOpen={false}
        instructions="Help inspect uploaded documents, summarize previews, and trigger available frontend tools when useful."
        labels={{
          title: "Document Copilot",
          initial: "문서를 선택하면 preview와 변환 흐름을 도와줄 수 있습니다.",
        }}
      >
        {content}
      </CopilotSidebar>
    </CopilotKit>
  );
}
