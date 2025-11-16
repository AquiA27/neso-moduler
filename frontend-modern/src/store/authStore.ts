import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

interface User {
  id?: number;
  username: string;
  role: string;
  aktif?: boolean;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  subeId: number;
  theme: 'light' | 'dark';
  isAuthenticated: boolean;
  
  // Actions
  setUser: (user: User | null) => void;
  setTokens: (accessToken: string, refreshToken?: string) => void;
  setSubeId: (subeId: number) => void;
  setTheme: (theme: 'light' | 'dark') => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      subeId: 1,
      theme: 'dark',
      isAuthenticated: false,
      
      setUser: (user) => set({ user, isAuthenticated: !!user }),
      
      setTokens: (accessToken, refreshToken) => {
        set({ accessToken, refreshToken: refreshToken || null });
        // localStorage'a da kaydet (eski sistemle uyumluluk için)
        localStorage.setItem('neso.accessToken', accessToken);
        if (refreshToken) {
          localStorage.setItem('neso.refreshToken', refreshToken);
        }
        // Eski format için sessionStorage
        sessionStorage.setItem('neso.token', accessToken);
      },
      
      setSubeId: (subeId) => {
        set({ subeId });
        localStorage.setItem('neso.subeId', String(subeId));
        sessionStorage.setItem('neso.subeId', String(subeId));
      },

      setTheme: (theme) => {
        set({ theme });
        localStorage.setItem('neso.theme', theme);
        if (typeof document !== 'undefined') {
          document.documentElement.classList.remove('dark', 'light');
          document.documentElement.classList.add(theme);
        }
      },
      
      logout: () => {
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          theme: 'dark',
          isAuthenticated: false,
        });
        localStorage.removeItem('neso.accessToken');
        localStorage.removeItem('neso.refreshToken');
        localStorage.removeItem('neso.subeId');
        localStorage.removeItem('neso.theme');
        sessionStorage.removeItem('neso.token');
        sessionStorage.removeItem('neso.subeId');
        if (typeof document !== 'undefined') {
          document.documentElement.classList.remove('light');
          document.documentElement.classList.add('dark');
        }
      },
    }),
    {
      name: 'neso-auth-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        subeId: state.subeId,
        theme: state.theme,
        isAuthenticated: state.isAuthenticated,
      }),
      onRehydrateStorage: () => (state) => {
        const theme = state?.theme ?? 'dark';
        if (typeof document !== 'undefined') {
          document.documentElement.classList.remove('light', 'dark');
          document.documentElement.classList.add(theme);
        }
      },
    }
  )
);

