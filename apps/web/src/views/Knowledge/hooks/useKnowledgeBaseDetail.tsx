import { useState, useEffect, useReducer } from 'react';
import type { SetStateAction } from 'react';
import { Form, Modal, message } from 'antd';
import { keepPreviousData, useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getKnowledgeBaseDocumentsApiV1KnowledgeBasesKnowledgeBaseIdDocumentsGet,
  uploadKnowledgeBaseDocumentApiV1KnowledgeBasesKnowledgeBaseIdUploadPost,
  deleteKnowledgeBaseDocumentApiV1KnowledgeBaseDocumentsKnowledgeBaseDocumentIdDelete,
  patchKnowledgeBaseApiV1KnowledgeBasesKnowledgeBaseIdPatch,
  deleteKnowledgeBaseApiV1KnowledgeBasesKnowledgeBaseIdDelete,
  getJobProcessHistoriesApiV1JobProcessHistoriesGet,
  getModelCatalogOptionsApiV1ModelCatalogOptionsGet,
} from '@/generated/api/sdk.gen';
import { AlertCircle } from 'lucide-react';
import type {
  KnowledgeBaseRead, KnowledgeBaseDocumentRead, KnowledgeBaseConfigApplyMode, KnowledgeBasePatch
} from '@/generated/api/types.gen';
import { API_BASE_URL } from '@/lib/config';

const normalizeExtensions = (
  obj: Record<string, string | null | undefined> | null | undefined
): Record<string, string> => {
  if (!obj) return {};
  return Object.fromEntries(
    Object.entries(obj).filter(([_, v]) => v !== undefined && v !== null && String(v).trim() !== '')
  ) as Record<string, string>;
};

const CONFIG_STEP_FIELDS = [
  [
    'name',
    ['default_parsing_config', 'provider'],
    ['default_parsing_config', 'extension_providers']
  ],
  [
    ['default_chunking_config', 'chunk_size'],
    ['default_chunking_config', 'chunk_overlap'],
    ['default_chunking_config', 'merge_max_chars'],
    ['default_chunking_config', 'breadcrumb_depth'],
    ['default_chunking_config', 'breadcrumb_separator']
  ]
];

const HISTORY_QUERY_STALE_TIME_MS = 30_000;

interface ConfigUiState {
  currentStep: number;
  showParserOverrides: boolean;
  configConfirmVisible: boolean;
  pendingConfigValues: KnowledgeBasePatch | null;
  configLoadType: 'low' | 'high' | 'reembed';
  applyMode: KnowledgeBaseConfigApplyMode;
}

type ConfigUiAction =
  | { type: 'reset' }
  | { type: 'setStep'; value: SetStateAction<number> }
  | { type: 'setShowParserOverrides'; value: boolean }
  | { type: 'setConfigConfirmVisible'; value: boolean }
  | { type: 'prepareSave'; pendingConfigValues: KnowledgeBasePatch; configLoadType: 'low' | 'high' | 'reembed'; applyMode: KnowledgeBaseConfigApplyMode }
  | { type: 'setApplyMode'; value: KnowledgeBaseConfigApplyMode };

const initialConfigUiState: ConfigUiState = {
  currentStep: 0,
  showParserOverrides: false,
  configConfirmVisible: false,
  pendingConfigValues: null,
  configLoadType: 'low',
  applyMode: 'INHERITED_ONLY',
};

const configUiReducer = (state: ConfigUiState, action: ConfigUiAction): ConfigUiState => {
  switch (action.type) {
    case 'reset':
      return { ...initialConfigUiState };
    case 'setStep':
      return {
        ...state,
        currentStep: typeof action.value === 'function' ? action.value(state.currentStep) : action.value,
      };
    case 'setShowParserOverrides':
      return { ...state, showParserOverrides: action.value };
    case 'setConfigConfirmVisible':
      return { ...state, configConfirmVisible: action.value };
    case 'prepareSave':
      return {
        ...state,
        pendingConfigValues: action.pendingConfigValues,
        configLoadType: action.configLoadType,
        applyMode: action.applyMode,
        configConfirmVisible: true,
      };
    case 'setApplyMode':
      return { ...state, applyMode: action.value };
  }
};

export interface UseKnowledgeBaseDetailProps {
  kb: KnowledgeBaseRead;
  onDeleteSelected: () => void;
  onUpdateKbName: (name: string) => void;
}

