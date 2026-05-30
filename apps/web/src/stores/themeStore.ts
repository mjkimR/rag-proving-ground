import { create } from 'zustand';

interface ThemeState {
  isDarkMode: boolean;
  activeTab: string;
  selectedKnowledgeName: string | null;
  toggleDarkMode: () => void;
  setActiveTab: (tab: string) => void;
  setSelectedKnowledgeName: (name: string | null) => void;
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
  };
});
