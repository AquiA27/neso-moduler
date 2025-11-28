import { useState, useEffect, useCallback, useMemo, memo } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { customizationApi } from '../lib/api';
import { getCurrentSubdomain, loadTenantByDomain } from '../lib/domain';
import { Menu, Settings, LogOut } from 'lucide-react';
import logo from '../assets/fistik-logo.svg';
import TenantSwitcher from './TenantSwitcher';

// Hex renk kodunu rgba'ya çevir
const hexToRgba = (hex: string, alpha: number = 0.9): string => {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

function Layout() {
  const { user, logout, tenantId, tenantCustomization, setTenantCustomization, selectedTenantId } = useAuthStore();
  const navigate = useNavigate();
  const [navOpen, setNavOpen] = useState(false);
  
  // Tenant customization'ı yükle (tenant_id veya subdomain'den)
  useEffect(() => {
    const loadCustomization = async () => {
      // Super admin tenant değiştirdiğinde selectedTenantId'yi kullan
      const effectiveTenantId = selectedTenantId || tenantId;
      
      // Önce subdomain'den dene (domain-based routing)
      const subdomain = getCurrentSubdomain();
      if (subdomain) {
        try {
          const API_BASE_URL = import.meta.env?.VITE_API_URL || 'http://localhost:8000';
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
      
      // Subdomain yoksa veya bulunamadıysa tenant_id'den yükle
      if (!effectiveTenantId) {
        setTenantCustomization(null);
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
        setTenantCustomization(null);
      }
    };
    
    loadCustomization();
  }, [tenantId, selectedTenantId, setTenantCustomization]);
  
  // Logo ve app name'i belirle (memoize edilmiş)
  const displayLogo = useMemo(() => tenantCustomization?.logo_url || logo, [tenantCustomization?.logo_url]);
  const displayName = useMemo(() => {
    if (tenantCustomization?.app_name) {
      return user?.role === 'super_admin' ? 'Neso Modüler' : `${tenantCustomization.app_name} Yönetim Paneli`;
    }
    return user?.role === 'super_admin' ? 'Neso Modüler' : 'Yönetim Paneli';
  }, [tenantCustomization?.app_name, user?.role]);
  
  // Header arka plan rengini hesapla
  const headerBackground = useMemo(() => {
    if (tenantCustomization?.primary_color) {
      const primary = hexToRgba(tenantCustomization.primary_color, 0.9);
      const secondary = tenantCustomization.secondary_color 
        ? hexToRgba(tenantCustomization.secondary_color, 0.9)
        : primary;
      return `linear-gradient(to right, ${primary}, ${secondary})`;
    }
    return 'linear-gradient(to right, rgb(6 78 59 / 0.9), rgb(5 46 22 / 0.9))';
  }, [tenantCustomization?.primary_color, tenantCustomization?.secondary_color]);
  
  const headerShadow = useMemo(() => {
    if (tenantCustomization?.primary_color) {
      const shadowColor = hexToRgba(tenantCustomization.primary_color, 0.25);
      return `0 10px 15px -3px ${shadowColor}, 0 4px 6px -2px ${shadowColor}`;
    }
    return '0 10px 15px -3px rgb(5 46 22 / 0.4), 0 4px 6px -2px rgb(5 46 22 / 0.2)';
  }, [tenantCustomization?.primary_color]);

  const handleLogout = useCallback(() => {
    logout();
    // Tüm storage'ı temizle ve login sayfasına yönlendir
    window.location.href = '/login';
  }, [logout]);

  const toggleNav = useCallback(() => setNavOpen((prev) => !prev), []);


  const resolvePanel = (username: string, role: string): string[] => {
    const u = username.toLowerCase();
    const r = role.toLowerCase();
    const panels: string[] = [];
    
    // Mutfak kullanıcıları ve barista mutfak ekranını görebilir
    if (u === 'mutfak' || r === 'mutfak' || r === 'barista') {
      return ['mutfak']; // Sadece mutfak, başka hiçbir panele erişim yok
    }
    
    // Garson terminal kullanabilir
    if (r === 'garson') {
      return ['terminal'];
    }
    
    // Admin yetkileri
    if (r === 'super_admin' || r === 'admin' || u === 'admin' || u === 'super') {
      panels.push('admin');
    }
    
    // Kasa/Operator yetkileri
    if (r === 'operator' || u === 'kasiyer') {
      panels.push('kasa');
    }
    
    return panels.length > 0 ? panels : ['admin'];
  };

  const allowedPanels = user ? resolvePanel(user.username, user.role) : ['admin'];
  const showAdmin = allowedPanels.includes('admin');
  const showKasa = allowedPanels.includes('kasa');
  const showMutfak = allowedPanels.includes('mutfak');
  const showTerminal = allowedPanels.includes('terminal');
  
  // Personeller sekmesi: super_admin ve admin görebilir
  const userRole = user?.role?.toLowerCase() || '';
  const username = user?.username?.toLowerCase() || '';
  const showPersoneller = user && (
    userRole === 'super_admin' || 
    username === 'super' ||
    userRole === 'admin'
  );
  
  // Debug için console.log (production'da kaldırılabilir)
  if (user && userRole === 'admin') {
    console.log('[Layout] Admin user detected:', { username, role: userRole, showPersoneller });
  }
  
  const showSuperAdmin = user && (userRole === 'super_admin' || username === 'super');
  
  // Super admin "Tüm İşletmeler" modundayken sadece Super Admin paneli gösterilmeli
  // Diğer veri sayfaları (raporlar, menü, stok, vb.) sadece tenant seçildiğinde gösterilmeli
  const isSuperAdminInAllTenantsMode = showSuperAdmin && selectedTenantId === null;
  const showTenantDataPages = !isSuperAdminInAllTenantsMode; // Tenant seçilmediyse veri sayfalarını gizle

  const getNavClass = (isActive: boolean, variant: 'desktop' | 'mobile') => {
    if (variant === 'mobile') {
      return `flex items-center gap-2 rounded-lg border border-white/15 px-4 py-3 text-sm transition-colors ${
        isActive ? 'bg-white/15 text-white' : 'bg-white/5 text-white/80 hover:bg-white/10'
      }`;
    }
    return `px-4 py-2 rounded-lg transition-colors ${
      isActive ? 'bg-white/15 text-white shadow-inner shadow-primary-900/30' : 'hover:bg-white/10 text-white/80'
    }`;
  };

  const renderLink = (to: string, label: string, variant: 'desktop' | 'mobile') => (
    <NavLink
      key={`${variant}-${to}`}
      to={to}
      className={({ isActive }) => getNavClass(isActive, variant)}
      onClick={variant === 'mobile' ? () => setNavOpen(false) : undefined}
    >
      {label}
    </NavLink>
  );

  const renderNavLinks = (variant: 'desktop' | 'mobile') => (
    <>
      {/* Veri sayfaları sadece tenant seçildiğinde gösterilmeli */}
      {showAdmin && showTenantDataPages && (
        <>
          {renderLink('/dashboard', 'Ana Sayfa', variant)}
          {renderLink('/raporlar', 'Raporlar', variant)}
          {renderLink('/menu', 'Menü', variant)}
          {renderLink('/stok', 'Stok', variant)}
          {renderLink('/giderler', 'Giderler', variant)}
          {renderLink('/masalar', 'Masalar', variant)}
          {renderLink('/recete', 'Reçete', variant)}
          {renderLink('/asistan', 'Müşteri Asistanı', variant)}
          {renderLink('/isletme-asistani', 'İşletme Asistanı', variant)}
        </>
      )}
      {/* Personeller sadece tenant seçildiğinde gösterilmeli */}
      {showPersoneller && showTenantDataPages && renderLink('/personeller', 'Personeller', variant)}
      {/* Super Admin paneli her zaman gösterilmeli */}
      {showSuperAdmin && renderLink('/superadmin', 'Super Admin', variant)}
      {/* Kasa, Mutfak, Terminal sadece tenant seçildiğinde gösterilmeli */}
      {showKasa && showTenantDataPages && renderLink('/kasa', 'Kasa', variant)}
      {showMutfak && showTenantDataPages && renderLink('/mutfak', 'Mutfak', variant)}
      {showTerminal && showTenantDataPages && renderLink('/terminal', 'El Terminali', variant)}
    </>
  );

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header 
        className="relative sticky top-0 z-50 border-b border-white/15 shadow-lg backdrop-blur-md"
        style={{
          background: headerBackground,
          boxShadow: headerShadow,
        }}
      >
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.15),_transparent_55%)]" aria-hidden="true" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_bottom,_rgba(163,230,53,0.12),_transparent_65%)]" aria-hidden="true" />
        <div className="relative container mx-auto px-3 py-2 md:px-4 md:py-4">
          <div className="flex flex-wrap items-center gap-2 md:gap-6">
            <div className="flex flex-1 flex-col items-center gap-2 md:gap-3 text-center min-w-[180px] md:min-w-[260px]">
              <img
                src={displayLogo}
                alt={displayName}
                className="h-12 w-12 md:h-24 md:w-24 object-contain drop-shadow-[0_18px_28px_rgba(45,212,191,0.35)]"
                onError={(e) => {
                  // Logo yüklenemezse varsayılan logo'yu göster
                  if (e.currentTarget.src !== logo) {
                    e.currentTarget.src = logo;
                  }
                }}
              />
              <div className="space-y-0.5 md:space-y-1">
                <h1 className="text-lg md:text-4xl font-extrabold tracking-wide bg-gradient-to-r from-amber-100 via-lime-200 to-emerald-200 bg-clip-text text-transparent">
                  {displayName}
                </h1>
                <p className="text-xs md:text-base text-white/70 hidden md:block">
                  Hoş geldiniz!
                </p>
              </div>
            </div>

            <div className="ml-auto flex items-center gap-2 md:hidden">
              <button
                onClick={() => navigate('/system')}
                className="rounded-lg border border-white/20 bg-white/5 p-1.5 text-white/80 transition hover:bg-white/10"
                aria-label="Sistem ayarları"
              >
                <Settings className="h-4 w-4" />
              </button>
              <button
                onClick={toggleNav}
                className="rounded-lg border border-white/20 bg-white/5 p-1.5 text-white/80 transition hover:bg-white/10"
                aria-label="Menüyü aç"
              >
                <Menu className="h-4 w-4" />
              </button>
            </div>

            <div className="hidden md:flex items-center gap-4">
              <nav className="flex flex-wrap items-center gap-2">
                {renderNavLinks('desktop')}
              </nav>
              {showSuperAdmin && <TenantSwitcher />}
              <button
                onClick={() => navigate('/system')}
                className="rounded-xl border border-white/20 bg-white/5 px-4 py-2 text-white/80 transition hover:bg-white/10"
              >
                <Settings className="w-5 h-5" />
              </button>
              <button
                onClick={handleLogout}
                className="rounded-xl bg-gradient-to-r from-tertiary-500 via-tertiary-400 to-tertiary-500 px-4 py-2 text-white shadow-lg shadow-tertiary-900/40 transition hover:opacity-90"
              >
                <LogOut className="w-5 h-5" />
              </button>
            </div>

            {navOpen && (
              <div className="mt-4 w-full space-y-3 rounded-2xl border border-white/15 bg-white/5 p-4 shadow-lg shadow-primary-950/30 md:hidden">
                <nav className="flex flex-col gap-2">
                  {renderNavLinks('mobile')}
                </nav>
                <div className="flex flex-col gap-2 border-t border-white/10 pt-3">
                  <button
                    onClick={() => navigate('/system')}
                    className="flex items-center justify-center gap-2 rounded-lg border border-white/15 bg-white/5 px-4 py-3 text-sm text-white/80 transition hover:bg-white/10"
                  >
                    <Settings className="h-4 w-4" /> Sistem Ayarları
                  </button>
                  <button
                    onClick={handleLogout}
                    className="flex items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-tertiary-500 via-tertiary-400 to-tertiary-500 px-4 py-3 text-sm font-semibold text-white shadow shadow-tertiary-900/40 transition hover:opacity-90"
                  >
                    <LogOut className="h-4 w-4" /> Çıkış Yap
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 container mx-auto px-4 py-6">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="glass border-t border-white/20 py-4">
        <div className="container mx-auto px-4 text-center text-sm text-white/70">
          <p>Neso Modüler v0.2.0 - Rol bazlı yetkiler için login sayfasından giriş yapınız.</p>
        </div>
      </footer>
    </div>
  );
}

export default memo(Layout);

