import { Suspense, lazy, type ReactNode } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './store/authStore';
import LoginPage from './pages/LoginPage';
import Layout from './components/Layout';

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
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="raporlar" element={<RaporlarPage />} />
            <Route path="menu" element={<MenuPage />} />
            <Route path="mutfak" element={<MutfakPage />} />
            <Route path="kasa" element={<KasaPage />} />
            <Route path="stok" element={<StokPage />} />
            <Route path="giderler" element={<GiderlerPage />} />
            <Route path="masalar" element={<MasalarPage />} />
            <Route path="recete" element={<RecetePage />} />
            <Route path="asistan" element={<AssistantPage />} />
            <Route path="isletme-asistani" element={<BIAssistantPage />} />
            <Route path="personeller" element={<PersonellerPage />} />
            <Route path="terminal" element={<PersonelTerminalPage />} />
            <Route path="system" element={<SystemSettingsPage />} />
            <Route path="superadmin" element={<SuperAdminPanel />} />
          </Route>
          
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}

export default App;

