import { NavLink } from 'react-router-dom';
import { 
  BarChart2, 
  Menu as MenuIcon, 
  Package, 
  CreditCard, 
  Users, 
  Settings, 
  LogOut, 
  ChevronLeft, 
  ChevronRight,
  TrendingDown,
  LayoutDashboard,
  UtensilsCrossed,
  Layers,
  Bot
} from 'lucide-react';
import { memo } from 'react';
import logo from '../assets/neso-logo.svg';

interface SidebarProps {
  isOpen: boolean;
  setIsOpen: (isOpen: boolean) => void;
  user: any;
  displayLogo: string;
  onLogout: () => void;
  showAdmin: boolean;
  showKasa: boolean;
  showMutfak: boolean;
  showTerminal: boolean;
  showPersoneller: boolean;
  showSuperAdmin: boolean;
  showTenantDataPages: boolean;
}

function Sidebar({ 
  isOpen, 
  setIsOpen, 
  user, 
  displayLogo, 
  onLogout,
  showAdmin,
  showKasa,
  showMutfak,
  showTerminal,
  showPersoneller,
  showSuperAdmin,
  showTenantDataPages
}: SidebarProps) {
  
  const navItems = [
    { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, show: showAdmin && showTenantDataPages },
    { to: '/raporlar', label: 'Raporlar', icon: BarChart2, show: showAdmin && showTenantDataPages },
    { to: '/menu', label: 'Menü Yönetimi', icon: MenuIcon, show: showAdmin && showTenantDataPages },
    { to: '/stok', label: 'Stok Takibi', icon: Package, show: showAdmin && showTenantDataPages },
    { to: '/giderler', label: 'Giderler', icon: TrendingDown, show: showAdmin && showTenantDataPages },
    { to: '/masalar', label: 'Masa Düzeni', icon: Layers, show: showAdmin && showTenantDataPages },
    { to: '/recete', label: 'Reçeteler', icon: UtensilsCrossed, show: showAdmin && showTenantDataPages },
    { to: '/asistan', label: 'Müşteri Asistanı', icon: Bot, show: showAdmin && showTenantDataPages },
    { to: '/isletme-asistani', label: 'İşletme Asistanı', icon: TrendingDown, show: showAdmin && showTenantDataPages },
    { to: '/personeller', label: 'Personeller', icon: Users, show: showPersoneller && showTenantDataPages },
    { to: '/superadmin', label: 'Sistem Yönetimi', icon: Settings, show: showSuperAdmin },
    { to: '/kasa', label: 'Kasa Ekranı', icon: CreditCard, show: showKasa && showTenantDataPages },
    { to: '/mutfak', label: 'Mutfak Ekranı', icon: UtensilsCrossed, show: showMutfak && showTenantDataPages },
    { to: '/terminal', label: 'El Terminali', icon: LayoutDashboard, show: showTerminal && showTenantDataPages },
  ];

  return (
    <>
      {/* Mobile Overlay */}
      <div 
        className={`fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-40 transition-opacity duration-300 md:hidden ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        onClick={() => setIsOpen(false)}
      />

      {/* Sidebar */}
      <aside 
        className={`fixed left-0 top-0 h-full glass-sidebar z-50 transition-all duration-500 ease-in-out flex flex-col
          ${isOpen ? 'w-72' : 'w-20 -left-20 md:left-0'} 
          ${isOpen ? 'translate-x-0' : 'md:translate-x-0'}`}
      >
        {/* Toggle Button (Desktop) */}
        <button 
          onClick={() => setIsOpen(!isOpen)}
          className="absolute -right-3 top-20 bg-emerald-500 text-white p-1 rounded-full shadow-lg shadow-emerald-500/40 hidden md:flex items-center justify-center hover:scale-110 transition-transform duration-300"
        >
          {isOpen ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
        </button>

        {/* Logo Section */}
        <div className={`p-6 flex items-center gap-4 ${!isOpen && 'justify-center'}`}>
          <img 
            src={displayLogo} 
            alt="Logo" 
            className={`transition-all duration-500 object-contain ${isOpen ? 'w-12 h-12' : 'w-10 h-10'} drop-shadow-[0_0_15px_rgba(16,185,129,0.3)]`}
            onError={(e) => {
              if (e.currentTarget.src !== logo) e.currentTarget.src = logo;
            }}
          />
          {isOpen && (
            <div className="flex flex-col min-w-0">
              <span className="font-bold text-lg text-white truncate leading-tight">Neso</span>
              <span className="text-xs text-emerald-400 font-medium tracking-wider uppercase">Modüler</span>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-4 space-y-1 overflow-y-auto">
          {navItems.filter(item => item.show).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }: { isActive: boolean }) => `
                flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-300 group
                ${isActive ? 'nav-link-active' : 'text-slate-400 hover:bg-white/5 hover:text-white'}
                ${!isOpen && 'justify-center'}
              `}
              onClick={() => window.innerWidth < 768 && setIsOpen(false)}
            >
              <item.icon size={22} className={`shrink-0 transition-transform duration-300 group-hover:scale-110 ${isOpen ? '' : 'mx-auto'}`} />
              {isOpen && <span className="font-medium truncate whitespace-nowrap">{item.label}</span>}
              {!isOpen && (
                <div className="absolute left-full ml-4 px-2 py-1 bg-slate-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity duration-300 z-[100] whitespace-nowrap border border-white/10">
                  {item.label}
                </div>
              )}
            </NavLink>
          ))}
        </nav>

        {/* User Profile / Footer */}
        <div className="p-4 border-t border-white/5 space-y-2">
          {isOpen && (
            <div className="flex items-center gap-3 p-2 rounded-xl bg-white/5 border border-white/5 mb-4">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center font-bold text-white shadow-lg">
                {user?.username?.[0]?.toUpperCase() || 'U'}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-white truncate">{user?.username || 'Kullanıcı'}</p>
                <p className="text-[10px] text-slate-500 uppercase tracking-tighter">{user?.role || 'Üye'}</p>
              </div>
            </div>
          )}

          <button
            onClick={onLogout}
            className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl text-red-400 hover:bg-red-500/10 transition-all duration-300 group ${!isOpen && 'justify-center'}`}
          >
            <LogOut size={22} className="shrink-0 transition-transform duration-300 group-hover:translate-x-1" />
            {isOpen && <span className="font-medium">Çıkış Yap</span>}
          </button>
        </div>
      </aside>
    </>
  );
}

export default memo(Sidebar);
