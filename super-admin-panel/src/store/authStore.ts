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
  isAuthenticated: boolean;
  setUser: (user: User | null) => void;
  setTokens: (accessToken: string, refreshToken?: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setTokens: (accessToken, refreshToken) => {
        set({ accessToken, refreshToken: refreshToken || null });
        localStorage.setItem('neso.accessToken', accessToken);
        if (refreshToken) {
          localStorage.setItem('neso.refreshToken', refreshToken);
        }
        sessionStorage.setItem('neso.token', accessToken);
      },
      logout: () => {
        set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false });
        localStorage.removeItem('neso.accessToken');
        localStorage.removeItem('neso.refreshToken');
        sessionStorage.removeItem('neso.token');
      },
    }),
    {
      name: 'super-admin-auth-storage',
      storage: createJSONStorage(() => localStorage),
    }
  )
);


