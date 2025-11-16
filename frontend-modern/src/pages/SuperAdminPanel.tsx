import { useState, useEffect, useCallback } from 'react';
import { superadminApi, subscriptionApi, paymentApi, customizationApi } from '../lib/api';
import { 
  Building2, CreditCard, Settings, Plus, Search, Edit, Trash2, 
  BarChart3, Users, AlertCircle, CheckCircle,
  DollarSign, Package
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

export default function SuperAdminPanel() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'tenants' | 'subscriptions' | 'payments' | 'customizations' | 'quick-setup'>('dashboard');
  const [loading, setLoading] = useState(false);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

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
      } else if (activeTab === 'customizations') {
        if (tenants.length === 0) {
          const tenantsRes = await superadminApi.tenantsList();
          setTenants(tenantsRes.data);
        }
      }
    } catch (error) {
      console.error('Error loading data:', error);
      alert('Veri yüklenirken hata oluştu');
    } finally {
      setLoading(false);
    }
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
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900">Super Admin Paneli</h1>
          <p className="text-gray-600 mt-1">İşletme, abonelik ve ödeme yönetimi</p>
        </div>

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
            />
          )}

          {!loading && activeTab === 'subscriptions' && (
            <SubscriptionsTab 
              subscriptions={filteredSubscriptions}
              searchTerm={searchTerm}
              onSearchChange={setSearchTerm}
            />
          )}

          {!loading && activeTab === 'payments' && (
            <PaymentsTab 
              payments={filteredPayments}
              searchTerm={searchTerm}
              onSearchChange={setSearchTerm}
            />
          )}

          {!loading && activeTab === 'customizations' && (
            <CustomizationsTab tenants={tenants} onRefresh={loadData} />
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
  onSearchChange 
}: { 
  tenants: Tenant[]; 
  searchTerm: string; 
  onSearchChange: (value: string) => void;
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
  onSearchChange 
}: { 
  subscriptions: Subscription[]; 
  searchTerm: string; 
  onSearchChange: (value: string) => void;
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
  onSearchChange 
}: { 
  payments: Payment[]; 
  searchTerm: string; 
  onSearchChange: (value: string) => void;
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
function CustomizationsTab({ tenants, onRefresh }: { tenants: Tenant[]; onRefresh: () => void }) {
  const [selectedTenant, setSelectedTenant] = useState<number | null>(tenants[0]?.id ?? null);
  const [formData, setFormData] = useState({
    domain: '',
    app_name: '',
    logo_url: '',
    primary_color: '#00c67f',
    secondary_color: '#0ea5e9',
    footer_text: '',
    email: '',
    telefon: '',
    adres: '',
  });
  const [initialLoaded, setInitialLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [exists, setExists] = useState(false);

  const resetState = useCallback(() => {
    setFormData({
      domain: '',
      app_name: '',
      logo_url: '',
      primary_color: '#00c67f',
      secondary_color: '#0ea5e9',
      footer_text: '',
      email: '',
      telefon: '',
      adres: '',
    });
    setExists(false);
    setError(null);
    setSuccess(null);
  }, []);

  useEffect(() => {
    if (!initialLoaded && tenants.length > 0) {
      setSelectedTenant(tenants[0].id);
      setInitialLoaded(true);
    }
  }, [initialLoaded, tenants]);

  useEffect(() => {
    const fetchCustomization = async () => {
      if (!selectedTenant) {
        resetState();
        return;
      }
      setLoading(true);
      setError(null);
      setSuccess(null);
      try {
        const response = await customizationApi.get(selectedTenant);
        setFormData({
          domain: response.data.domain || '',
          app_name: response.data.app_name || '',
          logo_url: response.data.logo_url || '',
          primary_color: response.data.primary_color || '#00c67f',
          secondary_color: response.data.secondary_color || '#0ea5e9',
          footer_text: response.data.footer_text || '',
          email: response.data.email || '',
          telefon: response.data.telefon || '',
          adres: response.data.adres || '',
        });
        setExists(true);
      } catch (err: any) {
        if (err?.response?.status === 404) {
          resetState();
        } else {
          setError(err.response?.data?.detail || err.message || 'Özelleştirme verisi alınamadı');
        }
      } finally {
        setLoading(false);
      }
    };

    fetchCustomization();
  }, [selectedTenant, resetState]);

  const handleSave = async () => {
    if (!selectedTenant) {
      setError('Lütfen önce bir işletme seçin');
      return;
    }
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const payload = {
        ...formData,
        isletme_id: selectedTenant,
        domain: formData.domain || undefined,
        app_name: formData.app_name || undefined,
        logo_url: formData.logo_url || undefined,
        primary_color: formData.primary_color || '#00c67f',
        secondary_color: formData.secondary_color || '#0ea5e9',
        footer_text: formData.footer_text || undefined,
        email: formData.email || undefined,
        telefon: formData.telefon || undefined,
        adres: formData.adres || undefined,
      };

      if (exists) {
        await customizationApi.update(selectedTenant, payload);
        setSuccess('Özelleştirme güncellendi');
      } else {
        await customizationApi.create(payload);
        setSuccess('Özelleştirme oluşturuldu');
        setExists(true);
      }
      onRefresh();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Kaydetme sırasında hata oluştu');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-8">
      <div className="bg-blue-50 border border-blue-100 rounded-xl p-6">
        <h2 className="text-xl font-semibold text-blue-900 mb-2">İşletme Özelleştirmeleri</h2>
        <p className="text-sm text-blue-700 leading-relaxed">
          Her işletme için alan adı, logo ve renkler gibi marka ayarlarını yapılandırın. Bu bilgiler müşteri arayüzüne ve e-posta başlıklarına
          yansır.
        </p>
      </div>

      <div className="flex flex-col md:flex-row md:items-center gap-4">
        <div className="flex-1">
          <label className="block text-sm font-medium text-gray-700 mb-2">İşletme Seç</label>
          <select
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white text-gray-900"
            value={selectedTenant ?? ''}
            onChange={(e) => setSelectedTenant(e.target.value ? Number(e.target.value) : null)}
          >
            {tenants.length === 0 && <option value="">İşletme bulunamadı.</option>}
            {tenants.map((tenant) => (
              <option key={tenant.id} value={tenant.id}>
                {tenant.ad} {tenant.aktif ? '' : '(Pasif)'}
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={handleSave}
          disabled={saving || !selectedTenant}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? 'Kaydediliyor...' : 'Kaydet'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      {success && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm rounded-lg px-4 py-3">
          {success}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-48 text-gray-500">Özelleştirme yükleniyor...</div>
      ) : selectedTenant ? (
        <div className="space-y-8">
          <section className="border border-gray-200 rounded-xl p-6 space-y-6">
            <h3 className="text-lg font-semibold text-gray-900">Alan Adı & Uygulama Kimliği</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Field
                label="Özel Domain"
                value={formData.domain}
                onChange={(value) => setFormData((prev) => ({ ...prev, domain: value }))}
                placeholder="restoran1.neso.com"
              />
              <Field
                label="Uygulama Adı"
                value={formData.app_name}
                onChange={(value) => setFormData((prev) => ({ ...prev, app_name: value }))}
                placeholder="Fıstık Kafe Masalar"
              />
            </div>
          </section>

          <section className="border border-gray-200 rounded-xl p-6 space-y-6">
            <h3 className="text-lg font-semibold text-gray-900">Marka Öğeleri</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Field
                label="Logo URL"
                value={formData.logo_url}
                onChange={(value) => setFormData((prev) => ({ ...prev, logo_url: value }))}
                placeholder="https://..."
              />
              <div className="flex flex-col">
                <label className="block text-sm font-medium text-gray-700 mb-2">Renkler</label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="flex items-center gap-3 border border-gray-200 rounded-lg px-3 py-2">
                    <input
                      type="color"
                      value={formData.primary_color}
                      onChange={(e) => setFormData((prev) => ({ ...prev, primary_color: e.target.value }))}
                      className="h-10 w-16 border border-gray-300 rounded-lg"
                    />
                    <div>
                      <p className="text-sm font-medium text-gray-700">Ana Renk</p>
                      <p className="text-xs text-gray-500">{formData.primary_color}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 border border-gray-200 rounded-lg px-3 py-2">
                    <input
                      type="color"
                      value={formData.secondary_color}
                      onChange={(e) => setFormData((prev) => ({ ...prev, secondary_color: e.target.value }))}
                      className="h-10 w-16 border border-gray-300 rounded-lg"
                    />
                    <div>
                      <p className="text-sm font-medium text-gray-700">İkincil Renk</p>
                      <p className="text-xs text-gray-500">{formData.secondary_color}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Field
                label="Footer Metni"
                value={formData.footer_text}
                onChange={(value) => setFormData((prev) => ({ ...prev, footer_text: value }))}
                placeholder="© Fıstık Kafe 2025"
              />
              <Field
                label="İletişim E-posta"
                value={formData.email}
                onChange={(value) => setFormData((prev) => ({ ...prev, email: value }))}
                placeholder="info@fistikkafe.com"
              />
              <Field
                label="İletişim Telefon"
                value={formData.telefon}
                onChange={(value) => setFormData((prev) => ({ ...prev, telefon: value }))}
                placeholder="+90 534 000 00 00"
              />
              <Field
                label="Adres"
                value={formData.adres}
                onChange={(value) => setFormData((prev) => ({ ...prev, adres: value }))}
                placeholder="Rıhtım Cad. No: 12 Kadıköy / İstanbul"
              />
            </div>
          </section>
        </div>
      ) : (
        <div className="h-48 flex items-center justify-center text-gray-500 text-sm">
          Özelleştirme yapmak için bir işletme seçin.
        </div>
      )}
    </div>
  );
}

// Quick Setup Tab
function QuickSetupTab({ onComplete }: { onComplete: () => void }) {
  const planPresets: Record<string, { label: string; description: string; price: number }> = {
    basic: {
      label: 'Basic',
      description: 'Yeni başlayan küçük işletmeler için 1 şube / 5 kullanıcı',
      price: 0,
    },
    pro: {
      label: 'Pro',
      description: 'Birden fazla şube ve geniş ekipler için 5 şube / 20 kullanıcı',
      price: 1499,
    },
    enterprise: {
      label: 'Enterprise',
      description: 'Kurumsal işletmeler için limitsiz şube ve kullanıcı',
      price: 3499,
    },
  };

  const initialForm = {
    isletme_ad: '',
    isletme_vergi_no: '',
    isletme_telefon: '',
    sube_ad: 'Merkez Şube',
    admin_username: '',
    admin_password: '',
    plan_type: 'basic',
    ayllik_fiyat: planPresets.basic.price,
    domain: '',
    app_name: '',
    logo_url: '',
    primary_color: '#00c67f',
  };

  const [formData, setFormData] = useState(initialForm);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [result, setResult] = useState<{
    isletme_id: number;
    sube_id: number;
    subscription_id: number;
    admin_username: string;
  } | null>(null);
  const [copied, setCopied] = useState(false);

  const validate = () => {
    const nextErrors: Record<string, string> = {};
    if (!formData.isletme_ad.trim()) nextErrors.isletme_ad = 'İşletme adı zorunlu';
    if (!formData.admin_username.trim()) nextErrors.admin_username = 'Admin kullanıcı adı zorunlu';
    if (!formData.admin_password || formData.admin_password.length < 6) nextErrors.admin_password = 'Şifre en az 6 karakter olmalı';
    if (formData.domain && !/^[a-z0-9.-]+$/i.test(formData.domain)) nextErrors.domain = 'Domain sadece harf, rakam ve nokta içerebilir';
    if (formData.logo_url && !/^https?:\/\//i.test(formData.logo_url)) nextErrors.logo_url = 'Geçerli bir URL girin';
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleChange = (field: string, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handlePlanSelect = (plan: string) => {
    handleChange('plan_type', plan);
    handleChange('ayllik_fiyat', planPresets[plan].price);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setLoading(true);
    setErrors({});
    try {
      const payload = {
        ...formData,
        admin_username: formData.admin_username.trim(),
        domain: formData.domain?.trim().toLowerCase() || undefined,
      };
      const response = await superadminApi.quickSetup(payload);
      setResult(response.data);
      setFormData(initialForm);
      onComplete();
    } catch (error: any) {
      const message = error.response?.data?.detail || error.message || 'Beklenmeyen bir hata oluştu';
      alert(`Kurulum başarısız: ${message}`);
    } finally {
      setLoading(false);
    }
  };

  const fillFistikKafe = () => {
    setFormData({
      ...initialForm,
      isletme_ad: 'Fıstık Kafe',
      isletme_vergi_no: '',
      isletme_telefon: '+90 532 000 00 00',
      sube_ad: 'Kadıköy',
      admin_username: 'fistik_admin',
      admin_password: 'fistik123',
      plan_type: 'basic',
      ayllik_fiyat: planPresets.basic.price,
      domain: 'fistik-kafe.neso.app',
      app_name: 'Fıstık Kafe Panel',
      logo_url: '',
      primary_color: '#00c67f',
    });
  };

  const copyCredentials = async () => {
    if (!result) return;
    const lines = [
      'Neso Modüler - İşletme Kurulum Bilgileri',
      '----------------------------------------',
      `İşletme ID: ${result.isletme_id}`,
      `Şube ID: ${result.sube_id}`,
      `Abonelik ID: ${result.subscription_id}`,
      `Admin Kullanıcı: ${result.admin_username}`,
      '',
      'Giriş URL: https://app.neso.moduler (veya kendi domaininiz)',
    ].join('\n');
    try {
      await navigator.clipboard.writeText(lines);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      alert('Panoya kopyalanamadı. Metni manuel kopyalayın:\n\n' + lines);
    }
  };

  const printCredentials = () => {
    if (!result) return;
    const html = `
      <html>
        <head><title>Kurulum Bilgileri</title></head>
        <body style="font-family: Arial, sans-serif; padding: 24px;">
          <h2>Neso Modüler - İşletme Kurulum Bilgileri</h2>
          <hr/>
          <p><strong>İşletme ID:</strong> ${result.isletme_id}</p>
          <p><strong>Şube ID:</strong> ${result.sube_id}</p>
          <p><strong>Abonelik ID:</strong> ${result.subscription_id}</p>
          <p><strong>Admin Kullanıcı:</strong> ${result.admin_username}</p>
          <p><strong>Giriş URL:</strong> https://app.neso.moduler</p>
        </body>
      </html>`;
    const w = window.open('', 'PRINT', 'height=600,width=800');
    if (!w) return;
    w.document.write(html);
    w.document.close();
    w.focus();
    w.print();
    w.close();
  };

  return (
    <div className="space-y-8">
      <div className="bg-blue-50 border border-blue-100 rounded-xl p-6">
        <h2 className="text-xl font-semibold text-blue-900 mb-2">Hızlı İşletme Kurulumu</h2>
        <p className="text-sm text-blue-700 leading-relaxed">
          Yeni bir işletme eklemek için aşağıdaki formu doldurun. İşletme, şube, admin kullanıcı ve abonelik bilgileri tek adımda oluşturulur.
          Kurulumdan sonra admin kullanıcı bilgilerini işletme sahibine iletmeyi unutmayın.
        </p>
        <div className="mt-4">
          <button
            type="button"
            onClick={fillFistikKafe}
            className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700"
          >
            Fıstık Kafe Örneğiyle Doldur
          </button>
        </div>
      </div>

      {result && (
        <div className="border border-emerald-200 bg-emerald-50 rounded-xl p-6 space-y-4">
          <div className="flex items-center gap-3 text-emerald-700">
            <CheckCircle className="w-6 h-6" />
            <div>
              <p className="font-semibold">Kurulum tamamlandı!</p>
              <p className="text-sm">İşletme ve bağlı varlıklar oluşturuldu. Aşağıdaki bilgileri not alın.</p>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div className="p-4 bg-white rounded-lg border border-emerald-100">
              <p className="text-gray-500">İşletme ID</p>
              <p className="font-semibold text-gray-900">{result.isletme_id}</p>
            </div>
            <div className="p-4 bg-white rounded-lg border border-emerald-100">
              <p className="text-gray-500">Şube ID</p>
              <p className="font-semibold text-gray-900">{result.sube_id}</p>
            </div>
            <div className="p-4 bg-white rounded-lg border border-emerald-100">
              <p className="text-gray-500">Abonelik ID</p>
              <p className="font-semibold text-gray-900">{result.subscription_id}</p>
            </div>
            <div className="p-4 bg-white rounded-lg border border-emerald-100">
              <p className="text-gray-500">Admin Kullanıcı</p>
              <p className="font-semibold text-gray-900">{result.admin_username}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={copyCredentials}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              {copied ? 'Kopyalandı' : 'Bilgileri Kopyala'}
            </button>
            <button
              type="button"
              onClick={printCredentials}
              className="px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-800"
            >
              Yazdır
            </button>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-10">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">İşletme Bilgileri</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Field
              label="İşletme Adı"
              required
              error={errors.isletme_ad}
              value={formData.isletme_ad}
              onChange={(value) => handleChange('isletme_ad', value)}
              placeholder="Örn. Fıstık Kafe Kadıköy"
            />
            <Field
              label="Vergi No"
              value={formData.isletme_vergi_no}
              onChange={(value) => handleChange('isletme_vergi_no', value)}
              placeholder="Opsiyonel"
            />
            <Field
              label="Telefon"
              value={formData.isletme_telefon}
              onChange={(value) => handleChange('isletme_telefon', value)}
              placeholder="+90 534 000 00 00"
            />
            <Field
              label="Şube Adı"
              value={formData.sube_ad}
              onChange={(value) => handleChange('sube_ad', value)}
              placeholder="Merkez Şube"
            />
          </div>
        </div>

        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Admin Kullanıcı</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Field
              label="Kullanıcı Adı"
              required
              error={errors.admin_username}
              value={formData.admin_username}
              onChange={(value) => handleChange('admin_username', value)}
              placeholder="örn. fistik_admin"
            />
            <Field
              label="Şifre"
              type="password"
              required
              error={errors.admin_password}
              value={formData.admin_password}
              onChange={(value) => handleChange('admin_password', value)}
              placeholder="En az 6 karakter"
            />
          </div>
        </div>

        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Abonelik Planı</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {Object.entries(planPresets).map(([plan, details]) => (
              <label
                key={plan}
                className={`border rounded-xl p-4 cursor-pointer transition ${
                  formData.plan_type === plan ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-blue-200'
                }`}
              >
                <input
                  type="radio"
                  name="plan"
                  value={plan}
                  checked={formData.plan_type === plan}
                  onChange={() => handlePlanSelect(plan)}
                  className="hidden"
                />
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-gray-900">{details.label}</span>
                    <span className="text-sm text-gray-500">{details.price === 0 ? 'Ücretsiz' : `${details.price} ₺/ay`}</span>
                  </div>
                  <p className="text-sm text-gray-600 leading-relaxed">{details.description}</p>
                </div>
              </label>
            ))}
          </div>
          <div className="mt-4 max-w-sm">
            <Field
              label="Aylık Fiyat (₺)"
              type="number"
              min={0}
              step="0.01"
              value={formData.ayllik_fiyat}
              onChange={(value) => handleChange('ayllik_fiyat', parseFloat(value) || 0)}
            />
          </div>
        </div>

        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Marka Özelleştirmeleri</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Field
              label="Domain"
              value={formData.domain}
              onChange={(value) => handleChange('domain', value)}
              placeholder="restoran1.neso.com"
              error={errors.domain}
            />
            <Field
              label="Uygulama Adı"
              value={formData.app_name}
              onChange={(value) => handleChange('app_name', value)}
              placeholder="Fıstık Kafe Panel"
            />
            <Field
              label="Logo URL"
              value={formData.logo_url}
              onChange={(value) => handleChange('logo_url', value)}
              placeholder="https://..."
              error={errors.logo_url}
            />
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Ana Renk</label>
              <div className="flex items-center gap-3">
                <input
                  type="color"
                  value={formData.primary_color}
                  onChange={(e) => handleChange('primary_color', e.target.value)}
                  className="h-10 w-16 border border-gray-300 rounded-lg"
                />
                <span className="text-sm text-gray-500">{formData.primary_color}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={loading}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Kuruluyor...' : 'İşletmeyi Kur'}
          </button>
        </div>
      </form>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  required,
  error,
  type = 'text',
  min,
  step,
}: {
  label: string;
  value: any;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
  error?: string;
  type?: string;
  min?: number;
  step?: number | string;
}) {
  return (
    <div className="flex flex-col">
      <label className="block text-sm font-medium text-gray-700 mb-2">
        {label} {required && <span className="text-red-500">*</span>}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        min={min}
        step={step}
        className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 bg-white text-gray-900 placeholder-gray-400 ${
          error ? 'border-red-400 focus:ring-red-300' : 'border-gray-300'
        }`}
      />
      {error && <span className="text-xs text-red-500 mt-1">{error}</span>}
    </div>
  );
}



