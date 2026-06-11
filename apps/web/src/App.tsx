import React from 'react';
import { ConfigProvider, theme, App as AntdApp } from 'antd';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { client } from './generated/api/client.gen';
import { useThemeStore } from './stores/themeStore';
import { Layout } from './components/Layout';
import { Dashboard } from './views/Dashboard';
import { Knowledge } from './views/Knowledge';
import { DocumentWorkbench } from './views/DocumentWorkbench';
import { Chat } from './views/Chat';
import { Playground } from './views/Playground';
import { Providers } from './views/Providers';
import { CopilotKit } from "@copilotkit/react-core";
import { CopilotSidebar } from "@copilotkit/react-ui";
import { API_BASE_URL, COPILOT_RUNTIME_URL } from '@/lib/config';

// Set up the generated OpenAPI Client Base URL
client.setConfig({
  baseUrl: API_BASE_URL,
});

// Configure React Query Client with sensible caching settings
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

const copilotRuntimeUrl = COPILOT_RUNTIME_URL;

const ContentSwitcher: React.FC = () => {
  const { activeTab } = useThemeStore();

  switch (activeTab) {
    case 'knowledge':
      return <Knowledge />;
    case 'playground':
      return <Playground />;
    case 'workbench':
      return <DocumentWorkbench copilotEnabled={Boolean(copilotRuntimeUrl)} />;
    case 'chat':
      return <Chat />;
    case 'providers':
      return <Providers />;
    case 'dashboard':
    default:
      return <Dashboard />;
  }
};

export function App() {
  const { isDarkMode } = useThemeStore();

  const mainContent = (
    <Layout>
      <ContentSwitcher />
    </Layout>
  );

  const themeConfig = {
    token: {
      colorPrimary: isDarkMode ? '#00f2fe' : '#4f46e5',
      borderRadius: 14,
      fontFamily: 'Outfit, Inter, -apple-system, BlinkMacSystemFont, sans-serif',
      colorBgContainer: isDarkMode ? '#111827' : '#ffffff',
      colorBgLayout: isDarkMode ? '#0b0f17' : '#f6f7f9',
    },
    algorithm: isDarkMode ? theme.darkAlgorithm : theme.defaultAlgorithm,
  };

  const copilotWrapper = (content: React.ReactNode) => {
    if (!copilotRuntimeUrl) return content;
    return (
      <CopilotKit runtimeUrl={copilotRuntimeUrl} agent="simple_chat">
        <CopilotSidebar
          defaultOpen={false}
          instructions="Help inspect uploaded documents, summarize previews, and trigger available frontend tools when useful."
          labels={{
            title: "Document Copilot",
            initial: "Select a document to preview and assist with the conversion flow.",
          }}
        >
          {content}
        </CopilotSidebar>
      </CopilotKit>
    );
  };

  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider theme={themeConfig}>
        <AntdApp>
          {copilotWrapper(mainContent)}
        </AntdApp>
      </ConfigProvider>
    </QueryClientProvider>
  );
}
