import { useState, useEffect, useCallback, useMemo, memo } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { customizationApi, subscriptionApi, normalizeApiUrl } from '../lib/api';
import { getCurrentSubdomain, loadTenantByDomain } from '../lib/domain';
import { Settings, AlertTriangle, X, Menu, Bell } from 'lucide-react';
import logo from '../assets/neso-logo.jpg';
import TenantSwitcher from './TenantSwitcher';
import Sidebar from './Sidebar';

function Layout() {
  const { user, logout, tenantId, tenantCustomization, setTenantCustomization, selectedTenantId } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [subscriptionStatus, setSubscriptionStatus] = useState<any>(null);
  const [showSubscriptionAlert, setShowSubscriptionAlert] = useState(true);

  // Close sidebar by default on mobile
  useEffect(() => {
    if (window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  }, []);

  // Tenant customization'ı yükle (tenant_id veya subdomain'den)
  useEffect(() => {
    const loadCustomization = async () => {
      const effectiveTenantId = selectedTenantId || tenantId;
      const subdomain = getCurrentSubdomain();

      if (subdomain) {
        try {
          const API_BASE_URL = normalizeApiUrl(import.meta.env.VITE_API_URL as string);
          const customization = await loadTenantByDomain(subdomain, API_BASE_URL);
          if (customization) {
            setTenantCustomization({
              app_name: customization.app_name,
              logo_url: customization.logo_url,
              primary_color: customization.primary_color,
              secondary_color: customization.secondary_color,
            });
            return;
          }
        } catch (error) {
          console.warn('Domain-based customization yüklenemedi:', error);
        }
      }

      if (!effectiveTenantId) {
        if (user?.role !== 'super_admin') {
          setTenantCustomization(null);
        }
        return;
      }

      try {
        const response = await customizationApi.get(effectiveTenantId);
        const customization = response.data;
        setTenantCustomization({
          app_name: customization.app_name,
          logo_url: customization.logo_url,
          primary_color: customization.primary_color,
          secondary_color: customization.secondary_color,
        });
      } catch (error) {
        console.warn('Tenant customization yüklenemedi:', error);
      }
    };

    if (user) {
      loadCustomization();
    }
  }, [tenantId, selectedTenantId, user, setTenantCustomization]);

  useEffect(() => {
    const checkSubscription = async () => {
      if (user?.role === 'super_admin') return;
      try {
        const response = await subscriptionApi.getMyStatus();
        setSubscriptionStatus(response.data);
      } catch (error: any) {
        if (error.response?.status !== 404) {
          console.warn('Subscription durumu kontrol edilemedi:', error);
        }
      }
    };

    if (user && tenantId) {
      checkSubscription();
    }
  }, [user, tenantId]);

  const displayLogo = useMemo(() => tenantCustomization?.logo_url || logo, [tenantCustomization?.logo_url]);
  const displayName = useMemo(() => {
    if (tenantCustomization?.app_name) {
      return user?.role === 'super_admin' ? 'Neso Modüler' : tenantCustomization.app_name;
    }
    return user?.role === 'super_admin' ? 'Neso Modüler' : 'Neso Panel';
  }, [tenantCustomization?.app_name, user?.role]);

  const handleLogout = useCallback(() => {
    logout();
    window.location.href = '/login';
  }, [logout]);

  const resolvePanel = (username: string, role: string): string[] => {
    const u = username.toLowerCase();
    const r = role.toLowerCase();
    const panels: string[] = [];
    if (u === 'mutfak' || r === 'mutfak' || r === 'barista') return ['mutfak'];
    if (r === 'garson') return ['terminal'];
    if (r === 'super_admin' || r === 'admin' || u === 'admin' || u === 'super') panels.push('admin');
    if (r === 'operator' || u === 'kasiyer') panels.push('kasa');
    return panels.length > 0 ? panels : ['admin'];
  };

  const allowedPanels = user ? resolvePanel(user.username, user.role) : ['admin'];
  const showAdmin = allowedPanels.includes('admin');
  const showKasa = allowedPanels.includes('kasa');
  const showMutfak = allowedPanels.includes('mutfak');
  const showTerminal = allowedPanels.includes('terminal');

  const userRole = user?.role?.toLowerCase() || '';
  const username = user?.username?.toLowerCase() || '';
  const showPersoneller = user && (userRole === 'super_admin' || username === 'super' || userRole === 'admin');
  const showSuperAdmin = user && (userRole === 'super_admin' || username === 'super');
  const isSuperAdminInAllTenantsMode = showSuperAdmin && selectedTenantId === null;
  const showTenantDataPages = !isSuperAdminInAllTenantsMode;

  const subscriptionAlertMessage = useMemo(() => {
    if (!subscriptionStatus || !showSubscriptionAlert) return null;
    const { status, days_until_expiry, expires_soon } = subscriptionStatus;
    if (status === 'suspended') return { type: 'error', message: 'Aboneliğiniz askıya alınmıştır.' };
    if (status === 'cancelled') return { type: 'error', message: 'Aboneliğiniz sonlandırılmıştır.' };
    if (expires_soon && days_until_expiry !== undefined) return { type: 'warning', message: `Aboneliğiniz ${days_until_expiry} gün içinde sona erecek.` };
    return null;
  }, [subscriptionStatus, showSubscriptionAlert]);

  // Current page title based on path
  const pageTitle = useMemo(() => {
    const path = location.pathname;
    if (path.includes('dashboard')) return 'Dashboard';
    if (path.includes('raporlar')) return 'Raporlar';
    if (path.includes('menu')) return 'Menü Yönetimi';
    if (path.includes('stok')) return 'Stok Takibi';
    if (path.includes('giderler')) return 'Giderler';
    if (path.includes('masalar')) return 'Masa Düzeni';
    if (path.includes('recete')) return 'Reçeteler';
    if (path.includes('asistan')) return 'Yapay Zeka Asistanı';
    if (path.includes('personeller')) return 'Personel Yönetimi';
    if (path.includes('kasa')) return 'Kasa Paneli';
    if (path.includes('superadmin')) return 'Sistem Yönetimi';
    return 'Neso Modüler';
  }, [location]);

  return (
    <div className="min-h-screen flex flex-row">
      {/* Sidebar Component */}
      <Sidebar
        isOpen={sidebarOpen}
        setIsOpen={setSidebarOpen}
        user={user}
        displayLogo={displayLogo}
        onLogout={handleLogout}
        showAdmin={showAdmin}
        showKasa={showKasa}
        showMutfak={showMutfak}
        showTerminal={showTerminal}
        showPersoneller={!!showPersoneller}
        showSuperAdmin={!!showSuperAdmin}
        showTenantDataPages={!!showTenantDataPages}
      />

      {/* Content Wrapper */}
      <div className={`flex-1 flex flex-col transition-all duration-500 min-w-0 ${sidebarOpen ? 'md:pl-72' : 'md:pl-20'}`}>

        {/* Top Header */}
        <header className="sticky top-0 z-30 h-16 md:h-20 flex items-center justify-between px-4 md:px-8 border-b border-white/5 bg-slate-950/20 backdrop-blur-3xl">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 -ml-2 text-slate-400 hover:text-white md:hidden"
            >
              <Menu size={24} />
            </button>
            <div className="flex flex-col">
              <h2 className="text-xl md:text-2xl font-bold text-white tracking-tight">{pageTitle}</h2>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
                <span className="text-[10px] md:text-xs text-slate-500 font-medium tracking-wide uppercase">{displayName}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 md:gap-4">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/5 text-slate-400">
              <Bell size={16} />
              <div className="w-[1px] h-3 bg-white/10 mx-1" />
              <span className="text-xs font-medium">0 Bildirim</span>
            </div>

            {showSuperAdmin && (
              <div className="scale-90 md:scale-100">
                <TenantSwitcher />
              </div>
            )}

            <button
              onClick={() => navigate('/system')}
              className="p-2.5 rounded-xl border border-white/5 bg-white/5 text-slate-400 hover:text-emerald-400 hover:border-emerald-500/30 transition-all duration-300"
              title="Sistem Ayarları"
            >
              <Settings className="w-5 h-5" />
            </button>
          </div>
        </header>

        {/* Subscription Alert */}
        {subscriptionAlertMessage && (
          <div className={`${subscriptionAlertMessage.type === 'error' ? 'bg-red-500/20 text-red-400 border-red-500/20' : 'bg-yellow-500/20 text-yellow-400 border-yellow-500/20'} border-b px-8 py-3 flex items-center justify-between animate-in fade-in slide-in-from-top duration-500`}>
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-5 h-5" />
              <span className="text-sm font-medium">{subscriptionAlertMessage.message}</span>
            </div>
            <button onClick={() => setShowSubscriptionAlert(false)} className="hover:bg-white/10 rounded-lg p-1 transition-colors">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Main Content Area */}
        <main className="flex-1 p-4 md:p-8 relative">
          <div className="max-w-[1600px] mx-auto animate-in fade-in slide-in-from-bottom duration-700">
            <Outlet />
          </div>
        </main>

        {/* Minimal Footer */}
        <footer className="px-8 py-6 border-t border-white/5 flex flex-col md:flex-row items-center justify-between gap-6 text-[10px] font-bold uppercase tracking-[0.1em] text-slate-600">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
            <p className="text-slate-500 normal-case font-medium tracking-normal">© 2026 Neso Modüler Dashboard. Premium Edition.</p>
            <div className="hidden md:block w-px h-3 bg-white/5" />
            <a href="/legal?type=kvkk" className="hover:text-emerald-400 transition-colors">KVKK Aydınlatma</a>
            <a href="/legal?type=terms" className="hover:text-emerald-400 transition-colors">Kullanım Koşulları</a>
            <a href="/legal?type=privacy" className="hover:text-emerald-400 transition-colors">Gizlilik & Çerez</a>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
              <span className="text-emerald-500/80">Sistem Aktif</span>
            </div>
            <span className="text-slate-800">|</span>
            <span className="text-slate-700 tracking-widest">v0.3.5</span>
          </div>
        </footer>
      </div>
    </div>
  );
}

export default memo(Layout);


