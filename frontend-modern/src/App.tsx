import { Suspense, lazy, type ReactNode } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './store/authStore';
import LoginPage from './pages/LoginPage';
import Layout from './components/Layout';
import TenantRequiredGuard from './components/TenantRequiredGuard';

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
const CustomerLandingPage = lazy(() => import('./pages/CustomerLandingPage'));
const CustomerChatPage = lazy(() => import('./pages/CustomerChatPage'));
const PublicMenuPage = lazy(() => import('./pages/PublicMenuPage'));
const SuperAdminPanel = lazy(() => import('./pages/SuperAdminPanel'));
const SystemSettingsPage = lazy(() => import('./pages/SystemSettingsPage'));

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

function App() {
  return (
    <BrowserRouter>
      <Suspense
        fallback={
          <div className="flex h-screen items-center justify-center text-sm text-slate-500">
            Uygulama yükleniyor...
          </div>
        }
      >
        <Routes>
          {/* Public routes - no authentication required */}
          <Route path="/musteri" element={<CustomerLandingPage />} />
          <Route path="/musteri/chat" element={<CustomerChatPage />} />
          <Route path="/musteri/menu" element={<PublicMenuPage />} />
          
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
      </Suspense>
    </BrowserRouter>
  );
}

export default App;

