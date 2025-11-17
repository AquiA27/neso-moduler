import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

interface User {
  id?: number;
  username: string;
  role: string;
  aktif?: boolean;
}

interface TenantCustomization {
  app_name?: string;
  logo_url?: string;
  primary_color?: string;
  secondary_color?: string;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  subeId: number;
  tenantId: number | null;
  tenantCustomization: TenantCustomization | null;
  theme: 'light' | 'dark';
  isAuthenticated: boolean;
  
  // Actions
  setUser: (user: User | null) => void;
  setTokens: (accessToken: string, refreshToken?: string) => void;
  setSubeId: (subeId: number) => void;
  setTenantId: (tenantId: number | null) => void;
  setTenantCustomization: (customization: TenantCustomization | null) => void;
  setTheme: (theme: 'light' | 'dark') => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      subeId: 1,
      tenantId: null,
      tenantCustomization: null,
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
        
        // Token'dan tenant_id'yi çıkar
        try {
          const payload = JSON.parse(atob(accessToken.split('.')[1]));
          const tenantId = payload.tenant_id || null;
          set({ tenantId });
          if (tenantId) {
            localStorage.setItem('neso.tenantId', String(tenantId));
          }
        } catch (e) {
          console.warn('Token parse error:', e);
        }
      },
      
      setSubeId: (subeId) => {
        set({ subeId });
        localStorage.setItem('neso.subeId', String(subeId));
        sessionStorage.setItem('neso.subeId', String(subeId));
      },
      
      setTenantId: (tenantId) => {
        set({ tenantId });
        if (tenantId) {
          localStorage.setItem('neso.tenantId', String(tenantId));
        } else {
          localStorage.removeItem('neso.tenantId');
        }
      },
      
      setTenantCustomization: (customization) => {
        set({ tenantCustomization: customization });
        if (customization?.primary_color && typeof document !== 'undefined') {
          document.documentElement.style.setProperty('--primary-color', customization.primary_color);
        }
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
          tenantId: null,
          tenantCustomization: null,
          theme: 'dark',
          isAuthenticated: false,
        });
        localStorage.removeItem('neso.accessToken');
        localStorage.removeItem('neso.refreshToken');
        localStorage.removeItem('neso.subeId');
        localStorage.removeItem('neso.tenantId');
        localStorage.removeItem('neso.theme');
        sessionStorage.removeItem('neso.token');
        sessionStorage.removeItem('neso.subeId');
        if (typeof document !== 'undefined') {
          document.documentElement.classList.remove('light');
          document.documentElement.classList.add('dark');
          document.documentElement.style.removeProperty('--primary-color');
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
        tenantId: state.tenantId,
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

