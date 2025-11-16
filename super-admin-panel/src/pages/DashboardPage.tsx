import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { superadminApi, subscriptionApi, paymentApi, customizationApi } from '../lib/api';
import { 
  Building2, CreditCard, Settings, Plus, Search, Edit, Trash2, 
  BarChart3, Users, TrendingUp, AlertCircle, CheckCircle, XCircle,
  Calendar, DollarSign, Package, Globe, LogOut
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
      alert('Veri yüklenirken hata oluştu');
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

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Super Admin Paneli</h1>
            <p className="text-sm text-gray-600">Platform Yönetim Paneli</p>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-600">{user?.username}</span>
            <button
              onClick={handleLogout}
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm flex items-center gap-2"
            >
              <LogOut className="w-4 h-4" />
              Çıkış
            </button>
          </div>
        </div>
      </header>
      <div className="max-w-7xl mx-auto p-6">
        {/* Tabs */}
        <div className="bg-white rounded-lg shadow mb-6">
          <div className="border-b border-gray-200">
            <nav className="flex -mb-px">
              {[
                { id: 'dashboard', label: 'Dashboard', icon: BarChart3 },
                { id: 'tenants', label: 'İşletmeler', icon: Building2 },
                { id: 'subscriptions', label: 'Abonelikler', icon: Package },
                { id: 'payments', label: 'Ödemeler', icon: CreditCard },
                { id: 'customizations', label: 'Özelleştirmeler', icon: Settings },
                { id: 'quick-setup', label: 'Hızlı Kurulum', icon: Plus },
              ].map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => setActiveTab(id as any)}
                  className={`flex items-center px-6 py-4 border-b-2 font-medium text-sm ${
                    activeTab === id
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <Icon className="w-5 h-5 mr-2" />
                  {label}
                </button>
              ))}
            </nav>
          </div>
        </div>

        {/* Content */}
        <div className="bg-white rounded-lg shadow p-6">
          {loading && (
            <div className="text-center py-12">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              <p className="mt-2 text-gray-600">Yükleniyor...</p>
            </div>
          )}

          {!loading && activeTab === 'dashboard' && stats && (
            <DashboardTab stats={stats} />
          )}

          {!loading && activeTab === 'tenants' && (
            <TenantsTab 
              tenants={filteredTenants}
              searchTerm={searchTerm}
              onSearchChange={setSearchTerm}
              onRefresh={loadData}
            />
          )}

          {!loading && activeTab === 'subscriptions' && (
            <SubscriptionsTab 
              subscriptions={filteredSubscriptions}
              searchTerm={searchTerm}
              onSearchChange={setSearchTerm}
              onRefresh={loadData}
            />
          )}

          {!loading && activeTab === 'payments' && (
            <PaymentsTab 
              payments={filteredPayments}
              searchTerm={searchTerm}
              onSearchChange={setSearchTerm}
              onRefresh={loadData}
            />
          )}

          {!loading && activeTab === 'customizations' && (
            <CustomizationsTab onRefresh={loadData} />
          )}

          {!loading && activeTab === 'quick-setup' && (
            <QuickSetupTab onComplete={loadData} />
          )}
        </div>
      </div>
    </div>
  );
}

// Dashboard Tab
function DashboardTab({ stats }: { stats: DashboardStats }) {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Dashboard</h2>
      
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard
          title="Toplam İşletme"
          value={stats.isletmeler.total}
          subtitle={`${stats.isletmeler.active} aktif`}
          icon={Building2}
          color="blue"
        />
        <StatCard
          title="Toplam Şube"
          value={stats.subeler.total}
          icon={Building2}
          color="green"
        />
        <StatCard
          title="Toplam Kullanıcı"
          value={stats.kullanicilar.total}
          icon={Users}
          color="purple"
        />
        <StatCard
          title="Aktif Abonelik"
          value={stats.abonelikler.active}
          icon={Package}
          color="orange"
        />
      </div>

      {/* Financial Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-blue-600 font-medium">Bu Ay Gelir</p>
              <p className="text-3xl font-bold text-blue-900 mt-2">
                ₺{stats.finansal.this_month_revenue.toFixed(2)}
              </p>
            </div>
            <DollarSign className="w-12 h-12 text-blue-600" />
          </div>
        </div>

        <div className="bg-gradient-to-br from-orange-50 to-orange-100 rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-orange-600 font-medium">Bekleyen Ödemeler</p>
              <p className="text-3xl font-bold text-orange-900 mt-2">
                ₺{stats.finansal.pending_payments.total.toFixed(2)}
              </p>
              <p className="text-sm text-orange-700 mt-1">
                {stats.finansal.pending_payments.count} adet
              </p>
            </div>
            <AlertCircle className="w-12 h-12 text-orange-600" />
          </div>
        </div>
      </div>

      {/* Plan Distribution */}
      <div className="bg-gray-50 rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4">Plan Dağılımı</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {stats.abonelikler.plan_distribution.map((plan) => (
            <div key={plan.plan_type} className="bg-white rounded-lg p-4 shadow">
              <p className="text-sm text-gray-600 capitalize">{plan.plan_type}</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{plan.count}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// Stat Card Component
function StatCard({ 
  title, 
  value, 
  subtitle, 
  icon: Icon, 
  color 
}: { 
  title: string; 
  value: number; 
  subtitle?: string; 
  icon: any; 
  color: string;
}) {
  const colorClasses = {
    blue: 'bg-blue-100 text-blue-600',
    green: 'bg-green-100 text-green-600',
    purple: 'bg-purple-100 text-purple-600',
    orange: 'bg-orange-100 text-orange-600',
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600">{title}</p>
          <p className="text-3xl font-bold text-gray-900 mt-2">{value}</p>
          {subtitle && <p className="text-sm text-gray-500 mt-1">{subtitle}</p>}
        </div>
        <div className={`${colorClasses[color as keyof typeof colorClasses]} p-3 rounded-full`}>
          <Icon className="w-6 h-6" />
        </div>
      </div>
    </div>
  );
}

// Tenants Tab
function TenantsTab({ 
  tenants, 
  searchTerm, 
  onSearchChange, 
  onRefresh 
}: { 
  tenants: Tenant[]; 
  searchTerm: string; 
  onSearchChange: (value: string) => void;
  onRefresh: () => void;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">İşletmeler</h2>
        <div className="flex items-center space-x-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              placeholder="Ara..."
              value={searchTerm}
              onChange={(e) => onSearchChange(e.target.value)}
              className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">İşletme Adı</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Vergi No</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Telefon</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Durum</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">İşlemler</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {tenants.map((tenant) => (
              <tr key={tenant.id}>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{tenant.id}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{tenant.ad}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{tenant.vergi_no || '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{tenant.telefon || '-'}</td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {tenant.aktif ? (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      Aktif
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                      Pasif
                    </span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                  <button className="text-blue-600 hover:text-blue-900 mr-4">
                    <Edit className="w-4 h-4" />
                  </button>
                  <button className="text-red-600 hover:text-red-900">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Subscriptions Tab
function SubscriptionsTab({ 
  subscriptions, 
  searchTerm, 
  onSearchChange, 
  onRefresh 
}: { 
  subscriptions: Subscription[]; 
  searchTerm: string; 
  onSearchChange: (value: string) => void;
  onRefresh: () => void;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Abonelikler</h2>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
          <input
            type="text"
            placeholder="İşletme ID ile ara..."
            value={searchTerm}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {subscriptions.map((sub) => (
          <div key={sub.id} className="border border-gray-200 rounded-lg p-6 hover:shadow-lg transition-shadow">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">İşletme #{sub.isletme_id}</h3>
              <span className={`px-2 py-1 rounded text-xs font-medium ${
                sub.status === 'active' ? 'bg-green-100 text-green-800' :
                sub.status === 'suspended' ? 'bg-yellow-100 text-yellow-800' :
                'bg-red-100 text-red-800'
              }`}>
                {sub.status}
              </span>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Plan:</span>
                <span className="font-medium capitalize">{sub.plan_type}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Aylık Fiyat:</span>
                <span className="font-medium">₺{sub.ayllik_fiyat.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Max Şube:</span>
                <span className="font-medium">{sub.max_subeler}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Max Kullanıcı:</span>
                <span className="font-medium">{sub.max_kullanicilar}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Payments Tab
function PaymentsTab({ 
  payments, 
  searchTerm, 
  onSearchChange, 
  onRefresh 
}: { 
  payments: Payment[]; 
  searchTerm: string; 
  onSearchChange: (value: string) => void;
  onRefresh: () => void;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Ödemeler</h2>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
          <input
            type="text"
            placeholder="Ara..."
            value={searchTerm}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">İşletme ID</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tutar</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ödeme Türü</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Durum</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tarih</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {payments.map((payment) => (
              <tr key={payment.id}>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{payment.id}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{payment.isletme_id}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">₺{payment.tutar.toFixed(2)}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{payment.odeme_turu}</td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {payment.durum === 'completed' ? (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      Tamamlandı
                    </span>
                  ) : payment.durum === 'pending' ? (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                      Bekliyor
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                      Başarısız
                    </span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {payment.odeme_tarihi ? new Date(payment.odeme_tarihi).toLocaleDateString('tr-TR') : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Customizations Tab
function CustomizationsTab({ onRefresh }: { onRefresh: () => void }) {
  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Özelleştirmeler</h2>
      <p className="text-gray-600">Özelleştirme yönetimi yakında eklenecek...</p>
    </div>
  );
}

// Quick Setup Tab
function QuickSetupTab({ onComplete }: { onComplete: () => void }) {
  const [formData, setFormData] = useState({
    isletme_ad: '',
    isletme_vergi_no: '',
    isletme_telefon: '',
    sube_ad: 'Merkez Şube',
    admin_username: '',
    admin_password: '',
    plan_type: 'basic',
    ayllik_fiyat: 0,
    domain: '',
    app_name: '',
    logo_url: '',
    primary_color: '#3b82f6',
  });

  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await superadminApi.quickSetup(formData);
      alert('İşletme başarıyla kuruldu!');
      setFormData({
        isletme_ad: '',
        isletme_vergi_no: '',
        isletme_telefon: '',
        sube_ad: 'Merkez Şube',
        admin_username: '',
        admin_password: '',
        plan_type: 'basic',
        ayllik_fiyat: 0,
        domain: '',
        app_name: '',
        logo_url: '',
        primary_color: '#3b82f6',
      });
      onComplete();
    } catch (error: any) {
      alert('Hata: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Hızlı İşletme Kurulumu</h2>
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">İşletme Adı *</label>
            <input
              type="text"
              required
              value={formData.isletme_ad}
              onChange={(e) => setFormData({ ...formData, isletme_ad: e.target.value })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Vergi No</label>
            <input
              type="text"
              value={formData.isletme_vergi_no}
              onChange={(e) => setFormData({ ...formData, isletme_vergi_no: e.target.value })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Telefon</label>
            <input
              type="text"
              value={formData.isletme_telefon}
              onChange={(e) => setFormData({ ...formData, isletme_telefon: e.target.value })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Şube Adı</label>
            <input
              type="text"
              value={formData.sube_ad}
              onChange={(e) => setFormData({ ...formData, sube_ad: e.target.value })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Admin Kullanıcı Adı *</label>
            <input
              type="text"
              required
              value={formData.admin_username}
              onChange={(e) => setFormData({ ...formData, admin_username: e.target.value })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Admin Şifre *</label>
            <input
              type="password"
              required
              minLength={6}
              value={formData.admin_password}
              onChange={(e) => setFormData({ ...formData, admin_password: e.target.value })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Plan Tipi</label>
            <select
              value={formData.plan_type}
              onChange={(e) => setFormData({ ...formData, plan_type: e.target.value })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="basic">Basic</option>
              <option value="pro">Pro</option>
              <option value="enterprise">Enterprise</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Aylık Fiyat</label>
            <input
              type="number"
              min="0"
              step="0.01"
              value={formData.ayllik_fiyat}
              onChange={(e) => setFormData({ ...formData, ayllik_fiyat: parseFloat(e.target.value) || 0 })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Domain</label>
            <input
              type="text"
              placeholder="restoran1.neso.com"
              value={formData.domain}
              onChange={(e) => setFormData({ ...formData, domain: e.target.value })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Uygulama Adı</label>
            <input
              type="text"
              value={formData.app_name}
              onChange={(e) => setFormData({ ...formData, app_name: e.target.value })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Logo URL</label>
            <input
              type="url"
              value={formData.logo_url}
              onChange={(e) => setFormData({ ...formData, logo_url: e.target.value })}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Ana Renk</label>
            <input
              type="color"
              value={formData.primary_color}
              onChange={(e) => setFormData({ ...formData, primary_color: e.target.value })}
              className="w-full h-10 border border-gray-300 rounded-lg"
            />
          </div>
        </div>
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={loading}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Kuruluyor...' : 'İşletmeyi Kur'}
          </button>
        </div>
      </form>
    </div>
  );
}


