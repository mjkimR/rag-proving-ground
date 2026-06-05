export interface AgentViewProps {
  assistantId: string;
  assistantName?: string | null;
  onBack: () => void;
}

export interface Reference {
  index: number;
  knowledge_base_id: string;
  doc_id: string;
  chunk_id: string;
  score: number;
  rerank_score?: number | null;
  content: string;
  page_content?: string | null;
  source?: string | null;
  page?: number | string | null;
}

export interface Message {
  id: string;
  type: 'human' | 'ai' | 'error';
  content: string;
  thinking?: string;
  references?: Reference[];
}
