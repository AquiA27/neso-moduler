import { Suspense, lazy, type ReactNode } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './store/authStore';
import LoginPage from './pages/LoginPage';
import RaporlarPage from './pages/RaporlarPage';
import MenuPage from './pages/MenuPage';
import MutfakPage from './pages/MutfakPage';
import KasaPage from './pages/KasaPage';
import StokPage from './pages/StokPage';
import GiderlerPage from './pages/GiderlerPage';
import MasalarPage from './pages/MasalarPage';
import RecetePage from './pages/RecetePage';
import AssistantPage from './pages/AssistantPage';
import BIAssistantPage from './pages/BIAssistantPage';
import PersonellerPage from './pages/PersonellerPage';
import PersonelTerminalPage from './pages/PersonelTerminalPage';
import CustomerLandingPage from './pages/CustomerLandingPage';
import CustomerChatPage from './pages/CustomerChatPage';
import PublicMenuPage from './pages/PublicMenuPage';
import SuperAdminPanel from './pages/SuperAdminPanel';
import SystemSettingsPage from './pages/SystemSettingsPage';
import Layout from './components/Layout';

const DashboardPage = lazy(() => import('./pages/DashboardPage'));

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