export const useKnowledgeBaseDetail = ({
  kb,
  onDeleteSelected,
  onUpdateKbName,
}: UseKnowledgeBaseDetailProps) => {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState('1');

  // Fetch dynamic configuration options
  const { data: configOptions, isLoading: configLoading } = useQuery({
    queryKey: ['configOptions'],
    queryFn: () => getModelCatalogOptionsApiV1ModelCatalogOptionsGet({ throwOnError: true }),
  });

  const embeddingModels = configOptions?.data?.embedding_models || [];
  const parserProviders = configOptions?.data?.parser_providers || [];

  const [selectedParserProvider, setParserProvider] = useState<string | null>(null);
  const parserProvider = (selectedParserProvider && parserProviders.includes(selectedParserProvider))
    ? selectedParserProvider
    : (parserProviders.includes('docling') ? 'docling' : (parserProviders[0] || 'docling'));

  const [isUploading, setIsUploading] = useState(false);
  const [selectedDocForSettings, setSelectedDocForSettings] = useState<KnowledgeBaseDocumentRead | null>(null);
  
  // Configuration settings form states
  const [settingsForm] = Form.useForm();
  const [{
    currentStep,
    showParserOverrides,
    configConfirmVisible,
    pendingConfigValues,
    configLoadType,
    applyMode,
  }, dispatchConfigUi] = useReducer(configUiReducer, initialConfigUiState);

  useEffect(() => {
    dispatchConfigUi({ type: 'reset' });
  }, [kb.id]);

  // --- QUERY 1: Fetch documents in KB ---
  const { data: fileList, isLoading: filesLoading, refetch: refetchFiles } = useQuery({
    queryKey: ['fileList', kb.id],
    queryFn: () => {
      return getKnowledgeBaseDocumentsApiV1KnowledgeBasesKnowledgeBaseIdDocumentsGet({
        path: { knowledge_base_id: kb.id },
        throwOnError: true,
      });
    },
    enabled: !!kb.id,
    refetchInterval: (query) => {
      const items = query.state.data?.data?.items || [];
      const hasActive = items.some(
        (doc: KnowledgeBaseDocumentRead) => !['COMPLETED', 'FAILED', 'READY'].includes(doc.status || '')
      );
      return hasActive ? 2000 : false;
    },
  });

  // --- QUERIES FOR HISTORY (TAB 3) ---
  const { data: parseHistory, isLoading: parsingHistLoading, refetch: refetchParseHist } = useQuery({
    queryKey: ['parsingHistory', kb.id],
    queryFn: () => getJobProcessHistoriesApiV1JobProcessHistoriesGet({
      query: { resource_type: 'knowledge_base_document', stage: 'parsing', limit: 20 },
      throwOnError: true,
    }),
    enabled: activeTab === '3',
    placeholderData: keepPreviousData,
    staleTime: HISTORY_QUERY_STALE_TIME_MS,
  });

  const { data: chunkHistory, isLoading: chunkingHistLoading, refetch: refetchChunkHist } = useQuery({
    queryKey: ['chunkingHistory', kb.id],
    queryFn: () => getJobProcessHistoriesApiV1JobProcessHistoriesGet({
      query: { resource_type: 'knowledge_base_document', stage: 'chunking', limit: 20 },
      throwOnError: true,
    }),
    enabled: activeTab === '3',
    placeholderData: keepPreviousData,
    staleTime: HISTORY_QUERY_STALE_TIME_MS,
  });

  const { data: embedHistory, isLoading: embeddingHistLoading, refetch: refetchEmbedHist } = useQuery({
    queryKey: ['embeddingHistory', kb.id],
    queryFn: () => getJobProcessHistoriesApiV1JobProcessHistoriesGet({
      query: { resource_type: 'knowledge_base_document', stage: 'embedding', limit: 20 },
      throwOnError: true,
    }),
    enabled: activeTab === '3',
    placeholderData: keepPreviousData,
    staleTime: HISTORY_QUERY_STALE_TIME_MS,
  });

  // Setup form default values when KB changes
  useEffect(() => {
    if (kb) {
      settingsForm.setFieldsValue({
        name: kb.name,
        embedding_config: {
          model: kb.embedding_config?.model || 'text-embedding-3-small',
          distance: kb.embedding_config?.distance || 'cosine',
          use_colpali: kb.embedding_config?.use_colpali || false,
          colpali_model: kb.embedding_config?.colpali_model || 'vidore/colpali-v1.2-merged',
          retrieval_mode: kb.embedding_config?.retrieval_mode || 'dense',
          sparse_model: kb.embedding_config?.sparse_model || 'en-bm25',
        },
        default_chunking_config: {
          chunk_size: kb.default_chunking_config?.chunk_size ?? 1024,
          chunk_overlap: kb.default_chunking_config?.chunk_overlap ?? 200,
          merge_max_chars: kb.default_chunking_config?.merge_max_chars ?? 4096,
          breadcrumb_depth: kb.default_chunking_config?.breadcrumb_depth ?? 2,
          include_root_breadcrumb: kb.default_chunking_config?.include_root_breadcrumb ?? true,
          breadcrumb_separator: kb.default_chunking_config?.breadcrumb_separator || ' > ',
        },
        default_parsing_config: {
          provider: kb.default_parsing_config?.provider || 'docling',
          extension_providers: kb.default_parsing_config?.extension_providers || {},
        }
      });
    }
  }, [kb, settingsForm]);


  // --- MUTATION: Upload Document ---
  const handleUpload = async (file: File) => {
    setIsUploading(true);
    try {
      await uploadKnowledgeBaseDocumentApiV1KnowledgeBasesKnowledgeBaseIdUploadPost({
        path: {
          knowledge_base_id: kb.id,
        },
        body: {
          file: file,
          provider: parserProvider,
        },
        throwOnError: true,
      });
      message.success(`Document "${file.name}" uploaded and queued for processing!`);
      refetchFiles();
      queryClient.invalidateQueries({ queryKey: ['kbList'] });
    } catch (e) {
      console.error('File parsing/upload failed:', e);
      Modal.error({
        title: 'Document Ingestion Failed',
        content: e instanceof Error ? e.message : 'Please check your backend connection, Docling parser logs, or LLM config.',
        icon: <AlertCircle color="#ef4444" />,
      });
    } finally {
      setIsUploading(false);
    }
  };

  // --- MUTATION: Delete Document ---
  const deleteDocMutation = useMutation({
    mutationFn: (docId: string) => {
      return deleteKnowledgeBaseDocumentApiV1KnowledgeBaseDocumentsKnowledgeBaseDocumentIdDelete({
        path: {
          knowledge_base_document_id: docId,
        },
        throwOnError: true,
      });
    },
    onSuccess: () => {
      message.success('Document deleted successfully.');
      refetchFiles();
      queryClient.invalidateQueries({ queryKey: ['kbList'] });
    },
    onError: (e) => {
      message.error(e instanceof Error ? e.message : 'Failed to delete document.');
    }
  });

  const handleDeleteDoc = (docId: string) => {
    Modal.confirm({
      title: 'Delete Document',
      content: 'Are you sure you want to delete this document and all its parsed elements/chunks from the database?',
      okText: 'Yes, Delete',
      okType: 'danger',
      onOk: () => deleteDocMutation.mutate(docId),
    });
  };

  const handleDownload = (docId: string) => {
    window.open(`${API_BASE_URL}/api/v1/knowledge_base_documents/${docId}/download`, '_blank');
  };

  // --- MUTATION: Delete KB ---
  const deleteKbMutation = useMutation({
    mutationFn: () => {
      return deleteKnowledgeBaseApiV1KnowledgeBasesKnowledgeBaseIdDelete({
        path: { knowledge_base_id: kb.id },
        throwOnError: true,
      });
    },
    onSuccess: () => {
      message.success('Knowledge Base deleted.');
      onDeleteSelected();
    },
    onError: (e) => {
      message.error(e instanceof Error ? e.message : 'Failed to delete collection.');
    }
  });

  const handleDeleteKb = () => {
    Modal.confirm({
      title: 'Delete Knowledge Base',
      content: `Are you sure you want to permanently delete "${kb.name}"? This deletes all raw files, layouts, and vector embeddings in Qdrant.`,
      okText: 'Delete Everything',
      okType: 'danger',
      onOk: () => deleteKbMutation.mutate(),
    });
  };

  // --- MUTATION: Patch KB Settings ---
  const patchKbMutation = useMutation({
    mutationFn: (payload: { body: KnowledgeBasePatch }) => {
      return patchKnowledgeBaseApiV1KnowledgeBasesKnowledgeBaseIdPatch({
        path: { knowledge_base_id: kb.id },
        body: payload.body,
        throwOnError: true,
      });
    },
    onSuccess: (response: { data: KnowledgeBaseRead }) => {
      message.success('Strategy configurations applied successfully!');
      if (response.data) {
        onUpdateKbName(response.data.name);
      }
      queryClient.invalidateQueries({ queryKey: ['kbList'] });
      refetchFiles();
      dispatchConfigUi({ type: 'setConfigConfirmVisible', value: false });
    },
    onError: (e) => {
      console.error('Failed to update knowledge base settings:', e);
      Modal.error({
        title: 'Update Failed',
        content: e instanceof Error ? e.message : 'Please check your connection and settings.',
      });
    }
  });

  const handlePreSaveConfig = (values: KnowledgeBasePatch) => {
    // Detect what has changed
    const embeddingChanged =
      kb.embedding_config?.model !== values.embedding_config?.model ||
      kb.embedding_config?.distance !== values.embedding_config?.distance ||
      kb.embedding_config?.use_colpali !== values.embedding_config?.use_colpali ||
      kb.embedding_config?.colpali_model !== values.embedding_config?.colpali_model ||
      kb.embedding_config?.retrieval_mode !== values.embedding_config?.retrieval_mode ||
      kb.embedding_config?.sparse_model !== values.embedding_config?.sparse_model;

    const parsingChanged =
      kb.default_parsing_config?.provider !== values.default_parsing_config?.provider ||
      JSON.stringify(normalizeExtensions(kb.default_parsing_config?.extension_providers)) !==
        JSON.stringify(normalizeExtensions(values.default_parsing_config?.extension_providers));

    const chunkingChanged =
      kb.default_chunking_config?.chunk_size !== values.default_chunking_config?.chunk_size ||
      kb.default_chunking_config?.chunk_overlap !== values.default_chunking_config?.chunk_overlap ||
      kb.default_chunking_config?.merge_max_chars !== values.default_chunking_config?.merge_max_chars ||
      kb.default_chunking_config?.breadcrumb_depth !== values.default_chunking_config?.breadcrumb_depth ||
      kb.default_chunking_config?.include_root_breadcrumb !== values.default_chunking_config?.include_root_breadcrumb ||
      kb.default_chunking_config?.breadcrumb_separator !== values.default_chunking_config?.breadcrumb_separator;

    let computedLoad: 'low' | 'high' | 'reembed' = 'low';
    let defaultApplyMode: KnowledgeBaseConfigApplyMode = 'INHERITED_ONLY';

    if (embeddingChanged) {
      computedLoad = 'reembed';
      defaultApplyMode = 'FORCE_ALL';
    } else if (parsingChanged) {
      computedLoad = 'high';
      defaultApplyMode = 'INHERITED_ONLY';
    } else if (chunkingChanged) {
      computedLoad = 'low';
      defaultApplyMode = 'INHERITED_ONLY';
    }

    dispatchConfigUi({
      type: 'prepareSave',
      pendingConfigValues: values,
      configLoadType: computedLoad,
      applyMode: defaultApplyMode,
    });
  };

  const handleFinalSaveConfig = () => {
    if (!pendingConfigValues) return;

    const body = {
      name: pendingConfigValues.name,
      embedding_config: pendingConfigValues.embedding_config,
      default_chunking_config: pendingConfigValues.default_chunking_config,
      default_parsing_config: {
        ...pendingConfigValues.default_parsing_config,
        extension_providers: normalizeExtensions(pendingConfigValues.default_parsing_config?.extension_providers)
      },
      apply_mode: applyMode,
    };

    patchKbMutation.mutate({ body });
  };

  const handlePrevConfig = () => {
    dispatchConfigUi({ type: 'setStep', value: (prev) => prev - 1 });
  };

  const handleNextConfig = async () => {
    try {
      const fieldsToValidate = CONFIG_STEP_FIELDS[currentStep];
      if (fieldsToValidate) {
        await settingsForm.validateFields(fieldsToValidate);
      }
      dispatchConfigUi({ type: 'setStep', value: (prev) => prev + 1 });
    } catch (errorInfo) {
      console.warn('Form validation failed:', errorInfo);
    }
  };

  const handleRefreshAll = () => {
    if (activeTab === '1') {
      refetchFiles();
      message.success('Document status refreshed.');
    } else if (activeTab === '3') {
      refetchParseHist();
      refetchChunkHist();
      refetchEmbedHist();
      message.success('Processing logs refreshed.');
    }
  };

  return {
    activeTab,
    setActiveTab,
    configLoading,
    embeddingModels,
    parserProviders,
    parserProvider,
    setParserProvider,
    isUploading,
    selectedDocForSettings,
    setSelectedDocForSettings,
    settingsForm,
    currentStep,
    showParserOverrides,
    setShowParserOverrides: (show: boolean) => dispatchConfigUi({ type: 'setShowParserOverrides', value: show }),
    configConfirmVisible,
    setConfigConfirmVisible: (show: boolean) => dispatchConfigUi({ type: 'setConfigConfirmVisible', value: show }),
    pendingConfigValues,
    configLoadType,
    applyMode,
    setApplyMode: (mode: KnowledgeBaseConfigApplyMode) => dispatchConfigUi({ type: 'setApplyMode', value: mode }),
    fileList,
    filesLoading,
    refetchFiles,
    parseHistory,
    parsingHistLoading,
    chunkHistory,
    chunkingHistLoading,
    embedHistory,
    embeddingHistLoading,
    handleUpload,
    handleDeleteDoc,
    handleDownload,
    handleDeleteKb,
    handlePreSaveConfig,
    handleFinalSaveConfig,
    handlePrevConfig,
    handleNextConfig,
    handleRefreshAll,
    patchKbMutation,
    refetchParseHist,
    refetchChunkHist,
    refetchEmbedHist,
  };
};
