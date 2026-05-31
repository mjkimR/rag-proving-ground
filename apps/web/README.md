# @rag-experiment/web

The frontend React application for the **Modular RAG Experimentation and Serving Scaffold**.

## Tech Stack

This project is built using the following primary technologies:

- **Framework**: [React](https://react.dev/) (v19)
- **Language**: [TypeScript](https://www.typescriptlang.org/)
- **Build Tool**: [Vite](https://vitejs.dev/) (v8)
- **State Management**: [Zustand](https://github.com/pmndrs/zustand)
- **Routing**: [React Router](https://reactrouter.com/) (v7)
- **Data Fetching & Caching**: [TanStack Query](https://tanstack.com/query/latest) (v5)
- **AI Agent UI**: [CopilotKit](https://www.copilotkit.ai/) (for dynamic in-app AI agents)
- **UI Components & Styling**: [Ant Design (antd)](https://ant.design/) (v6) with dynamic token-based styling
- **Markdown & PDF Rendering**:
  - `react-markdown` + `rehype-sanitize` + `remark-gfm` (Strictly sanitized markdown rendering)
  - `@react-pdf-viewer/core` + `pdfjs-dist` (High-fidelity PDF document viewing)
- **API Client**: [@hey-api/openapi-ts](https://github.com/hey-api/openapi-ts) with [@hey-api/client-fetch](https://github.com/hey-api/client-fetch) (Fully type-safe OpenAPI-based client generation)

---

## Directory Structure

```
apps/web/src/
├── assets/              # Static assets (images, fonts, etc.)
├── components/          # Shared/common UI components
├── config/              # Application configuration and environment constants
├── generated/           # Auto-generated code
│   └── api/             # OpenAPI-based type-safe API client (types, SDK, client)
├── stores/              # Global state management (Zustand)
├── styles.css           # Global custom Tailwind/CSS styling
├── utils/               # General utility helper functions
├── App.tsx              # Main App component and route configuration
└── main.tsx             # Application entry point
```

---

## Getting Started

### 1. Install Dependencies

Ensure you have Node.js `>=24.0.0` and npm `>=11.0.0` installed.

```bash
npm install
```

### 2. Run the Development Server

Starts the Vite development server bound to `127.0.0.1`.

```bash
npm run dev
```

### 3. Generate Type-Safe API Client

You can automatically generate the frontend client SDK, client routes, and typescript interfaces directly from the FastAPI Python backend OpenAPI schema:

**Method A: Recommended (From the repository workspace root)**
Run the orchestrator command, which automatically exports the latest OpenAPI JSON from the Python backend and compiles the frontend client:
```bash
just gen-ui-api
```

**Method B: Manual (From the `apps/web` directory)**
If you have a running backend server (at `http://127.0.0.1:8389` or specified by `VITE_API_BASE_URL`):
```bash
npm run gen:api
```

### 4. Build for Production

Performs type checks (`tsc --noEmit`) and compiles optimized static assets using Vite:

```bash
npm run build
```

---

## Type-Safe API Integration Guide

This project utilizes `@hey-api/client-fetch` and `@hey-api/openapi-ts` to ensure 100% type safety between Python models (Pydantic) and the React frontend.

The generated code resides in `src/generated/api`.

### 1. Initializing the Global API Client

Set up the base URL for the API client. You typically configure this once at the app entry point:

```typescript
import { client } from './generated/api/client';

// Points to the FastAPI gateway proxy or backend server
client.setConfig({
    baseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8389',
});
```

### 2. Making Requests with the Generated SDK

The generated SDK exports ready-to-use, fully typed asynchronous functions matching backend endpoint tags:

```tsx
import React, { useEffect, useState } from 'react';
import { uploadKnowledgeBaseDocumentApiV1KnowledgeBasesKnowledgeBaseIdUploadPost } from '@/generated/api/sdk.gen';
import { App, Upload } from 'antd';

export const DocumentUpload: React.FC = () => {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);

  const handleUpload = async (file: File) => {
    setLoading(true);
    try {
      // Endpoint: /api/v1/knowledge_bases/{knowledge_base_id}/upload
      const response = await uploadKnowledgeBaseDocumentApiV1KnowledgeBasesKnowledgeBaseIdUploadPost({
        path: {
          knowledge_base_id: 'a384b6f1-a1e4-4fa9-b873-90974b67329d', // Knowledge Base UUID
        },
        body: {
          file: file,
          provider: 'docling',
        },
      });

      message.success(`Successfully uploaded and parsed document! Hash: ${response.data?.file_md5}`);
      console.log('Parsed Document Info:', response.data?.document_info);
    } catch (error) {
      console.error('Upload failed:', error);
      message.error('Failed to parse document.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Upload.Dragger
      customRequest={({ file }) => handleUpload(file as File)}
      showUploadList={false}
      disabled={loading}
    >
      <p className="ant-upload-text">Click or drag document to parse into Knowledge Base</p>
    </Upload.Dragger>
  );
};
```

---

## Ant Design (antd) Integration Guide

This project leverages **Ant Design (antd) v6** as its primary design system. Ant Design v6 uses a modern **CSS-in-JS** styling engine, enabling dynamic, token-based runtime styling.

To maintain a consistent design system, follow these practices:

### 1. Dynamic Theme Customization

The design system's theme is defined centrally using the `ConfigProvider` component. Customize tokens (like colors, border radiuses, and fonts) globally:

```tsx
// src/App.tsx
import React from 'react';
import { ConfigProvider, theme } from 'antd';

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#4f46e5', // Sleek Indigo brand primary color
          borderRadius: 8,         // Modern rounded card border radius
          fontFamily: 'Outfit, Inter, sans-serif',
        },
        algorithm: theme.darkAlgorithm, // Supports darkAlgorithm out of the box
      }}
    >
      {children}
    </ConfigProvider>
  );
};
```

### 2. Static Methods & Sub-components (Global Context)

Ant Design v6 components like `message`, `notification`, and `Modal` require a correct React context to inherit theme customizations. Wrap the route/view tree inside an `<App>` component. You can then use the `App.useApp()` hook to access seamless, consistent static methods:

```tsx
import { Button, App } from 'antd';

export const MyComponent = () => {
  const { message, modal, notification } = App.useApp();

  const handleAction = () => {
    message.success('Document uploaded successfully!');
  };

  return <Button onClick={handleAction}>Upload Doc</Button>;
};
```

---

## Project Settings & Best Practices

- **Path Aliases**: The `@` symbol points to the `src/` directory. 
  - Configured in: `vite.config.ts`, `tsconfig.json`
- **Markdown Sanitization**: Always use `rehype-sanitize` when rendering document content via `react-markdown` to prevent HTML injection/XSS vulnerabilities.
