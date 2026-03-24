import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { superadminApi, subscriptionApi, paymentApi, customizationApi } from '../lib/api';
import {
  Building2, CreditCard, Settings, Plus, Search, Edit, Trash2,
  BarChart3, Users, TrendingUp, AlertCircle, CheckCircle, XCircle,
  Calendar, DollarSign, Package, Globe, LogOut, Menu, X, Bell,
  ChevronRight, ArrowUpRight, Activity
} from 'lucide-react';

interface Tenant {
  id: number;
  ad: string;
  vergi_no?: string;
  telefon?: string;
  aktif: boolean;
}

interface Subscription {
  id: number;
  isletme_id: number;
  plan_type: string;
  status: string;
  max_subeler: number;
  max_kullanicilar: number;
  max_menu_items: number;
  ayllik_fiyat: number;
  baslangic_tarihi: string;
  bitis_tarihi?: string;
}

interface Payment {
  id: number;
  isletme_id: number;
  tutar: number;
  odeme_turu: string;
  durum: string;
  fatura_no?: string;
  odeme_tarihi?: string;
  created_at: string;
}

interface Customization {
  id: number;
  isletme_id: number;
  domain?: string;
  app_name?: string;
  logo_url?: string;
  primary_color?: string;
  secondary_color?: string;
}

