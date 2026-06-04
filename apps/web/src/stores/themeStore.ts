import { create } from 'zustand';

interface ThemeState {
  isDarkMode: boolean;
  activeTab: string;
  selectedKnowledgeName: string | null;
  selectedKnowledgeId: string | null;
  selectedAssistantId: string | null;
  selectedAssistantName: string | null;
  selectedAssistantGraphId: string | null;
  toggleDarkMode: () => void;
  setActiveTab: (tab: string) => void;
  setSelectedKnowledgeName: (name: string | null) => void;
  setSelectedKnowledgeId: (id: string | null) => void;
  setSelectedAssistantId: (id: string | null) => void;
  setSelectedAssistant: (assistant: { id: string; name: string; graphId: string } | null) => void;
}

export const useThemeStore = create<ThemeState>((set) => {
  const savedTheme = localStorage.getItem('rag-proving-ground-theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const initialDark = savedTheme ? savedTheme === 'dark' : prefersDark;

  if (initialDark) {
    document.documentElement.classList.add('dark-theme');
  } else {
    document.documentElement.classList.remove('dark-theme');
  }

  return {
    isDarkMode: initialDark,
    activeTab: 'dashboard',
    selectedKnowledgeName: null,
    selectedKnowledgeId: null,
    selectedAssistantId: null,
    selectedAssistantName: null,
    selectedAssistantGraphId: null,
    toggleDarkMode: () =>
      set((state) => {
        const nextDark = !state.isDarkMode;
        localStorage.setItem('rag-proving-ground-theme', nextDark ? 'dark' : 'light');
        if (nextDark) {
          document.documentElement.classList.add('dark-theme');
        } else {
          document.documentElement.classList.remove('dark-theme');
        }
        return { isDarkMode: nextDark };
      }),
    setActiveTab: (tab) => set({ activeTab: tab }),
    setSelectedKnowledgeName: (name) => set({ selectedKnowledgeName: name }),
    setSelectedKnowledgeId: (id) => set({ selectedKnowledgeId: id }),
    setSelectedAssistantId: (id) => set({ selectedAssistantId: id }),
    setSelectedAssistant: (assistant) =>
      set({
        selectedAssistantId: assistant?.id ?? null,
        selectedAssistantName: assistant?.name ?? null,
        selectedAssistantGraphId: assistant?.graphId ?? null,
      }),
  };
});
