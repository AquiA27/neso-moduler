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
  Bot,
  Sparkles
} from 'lucide-react';
import { memo } from 'react';
import logo from '../assets/neso-logo.jpg';

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
    { to: '/analitik', label: 'Akıllı Analitik', icon: Sparkles, show: showAdmin && showTenantDataPages },
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
        className={`fixed inset-0 bg-slate-950/80 backdrop-blur-md z-40 transition-opacity duration-500 md:hidden ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        onClick={() => setIsOpen(false)}
      />

      {/* Sidebar */}
      <aside
        className={`fixed left-0 top-0 h-full glass-sidebar z-50 transition-all duration-500 ease-in-out flex flex-col
          ${isOpen ? 'w-72' : 'w-20 -left-20 md:left-0'}`}
      >
        {/* Toggle Button (Desktop) */}
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="absolute -right-3.5 top-20 bg-emerald-500 text-slate-950 p-1.5 rounded-full shadow-[0_0_20px_rgba(16,185,129,0.4)] hidden md:flex items-center justify-center hover:scale-110 active:scale-90 transition-all duration-300 z-50"
        >
          {isOpen ? <ChevronLeft size={16} strokeWidth={3} /> : <ChevronRight size={16} strokeWidth={3} />}
        </button>

        {/* Logo Section */}
        <div className={`p-8 flex items-center gap-4 ${!isOpen && 'justify-center'}`}>
          <div className="relative group cursor-pointer">
            <div className="absolute inset-0 bg-emerald-500/20 blur-xl rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
            <img
              src={displayLogo}
              alt="Logo"
              className={`relative transition-all duration-500 object-cover rounded-xl border border-white/5 ${isOpen ? 'w-14 h-14' : 'w-10 h-10'} drop-shadow-[0_0_15px_rgba(16,185,129,0.4)]`}
              onError={(e) => {
                if (e.currentTarget.src !== logo) e.currentTarget.src = logo;
              }}
            />
          </div>
          {isOpen && (
            <div className="flex flex-col min-w-0">
              <span className="font-extrabold text-2xl text-white tracking-tighter leading-none italic">NESO</span>
            </div>
          )}
        </div>

        {/* Navigation */}
        <div className="px-4 mb-4">
          {isOpen && <p className="text-[10px] font-bold text-slate-600 uppercase tracking-widest px-4 mb-2">Main Navigation</p>}
        </div>
        <nav className="flex-1 px-3 space-y-1.5 overflow-y-auto custom-scrollbar">
          {navItems.filter(item => item.show).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }: { isActive: boolean }) => `
                flex items-center gap-4 px-4 py-3.5 rounded-2xl transition-all duration-300 group relative
                ${isActive ? 'nav-link-active' : 'text-slate-400 hover:bg-white/[0.03] hover:text-white'}
                ${!isOpen && 'justify-center'}
              `}
              onClick={() => window.innerWidth < 768 && setIsOpen(false)}
            >
              {({ isActive }) => (
                <>
                  <item.icon size={20} strokeWidth={isActive ? 2.5 : 2} className={`shrink-0 transition-all duration-300 group-hover:scale-110 group-hover:rotate-3 ${isActive ? 'text-emerald-400' : ''}`} />
                  {isOpen && <span className={`font-semibold text-sm tracking-tight ${isActive ? 'text-white' : ''}`}>{item.label}</span>}
                  {!isOpen && (
                    <div className="absolute left-full ml-4 px-3 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl opacity-0 group-hover:opacity-100 pointer-events-none transition-all duration-300 z-[100] whitespace-nowrap shadow-2xl border border-white/10 translate-x-2 group-hover:translate-x-0">
                      {item.label}
                    </div>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* User Profile / Footer */}
        <div className="p-4 bg-slate-900/40 border-t border-white/[0.03] space-y-4">
          {isOpen && (
            <div className="group relative p-4 rounded-3xl bg-slate-950/50 border border-white/[0.03] hover:border-emerald-500/20 transition-all duration-500 cursor-pointer overflow-hidden">
              <div className="absolute inset-x-0 bottom-0 h-1 bg-gradient-to-r from-emerald-500 to-cyan-500 opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="flex items-center gap-4 relative z-10">
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-emerald-500 via-emerald-600 to-cyan-600 flex items-center justify-center font-black text-slate-950 shadow-lg group-hover:scale-110 transition-transform duration-500">
                  {user?.username?.[0]?.toUpperCase() || 'U'}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold text-white truncate group-hover:text-emerald-400 transition-colors uppercase tracking-tight">{user?.username || 'Kullanıcı'}</p>
                  <div className="flex items-center gap-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  </div>
                </div>
              </div>
            </div>
          )}

          <button
            onClick={onLogout}
            className={`w-full flex items-center gap-4 px-5 py-4 rounded-2xl text-slate-400 hover:bg-rose-500/10 hover:text-rose-400 transition-all duration-300 group ${!isOpen && 'justify-center'}`}
          >
            <LogOut size={20} className="shrink-0 transition-transform duration-300 group-hover:rotate-12" />
            {isOpen && <span className="font-bold text-sm tracking-widest uppercase">Sign Out</span>}
          </button>
        </div>
      </aside>
    </>
  );
}

export default memo(Sidebar);