interface DashboardStats {
  isletmeler: { total: number; active: number };
  subeler: { total: number };
  kullanicilar: { total: number };
  abonelikler: { active: number; plan_distribution: Array<{ plan_type: string; count: number }> };
  finansal: {
    this_month_revenue: number;
    pending_payments: { total: number; count: number };
  };
}

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'tenants' | 'subscriptions' | 'payments' | 'customizations' | 'quick-setup'>('dashboard');
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [loading, setLoading] = useState(false);
  
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    loadData();
  }, [activeTab]);

  const loadData = async () => {
    setLoading(true);
    try {
      if (activeTab === 'dashboard') {
        const statsRes = await superadminApi.dashboardStats();
        setStats(statsRes.data);
      } else if (activeTab === 'tenants') {
        const tenantsRes = await superadminApi.tenantsList();
        setTenants(tenantsRes.data);
      } else if (activeTab === 'subscriptions') {
        const subsRes = await subscriptionApi.list();
        setSubscriptions(subsRes.data);
      } else if (activeTab === 'payments') {
        const paymentsRes = await paymentApi.list();
        setPayments(paymentsRes.data);
      }
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const filteredTenants = tenants.filter(t =>
    t.ad.toLowerCase().includes(searchTerm.toLowerCase()) ||
    t.vergi_no?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredSubscriptions = subscriptions.filter(s =>
    s.isletme_id.toString().includes(searchTerm)
  );

  const filteredPayments = payments.filter(p =>
    p.isletme_id.toString().includes(searchTerm) ||
    p.fatura_no?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const navItems = [
    { id: 'dashboard', label: 'Genel Bakış', icon: BarChart3 },
    { id: 'tenants', label: 'İşletmeler', icon: Building2 },
    { id: 'subscriptions', label: 'Abonelikler', icon: Package },
    { id: 'payments', label: 'Finans', icon: CreditCard },
    { id: 'customizations', label: 'Uygulama Ayarları', icon: Settings },
    { id: 'quick-setup', label: 'Hızlı Kurulum', icon: Plus },
  ];

  return (
    <div className="flex h-screen bg-[#F8FAFC] font-sans overflow-hidden">
      
      {/* Sidebar */}
      <aside className={`bg-[#0B3B24] text-white flex flex-col transition-all duration-300 ${isSidebarOpen ? 'w-64' : 'w-20'}`}>
        <div className="h-20 flex items-center justify-between px-6 border-b border-white/10">
          {isSidebarOpen ? (
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-emerald-500 flex items-center justify-center">
                <BoxIcon className="w-5 h-5 text-white" />
              </div>
              <span className="font-bold text-lg tracking-wide">Neso<span className="text-emerald-400">Admin</span></span>
            </div>
          ) : (
            <div className="w-8 h-8 mx-auto rounded-lg bg-emerald-500 flex items-center justify-center">
              <BoxIcon className="w-5 h-5 text-white" />
            </div>
          )}
        </div>

        <div className="flex-1 py-6 px-4 space-y-2 overflow-y-auto">
          {navItems.map(({ id, label, icon: Icon }) => {
            const isActive = activeTab === id;
            return (
              <button
                key={id}
                onClick={() => setActiveTab(id as any)}
                className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-200 group ${
                  isActive 
                    ? 'bg-emerald-500 text-white shadow-md shadow-emerald-900/20' 
                    : 'text-white/60 hover:bg-white/5 hover:text-white'
                }`}
                title={!isSidebarOpen ? label : ''}
              >
                <Icon className={`w-5 h-5 flex-shrink-0 ${isActive ? 'text-white' : 'text-white/60 group-hover:text-white'}`} />
                {isSidebarOpen && <span className="font-medium text-sm">{label}</span>}
              </button>
            )
          })}
        </div>

        <div className="p-4 border-t border-white/10">
          <button
            onClick={handleLogout}
            className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl text-red-300 hover:bg-red-500/10 transition-colors ${
              !isSidebarOpen && 'justify-center'
            }`}
            title={!isSidebarOpen ? 'Çıkış Yap' : ''}
          >
            <LogOut className="w-5 h-5" />
            {isSidebarOpen && <span className="font-medium text-sm">Çıkış Yap</span>}
          </button>
        </div>
      </aside>

      {/* Main Layout */}
      <div className="flex-1 flex flex-col min-w-0">
        
        {/* Header */}
        <header className="h-20 bg-white border-b border-gray-100 flex items-center justify-between px-8 shadow-sm z-10">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="p-2 -ml-2 rounded-lg text-gray-400 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              <Menu className="w-5 h-5" />
            </button>
            <h1 className="text-xl font-bold text-gray-800 tracking-tight">
              {navItems.find(i => i.id === activeTab)?.label}
            </h1>
          </div>
          
          <div className="flex items-center gap-6">
            <button className="relative p-2 text-gray-400 hover:bg-gray-50 rounded-full transition-colors">
              <Bell className="w-5 h-5" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border-2 border-white"></span>
            </button>
            <div className="h-8 w-px bg-gray-200"></div>
            <div className="flex items-center gap-3 cursor-pointer group">
              <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-700 font-bold border-2 border-white shadow-sm">
                {user?.username?.charAt(0).toUpperCase() || 'A'}
              </div>
              <div className="hidden md:block text-sm">
                <p className="font-semibold text-gray-700 group-hover:text-emerald-600 transition-colors">{user?.username}</p>
                <p className="text-xs text-gray-400">Yönetici</p>
              </div>
            </div>
          </div>
        </header>

        {/* Dynamic Content */}
        <main className="flex-1 overflow-y-auto p-4 md:p-8">
          <div className="max-w-7xl mx-auto">
            {loading && (
              <div className="h-64 flex items-center justify-center">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-500"></div>
              </div>
            )}

            {!loading && activeTab === 'dashboard' && stats && <DashboardTab stats={stats} />}
            {!loading && activeTab === 'tenants' && (
              <TenantsTab tenants={filteredTenants} searchTerm={searchTerm} onSearchChange={setSearchTerm} onRefresh={loadData} />
            )}
            {!loading && activeTab === 'subscriptions' && (
              <SubscriptionsTab subscriptions={filteredSubscriptions} searchTerm={searchTerm} onSearchChange={setSearchTerm} onRefresh={loadData} />
            )}
            {!loading && activeTab === 'payments' && (
              <PaymentsTab payments={filteredPayments} searchTerm={searchTerm} onSearchChange={setSearchTerm} onRefresh={loadData} />
            )}
            {!loading && activeTab === 'customizations' && <CustomizationsTab onRefresh={loadData} />}
            {!loading && activeTab === 'quick-setup' && <QuickSetupTab onComplete={loadData} />}
          </div>
        </main>

      </div>
    </div>
  );
}

// Just an SVG wrapper for the Box Icon
function BoxIcon(props: any) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
      <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
      <line x1="12" y1="22.08" x2="12" y2="12"></line>
    </svg>
  );
}

// ----------------------------------------------------
// Dashboard Tab
// ----------------------------------------------------
function DashboardTab({ stats }: { stats: DashboardStats }) {
  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      
      {/* Top Banner / Welcome */}
      <div className="bg-gradient-to-r from-[#0B3B24] to-emerald-800 rounded-2xl p-8 text-white shadow-lg overflow-hidden relative">
        <div className="relative z-10 w-full md:w-2/3">
          <h2 className="text-3xl font-bold mb-2">Sisteme Hoş Geldiniz 🎉</h2>
          <p className="text-emerald-50/80 leading-relaxed max-w-lg">
            Platformunuzun tüm verilerini, aktif abonelikleri ve gelir özetlerini buradan canlı olarak takip edebilirsiniz.
          </p>
        </div>
        <div className="absolute right-0 top-0 bottom-0 w-1/3 bg-white/5 skew-x-12 transform origin-bottom border-l border-white/10 hidden md:block"></div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard title="Toplam İşletme" value={stats.isletmeler.total} subtitle={`${stats.isletmeler.active} aktif`} icon={Building2} bg="bg-blue-50" color="text-blue-600" />
        <StatCard title="Kayıtlı Şube" value={stats.subeler.total} icon={Activity} bg="bg-emerald-50" color="text-emerald-600" />
        <StatCard title="Kullanıcı Ort." value={stats.kullanicilar.total} icon={Users} bg="bg-indigo-50" color="text-indigo-600" />
        <StatCard title="Aktif Abonelik" value={stats.abonelikler.active} icon={Package} bg="bg-orange-50" color="text-orange-500" />
      </div>

      {/* Financials & Plans */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 flex items-center justify-between group">
            <div>
              <p className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-2">Aylık Tahmini Gelir</p>
              <h3 className="text-3xl font-bold text-gray-900 group-hover:text-emerald-600 transition-colors">
                ₺{stats.finansal.this_month_revenue.toLocaleString('tr-TR')}
              </h3>
            </div>
            <div className="w-16 h-16 rounded-full bg-emerald-50 flex items-center justify-center">
              <DollarSign className="w-8 h-8 text-emerald-500" />
            </div>
          </div>
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 flex items-center justify-between group">
            <div>
              <p className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-2">Bekleyen Tahsilat</p>
              <h3 className="text-3xl font-bold text-gray-900 group-hover:text-rose-600 transition-colors">
                ₺{stats.finansal.pending_payments.total.toLocaleString('tr-TR')}
              </h3>
              <p className="text-sm text-gray-500 mt-2">{stats.finansal.pending_payments.count} adet açık ödeme</p>
            </div>
            <div className="w-16 h-16 rounded-full bg-rose-50 flex items-center justify-center">
              <TrendingUp className="w-8 h-8 text-rose-500" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-bold text-gray-800">Plan Dağılımı</h3>
            <ArrowUpRight className="w-4 h-4 text-gray-400" />
          </div>
          <div className="space-y-4">
            {stats.abonelikler.plan_distribution.map((plan, idx) => (
              <div key={idx} className="flex items-center justify-between p-3 rounded-xl bg-gray-50 hover:bg-gray-100 transition-colors">
                <div className="flex items-center gap-3">
                  <span className={`w-3 h-3 rounded-full ${idx === 0 ? 'bg-emerald-500' : idx === 1 ? 'bg-blue-500' : 'bg-purple-500'}`}></span>
                  <span className="text-sm font-medium text-gray-700 capitalize">{plan.plan_type} Plan</span>
                </div>
                <span className="font-bold text-gray-900 bg-white px-3 py-1 rounded-full shadow-sm border border-gray-100">{plan.count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ title, value, subtitle, icon: Icon, bg, color }: any) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 flex flex-col group hover:shadow-md transition-all">
      <div className="flex justify-between items-start mb-4">
        <div className={`p-3 rounded-xl ${bg} ${color}`}>
          <Icon className="w-6 h-6" />
        </div>
        {subtitle && <span className="text-xs font-medium px-2 py-1 bg-gray-50 text-gray-500 rounded-full border border-gray-100">{subtitle}</span>}
      </div>
      <div>
        <h4 className="text-3xl font-bold text-gray-900">{value}</h4>
        <p className="text-sm font-medium text-gray-500 mt-1">{title}</p>
      </div>
    </div>
  );
}

// ----------------------------------------------------
// Shared Table Wrapper
// ----------------------------------------------------
function CardTable({ title, searchPlaceholder, searchTerm, onSearchChange, children }: any) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="p-6 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <h2 className="text-xl font-bold text-gray-800">{title}</h2>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
          <input
            type="text"
            placeholder={searchPlaceholder}
            value={searchTerm}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-10 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 text-sm w-full sm:w-64 transition-all"
          />
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          {children}
        </table>
      </div>
    </div>
  )
}

// ----------------------------------------------------
// Tenants Tab
// ----------------------------------------------------
function TenantsTab({ tenants, searchTerm, onSearchChange, onRefresh }: any) {
  const [editingTenant, setEditingTenant] = useState<Tenant | null>(null);

  const handleDelete = async (id: number) => {
    if (window.confirm('Bu işletmeyi (ve tüm verilerini) kalıcı olarak silmek istediğinize emin misiniz?')) {
      try {
        await superadminApi.tenantDelete(id);
        onRefresh();
      } catch (err: any) {
        alert('Silme hatası: ' + err.message);
      }
    }
  };

  return (
    <>
      <CardTable title="Kayıtlı İşletmeler" searchPlaceholder="İşletme adı veya vergi no ara..." searchTerm={searchTerm} onSearchChange={onSearchChange}>
        <thead className="bg-gray-50/50">
          <tr>
            <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">İşletme Bilgisi</th>
            <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">İletişim</th>
            <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Durum</th>
            <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase tracking-wider text-right">İşlemler</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {tenants.map((tenant: Tenant) => (
            <tr key={tenant.id} className="hover:bg-gray-50/50 transition-colors">
              <td className="px-6 py-4">
                <div className="font-semibold text-gray-900">{tenant.ad}</div>
                <div className="text-sm text-gray-400 mt-0.5">ID: {tenant.id} &bull; V.No: {tenant.vergi_no || '-'}</div>
              </td>
              <td className="px-6 py-4 text-sm text-gray-600">{tenant.telefon || '-'}</td>
              <td className="px-6 py-4">
                {tenant.aktif ? (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-100">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> Aktif
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-100">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span> Pasif
                  </span>
                )}
              </td>
              <td className="px-6 py-4 text-right">
                <div className="flex items-center justify-end gap-3">
                  <button onClick={() => setEditingTenant(tenant)} className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors" title="Düzenle">
                    <Edit className="w-4 h-4" />
                  </button>
                  <button onClick={() => handleDelete(tenant.id)} className="p-2 text-gray-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors" title="Sil">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
          {tenants.length === 0 && (
            <tr><td colSpan={4} className="px-6 py-12 text-center text-gray-500">Kayıt bulunamadı.</td></tr>
          )}
        </tbody>
      </CardTable>

      {/* Editing Modal */}
      {editingTenant && (
        <div className="fixed inset-0 bg-gray-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in">
          <div className="bg-white rounded-2xl p-8 max-w-md w-full shadow-2xl scale-100 animate-in zoom-in-95 duration-200">
            <h3 className="text-2xl font-bold text-gray-900 mb-6">İşletme Düzenle</h3>
            <div className="space-y-5">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1.5">İşletme Adı</label>
                <input type="text" value={editingTenant.ad} onChange={(e) => setEditingTenant({ ...editingTenant, ad: e.target.value })} className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition-all font-medium" />
              </div>
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1.5">Vergi No</label>
                <input type="text" value={editingTenant.vergi_no || ''} onChange={(e) => setEditingTenant({ ...editingTenant, vergi_no: e.target.value })} className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 transition-all text-sm" />
              </div>
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-1.5">Telefon</label>
                <input type="text" value={editingTenant.telefon || ''} onChange={(e) => setEditingTenant({ ...editingTenant, telefon: e.target.value })} className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 transition-all text-sm" />
              </div>
              <label className="flex items-center gap-3 p-4 bg-gray-50 rounded-xl border border-gray-200 cursor-pointer hover:bg-gray-100 transition-colors">
                <input type="checkbox" checked={editingTenant.aktif} onChange={(e) => setEditingTenant({ ...editingTenant, aktif: e.target.checked })} className="w-5 h-5 text-emerald-600 rounded border-gray-300 focus:ring-emerald-500" />
                <span className="font-semibold text-gray-700">İşletme Aktif</span>
              </label>
            </div>
            <div className="mt-8 flex justify-end gap-3">
              <button onClick={() => setEditingTenant(null)} className="px-5 py-2.5 rounded-xl text-gray-600 font-semibold hover:bg-gray-100 transition-colors">İptal</button>
              <button onClick={async () => {
                try {
                  await superadminApi.tenantUpdate(editingTenant.id, {
                    ad: editingTenant.ad, vergi_no: editingTenant.vergi_no, telefon: editingTenant.telefon, aktif: editingTenant.aktif
                  });
                  setEditingTenant(null); onRefresh();
                } catch (err: any) { alert('Hata: ' + err.message); }
              }} className="px-5 py-2.5 bg-emerald-600 text-white font-semibold rounded-xl hover:bg-emerald-700 shadow-sm transition-colors">Değişiklikleri Kaydet</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ----------------------------------------------------
// Subscriptions Tab
// ----------------------------------------------------
function SubscriptionsTab({ subscriptions, searchTerm, onSearchChange }: any) {
  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex items-center justify-between">
         <div>
            <h2 className="text-2xl font-bold text-gray-900">Abonelik Yönetimi</h2>
            <p className="text-sm text-gray-500 mt-1">Sistemdeki tüm işletmelerin aktif-pasif lisans durumları</p>
         </div>
         <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
          <input type="text" placeholder="İşletme ID ile ara..." value={searchTerm} onChange={(e) => onSearchChange(e.target.value)} className="pl-10 pr-4 py-2 border border-gray-200 bg-white rounded-xl focus:ring-2 focus:ring-emerald-500 w-64 shadow-sm" />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {subscriptions.map((sub: Subscription) => (
          <div key={sub.id} className="bg-white border border-gray-100 rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow relative overflow-hidden group">
            {sub.status === 'active' && <div className="absolute top-0 right-0 w-2 h-full bg-emerald-500"></div>}
            {sub.status === 'suspended' && <div className="absolute top-0 right-0 w-2 h-full bg-orange-500"></div>}
            {sub.status === 'cancelled' && <div className="absolute top-0 right-0 w-2 h-full bg-rose-500"></div>}
            
            <div className="flex items-center justify-between mb-5">
              <div>
                <h3 className="text-lg font-bold text-gray-800">İşletme #{sub.isletme_id}</h3>
                <span className="text-xs text-gray-400 font-medium">Plan Sınırları &amp; Durum</span>
              </div>
              <span className={`px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wide
                  ${sub.status === 'active' ? 'bg-emerald-50 text-emerald-700' :
                    sub.status === 'suspended' ? 'bg-orange-50 text-orange-700' : 'bg-rose-50 text-rose-700'
                }`}>
                {sub.status}
              </span>
            </div>
            
            <div className="space-y-3 p-4 bg-gray-50/50 rounded-xl border border-gray-100/50">
              <div className="flex justify-between items-center text-sm">
                <span className="text-gray-500">Tarife:</span>
                <span className="font-bold text-gray-900 capitalize">{sub.plan_type}</span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-gray-500">Aylık Lisans Ücreti:</span>
                <span className="font-bold text-gray-900">₺{sub.ayllik_fiyat.toLocaleString('tr-TR')}</span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-gray-500">Max Şube:</span>
                <span className="font-semibold text-gray-700 bg-white px-2 py-0.5 rounded shadow-sm border border-gray-100">{sub.max_subeler}</span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-gray-500">Max Kullanıcı:</span>
                <span className="font-semibold text-gray-700 bg-white px-2 py-0.5 rounded shadow-sm border border-gray-100">{sub.max_kullanicilar}</span>
              </div>
            </div>
          </div>
        ))}
        {subscriptions.length === 0 && (
          <div className="col-span-3 text-center py-12 text-gray-500 bg-white rounded-2xl border border-gray-100 border-dashed">
            İlgili abonelik bulunamadı.
          </div>
        )}
      </div>
    </div>
  );
}

// ----------------------------------------------------
// Payments Tab
// ----------------------------------------------------
function PaymentsTab({ payments, searchTerm, onSearchChange }: any) {
  return (
    <CardTable title="Tüm Ödemeler / Finansal Hareketler" searchPlaceholder="Fatura veya ID ara..." searchTerm={searchTerm} onSearchChange={onSearchChange}>
      <thead className="bg-gray-50/50 border-b border-gray-100">
        <tr>
          <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase">Referans</th>
          <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase">İşletme &amp; Tutar</th>
          <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase">Metod</th>
          <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase">Tarih</th>
          <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase text-right">Düzen & Durum</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-gray-100">
        {payments.map((payment: Payment) => (
          <tr key={payment.id} className="hover:bg-gray-50/50 transition-colors">
            <td className="px-6 py-4">
              <span className="font-mono text-xs font-semibold text-gray-600 bg-gray-100 px-2 py-1 rounded-md">#{payment.id}</span>
            </td>
            <td className="px-6 py-4">
              <div className="font-bold text-gray-900">₺{payment.tutar.toLocaleString('tr-TR')}</div>
              <div className="text-xs font-medium text-gray-500 mt-0.5">İşletme ID: {payment.isletme_id}</div>
            </td>
            <td className="px-6 py-4">
              <div className="text-sm font-medium text-gray-700 bg-white shadow-sm border border-gray-200 px-3 py-1 rounded-lg inline-flex items-center gap-2">
                <CreditCard className="w-4 h-4 text-emerald-600" />
                <span className="uppercase text-xs">{payment.odeme_turu}</span>
              </div>
            </td>
            <td className="px-6 py-4 text-sm font-medium text-gray-500">
              {payment.odeme_tarihi ? new Date(payment.odeme_tarihi).toLocaleDateString('tr-TR') : '-'}
            </td>
            <td className="px-6 py-4 text-right">
              {payment.durum === 'completed' ? (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-100"><CheckCircle className="w-3.5 h-3.5" /> Ödendi</span>
              ) : payment.durum === 'pending' ? (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-orange-50 text-orange-700 border border-orange-100"><AlertCircle className="w-3.5 h-3.5" /> Bekliyor</span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-50 text-rose-700 border border-rose-100"><XCircle className="w-3.5 h-3.5" /> Başarısız</span>
              )}
            </td>
          </tr>
        ))}
         {payments.length === 0 && (
          <tr><td colSpan={5} className="px-6 py-12 text-center text-gray-500">Kayıt bulunamadı.</td></tr>
        )}
      </tbody>
    </CardTable>
  );
}

// ----------------------------------------------------
// Customizations Tab
// ----------------------------------------------------
function CustomizationsTab({ onRefresh }: { onRefresh: () => void }) {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [selectedTenant, setSelectedTenant] = useState<number | ''>('');
  const [customization, setCustomization] = useState<Customization | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    superadminApi.tenantsList().then((res: any) => setTenants(res.data)).catch(console.error);
  }, []);

  useEffect(() => {
    if (selectedTenant) {
      setLoading(true);
      customizationApi.get(Number(selectedTenant))
        .then((res: any) => setCustomization(res.data))
        .catch(() => setCustomization({ id: 0, isletme_id: Number(selectedTenant), domain: '', app_name: '', logo_url: '', primary_color: '#3b82f6', secondary_color: '#1e40af' }))
        .finally(() => setLoading(false));
    } else {
      setCustomization(null);
    }
  }, [selectedTenant]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customization) return;
    try {
      if (customization.id) await customizationApi.update(customization.isletme_id, customization);
      else await customizationApi.create(customization);
      alert('Seçili işletmenin beyaz etiket yapılandırması (white-label) başarıyla güncellendi!');
      onRefresh();
    } catch (err: any) { alert('Hata: ' + err.message); }
  };

  return (
    <div className="max-w-4xl animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
        <div className="flex justify-between items-start mb-8 pb-6 border-b border-gray-100">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">White-Label & Marka Yönetimi</h2>
            <p className="text-gray-500 mt-2 text-sm">Bir işletme seçerek o işletmeye özel sistem adı, logo ve temel renk kodlarını belirleyebilirsiniz.</p>
          </div>
          <div className="p-3 bg-indigo-50 rounded-xl text-indigo-600 hidden sm:block">
            <Globe className="w-6 h-6" />
          </div>
        </div>

        <div className="mb-8 p-6 bg-gray-50 border border-gray-200 rounded-xl">
          <label className="block text-sm font-bold text-gray-700 mb-2">Kurulum Yapılacak İşletme (Tenant)</label>
          <select
            className="w-full px-4 py-3 bg-white border border-gray-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition-shadow appearance-none font-medium"
            value={selectedTenant} onChange={e => setSelectedTenant(Number(e.target.value) || '')}
          >
            <option value="">Ayar yapılacak işletmeyi seçiniz...</option>
            {tenants.map(t => <option key={t.id} value={t.id}>{t.ad} (ID: {t.id})</option>)}
          </select>
        </div>

        {loading && <div className="text-center py-10 font-medium text-emerald-600 animate-pulse">Konfigürasyon Yükleniyor...</div>}

        {!loading && customization && (
          <form onSubmit={handleSave} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="space-y-2">
                <label className="block text-sm font-bold text-gray-700">Canlı Domain / Alt Domain</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <Globe className="h-5 w-5 text-gray-400" />
                  </div>
                  <input type="text" value={customization.domain || ''} placeholder="ornek.neso.com" onChange={(e) => setCustomization({ ...customization, domain: e.target.value })} className="pl-11 w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:bg-white transition-all text-sm" />
                </div>
              </div>
              <div className="space-y-2">
                <label className="block text-sm font-bold text-gray-700">Uygulama Sistem Adı</label>
                <input type="text" value={customization.app_name || ''} placeholder="Müşterinin Göreceği Panel Adı" onChange={(e) => setCustomization({ ...customization, app_name: e.target.value })} className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:bg-white transition-all text-sm" />
              </div>
              <div className="space-y-2 md:col-span-2">
                <label className="block text-sm font-bold text-gray-700">Giriş ve Header Logo URL</label>
                <input type="url" value={customization.logo_url || ''} placeholder="https://cdn.example.com/logo.png" onChange={(e) => setCustomization({ ...customization, logo_url: e.target.value })} className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:bg-white transition-all text-sm" />
                <p className="text-xs text-gray-400 mt-1">Lütfen tam uzantıyı (https://) kullandığınızdan emin olun. SVG desteklenir.</p>
              </div>
              
              <div className="p-5 border border-gray-100 bg-gray-50 rounded-xl space-y-4">
                 <label className="block text-sm font-bold text-gray-700">Ana Tema Rengi (Primary Color)</label>
                 <div className="flex gap-4 items-center">
                    <input type="color" value={customization.primary_color || '#3b82f6'} onChange={(e) => setCustomization({ ...customization, primary_color: e.target.value })} className="w-14 h-14 rounded-lg cursor-pointer border-0 p-0 shadow-sm shrink-0" />
                    <input type="text" value={customization.primary_color || '#3b82f6'} onChange={(e) => setCustomization({ ...customization, primary_color: e.target.value })} className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl font-mono text-sm uppercase shrink" />
                 </div>
              </div>

               <div className="p-5 border border-gray-100 bg-gray-50 rounded-xl space-y-4">
                 <label className="block text-sm font-bold text-gray-700">İkincil / Vurgu Rengi (Secondary)</label>
                 <div className="flex gap-4 items-center">
                    <input type="color" value={customization.secondary_color || '#1e40af'} onChange={(e) => setCustomization({ ...customization, secondary_color: e.target.value })} className="w-14 h-14 rounded-lg cursor-pointer border-0 p-0 shadow-sm shrink-0" />
                    <input type="text" value={customization.secondary_color || '#1e40af'} onChange={(e) => setCustomization({ ...customization, secondary_color: e.target.value })} className="w-full px-4 py-3 bg-white border border-gray-200 rounded-xl font-mono text-sm uppercase shrink" />
                 </div>
              </div>

            </div>
            
            <div className="flex items-center justify-end pt-6 border-t border-gray-100">
              <button type="submit" className="px-8 py-3 bg-emerald-600 text-white font-bold rounded-xl hover:bg-emerald-700 hover:shadow-lg hover:shadow-emerald-600/20 transition-all flex items-center gap-2">
                 <CheckCircle className="w-5 h-5" />
                Özelleştirmeyi Canlıya Al
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

// ----------------------------------------------------
// Quick Setup Tab
// ----------------------------------------------------
function QuickSetupTab({ onComplete }: { onComplete: () => void }) {
  const [formData, setFormData] = useState({
    isletme_ad: '', isletme_vergi_no: '', isletme_telefon: '', sube_ad: 'Merkez Şube',
    admin_username: '', admin_password: '', plan_type: 'basic', ayllik_fiyat: 0,
    domain: '', app_name: '', logo_url: '', primary_color: '#10b981',
  });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await superadminApi.quickSetup(formData);
      alert('Süper! İşletme, Yönetici Hesabı ve Abonelik başarıyla tek adımda kuruldu.');
      setFormData({ isletme_ad: '', isletme_vergi_no: '', isletme_telefon: '', sube_ad: 'Merkez Şube', admin_username: '', admin_password: '', plan_type: 'basic', ayllik_fiyat: 0, domain: '', app_name: '', logo_url: '', primary_color: '#10b981' });
      onComplete();
    } catch (error: any) { alert('Hata: ' + (error.response?.data?.detail || error.message)); }
    finally { setLoading(false); }
  };

  const formSections = [
    {
      title: 'İşletme ve İletişim Bilgileri',
      fields: [
        { key: 'isletme_ad', label: 'İşletme Adı *', type: 'text', required: true, width: 'full' },
        { key: 'isletme_vergi_no', label: 'Vergi Numarası', type: 'text', width: 'half' },
        { key: 'isletme_telefon', label: 'İletişim Telefonu', type: 'text', width: 'half' },
        { key: 'sube_ad', label: 'Varsayılan Şube Adı', type: 'text', width: 'half' },
      ]
    },
    {
      title: 'Sistem Yöneticisi Giriş',
      fields: [
        { key: 'admin_username', label: 'Yönetici Kullanıcı Adı *', type: 'text', required: true, width: 'half' },
        { key: 'admin_password', label: 'Yönetici Güvenli Şifresi *', type: 'password', required: true, minLength: 6, width: 'half' },
      ]
    },
    {
      title: 'Abonelik ve Plan',
      fields: [
        { key: 'plan_type', label: 'Paket / Plan', type: 'select', width: 'half', options: [{v:'basic', l:'Basic Plan'}, {v:'pro', l:'Pro Plan'}, {v:'enterprise', l:'Enterprise Plan'}] },
        { key: 'ayllik_fiyat', label: 'Aylık Fatura Tutarı (₺)', type: 'number', step: '0.01', width: 'half' },
      ]
    },
    {
      title: 'Hızlı Uygulama Görünümü (White-label)',
      fields: [
        { key: 'domain', label: 'Özel Subdomain Alanı', type: 'text', placeholder: 'firma.neso.com', width: 'half' },
        { key: 'app_name', label: 'Platform Sistem Adı', type: 'text', width: 'half' },
        { key: 'primary_color', label: 'Marka Ana Rengi', type: 'color', width: 'full' },
      ]
    }
  ];

  return (
    <div className="max-w-5xl animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 relative overflow-hidden">
         <div className="absolute top-0 right-0 p-8 opacity-5">
           <Building2 className="w-64 h-64" />
         </div>

         <div className="relative z-10 mb-8 pb-6 border-b border-gray-100">
           <h2 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
             <Plus className="w-8 h-8 text-emerald-600 bg-emerald-50 rounded-xl p-1" />
             Yeni Sisteme Geçiş Sihirbazı
           </h2>
           <p className="text-gray-500 mt-2 ml-11 max-w-2xl">Bu sayfadan yeni bir müşteriyi (işletmeyi) tüm rolleri, abonelik modeli ve tema ayarlarıyla direkt olarak ayağa kaldırabilirsiniz.</p>
         </div>

        <form onSubmit={handleSubmit} className="relative z-10 space-y-10">
          
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-12 gap-y-10">
            {formSections.map((section, sidx) => (
              <div key={sidx} className="space-y-6">
                <h3 className="text-lg font-bold border-b border-gray-100 pb-2 text-emerald-800">{section.title}</h3>
                <div className="grid grid-cols-2 gap-4">
                  {section.fields.map((field, fidx) => (
                    <div key={fidx} className={field.width === 'full' ? 'col-span-2' : 'col-span-2 sm:col-span-1'}>
                      <label className="block text-sm font-bold text-gray-700 mb-2">{field.label}</label>
                      
                      {field.type === 'select' ? (
                        <select
                          value={(formData as any)[field.key]}
                          onChange={(e) => setFormData({ ...formData, [field.key]: e.target.value })}
                          className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 font-medium transition-shadow appearance-none"
                        >
                          {field.options?.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
                        </select>
                      ) : field.type === 'color' ? (
                         <div className="flex gap-4 items-center p-3 bg-gray-50 rounded-xl border border-gray-200">
                          <input type="color" value={(formData as any)[field.key]} onChange={(e) => setFormData({ ...formData, [field.key]: e.target.value })} className="w-12 h-12 rounded-lg cursor-pointer border-0 p-0 shadow-sm shrink-0" />
                          <input type="text" value={(formData as any)[field.key]} onChange={(e) => setFormData({ ...formData, [field.key]: e.target.value })} className="w-full px-4 py-2 bg-white border border-gray-200 rounded-xl font-mono text-sm uppercase shrink" />
                        </div>
                      ) : (
                        <input
                          type={field.type}
                          required={field.required}
                          minLength={field.minLength}
                          step={field.step}
                          placeholder={field.placeholder}
                          value={(formData as any)[field.key]}
                          onChange={(e) => setFormData({ ...formData, [field.key]: field.type === 'number' ? parseFloat(e.target.value) || 0 : e.target.value })}
                          className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:bg-white focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition-all font-medium text-gray-900"
                        />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="flex justify-end pt-8 border-t border-gray-100">
            <button
              type="submit"
              disabled={loading}
              className="px-8 py-4 bg-emerald-600 text-white font-bold text-lg rounded-2xl hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-xl hover:shadow-emerald-600/20 transition-all flex items-center gap-3"
            >
              {loading ? (
                <><div className="w-6 h-6 border-4 border-white border-t-transparent rounded-full animate-spin"></div> Kayıt İşleniyor...</>
              ) : (
                 <><CheckCircle className="w-6 h-6" /> Yeni İşletmeyi Kur ve Başlat</>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
