import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { superadminApi, subscriptionApi, paymentApi, customizationApi } from '../lib/api';
import { useAuthStore } from '../store/authStore';
import { 
  Building2, CreditCard, Settings, Plus, Search, 
  BarChart3, Users, AlertCircle, CheckCircle,
  DollarSign, Package, ArrowLeft, Phone, Calendar,
  ExternalLink, UserCog, Menu as MenuIcon, FileText,
  Trash2, Activity
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
  isletme_ad?: string;
  plan_type: string;
  status: string;
  max_subeler: number;
  max_kullanicilar: number;
  max_menu_items: number;
  ayllik_fiyat: number;
  baslangic_tarihi: string;
  bitis_tarihi?: string;
  otomatik_yenileme?: boolean;
}

interface Payment {
  id: number;
  isletme_id: number;
  isletme_ad?: string;
  subscription_id?: number;
  tutar: number;
  odeme_turu: string;
  durum: string;
  fatura_no?: string;
  aciklama?: string;
  odeme_tarihi?: string;
  created_at: string;
}

interface DashboardStats {
  isletmeler: { total: number; active: number; passive: number };
  subeler: { total: number };
  kullanicilar: { total: number };
  abonelikler: { active: number; plan_distribution: Array<{ plan_type: string; count: number }> };
  ariza_servis_talepleri: number;
  finansal: {
    this_month_revenue: number;
    pending_payments: { total: number; count: number };
  };
}

interface TenantDetail {
  isletme: {
    id: number;
    ad: string;
    vergi_no?: string;
    telefon?: string;
    aktif: boolean;
    created_at: string;
  };
  subscription?: {
    id: number;
    plan_type: string;
    status: string;
    max_subeler: number;
    max_kullanicilar: number;
    max_menu_items: number;
    ayllik_fiyat: number;
    trial_baslangic?: string;
    trial_bitis?: string;
    baslangic_tarihi: string;
    bitis_tarihi?: string;
    otomatik_yenileme: boolean;
  };
  subeler: Array<{
    id: number;
    ad: string;
    adres?: string;
    telefon?: string;
    aktif: boolean;
    created_at: string;
  }>;
  kullanicilar: Array<{
    id: number;
    username: string;
    role: string;
    aktif: boolean;
    created_at: string;
  }>;
  customization?: {
    domain?: string;
    app_name?: string;
    logo_url?: string;
    primary_color?: string;
    secondary_color?: string;
  };
  istatistikler: {
    siparis_sayisi: number;
    toplam_gelir: number;
    menu_item_sayisi: number;
    kullanici_sayisi: number;
    sube_sayisi: number;
    son_siparis_tarihi?: string;
  };
}

