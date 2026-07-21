import { Suspense, lazy, type ReactNode, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import ErrorBoundary from './components/ErrorBoundary';
import { useAuthStore } from './store/authStore';
import LoginPage from './pages/LoginPage';
import Layout from './components/Layout';
import TenantRequiredGuard from './components/TenantRequiredGuard';
import { getCurrentSubdomain } from './lib/domain';

// Lazy load heavy pages for better initial bundle size
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const RaporlarPage = lazy(() => import('./pages/RaporlarPage'));
const MenuPage = lazy(() => import('./pages/MenuPage'));
const MutfakPage = lazy(() => import('./pages/MutfakPage'));
const KasaPage = lazy(() => import('./pages/KasaPage'));
const StokPage = lazy(() => import('./pages/StokPage'));
const GiderlerPage = lazy(() => import('./pages/GiderlerPage'));
const MasalarPage = lazy(() => import('./pages/MasalarPage'));
const RecetePage = lazy(() => import('./pages/RecetePage'));
const AssistantPage = lazy(() => import('./pages/AssistantPage'));
const BIAssistantPage = lazy(() => import('./pages/BIAssistantPage'));
const PersonellerPage = lazy(() => import('./pages/PersonellerPage'));
const PersonelTerminalPage = lazy(() => import('./pages/PersonelTerminalPage'));
const CustomerChatPage = lazy(() => import('./pages/CustomerChatPage'));
const PublicMenuPage = lazy(() => import('./pages/PublicMenuPage'));
const SuperAdminPanel = lazy(() => import('./pages/SuperAdminPanel'));
const SystemSettingsPage = lazy(() => import('./pages/SystemSettingsPage'));
const LegalPage = lazy(() => import('./pages/LegalPage'));

// Protected Route component
function ProtectedRoute({ children }: { children: ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

// Index redirect component - Super Admin "Tüm İşletmeler" modundaysa Super Admin paneline yönlendir
function IndexRedirect() {
  const { user, selectedTenantId } = useAuthStore();
  const userRole = user?.role?.toLowerCase();
  const username = user?.username?.toLowerCase();
  const isSuperAdmin = user && (userRole === 'super_admin' || username === 'super');

  // Super admin "Tüm İşletmeler" modundaysa Super Admin paneline yönlendir
  if (isSuperAdmin && selectedTenantId === null) {
    return <Navigate to="/superadmin" replace />;
  }

  // Diğer durumlarda dashboard'a yönlendir
  return <Navigate to="/dashboard" replace />;
}

// Subdomain detection component - uygulama başlangıcında subdomain'i algılar
function SubdomainDetector() {
  const { setTenantId } = useAuthStore();

  useEffect(() => {
    const subdomain = getCurrentSubdomain();
    if (subdomain) {
      // Subdomain varsa, backend'den tenant'ı al ve store'a ekle
      // Bu işlem Layout component'inde yapılıyor (loadTenantByDomain),
      // ama burada da subdomain'i loglamak için kullanabiliriz
      console.log('Subdomain detected:', subdomain);
    }
  }, [setTenantId]);

  return null;
}

function App() {
  return (
    <BrowserRouter>
      <SubdomainDetector />
      <Toaster
        position="top-right"
        gutter={12}
        toastOptions={{
          duration: 3500,
          style: {
            background: 'rgba(15, 23, 42, 0.95)',
            color: '#e2e8f0',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '16px',
            padding: '14px 18px',
            fontSize: '14px',
            fontWeight: 600,
            backdropFilter: 'blur(12px)',
            boxShadow: '0 20px 40px -12px rgba(0, 0, 0, 0.6)',
          },
          success: { iconTheme: { primary: '#10b981', secondary: '#020617' } },
          error: { iconTheme: { primary: '#f43f5e', secondary: '#020617' } },
        }}
      />
      <Suspense
        fallback={
          <div className="flex h-screen flex-col items-center justify-center gap-6 animate-in fade-in duration-500">
            <div className="relative">
              <div className="w-14 h-14 rounded-full border-2 border-emerald-500/20 border-t-emerald-500 animate-spin" />
              <div className="absolute inset-0 rounded-full bg-emerald-500/10 blur-xl" />
            </div>
            <div className="flex flex-col items-center gap-1">
              <span className="text-lg font-bold tracking-tight text-white">Neso Modüler</span>
              <span className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">Yükleniyor</span>
            </div>
          </div>
        }
      >
        <ErrorBoundary>
        <Routes>
          {/* Public routes - no authentication required */}
          <Route path="/musteri/chat" element={<CustomerChatPage />} />
          <Route path="/musteri/menu" element={<PublicMenuPage />} />
          <Route path="/legal" element={<LegalPage />} />

          {/* Auth routes */}
          <Route path="/login" element={<LoginPage />} />

          {/* Protected routes */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<IndexRedirect />} />
            {/* Veri sayfaları - tenant seçilmesi gerekiyor */}
            <Route path="dashboard" element={<TenantRequiredGuard><DashboardPage /></TenantRequiredGuard>} />
            <Route path="raporlar" element={<TenantRequiredGuard><RaporlarPage /></TenantRequiredGuard>} />
            <Route path="menu" element={<TenantRequiredGuard><MenuPage /></TenantRequiredGuard>} />
            <Route path="stok" element={<TenantRequiredGuard><StokPage /></TenantRequiredGuard>} />
            <Route path="giderler" element={<TenantRequiredGuard><GiderlerPage /></TenantRequiredGuard>} />
            <Route path="masalar" element={<TenantRequiredGuard><MasalarPage /></TenantRequiredGuard>} />
            <Route path="recete" element={<TenantRequiredGuard><RecetePage /></TenantRequiredGuard>} />
            <Route path="asistan" element={<TenantRequiredGuard><AssistantPage /></TenantRequiredGuard>} />
            <Route path="isletme-asistani" element={<TenantRequiredGuard><BIAssistantPage /></TenantRequiredGuard>} />
            <Route path="personeller" element={<TenantRequiredGuard><PersonellerPage /></TenantRequiredGuard>} />
            <Route path="mutfak" element={<TenantRequiredGuard><MutfakPage /></TenantRequiredGuard>} />
            <Route path="kasa" element={<TenantRequiredGuard><KasaPage /></TenantRequiredGuard>} />
            <Route path="terminal" element={<TenantRequiredGuard><PersonelTerminalPage /></TenantRequiredGuard>} />
            {/* Sistem ayarları ve Super Admin - her zaman erişilebilir */}
            <Route path="system" element={<SystemSettingsPage />} />
            <Route path="superadmin" element={<SuperAdminPanel />} />
          </Route>

          <Route path="*" element={<IndexRedirect />} />
        </Routes>
        </ErrorBoundary>
      </Suspense>
    </BrowserRouter>
  );
}

export default App;

