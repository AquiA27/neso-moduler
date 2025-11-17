import { useState, useEffect } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { customizationApi } from '../lib/api';
import { Menu, Settings, LogOut } from 'lucide-react';
import logo from '../assets/fistik-logo.svg';

export default function Layout() {
  const { user, logout, tenantId, tenantCustomization, setTenantCustomization } = useAuthStore();
  const navigate = useNavigate();
  const [navOpen, setNavOpen] = useState(false);
  
  // Tenant customization'ı yükle
  useEffect(() => {
    const loadCustomization = async () => {
      if (!tenantId) {
        setTenantCustomization(null);
        return;
      }
      
      try {
        const response = await customizationApi.get(tenantId);
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
  }, [tenantId, setTenantCustomization]);
  
  // Logo ve app name'i belirle
  const displayLogo = tenantCustomization?.logo_url || logo;
  const displayName = tenantCustomization?.app_name || (user?.role === 'super_admin' ? 'Neso Modüler' : 'Fıstık Kafe Yönetim Paneli');

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const toggleNav = () => setNavOpen((prev) => !prev);


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
      {showAdmin && (
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
      {showPersoneller && renderLink('/personeller', 'Personeller', variant)}
      {showSuperAdmin && renderLink('/superadmin', 'Super Admin', variant)}
      {showKasa && renderLink('/kasa', 'Kasa', variant)}
      {showMutfak && renderLink('/mutfak', 'Mutfak', variant)}
      {showTerminal && renderLink('/terminal', 'El Terminali', variant)}
    </>
  );

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="relative sticky top-0 z-50 border-b border-white/15 bg-gradient-to-r from-emerald-900/90 via-primary-900 to-primary-900 shadow-lg shadow-primary-950/40 backdrop-blur-md">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.15),_transparent_55%)]" aria-hidden="true" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_bottom,_rgba(163,230,53,0.12),_transparent_65%)]" aria-hidden="true" />
        <div className="relative container mx-auto px-4 py-4">
          <div className="flex flex-wrap items-center gap-4 md:gap-6">
            <div className="flex flex-1 flex-col items-center gap-3 text-center min-w-[260px]">
              <img
                src={displayLogo}
                alt={displayName}
                className="h-20 w-20 md:h-24 md:w-24 object-contain drop-shadow-[0_18px_28px_rgba(45,212,191,0.35)]"
                onError={(e) => {
                  // Logo yüklenemezse varsayılan logo'yu göster
                  if (e.currentTarget.src !== logo) {
                    e.currentTarget.src = logo;
                  }
                }}
              />
              <div className="space-y-1">
                <h1 className="text-3xl md:text-4xl font-extrabold tracking-wide bg-gradient-to-r from-amber-100 via-lime-200 to-emerald-200 bg-clip-text text-transparent">
                  {displayName}
                </h1>
                <p className="text-sm md:text-base text-white/70">
                  Hoş geldiniz!
                </p>
              </div>
            </div>

            <div className="ml-auto flex items-center gap-3 md:hidden">
              <button
                onClick={() => navigate('/system')}
                className="rounded-xl border border-white/20 bg-white/5 p-2 text-white/80 transition hover:bg-white/10"
                aria-label="Sistem ayarları"
              >
                <Settings className="h-5 w-5" />
              </button>
              <button
                onClick={toggleNav}
                className="rounded-xl border border-white/20 bg-white/5 p-2 text-white/80 transition hover:bg-white/10"
                aria-label="Menüyü aç"
              >
                <Menu className="h-5 w-5" />
              </button>
            </div>

            <div className="hidden md:flex items-center gap-4">
              <nav className="flex flex-wrap items-center gap-2">
                {renderNavLinks('desktop')}
              </nav>
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