export default function SuperAdminPanel() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'tenants' | 'subscriptions' | 'payments' | 'customizations' | 'quick-setup' | 'api-usage'>('dashboard');
  const [loading, setLoading] = useState(false);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTenantId, setSelectedTenantId] = useState<number | null>(null);
  const [tenantDetail, setTenantDetail] = useState<TenantDetail | null>(null);

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
    s.isletme_id.toString().includes(searchTerm) ||
    s.isletme_ad?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredPayments = payments.filter(p => 
    p.isletme_id.toString().includes(searchTerm) ||
    p.isletme_ad?.toLowerCase().includes(searchTerm.toLowerCase()) ||
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
                { id: 'api-usage', label: 'API Kullanım', icon: Activity },
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
            selectedTenantId ? (
              <TenantDetailTab 
                tenantDetail={tenantDetail}
                onBack={() => {
                  setSelectedTenantId(null);
                  setTenantDetail(null);
                }}
                onRefresh={async () => {
                  try {
                    const response = await superadminApi.tenantDetail(selectedTenantId);
                    setTenantDetail(response.data);
                  } catch (error) {
                    console.error('Error loading tenant detail:', error);
                    alert('Tenant detayı yüklenirken hata oluştu');
                  }
                }}
              />
            ) : (
              <TenantsTab 
                tenants={filteredTenants}
                searchTerm={searchTerm}
                onSearchChange={setSearchTerm}
                onTenantClick={async (tenantId: number) => {
                  setSelectedTenantId(tenantId);
                  setLoading(true);
                  try {
                    const response = await superadminApi.tenantDetail(tenantId);
                    setTenantDetail(response.data);
                  } catch (error) {
                    console.error('Error loading tenant detail:', error);
                    alert('Tenant detayı yüklenirken hata oluştu');
                    setSelectedTenantId(null);
                  } finally {
                    setLoading(false);
                  }
                }}
              />
            )
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

          {!loading && activeTab === 'api-usage' && (
            <ApiUsageTab />
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
          title="Aktif İşletme"
          value={stats.isletmeler.active}
          subtitle={`${stats.isletmeler.passive} pasif`}
          icon={Building2}
          color="green"
        />
        <StatCard
          title="Toplam Şube"
          value={stats.subeler.total}
          icon={Building2}
          color="purple"
        />
        <StatCard
          title="Pasif İşletme"
          value={stats.isletmeler.passive}
          icon={AlertCircle}
          color="red"
        />
      </div>

      {/* Second Row Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <StatCard
          title="Toplam Kullanıcı"
          value={stats.kullanicilar.total}
          icon={Users}
          color="indigo"
        />
        <StatCard
          title="Arıza ve Servis Talepleri"
          value={stats.ariza_servis_talepleri}
          icon={AlertCircle}
          color="orange"
        />
        <StatCard
          title="Aktif Abonelik"
          value={stats.abonelikler.active}
          icon={Package}
          color="teal"
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
  value: number | string; 
  subtitle?: string; 
  icon: any; 
  color: string;
}) {
  const colorClasses = {
    blue: 'bg-blue-100 text-blue-600',
    green: 'bg-green-100 text-green-600',
    purple: 'bg-purple-100 text-purple-600',
    orange: 'bg-orange-100 text-orange-600',
    red: 'bg-red-100 text-red-600',
    indigo: 'bg-indigo-100 text-indigo-600',
    teal: 'bg-teal-100 text-teal-600',
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
  onTenantClick
}: { 
  tenants: Tenant[]; 
  searchTerm: string; 
  onSearchChange: (value: string) => void;
  onTenantClick: (tenantId: number) => void;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">İşletmeler</h2>
          <p className="text-sm text-gray-600 mt-1">Toplam {tenants.length} işletme</p>
        </div>
        <div className="flex items-center space-x-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              placeholder="İşletme adı veya vergi no ile ara..."
              value={searchTerm}
              onChange={(e) => onSearchChange(e.target.value)}
              className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent w-64"
            />
          </div>
        </div>
      </div>

      {tenants.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
          <Building2 className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">İşletme bulunamadı</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {tenants.map((tenant) => (
            <div
              key={tenant.id}
              className="bg-white rounded-xl shadow-sm border border-gray-200 hover:shadow-lg transition-all duration-200 overflow-hidden"
            >
              <div className={`h-2 ${tenant.aktif ? 'bg-green-500' : 'bg-red-500'}`} />
              <div className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold text-gray-900 mb-1">{tenant.ad}</h3>
                    <p className="text-sm text-gray-500">ID: {tenant.id}</p>
                  </div>
                  {tenant.aktif ? (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      <CheckCircle className="w-3 h-3 mr-1" />
                      Aktif
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                      <AlertCircle className="w-3 h-3 mr-1" />
                      Pasif
                    </span>
                  )}
                </div>
                
                <div className="space-y-2 mb-4">
                  {tenant.vergi_no && (
                    <div className="flex items-center text-sm text-gray-600">
                      <span className="font-medium mr-2">Vergi No:</span>
                      <span>{tenant.vergi_no}</span>
                    </div>
                  )}
                  {tenant.telefon && (
                    <div className="flex items-center text-sm text-gray-600">
                      <Phone className="w-4 h-4 mr-2" />
                      <span>{tenant.telefon}</span>
                    </div>
                  )}
                </div>

                <button
                  onClick={() => onTenantClick(tenant.id)}
                  className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium text-sm flex items-center justify-center"
                >
                  <Settings className="w-4 h-4 mr-2" />
                  Detayları Gör
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Tenant Detail Tab
function TenantDetailTab({
  tenantDetail,
  onBack,
  onRefresh
}: {
  tenantDetail: TenantDetail | null;
  onBack: () => void;
  onRefresh: () => void;
}) {
  if (!tenantDetail) {
    return (
      <div className="text-center py-12">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <p className="mt-2 text-gray-600">Yükleniyor...</p>
      </div>
    );
  }

  const { isletme, subscription, subeler, kullanicilar, customization, istatistikler } = tenantDetail;
  const navigate = useNavigate();
  const { setSelectedTenantId } = useAuthStore();

  const handleSwitchToTenant = () => {
    setSelectedTenantId(isletme.id);
    navigate('/dashboard');
  };

  const handleQuickAccess = (path: string) => {
    setSelectedTenantId(isletme.id);
    navigate(path);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-4">
          <button
            onClick={onBack}
            className="text-gray-600 hover:text-gray-900 transition-colors"
            title="Geri"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">{isletme.ad}</h2>
            <p className="text-sm text-gray-500 mt-1">ID: {isletme.id}</p>
          </div>
          {isletme.aktif ? (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
              <CheckCircle className="w-3 h-3 mr-1" />
              Aktif
            </span>
          ) : (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
              <AlertCircle className="w-3 h-3 mr-1" />
              Pasif
            </span>
          )}
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={onRefresh}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
          >
            Yenile
          </button>
          <button
            onClick={handleSwitchToTenant}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center"
          >
            <ExternalLink className="w-4 h-4 mr-2" />
            İşletmeye Geç
          </button>
        </div>
      </div>

      {/* Hızlı Erişim Butonları */}
      <div className="mb-6 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-6 border border-blue-100">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Hızlı Erişim</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <button
            onClick={() => handleQuickAccess('/dashboard')}
            className="flex items-center justify-center px-4 py-3 bg-white rounded-lg hover:bg-blue-50 border border-blue-200 transition-all group"
          >
            <BarChart3 className="w-5 h-5 mr-2 text-blue-600 group-hover:text-blue-700" />
            <span className="font-medium text-gray-700">Dashboard</span>
          </button>
          <button
            onClick={() => handleQuickAccess('/personeller')}
            className="flex items-center justify-center px-4 py-3 bg-white rounded-lg hover:bg-blue-50 border border-blue-200 transition-all group"
          >
            <UserCog className="w-5 h-5 mr-2 text-blue-600 group-hover:text-blue-700" />
            <span className="font-medium text-gray-700">Personeller</span>
          </button>
          <button
            onClick={() => handleQuickAccess('/menu')}
            className="flex items-center justify-center px-4 py-3 bg-white rounded-lg hover:bg-blue-50 border border-blue-200 transition-all group"
          >
            <MenuIcon className="w-5 h-5 mr-2 text-blue-600 group-hover:text-blue-700" />
            <span className="font-medium text-gray-700">Menü</span>
          </button>
          <button
            onClick={() => handleQuickAccess('/raporlar')}
            className="flex items-center justify-center px-4 py-3 bg-white rounded-lg hover:bg-blue-50 border border-blue-200 transition-all group"
          >
            <FileText className="w-5 h-5 mr-2 text-blue-600 group-hover:text-blue-700" />
            <span className="font-medium text-gray-700">Raporlar</span>
          </button>
        </div>
      </div>

      {/* İşletme Bilgileri */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center">
            <Building2 className="w-5 h-5 mr-2 text-blue-600" />
            İşletme Bilgileri
          </h3>
          <div className="space-y-3">
            <div>
              <p className="text-sm text-gray-600">İşletme ID</p>
              <p className="font-medium text-gray-900">{isletme.id}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">İşletme Adı</p>
              <p className="font-medium text-gray-900">{isletme.ad}</p>
            </div>
            {isletme.vergi_no && (
              <div>
                <p className="text-sm text-gray-600">Vergi No</p>
                <p className="font-medium text-gray-900">{isletme.vergi_no}</p>
              </div>
            )}
            {isletme.telefon && (
              <div>
                <p className="text-sm text-gray-600">Telefon</p>
                <p className="font-medium text-gray-900 flex items-center">
                  <Phone className="w-4 h-4 mr-1 text-gray-600" />
                  {isletme.telefon}
                </p>
              </div>
            )}
            <div>
              <p className="text-sm text-gray-600">Oluşturulma Tarihi</p>
              <p className="font-medium text-gray-900 flex items-center">
                <Calendar className="w-4 h-4 mr-1 text-gray-600" />
                {new Date(isletme.created_at).toLocaleDateString('tr-TR')}
              </p>
            </div>
          </div>
        </div>

        {/* Abonelik Bilgileri */}
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center">
            <Package className="w-5 h-5 mr-2 text-green-600" />
            Abonelik Bilgileri
          </h3>
          {subscription ? (
            <div className="space-y-3">
              <div>
                <p className="text-sm text-gray-600">Plan Tipi</p>
                <p className="font-medium text-gray-900 capitalize">{subscription.plan_type}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Durum</p>
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  subscription.status === 'active' ? 'bg-green-100 text-green-800' :
                  subscription.status === 'suspended' ? 'bg-yellow-100 text-yellow-800' :
                  'bg-red-100 text-red-800'
                }`}>
                  {subscription.status}
                </span>
              </div>
              <div>
                <p className="text-sm text-gray-600">Aylık Fiyat</p>
                <p className="font-medium text-lg text-gray-900">₺{subscription.ayllik_fiyat.toFixed(2)}</p>
              </div>
              <div className="grid grid-cols-2 gap-3 mt-4 pt-4 border-t border-gray-200">
                <div>
                  <p className="text-xs text-gray-500">Max Şube</p>
                  <p className="font-medium text-gray-900">{subscription.max_subeler}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Max Kullanıcı</p>
                  <p className="font-medium text-gray-900">{subscription.max_kullanicilar}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Max Menü</p>
                  <p className="font-medium text-gray-900">{subscription.max_menu_items}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Otomatik Yenileme</p>
                  <p className="font-medium text-gray-900">{subscription.otomatik_yenileme ? 'Evet' : 'Hayır'}</p>
                </div>
              </div>
              {subscription.bitis_tarihi && (
                <div>
                  <p className="text-sm text-gray-600">Bitiş Tarihi</p>
                  <p className="font-medium text-gray-900">{new Date(subscription.bitis_tarihi).toLocaleDateString('tr-TR')}</p>
                </div>
              )}
              {subscription.trial_bitis && (
                <div>
                  <p className="text-sm text-gray-600">Trial Bitiş</p>
                  <p className="font-medium text-gray-900">{new Date(subscription.trial_bitis).toLocaleDateString('tr-TR')}</p>
                </div>
              )}
              <div className="mt-4 pt-4 border-t border-gray-200">
                <p className="text-sm text-gray-600 mb-2">Plan Güncelle</p>
                <div className="flex gap-2">
                  {subscription.plan_type !== 'pro' && (
                    <button
                      onClick={async () => {
                        if (!confirm(`${isletme.ad} işletmesinin planını Pro'ya güncellemek istediğinizden emin misiniz?`)) return;
                        try {
                          const planPresets = {
                            basic: { max_subeler: 1, max_kullanicilar: 5, max_menu_items: 100, ayllik_fiyat: 0 },
                            pro: { max_subeler: 5, max_kullanicilar: 20, max_menu_items: 500, ayllik_fiyat: 999 },
                            enterprise: { max_subeler: 999, max_kullanicilar: 999, max_menu_items: 9999, ayllik_fiyat: 2999 }
                          };
                          const newPlan = subscription.plan_type === 'basic' ? 'pro' : 'enterprise';
                          await subscriptionApi.update(isletme.id, {
                            ...subscription,
                            plan_type: newPlan,
                            ...planPresets[newPlan as keyof typeof planPresets]
                          });
                          alert('Plan başarıyla güncellendi');
                          onRefresh();
                        } catch (error: any) {
                          alert(`Plan güncellenemedi: ${error.response?.data?.detail || error.message}`);
                        }
                      }}
                      className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors"
                    >
                      {subscription.plan_type === 'basic' ? 'Pro\'ya Yükselt' : 'Enterprise\'a Yükselt'}
                    </button>
                  )}
                  {subscription.plan_type !== 'basic' && (
                    <button
                      onClick={async () => {
                        if (!confirm(`${isletme.ad} işletmesinin planını ${subscription.plan_type === 'pro' ? 'Basic' : 'Pro'}'ye düşürmek istediğinizden emin misiniz?`)) return;
                        try {
                          const planPresets = {
                            basic: { max_subeler: 1, max_kullanicilar: 5, max_menu_items: 100, ayllik_fiyat: 0 },
                            pro: { max_subeler: 5, max_kullanicilar: 20, max_menu_items: 500, ayllik_fiyat: 999 },
                            enterprise: { max_subeler: 999, max_kullanicilar: 999, max_menu_items: 9999, ayllik_fiyat: 2999 }
                          };
                          const newPlan = subscription.plan_type === 'enterprise' ? 'pro' : 'basic';
                          await subscriptionApi.update(isletme.id, {
                            ...subscription,
                            plan_type: newPlan,
                            ...planPresets[newPlan as keyof typeof planPresets]
                          });
                          alert('Plan başarıyla güncellendi');
                          onRefresh();
                        } catch (error: any) {
                          alert(`Plan güncellenemedi: ${error.response?.data?.detail || error.message}`);
                        }
                      }}
                      className="px-3 py-1.5 bg-orange-600 text-white text-sm rounded-lg hover:bg-orange-700 transition-colors"
                    >
                      {subscription.plan_type === 'enterprise' ? 'Pro\'ya Düşür' : 'Basic\'e Düşür'}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <p className="text-gray-500 text-sm">Abonelik bulunamadı</p>
          )}
        </div>
      </div>
      
      {/* İşletme Silme */}
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 mb-6">
        <h3 className="text-lg font-semibold text-red-900 mb-2 flex items-center">
          <AlertCircle className="w-5 h-5 mr-2" />
          Tehlikeli İşlemler
        </h3>
        <p className="text-sm text-red-700 mb-4">
          İşletmeyi silmek, tüm ilişkili verileri (şubeler, menüler, siparişler, ödemeler, abonelikler, vb.) kalıcı olarak silecektir. Bu işlem geri alınamaz!
        </p>
        <button
          onClick={async () => {
            if (!confirm(`"${isletme.ad}" işletmesini ve TÜM ilişkili verilerini silmek istediğinizden emin misiniz?\n\nBu işlem geri alınamaz!`)) return;
            if (!confirm('Son bir kez daha onaylıyor musunuz? Bu işlem geri alınamaz!')) return;
            try {
              await superadminApi.tenantDelete(isletme.id);
              alert('İşletme ve tüm ilişkili veriler başarıyla silindi');
              onBack();
            } catch (error: any) {
              alert(`İşletme silinemedi: ${error.response?.data?.detail || error.message}`);
            }
          }}
          className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors flex items-center"
        >
          <Trash2 className="w-4 h-4 mr-2" />
          İşletmeyi Sil
        </button>
      </div>

      {/* İstatistikler */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
          <BarChart3 className="w-5 h-5 mr-2 text-purple-600" />
          İstatistikler
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <StatCard title="Sipariş Sayısı" value={istatistikler.siparis_sayisi} color="blue" icon={BarChart3} />
          <StatCard title="Toplam Gelir" value={`₺${istatistikler.toplam_gelir.toFixed(2)}`} color="green" icon={DollarSign} />
          <StatCard title="Menü Sayısı" value={istatistikler.menu_item_sayisi} color="orange" icon={Package} />
          <StatCard title="Kullanıcı" value={istatistikler.kullanici_sayisi} color="purple" icon={Users} />
          <StatCard title="Şube" value={istatistikler.sube_sayisi} color="blue" icon={Building2} />
          {istatistikler.son_siparis_tarihi && (
            <div className="bg-gray-50 rounded-lg p-4">
              <p className="text-xs text-gray-600">Son Sipariş</p>
              <p className="font-medium text-sm text-gray-900 mt-1">{new Date(istatistikler.son_siparis_tarihi).toLocaleDateString('tr-TR')}</p>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Şubeler */}
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <Building2 className="w-5 h-5 mr-2 text-indigo-600" />
            Şubeler ({subeler.length})
          </h3>
          {subeler.length > 0 ? (
            <div className="space-y-3">
              {subeler.map((sube) => (
                <div key={sube.id} className="border border-gray-200 rounded-lg p-4 bg-white">
                  <div className="flex items-center justify-between mb-2">
                    <p className="font-medium text-gray-900">{sube.ad}</p>
                    {sube.aktif ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        Aktif
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                        Pasif
                      </span>
                    )}
                  </div>
                  {sube.adres && (
                    <p className="text-sm text-gray-700">{sube.adres}</p>
                  )}
                  {sube.telefon && (
                    <p className="text-sm text-gray-700 flex items-center mt-1">
                      <Phone className="w-3 h-3 mr-1 text-gray-500" />
                      {sube.telefon}
                    </p>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">Şube bulunamadı</p>
          )}
        </div>

        {/* Kullanıcılar */}
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <Users className="w-5 h-5 mr-2 text-purple-600" />
            Kullanıcılar ({kullanicilar.length})
          </h3>
          {kullanicilar.length > 0 ? (
            <div className="space-y-3">
              {kullanicilar.map((user) => (
                <div key={user.id} className="border border-gray-200 rounded-lg p-4 bg-white">
                  <div className="flex items-center justify-between mb-2">
                    <p className="font-medium text-gray-900">{user.username}</p>
                    <div className="flex items-center space-x-2">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 capitalize">
                        {user.role}
                      </span>
                      {user.aktif ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                          Aktif
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                          Pasif
                        </span>
                      )}
                    </div>
                  </div>
                  <p className="text-xs text-gray-600">
                    {new Date(user.created_at).toLocaleDateString('tr-TR')}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">Kullanıcı bulunamadı</p>
          )}
        </div>
      </div>

      {/* Customization */}
      {customization && (
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <Settings className="w-5 h-5 mr-2 text-yellow-600" />
            Özelleştirme
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {customization.app_name && (
              <div>
                <p className="text-sm text-gray-600">App Adı</p>
                <p className="font-medium text-gray-900">{customization.app_name}</p>
              </div>
            )}
            {customization.domain && (
              <div>
                <p className="text-sm text-gray-600">Domain</p>
                <p className="font-medium text-gray-900">{customization.domain}</p>
              </div>
            )}
            {customization.logo_url && (
              <div>
                <p className="text-sm text-gray-600">Logo URL</p>
                <p className="font-medium text-gray-900 break-all">{customization.logo_url}</p>
              </div>
            )}
            {customization.primary_color && (
              <div>
                <p className="text-sm text-gray-600">Tema</p>
                <div className="flex items-center space-x-2">
                  <div 
                    className="w-8 h-8 rounded border border-gray-300"
                    style={{ backgroundColor: customization.primary_color }}
                  />
                  {customization.secondary_color && (
                    <div 
                      className="w-8 h-8 rounded border border-gray-300"
                      style={{ backgroundColor: customization.secondary_color }}
                    />
                  )}
                  <p className="font-medium text-gray-900">
                    {customization.primary_color} / {customization.secondary_color || 'N/A'}
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
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
            placeholder="İşletme adı veya ID ile ara..."
            value={searchTerm}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {subscriptions.map((sub) => {
          // Kullanım süresi hesapla
          const baslangic = sub.baslangic_tarihi ? new Date(sub.baslangic_tarihi) : null;
          const bitis = sub.bitis_tarihi ? new Date(sub.bitis_tarihi) : null;
          const simdi = new Date();
          
          let kullanimSuresi = '';
          let sonrakiYenileme = '';
          
          if (baslangic) {
            const gunFarki = Math.floor((simdi.getTime() - baslangic.getTime()) / (1000 * 60 * 60 * 24));
            if (gunFarki < 30) {
              kullanimSuresi = `${gunFarki} gün`;
            } else if (gunFarki < 365) {
              const ay = Math.floor(gunFarki / 30);
              kullanimSuresi = `${ay} ay`;
            } else {
              const yil = Math.floor(gunFarki / 365);
              const ay = Math.floor((gunFarki % 365) / 30);
              kullanimSuresi = ay > 0 ? `${yil} yıl ${ay} ay` : `${yil} yıl`;
            }
          }
          
          if (sub.otomatik_yenileme && bitis) {
            sonrakiYenileme = new Date(bitis).toLocaleDateString('tr-TR');
          } else if (bitis) {
            sonrakiYenileme = new Date(bitis).toLocaleDateString('tr-TR');
          }
          
          return (
            <div key={sub.id} className="border border-gray-200 rounded-lg p-6 hover:shadow-lg transition-shadow bg-white">
              <div className="flex items-center justify-between mb-4">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-gray-900">
                    {sub.isletme_ad || `İşletme #${sub.isletme_id}`}
                  </h3>
                  {sub.isletme_ad && (
                    <p className="text-xs text-gray-500 mt-1">ID: {sub.isletme_id}</p>
                  )}
                </div>
                <span className={`px-2 py-1 rounded text-xs font-medium whitespace-nowrap ${
                  sub.status === 'active' ? 'bg-green-100 text-green-800' :
                  sub.status === 'suspended' ? 'bg-yellow-100 text-yellow-800' :
                  'bg-red-100 text-red-800'
                }`}>
                  {sub.status === 'active' ? 'Aktif' : sub.status === 'suspended' ? 'Askıya Alındı' : 'İptal'}
                </span>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">Plan:</span>
                  <span className="font-medium text-gray-900 capitalize">{sub.plan_type}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Aylık Fiyat:</span>
                  <span className="font-medium text-gray-900">₺{sub.ayllik_fiyat.toFixed(2)}</span>
                </div>
                {kullanimSuresi && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">Kullanım Süresi:</span>
                    <span className="font-medium text-gray-900">{kullanimSuresi}</span>
                  </div>
                )}
                {sonrakiYenileme && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">{sub.otomatik_yenileme ? 'Yenilenme' : 'Bitiş'} Tarihi:</span>
                    <span className="font-medium text-gray-900">{sonrakiYenileme}</span>
                  </div>
                )}
                <div className="pt-2 mt-2 border-t border-gray-200 grid grid-cols-2 gap-2">
                  <div>
                    <span className="text-xs text-gray-500">Max Şube</span>
                    <p className="font-medium text-gray-900">{sub.max_subeler}</p>
                  </div>
                  <div>
                    <span className="text-xs text-gray-500">Max Kullanıcı</span>
                    <p className="font-medium text-gray-900">{sub.max_kullanicilar}</p>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
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
            placeholder="İşletme adı, ID veya fatura no ile ara..."
            value={searchTerm}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
      </div>

      {payments.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-lg p-8 text-center">
          <p className="text-gray-500 text-lg">Henüz ödeme kaydı bulunmuyor.</p>
          <p className="text-gray-400 text-sm mt-2">Ödeme kayıtları burada görüntülenecek.</p>
        </div>
      ) : (
        <div className="overflow-x-auto bg-white border border-gray-200 rounded-lg">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">İşletme</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tutar</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ödeme Türü</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Durum</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ödeme Tarihi</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Fatura No</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {payments.map((payment) => (
                <tr key={payment.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{payment.id}</td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {payment.isletme_ad || `İşletme #${payment.isletme_id}`}
                      </p>
                      {payment.isletme_ad && (
                        <p className="text-xs text-gray-500">ID: {payment.isletme_id}</p>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-gray-900">₺{payment.tutar.toFixed(2)}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600 capitalize">
                    {payment.odeme_turu === 'odeme_sistemi' ? 'Ödeme Sistemi' :
                     payment.odeme_turu === 'kredi_karti' ? 'Kredi Kartı' :
                     payment.odeme_turu === 'havale' ? 'Havale' :
                     payment.odeme_turu === 'nakit' ? 'Nakit' : payment.odeme_turu}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {payment.durum === 'completed' ? (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        Tamamlandı
                      </span>
                    ) : payment.durum === 'pending' ? (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                        Bekliyor
                      </span>
                    ) : payment.durum === 'failed' ? (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                        Başarısız
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                        İade Edildi
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    {payment.odeme_tarihi ? new Date(payment.odeme_tarihi).toLocaleDateString('tr-TR', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric'
                    }) : '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                    {payment.fatura_no || '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// Customizations Tab
function CustomizationsTab({ tenants, onRefresh }: { tenants: Tenant[]; onRefresh: () => void }) {
  // Tema paketleri
  const themePresets = {
    green: {
      name: 'Yeşil',
      primary: '#00c67f',
      secondary: '#00e699',
      description: 'Doğal ve taze hissiyat',
    },
    blue: {
      name: 'Mavi',
      primary: '#2563eb',
      secondary: '#3b82f6',
      description: 'Profesyonel ve güvenilir görünüm',
    },
    purple: {
      name: 'Mor',
      primary: '#7c3aed',
      secondary: '#8b5cf6',
      description: 'Yaratıcı ve modern',
    },
    rose: {
      name: 'Pembe',
      primary: '#e11d48',
      secondary: '#f43f5e',
      description: 'Sıcak ve davetkar',
    },
  };

  // Renkten temaya çevirme fonksiyonu
  const getThemeFromColors = (primary: string, secondary: string): keyof typeof themePresets => {
    // Mevcut renkleri tema paketlerine eşleştir
    const colorMap: Record<string, keyof typeof themePresets> = {
      '#00c67f': 'green',
      '#00e699': 'green',
      '#10b981': 'green',
      '#34d399': 'green',
      '#2563eb': 'blue',
      '#3b82f6': 'blue',
      '#60a5fa': 'blue',
      '#7c3aed': 'purple',
      '#8b5cf6': 'purple',
      '#a78bfa': 'purple',
      '#e11d48': 'rose',
      '#f43f5e': 'rose',
    };
    
    const normalizedPrimary = primary.toLowerCase();
    const themeKey = colorMap[normalizedPrimary];
    
    if (themeKey) {
      return themeKey;
    }
    
    // Eğer eşleşme yoksa, en yakın temayı bul
    for (const [key, theme] of Object.entries(themePresets)) {
      if (theme.primary.toLowerCase() === normalizedPrimary || 
          theme.secondary.toLowerCase() === secondary.toLowerCase()) {
        return key as keyof typeof themePresets;
      }
    }
    
    return 'green'; // Varsayılan
  };

  const [selectedTenant, setSelectedTenant] = useState<number | null>(tenants[0]?.id ?? null);
  const [formData, setFormData] = useState({
    domain: '',
    app_name: '',
    logo_url: '',
    theme: 'green' as keyof typeof themePresets,
    footer_text: '',
    email: '',
    telefon: '',
    adres: '',
    openai_api_key: '',
    openai_model: 'gpt-4o-mini',
    // Müşteri asistanı ayarları
    customer_assistant_openai_api_key: '',
    customer_assistant_openai_model: 'gpt-4o-mini',
    customer_assistant_tts_voice_id: '',
    customer_assistant_tts_speech_rate: 1.0,
    customer_assistant_tts_provider: 'system',
    // İşletme asistanı ayarları
    business_assistant_openai_api_key: '',
    business_assistant_openai_model: 'gpt-4o-mini',
    business_assistant_tts_voice_id: '',
    business_assistant_tts_speech_rate: 1.0,
    business_assistant_tts_provider: 'system',
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
      theme: 'green',
      footer_text: '',
      email: '',
      telefon: '',
      adres: '',
      openai_api_key: '',
      openai_model: 'gpt-4o-mini',
      // Müşteri asistanı ayarları
      customer_assistant_openai_api_key: '',
      customer_assistant_openai_model: 'gpt-4o-mini',
      customer_assistant_tts_voice_id: '',
      customer_assistant_tts_speech_rate: 1.0,
      customer_assistant_tts_provider: 'system',
      // İşletme asistanı ayarları
      business_assistant_openai_api_key: '',
      business_assistant_openai_model: 'gpt-4o-mini',
      business_assistant_tts_voice_id: '',
      business_assistant_tts_speech_rate: 1.0,
      business_assistant_tts_provider: 'system',
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
        const primary = response.data.primary_color || themePresets.green.primary;
        const secondary = response.data.secondary_color || themePresets.green.secondary;
        // API key'leri maskelenmiş olarak göster
        const maskApiKey = (key: string | undefined) => {
          if (!key) return '';
          return key.length > 12 ? `${key.substring(0, 8)}...${key.substring(key.length - 4)}` : key;
        };
        
        setFormData({
          domain: response.data.domain || '',
          app_name: response.data.app_name || '',
          logo_url: response.data.logo_url || '',
          theme: getThemeFromColors(primary, secondary),
          footer_text: response.data.footer_text || '',
          email: response.data.email || '',
          telefon: response.data.telefon || '',
          adres: response.data.adres || '',
          openai_api_key: maskApiKey(response.data.openai_api_key),
          openai_model: response.data.openai_model || 'gpt-4o-mini',
          // Müşteri asistanı ayarları
          customer_assistant_openai_api_key: maskApiKey(response.data.customer_assistant_openai_api_key),
          customer_assistant_openai_model: response.data.customer_assistant_openai_model || 'gpt-4o-mini',
          customer_assistant_tts_voice_id: response.data.customer_assistant_tts_voice_id || '',
          customer_assistant_tts_speech_rate: typeof response.data.customer_assistant_tts_speech_rate === 'number' ? response.data.customer_assistant_tts_speech_rate : parseFloat(String(response.data.customer_assistant_tts_speech_rate || '1.0')) || 1.0,
          customer_assistant_tts_provider: response.data.customer_assistant_tts_provider || 'system',
          // İşletme asistanı ayarları
          business_assistant_openai_api_key: maskApiKey(response.data.business_assistant_openai_api_key),
          business_assistant_openai_model: response.data.business_assistant_openai_model || 'gpt-4o-mini',
          business_assistant_tts_voice_id: response.data.business_assistant_tts_voice_id || '',
          business_assistant_tts_speech_rate: typeof response.data.business_assistant_tts_speech_rate === 'number' ? response.data.business_assistant_tts_speech_rate : parseFloat(String(response.data.business_assistant_tts_speech_rate || '1.0')) || 1.0,
          business_assistant_tts_provider: response.data.business_assistant_tts_provider || 'system',
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
      const selectedTheme = themePresets[formData.theme];
      const payload = {
        isletme_id: selectedTenant,
        domain: formData.domain || undefined,
        app_name: formData.app_name || undefined,
        logo_url: formData.logo_url || undefined,
        primary_color: selectedTheme.primary,
        secondary_color: selectedTheme.secondary,
        footer_text: formData.footer_text || undefined,
        email: formData.email || undefined,
        telefon: formData.telefon || undefined,
        adres: formData.adres || undefined,
        openai_api_key: formData.openai_api_key && !formData.openai_api_key.includes('...') 
          ? formData.openai_api_key 
          : undefined,
        openai_model: formData.openai_model || 'gpt-4o-mini',
        // Müşteri asistanı ayarları
        customer_assistant_openai_api_key: formData.customer_assistant_openai_api_key && !formData.customer_assistant_openai_api_key.includes('...') 
          ? formData.customer_assistant_openai_api_key 
          : undefined,
        customer_assistant_openai_model: formData.customer_assistant_openai_model || 'gpt-4o-mini',
        customer_assistant_tts_voice_id: formData.customer_assistant_tts_voice_id || undefined,
        customer_assistant_tts_speech_rate: formData.customer_assistant_tts_speech_rate || 1.0,
        customer_assistant_tts_provider: formData.customer_assistant_tts_provider || 'system',
        // İşletme asistanı ayarları
        business_assistant_openai_api_key: formData.business_assistant_openai_api_key && !formData.business_assistant_openai_api_key.includes('...') 
          ? formData.business_assistant_openai_api_key 
          : undefined,
        business_assistant_openai_model: formData.business_assistant_openai_model || 'gpt-4o-mini',
        business_assistant_tts_voice_id: formData.business_assistant_tts_voice_id || undefined,
        business_assistant_tts_speech_rate: formData.business_assistant_tts_speech_rate || 1.0,
        business_assistant_tts_provider: formData.business_assistant_tts_provider || 'system',
      };

      if (exists) {
        await customizationApi.update(selectedTenant, payload);
        setSuccess('Özelleştirme güncellendi');
      } else {
        await customizationApi.create(payload);
        setSuccess('Özelleştirme oluşturuldu');
        setExists(true);
      }
      
      // FormData'yı yeniden yükle
      const response = await customizationApi.get(selectedTenant);
      const primary = response.data.primary_color || themePresets.green.primary;
      const secondary = response.data.secondary_color || themePresets.green.secondary;
      // API key'leri maskelenmiş olarak göster
      const maskApiKey = (key: string | undefined) => {
        if (!key) return '';
        return key.length > 12 ? `${key.substring(0, 8)}...${key.substring(key.length - 4)}` : key;
      };
      
      setFormData({
        domain: response.data.domain || '',
        app_name: response.data.app_name || '',
        logo_url: response.data.logo_url || '',
        theme: getThemeFromColors(primary, secondary),
        footer_text: response.data.footer_text || '',
        email: response.data.email || '',
        telefon: response.data.telefon || '',
        adres: response.data.adres || '',
        openai_api_key: maskApiKey(response.data.openai_api_key),
        openai_model: response.data.openai_model || 'gpt-4o-mini',
        // Müşteri asistanı ayarları
        customer_assistant_openai_api_key: maskApiKey(response.data.customer_assistant_openai_api_key),
        customer_assistant_openai_model: response.data.customer_assistant_openai_model || 'gpt-4o-mini',
        customer_assistant_tts_voice_id: response.data.customer_assistant_tts_voice_id || '',
        customer_assistant_tts_speech_rate: typeof response.data.customer_assistant_tts_speech_rate === 'number' ? response.data.customer_assistant_tts_speech_rate : (parseFloat(String(response.data.customer_assistant_tts_speech_rate || '1.0')) || 1.0),
        customer_assistant_tts_provider: response.data.customer_assistant_tts_provider || 'system',
        // İşletme asistanı ayarları
        business_assistant_openai_api_key: maskApiKey(response.data.business_assistant_openai_api_key),
        business_assistant_openai_model: response.data.business_assistant_openai_model || 'gpt-4o-mini',
        business_assistant_tts_voice_id: response.data.business_assistant_tts_voice_id || '',
        business_assistant_tts_speech_rate: typeof response.data.business_assistant_tts_speech_rate === 'number' ? response.data.business_assistant_tts_speech_rate : (parseFloat(String(response.data.business_assistant_tts_speech_rate || '1.0')) || 1.0),
        business_assistant_tts_provider: response.data.business_assistant_tts_provider || 'system',
      });
      
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
                <label className="block text-sm font-medium text-gray-700 mb-3">Tema Paketi</label>
                <div className="grid grid-cols-2 gap-3">
                  {Object.entries(themePresets).map(([key, theme]) => (
                    <label
                      key={key}
                      className={`border-2 rounded-lg p-3 cursor-pointer transition ${
                        formData.theme === key
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <input
                        type="radio"
                        name="theme"
                        value={key}
                        checked={formData.theme === key}
                        onChange={() => setFormData((prev) => ({ ...prev, theme: key as keyof typeof themePresets }))}
                        className="hidden"
                      />
                      <div className="flex items-center gap-2 mb-1">
                        <div
                          className="w-6 h-6 rounded border border-gray-300"
                          style={{ backgroundColor: theme.primary }}
                        />
                        <span className="font-medium text-sm text-gray-900">{theme.name}</span>
                      </div>
                      <p className="text-xs text-gray-600">{theme.description}</p>
                    </label>
                  ))}
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
            
            {/* Genel OpenAI API Ayarları */}
            <div className="border-t pt-6 mt-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Genel OpenAI API Ayarları</h3>
              <p className="text-sm text-gray-600 mb-4">Asistan-specific ayarlar yoksa kullanılacak genel ayarlar</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Field
                  label="OpenAI API Key (Genel)"
                  type="password"
                  value={formData.openai_api_key}
                  onChange={(value) => setFormData((prev) => ({ ...prev, openai_api_key: value }))}
                  placeholder="sk-..."
                  helpText="İşletme bazında genel OpenAI API anahtarı. Boş bırakılırsa global API key kullanılır."
                />
                <Field
                  label="OpenAI Model (Genel)"
                  value={formData.openai_model}
                  onChange={(value) => setFormData((prev) => ({ ...prev, openai_model: value }))}
                  placeholder="gpt-4o-mini"
                  helpText="Genel OpenAI model (örn: gpt-4o-mini, gpt-4o)"
                />
              </div>
            </div>

            {/* Müşteri Asistanı Ayarları */}
            <div className="border-t pt-6 mt-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Müşteri Asistanı Ayarları</h3>
              <p className="text-sm text-gray-600 mb-4">Müşteri sipariş asistanı için özel ayarlar</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Field
                  label="OpenAI API Key (Müşteri Asistanı)"
                  type="password"
                  value={formData.customer_assistant_openai_api_key}
                  onChange={(value) => setFormData((prev) => ({ ...prev, customer_assistant_openai_api_key: value }))}
                  placeholder="sk-..."
                  helpText="Müşteri asistanı için özel API anahtarı. Boş bırakılırsa genel veya global API key kullanılır."
                />
                <Field
                  label="OpenAI Model (Müşteri Asistanı)"
                  value={formData.customer_assistant_openai_model}
                  onChange={(value) => setFormData((prev) => ({ ...prev, customer_assistant_openai_model: value }))}
                  placeholder="gpt-4o-mini"
                  helpText="Müşteri asistanı için OpenAI model (örn: gpt-4o-mini)"
                />
                <Field
                  label="TTS Ses ID (Müşteri Asistanı)"
                  value={formData.customer_assistant_tts_voice_id}
                  onChange={(value) => setFormData((prev) => ({ ...prev, customer_assistant_tts_voice_id: value }))}
                  placeholder="system_tr_default"
                  helpText="Müşteri asistanı için TTS ses ID (örn: system_tr_default)"
                />
                <Field
                  label="TTS Konuşma Hızı (Müşteri Asistanı)"
                  type="number"
                  step="0.1"
                  min={0.5}
                  max={2.0}
                  value={formData.customer_assistant_tts_speech_rate.toString()}
                  onChange={(value) => setFormData((prev) => ({ ...prev, customer_assistant_tts_speech_rate: parseFloat(value) || 1.0 }))}
                  placeholder="1.0"
                  helpText="Müşteri asistanı için TTS konuşma hızı (0.5 - 2.0)"
                />
                <Field
                  label="TTS Provider (Müşteri Asistanı)"
                  value={formData.customer_assistant_tts_provider}
                  onChange={(value) => setFormData((prev) => ({ ...prev, customer_assistant_tts_provider: value }))}
                  placeholder="system"
                  helpText="Müşteri asistanı için TTS provider (system, google, azure, openai)"
                />
              </div>
            </div>

            {/* İşletme Asistanı Ayarları */}
            <div className="border-t pt-6 mt-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">İşletme Asistanı Ayarları</h3>
              <p className="text-sm text-gray-600 mb-4">İşletme analiz asistanı için özel ayarlar</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Field
                  label="OpenAI API Key (İşletme Asistanı)"
                  type="password"
                  value={formData.business_assistant_openai_api_key}
                  onChange={(value) => setFormData((prev) => ({ ...prev, business_assistant_openai_api_key: value }))}
                  placeholder="sk-..."
                  helpText="İşletme asistanı için özel API anahtarı. Boş bırakılırsa genel veya global API key kullanılır."
                />
                <Field
                  label="OpenAI Model (İşletme Asistanı)"
                  value={formData.business_assistant_openai_model}
                  onChange={(value) => setFormData((prev) => ({ ...prev, business_assistant_openai_model: value }))}
                  placeholder="gpt-4o-mini"
                  helpText="İşletme asistanı için OpenAI model (örn: gpt-4o, gpt-4o-mini)"
                />
                <Field
                  label="TTS Ses ID (İşletme Asistanı)"
                  value={formData.business_assistant_tts_voice_id}
                  onChange={(value) => setFormData((prev) => ({ ...prev, business_assistant_tts_voice_id: value }))}
                  placeholder="system_tr_default"
                  helpText="İşletme asistanı için TTS ses ID (örn: system_tr_default)"
                />
                <Field
                  label="TTS Konuşma Hızı (İşletme Asistanı)"
                  type="number"
                  step="0.1"
                  min={0.5}
                  max={2.0}
                  value={formData.business_assistant_tts_speech_rate.toString()}
                  onChange={(value) => setFormData((prev) => ({ ...prev, business_assistant_tts_speech_rate: parseFloat(value) || 1.0 }))}
                  placeholder="1.0"
                  helpText="İşletme asistanı için TTS konuşma hızı (0.5 - 2.0)"
                />
                <Field
                  label="TTS Provider (İşletme Asistanı)"
                  value={formData.business_assistant_tts_provider}
                  onChange={(value) => setFormData((prev) => ({ ...prev, business_assistant_tts_provider: value }))}
                  placeholder="system"
                  helpText="İşletme asistanı için TTS provider (system, google, azure, openai)"
                />
              </div>
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

// API Usage Tab
function ApiUsageTab() {
  const [stats, setStats] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [days, setDays] = useState(30);
  const [selectedTenant, setSelectedTenant] = useState<number | null>(null);
  const [tenants, setTenants] = useState<Tenant[]>([]);

  useEffect(() => {
    loadTenants();
    loadStats();
  }, [days, selectedTenant]);

  const loadTenants = async () => {
    try {
      const response = await superadminApi.tenantsList();
      setTenants(response.data);
    } catch (error) {
      console.error('Error loading tenants:', error);
    }
  };

  const loadStats = async () => {
    setLoading(true);
    try {
      const response = await superadminApi.apiUsage({
        isletme_id: selectedTenant || undefined,
        days,
        api_type: 'openai',
      });
      setStats(response.data);
    } catch (error) {
      console.error('Error loading API usage stats:', error);
    } finally {
      setLoading(false);
    }
  };

  const totalCost = stats.reduce((sum, stat) => sum + (parseFloat(stat.total_cost_usd) || 0), 0);
  const totalTokens = stats.reduce((sum, stat) => sum + (parseInt(stat.total_tokens) || 0), 0);
  const totalRequests = stats.reduce((sum, stat) => sum + (parseInt(stat.total_requests) || 0), 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">API Kullanım İstatistikleri</h2>
        <div className="flex items-center gap-4">
          <select
            value={selectedTenant || ''}
            onChange={(e) => setSelectedTenant(e.target.value ? parseInt(e.target.value) : null)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">Tüm İşletmeler</option>
            {tenants.map((tenant) => (
              <option key={tenant.id} value={tenant.id}>
                {tenant.ad}
              </option>
            ))}
          </select>
          <select
            value={days}
            onChange={(e) => setDays(parseInt(e.target.value))}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value={7}>Son 7 Gün</option>
            <option value={30}>Son 30 Gün</option>
            <option value={90}>Son 90 Gün</option>
            <option value={365}>Son 1 Yıl</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="mt-2 text-gray-600">Yükleniyor...</p>
        </div>
      ) : (
        <>
          {/* Özet Kartlar */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-6 border border-blue-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-blue-600">Toplam Maliyet</p>
                  <p className="text-2xl font-bold text-blue-900 mt-1">${totalCost.toFixed(4)}</p>
                </div>
                <DollarSign className="w-8 h-8 text-blue-500" />
              </div>
            </div>
            <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-lg p-6 border border-green-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-green-600">Toplam Token</p>
                  <p className="text-2xl font-bold text-green-900 mt-1">{totalTokens.toLocaleString()}</p>
                </div>
                <Activity className="w-8 h-8 text-green-500" />
              </div>
            </div>
            <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-6 border border-purple-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-purple-600">Toplam İstek</p>
                  <p className="text-2xl font-bold text-purple-900 mt-1">{totalRequests.toLocaleString()}</p>
                </div>
                <BarChart3 className="w-8 h-8 text-purple-500" />
              </div>
            </div>
          </div>

          {/* Detaylı Liste */}
          {stats.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg">
              <Activity className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600">Bu dönemde API kullanım kaydı bulunamadı.</p>
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">İşletme</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Model</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Token (Prompt)</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Token (Completion)</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Toplam Token</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Maliyet (USD)</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">İstek Sayısı</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ort. Yanıt Süresi</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {stats.map((stat, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {stat.isletme_ad || `İşletme #${stat.isletme_id}`}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">{stat.model || '-'}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                        {parseInt(stat.total_prompt_tokens || 0).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                        {parseInt(stat.total_completion_tokens || 0).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {parseInt(stat.total_tokens || 0).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-green-600">
                        ${parseFloat(stat.total_cost_usd || 0).toFixed(4)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                        {parseInt(stat.total_requests || 0).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                        {stat.avg_response_time_ms ? `${Math.round(stat.avg_response_time_ms)}ms` : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
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

  // Tema paketleri
  const themePresets = {
    green: {
      name: 'Yeşil',
      primary: '#00c67f',
      secondary: '#00e699',
      description: 'Doğal ve taze hissiyat',
    },
    blue: {
      name: 'Mavi',
      primary: '#2563eb',
      secondary: '#3b82f6',
      description: 'Profesyonel ve güvenilir görünüm',
    },
    purple: {
      name: 'Mor',
      primary: '#7c3aed',
      secondary: '#8b5cf6',
      description: 'Yaratıcı ve modern',
    },
    rose: {
      name: 'Pembe',
      primary: '#e11d48',
      secondary: '#f43f5e',
      description: 'Sıcak ve davetkar',
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
    theme: 'green' as keyof typeof themePresets,
    odeme_turu: 'odeme_sistemi' as 'odeme_sistemi' | 'nakit' | 'havale' | 'kredi_karti',
    openai_api_key: '',
    openai_model: 'gpt-4o-mini',
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
              <label className="block text-sm font-medium text-gray-700 mb-3">Tema Paketi</label>
              <div className="grid grid-cols-2 gap-3">
                {Object.entries(themePresets).map(([key, theme]) => (
                  <label
                    key={key}
                    className={`border-2 rounded-lg p-3 cursor-pointer transition ${
                      formData.theme === key
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <input
                      type="radio"
                      name="theme"
                      value={key}
                      checked={formData.theme === key}
                      onChange={() => handleChange('theme', key)}
                      className="hidden"
                    />
                    <div className="flex items-center gap-2 mb-1">
                      <div
                        className="w-6 h-6 rounded border border-gray-300"
                        style={{ backgroundColor: theme.primary }}
                      />
                      <span className="font-medium text-sm text-gray-900">{theme.name}</span>
                    </div>
                    <p className="text-xs text-gray-600">{theme.description}</p>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Ödeme Bilgileri</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">Ödeme Türü</label>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { value: 'odeme_sistemi', label: 'Ödeme Sistemi', icon: '💳' },
                  { value: 'kredi_karti', label: 'Kredi Kartı', icon: '💳' },
                  { value: 'havale', label: 'Havale', icon: '🏦' },
                  { value: 'nakit', label: 'Nakit', icon: '💵' },
                ].map((option) => (
                  <label
                    key={option.value}
                    className={`border-2 rounded-lg p-3 cursor-pointer transition ${
                      formData.odeme_turu === option.value
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <input
                      type="radio"
                      name="odeme_turu"
                      value={option.value}
                      checked={formData.odeme_turu === option.value}
                      onChange={() => handleChange('odeme_turu', option.value)}
                      className="hidden"
                    />
                    <div className="flex items-center gap-2">
                      <span className="text-xl">{option.icon}</span>
                      <span className="font-medium text-sm text-gray-900">{option.label}</span>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          </div>
          
          {/* OpenAI API Ayarları */}
          <div className="border-t pt-6 mt-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">OpenAI API Ayarları</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Field
                label="OpenAI API Key"
                type="password"
                value={formData.openai_api_key}
                onChange={(value) => handleChange('openai_api_key', value)}
                placeholder="sk-..."
                helpText="İşletme bazında OpenAI API anahtarı (opsiyonel)"
              />
              <Field
                label="OpenAI Model"
                value={formData.openai_model}
                onChange={(value) => handleChange('openai_model', value)}
                placeholder="gpt-4o-mini"
                helpText="Kullanılacak OpenAI model"
              />
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
  max,
  step,
  helpText,
}: {
  label: string;
  value: string | number;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
  error?: string;
  type?: string;
  min?: number;
  max?: number;
  step?: number | string;
  helpText?: string;
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
        max={max}
        step={step}
        className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 bg-white text-gray-900 placeholder-gray-400 ${
          error ? 'border-red-400 focus:ring-red-300' : 'border-gray-300'
        }`}
      />
      {error && <span className="text-xs text-red-500 mt-1">{error}</span>}
      {helpText && !error && <span className="text-xs text-gray-500 mt-1">{helpText}</span>}
    </div>
  );
}



