import { useEffect, useMemo, useState } from 'react';
import { analyticsApi, adminApi, kasaApi, stokApi } from '../lib/api';
import axios from 'axios';
import { useCache } from '../hooks/useCache';
import { performanceUtils } from '../hooks/usePerformance';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import {
  Download,
  Calendar,
  TrendingUp,
  DollarSign,
  ShoppingCart,
  Users,
  Package,
  RefreshCw,
  Award,
  Activity,
  Clock,
  BarChart3,
} from 'lucide-react';

// ... (keep all existing interfaces)
interface TrendData {
  gun: string;
  siparis_adedi: number;
  ciro: number;
}

interface ProductData {
  urun_adi: string;
  satis_adeti: number;
  toplam_tutar: number;
  kategori?: string;
}

interface DailySummary {
  gun: string;
  siparis_sayisi: number;
  ciro: number;
  ortalama_siparis: number;
  iptal_sayisi: number;
  stok_degeri: number;
  period_label?: string;
}

interface PaymentBreakdown {
  yontem: string;
  tutar: number;
}

interface DailyPaymentSummary {
  gunluk_ciro_siparis: number;
  gunluk_odeme_dagilimi: PaymentBreakdown[];
  gunluk_iskonto?: number;
  gunluk_ikram?: number;
}

const COLORS = ['#06b6d4', '#22c55e', '#14b8a6', '#0ea5e9', '#10b981', '#a855f7'];

const API_BASE_URL = import.meta.env?.VITE_API_URL || 'http://localhost:8000';

// Create axios instance with automatic token handling
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Add token interceptor
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('neso.accessToken') || sessionStorage.getItem('neso.token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default function RaporlarPage() {
  const [activeTab, setActiveTab] = useState<'general' | 'profitability' | 'personnel' | 'customer' | 'category' | 'time'>('general');

  // Existing states
  const [trendData, setTrendData] = useState<TrendData[]>([]);
  const [productData, setProductData] = useState<ProductData[]>([]);
  const [dailySummary, setDailySummary] = useState<DailySummary | null>(null);
  const [dailyPayments, setDailyPayments] = useState<DailyPaymentSummary | null>(null);
  const [productPeriod, setProductPeriod] = useState<'gunluk' | 'haftalik' | 'aylik' | 'tumu'>('tumu');
  const [trendDays, setTrendDays] = useState<number>(7);
  const [dateRange, setDateRange] = useState<{ start: string; end: string }>({
    start: new Date().toISOString().split('T')[0],
    end: new Date().toISOString().split('T')[0],
  });
  const [appliedRange, setAppliedRange] = useState<{ start: string; end: string } | null>(null);

  // Advanced analytics fetchers
  const buildRangeParams = (params: Record<string, string>) => {
    if (appliedRange) {
      params.start_date = appliedRange.start;
      params.end_date = appliedRange.end;
    } else {
      if (dateRange.start) params.start_date = dateRange.start;
      if (dateRange.end) params.end_date = dateRange.end;
    }
    return params;
  };

  const fetchProfitability = async () => {
    const params: Record<string, string> = {};
    buildRangeParams(params);

    return performanceUtils.measure('fetch_profitability', async () => {
      const response = await apiClient.get('/analytics/advanced/product-profitability', { params });
      return response.data;
    });
  };

  const fetchPersonnel = async () => {
    const params: Record<string, string> = {};
    buildRangeParams(params);
    if (appliedRange && appliedRange.start === appliedRange.end) {
      params.period = 'day';
    } else if (!appliedRange && dateRange.start === dateRange.end) {
      params.period = 'day';
    } else {
      params.period = 'custom';
    }

    return performanceUtils.measure('fetch_personnel', async () => {
      const response = await apiClient.get('/analytics/advanced/personnel-performance', { params });
      return response.data;
    });
  };

  const fetchCustomer = async () => {
    const params: Record<string, string> = {};
    buildRangeParams(params);

    return performanceUtils.measure('fetch_customer', async () => {
      const response = await apiClient.get('/analytics/advanced/customer-behavior', { params });
      return response.data;
    });
  };

  const fetchCategory = async () => {
    const params: Record<string, string> = {};
    buildRangeParams(params);

    return performanceUtils.measure('fetch_category', async () => {
      const response = await apiClient.get('/analytics/advanced/category-analysis', { params });
      return response.data;
    });
  };

  const fetchTime = async () => {
    const params: Record<string, string> = {};
    buildRangeParams(params);

    return performanceUtils.measure('fetch_time', async () => {
      const response = await apiClient.get('/analytics/advanced/time-based-analysis', { params });
      return response.data;
    });
  };

  // Use cache hooks for advanced analytics
  const cacheKeySuffix = appliedRange ? `${appliedRange.start}_${appliedRange.end}` : `${dateRange.start}_${dateRange.end}`;

  const profitability = useCache(`profitability_${cacheKeySuffix}`, fetchProfitability, { ttl: 0 });

  const personnel = useCache(`personnel_${cacheKeySuffix}`, fetchPersonnel, { ttl: 0 });

  const customer = useCache(`customer_${cacheKeySuffix}`, fetchCustomer, { ttl: 0 });

  const category = useCache(`category_${cacheKeySuffix}`, fetchCategory, { ttl: 0 });

  const timeAnalysis = useCache(`time_${cacheKeySuffix}`, fetchTime, { ttl: 0 });

  // Existing useEffects
  useEffect(() => {
    loadTrendData();
  }, [trendDays, appliedRange, dateRange]);

  useEffect(() => {
    loadProductData();
  }, [productPeriod, appliedRange, dateRange]);

  useEffect(() => {
    profitability.refresh();
    personnel.refresh();
    customer.refresh();
    category.refresh();
    timeAnalysis.refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cacheKeySuffix]);

  useEffect(() => {
    if (appliedRange) {
      loadDailySummary(appliedRange.start, appliedRange.end);
      loadDailyPayments();
    }
  }, [appliedRange]);

  useEffect(() => {
    if (!appliedRange && dateRange.start && dateRange.end) {
      loadDailySummary(dateRange.start, dateRange.end);
      loadDailyPayments();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dateRange.start, dateRange.end]);

  const loadTrendData = async () => {
    try {
    let response;
    if (appliedRange || (dateRange.start && dateRange.end)) {
      const params: Record<string, string | number> = {};
      buildRangeParams(params as Record<string, string>);
      response = await adminApi.trend({
        start: params.start_date as string,
        end: params.end_date as string,
      });
    } else {
      response = await adminApi.trend({ gunSay: trendDays });
    }
      setTrendData(response.data || []);
    } catch (err) {
      console.error('Trend verileri yüklenemedi:', err);
    }
  };

  const loadProductData = async () => {
    try {
      if (productPeriod === 'tumu') {
        const params: Record<string, string> = {};
        buildRangeParams(params);
        const response = await adminApi.topUrunler({
          start: params.start_date,
          end: params.end_date,
          limit: 15,
          metrik: 'ciro',
        });
        const mapped = (response.data?.liste || []).map((item: any) => ({
          urun_adi: item.urun ?? '',
          satis_adeti: Number(item.adet ?? 0),
          toplam_tutar: Number(item.ciro ?? 0),
          kategori: item.kategori ?? undefined,
        }));
        setProductData(mapped);
      } else {
        const response = await analyticsApi.enCokTercihEdilenUrunler(15, productPeriod);
        setProductData(response.data || []);
      }
    } catch (err) {
      console.error('Ürün verileri yüklenemedi:', err);
    }
  };

  const loadDailySummary = async (start: string, end?: string) => {
    try {
      const [adminRes, analyticsRes, stockRes] = await Promise.all([
        end && end !== start ? adminApi.ozet({ start, end }) : adminApi.ozet({ gun: start }),
        analyticsApi.ozet({ start, end }),
        stokApi.list({ limit: 2000 }),
      ]);

      const adminData = adminRes.data || {};
      const analyticsData = analyticsRes.data || {};
      const stockRaw = stockRes?.data;
      const stockItems = Array.isArray(stockRaw)
        ? stockRaw
        : Array.isArray(stockRaw?.data)
          ? stockRaw.data
          : [];
      const stockValue = stockItems.reduce((sum: number, item: any) => {
        const qty = Number(item?.mevcut ?? 0);
        const unitCost = Number(item?.alis_fiyat ?? 0);
        const safeQty = Number.isFinite(qty) ? qty : 0;
        const safeCost = Number.isFinite(unitCost) ? unitCost : 0;
        return sum + safeQty * safeCost;
      }, 0);
      const normalizedStockValue = Number.isFinite(stockValue) ? stockValue : 0;
      const periodLabel = analyticsData.period_label || adminData.kapsam || 'Özet';

      setDailySummary({
        gun:
          analyticsData.period_label === 'Özel Aralık' || (end && end !== start)
            ? `${start} - ${end}`
            : adminData.gun || analyticsData.period_label || start,
        siparis_sayisi: analyticsData.siparis_sayisi ?? adminData.siparis_sayisi ?? 0,
        ciro: analyticsData.toplam_ciro ?? adminData.ciro ?? 0,
        ortalama_siparis: analyticsData.ortalama_sepet ?? adminData.ortalama_siparis ?? 0,
        iptal_sayisi: adminData.iptal_sayisi ?? 0,
        stok_degeri: normalizedStockValue,
        period_label: periodLabel,
      });
    } catch (err) {
      console.error('Özet yüklenemedi:', err);
    }
  };

  const handleDateRangeSubmit = () => {
    const startDate = new Date(dateRange.start);
    const endDate = new Date(dateRange.end);
    if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
      alert('Geçerli bir tarih aralığı seçin');
      return;
    }
    if (startDate > endDate) {
      alert('Başlangıç tarihi bitiş tarihinden büyük olamaz');
      return;
    }
    const diffTime = Math.abs(endDate.getTime() - startDate.getTime());
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24)) + 1;

    if (diffDays <= 60) {
      setTrendDays(diffDays);
      setAppliedRange({ start: dateRange.start, end: dateRange.end });
      loadDailySummary(dateRange.start, dateRange.end);
      loadDailyPayments();
    } else {
      alert('Maksimum 60 günlük tarih aralığı seçebilirsiniz');
    }
  };

  const exportData = () => {
    const csv = [
      ['Tarih Aralığı Raporu', dateRange.start, 'ile', dateRange.end].join(','),
      ['Ürün', 'Satış Adedi', 'Toplam Tutar', 'Kategori'].join(','),
      ...productData.map(p => [p.urun_adi, p.satis_adeti, p.toplam_tutar, p.kategori || ''].join(',')),
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `rapor_${dateRange.start}_${dateRange.end}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const loadDailyPayments = async () => {
    try {
      const response = await kasaApi.gunlukOzet();
      setDailyPayments(response.data || null);
    } catch (err) {
      console.error('Günlük ödeme dağılımı yüklenemedi:', err);
    }
  };

  const paymentColors: Record<string, string> = useMemo(() => ({
    nakit: '#22c55e',
    kart: '#3b82f6',
    kredi_karti: '#3b82f6',
    havale: '#8b5cf6',
    iyzico: '#ec4899',
    papara: '#f97316',
    diger: '#94a3b8',
    iskonto: '#facc15',
    ikram: '#a855f7',
  }), []);

  const handleRefresh = () => {
    const start = (appliedRange?.start ?? dateRange.start) || '';
    const end = (appliedRange?.end ?? dateRange.end) || start;

    switch (activeTab) {
      case 'profitability':
        profitability.refresh();
        break;
      case 'personnel':
        personnel.refresh();
        break;
      case 'customer':
        customer.refresh();
        break;
      case 'category':
        category.refresh();
        break;
      case 'time':
        timeAnalysis.refresh();
        break;
      default:
        loadTrendData();
        loadProductData();
        if (start) {
          loadDailySummary(start, end);
          loadDailyPayments();
        }
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl md:text-3xl font-bold">Raporlar & Analiz</h2>
          <p className="text-sm text-white/60 mt-1">Satış raporları ve gelişmiş analiz</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={handleRefresh}
            className="flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm transition-colors hover:bg-primary-700"
          >
            <RefreshCw className="h-4 w-4" />
            Yenile
          </button>
          <button
            onClick={exportData}
            className="flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm transition-colors hover:bg-green-700"
          >
            <Download className="h-4 w-4" />
            CSV İndir
          </button>
        </div>
      </div>

      {/* Tarih Seçimi */}
      <div className="card">
        <h3 className="text-xl font-semibold mb-4 flex items-center gap-2">
          <Calendar className="w-5 h-5" />
          Tarih Aralığı Seçimi
        </h3>
        <div className="flex flex-col gap-4 md:flex-row md:items-end">
          <div className="w-full">
            <label className="block text-sm text-white/70 mb-2">Başlangıç Tarihi</label>
            <input
              type="date"
              value={dateRange.start}
              onChange={(e) => setDateRange({ ...dateRange, start: e.target.value })}
              className="w-full px-4 py-2 bg-slate-700/50 border border-slate-600/50 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-white placeholder-slate-400"
            />
          </div>
          <div className="w-full">
            <label className="block text-sm text-white/70 mb-2">Bitiş Tarihi</label>
            <input
              type="date"
              value={dateRange.end}
              onChange={(e) => setDateRange({ ...dateRange, end: e.target.value })}
              className="w-full px-4 py-2 bg-slate-700/50 border border-slate-600/50 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-white placeholder-slate-400"
            />
          </div>
          <button
            onClick={handleDateRangeSubmit}
            className="w-full px-6 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors md:w-auto"
          >
            Uygula
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-white/10 pb-2">
        {[
          { id: 'general', icon: BarChart3, label: 'Genel Raporlar' },
          { id: 'profitability', icon: TrendingUp, label: 'Karlılık' },
          { id: 'personnel', icon: Users, label: 'Personel' },
          { id: 'customer', icon: ShoppingCart, label: 'Müşteri' },
          { id: 'category', icon: BarChart3, label: 'Kategori' },
          { id: 'time', icon: Clock, label: 'Zaman' },
        ].map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-t-lg transition ${
                activeTab === tab.id
                  ? 'bg-primary-600 text-white'
                  : 'bg-white/5 text-white/70 hover:bg-white/10 hover:text-white'
              }`}
            >
              <Icon className="h-4 w-4" />
              <span className="hidden sm:inline">{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      {activeTab === 'general' && (
        <div className="space-y-6">
          {/* Özet Kartlar */}
          {dailySummary && (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="card">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-white/70">Sipariş Sayısı</p>
                    <p className="text-2xl font-bold">{dailySummary.siparis_sayisi}</p>
                    <p className="text-xs text-white/50 mt-1">İptal: {dailySummary.iptal_sayisi}</p>
                  </div>
                  <ShoppingCart className="h-6 w-6 text-primary-400 sm:h-8 sm:w-8" />
                </div>
              </div>

              <div className="card">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-white/70">Toplam Ciro</p>
                    <p className="text-2xl font-bold">{dailySummary.ciro.toFixed(2)} ₺</p>
                  </div>
                  <DollarSign className="h-6 w-6 text-green-400 sm:h-8 sm:w-8" />
                </div>
              </div>

              <div className="card">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-white/70">Ortalama Sipariş</p>
                    <p className="text-2xl font-bold">{dailySummary.ortalama_siparis.toFixed(2)} ₺</p>
                  </div>
                  <TrendingUp className="h-6 w-6 text-blue-400 sm:h-8 sm:w-8" />
                </div>
              </div>

              <div className="card">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-white/70">Güncel Stok Değeri</p>
                    <p className="text-2xl font-bold">
                      ₺
                      {dailySummary.stok_degeri.toLocaleString('tr-TR', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </p>
                    <p className="text-xs text-white/50 mt-1">
                      {dailySummary.period_label || dailySummary.gun}
                    </p>
                  </div>
                  <Package className="h-6 w-6 text-yellow-400 sm:h-8 sm:w-8" />
                </div>
              </div>
            </div>
          )}

          {/* Trend Grafiği */}
          <div className="card">
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <h3 className="text-xl font-semibold">Ciro Trendi</h3>
              <select
                value={trendDays}
                onChange={(e) => {
                  const value = Number(e.target.value);
                  setTrendDays(value);
                  setAppliedRange(null);
                }}
                className="w-full rounded-lg border border-slate-600/50 bg-slate-700/50 px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-primary-500 sm:w-44"
              >
                {[7, 14, 30, 60].map((option) => (
                  <option key={option} value={option} className="bg-slate-800">
                    {option} Gün
                  </option>
                ))}
                {!([7, 14, 30, 60].includes(trendDays)) && (
                  <option value={trendDays} className="bg-slate-800">{trendDays} Gün (Özel)</option>
                )}
              </select>
            </div>

            {trendData.length === 0 ? (
              <div className="h-64 flex items-center justify-center text-white/50">Veri bulunamadı</div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                  <XAxis
                    dataKey="gun"
                    stroke="rgba(255,255,255,0.5)"
                    tick={{ fill: 'rgba(255,255,255,0.7)' }}
                  />
                  <YAxis
                    yAxisId="left"
                    stroke="rgba(255,255,255,0.5)"
                    tick={{ fill: 'rgba(255,255,255,0.7)' }}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    stroke="rgba(255,255,255,0.5)"
                    tick={{ fill: 'rgba(255,255,255,0.7)' }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'rgba(0,0,0,0.95)',
                      border: '1px solid rgba(255,255,255,0.3)',
                      borderRadius: '8px'
                    }}
                  />
                  <Legend />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="siparis_adedi"
                    stroke="#0ea5e9"
                    strokeWidth={2}
                    name="Sipariş Sayısı"
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="ciro"
                    stroke="#22c55e"
                    strokeWidth={2}
                    name="Ciro (₺)"
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Charts Grid */}
          {(productData.length > 0 || dailyPayments) && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              {/* Pie Chart */}
              {productData.length > 0 && (
                <div className="card">
                  <h3 className="text-xl font-semibold mb-4">Kategorilere Göre Satış Dağılımı</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie
                        data={productData}
                        dataKey="toplam_tutar"
                        nameKey="urun_adi"
                        cx="50%"
                        cy="50%"
                        outerRadius={100}
                        label={({ percent }) => `${(percent * 100).toFixed(0)}%`}
                      >
                        {productData.map((_entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'rgba(0,0,0,0.95)',
                          border: '1px solid rgba(255,255,255,0.3)',
                          borderRadius: '8px'
                        }}
                      />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Payment Distribution */}
              {dailyPayments && dailyPayments.gunluk_odeme_dagilimi.length > 0 && (
                <div className="card">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-xl font-semibold">Günlük Ödeme Dağılımı</h3>
                    <div className="text-sm text-white/60">
                      Toplam: {dailyPayments.gunluk_odeme_dagilimi.reduce((sum, item) => sum + item.tutar, 0).toFixed(2)} ₺
                    </div>
                  </div>
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={dailyPayments.gunluk_odeme_dagilimi}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                      <XAxis
                        dataKey="yontem"
                        stroke="rgba(255,255,255,0.5)"
                        tick={{ fill: 'rgba(255,255,255,0.7)', fontSize: 12 }}
                      />
                      <YAxis stroke="rgba(255,255,255,0.5)" tick={{ fill: 'rgba(255,255,255,0.7)' }} />
                      <Tooltip
                        formatter={(value: number) => [`${value.toFixed(2)} ₺`, 'Tutar']}
                        labelFormatter={(label) => label.toUpperCase()}
                        contentStyle={{
                          backgroundColor: 'rgba(0,0,0,0.95)',
                          border: '1px solid rgba(255,255,255,0.3)',
                          borderRadius: '8px',
                          color: '#fff',
                        }}
                      />
                      <Legend />
                      <Bar dataKey="tutar" name="Tutar (₺)" radius={[8, 8, 0, 0]}>
                        {dailyPayments.gunluk_odeme_dagilimi.map((item, index) => (
                          <Cell
                            key={`payment-${index}`}
                            fill={paymentColors[item.yontem.toLowerCase()] || '#0ea5e9'}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          )}

          {/* En Çok Tercih Edilen Ürünler */}
          {productData.length > 0 && (
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xl font-semibold">En Çok Tercih Edilen Ürünler</h3>
                <select
                  value={productPeriod}
                  onChange={(e) => setProductPeriod(e.target.value as 'gunluk' | 'haftalik' | 'aylik' | 'tumu')}
                  disabled={Boolean(appliedRange && appliedRange.start !== appliedRange.end)}
                  className="px-4 py-2 bg-slate-700/50 border border-slate-600/50 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-50"
                >
                  <option value="tumu" className="bg-slate-800">Tümü</option>
                  <option value="gunluk" className="bg-slate-800">Günlük</option>
                  <option value="haftalik" className="bg-slate-800">Haftalık</option>
                  <option value="aylik" className="bg-slate-800">Aylık</option>
                </select>
              </div>

              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={productData.slice(0, 10)}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                  <XAxis
                    dataKey="urun_adi"
                    stroke="rgba(255,255,255,0.5)"
                    tick={{ fill: 'rgba(255,255,255,0.7)', fontSize: 11 }}
                    angle={-45}
                    textAnchor="end"
                    height={80}
                  />
                  <YAxis stroke="rgba(255,255,255,0.5)" tick={{ fill: 'rgba(255,255,255,0.7)' }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'rgba(0,0,0,0.95)',
                      border: '1px solid rgba(255,255,255,0.3)',
                      borderRadius: '8px'
                    }}
                  />
                  <Legend />
                  <Bar dataKey="satis_adeti" fill="#06b6d4" name="Satış Adedi" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Detaylı Tablo */}
          <div className="card">
            <h3 className="text-xl font-semibold mb-4">Detaylı Ürün Raporu</h3>
            {productData.length === 0 ? (
              <div className="flex items-center justify-center h-32 text-white/50">Veri bulunamadı</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-white/10">
                      <th className="text-left py-3 px-4 text-white/70">Ürün</th>
                      <th className="text-left py-3 px-4 text-white/70">Kategori</th>
                      <th className="text-right py-3 px-4 text-white/70">Satış Adedi</th>
                      <th className="text-right py-3 px-4 text-white/70">Toplam Tutar</th>
                    </tr>
                  </thead>
                  <tbody>
                    {productData.map((product, idx) => (
                      <tr key={idx} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                        <td className="py-3 px-4 font-medium">{product.urun_adi}</td>
                        <td className="py-3 px-4 text-white/60">{product.kategori || '-'}</td>
                        <td className="py-3 px-4 text-right">{product.satis_adeti}</td>
                        <td className="py-3 px-4 text-right font-semibold">{product.toplam_tutar.toFixed(2)} ₺</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Profitability Tab - Will continue in next message */}
      {activeTab === 'profitability' && (
        <div className="space-y-4">
          {profitability.loading && (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-8 w-8 animate-spin text-primary-600" />
            </div>
          )}

          {profitability.error && (
            <div className="card border border-red-500/20 bg-red-500/10">
              <p className="text-sm text-red-400">Hata: {profitability.error.message}</p>
            </div>
          )}

          {!profitability.loading && !profitability.error && profitability.data && (
            <>
              {/* Summary Cards */}
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div className="card">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-green-500/20 p-2">
                      <DollarSign className="h-5 w-5 text-green-400" />
                    </div>
                    <div>
                      <p className="text-xs text-white/60">Toplam Gelir</p>
                      <p className="text-lg font-bold">
                        ₺{profitability.data.total_revenue?.toLocaleString('tr-TR', { minimumFractionDigits: 2 }) || '0.00'}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-orange-500/20 p-2">
                      <Activity className="h-5 w-5 text-orange-400" />
                    </div>
                    <div>
                      <p className="text-xs text-white/60">Toplam Maliyet</p>
                      <p className="text-lg font-bold">
                        ₺{profitability.data.total_cost?.toLocaleString('tr-TR', { minimumFractionDigits: 2 }) || '0.00'}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-blue-500/20 p-2">
                      <TrendingUp className="h-5 w-5 text-blue-400" />
                    </div>
                    <div>
                      <p className="text-xs text-white/60">Toplam Kar</p>
                      <p className="text-lg font-bold">
                        ₺{profitability.data.total_profit?.toLocaleString('tr-TR', { minimumFractionDigits: 2 }) || '0.00'}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-purple-500/20 p-2">
                      <Award className="h-5 w-5 text-purple-400" />
                    </div>
                    <div>
                      <p className="text-xs text-white/60">Kar Marjı</p>
                      <p className="text-lg font-bold">
                        {profitability.data.profit_margin?.toFixed(1) || '0.0'}%
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Products Table */}
              <div className="card overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-white/5 border-b border-white/10">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-white/70">Ürün</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-white/70">Adet</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-white/70">Gelir</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-white/70">Maliyet</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-white/70">Kar</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-white/70">Marj %</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {profitability.data.products?.map((product: any, idx: number) => (
                        <tr key={idx} className="hover:bg-white/5 transition">
                          <td className="px-4 py-3 text-sm font-medium">{product.urun}</td>
                          <td className="px-4 py-3 text-sm text-right text-white/60">{product.total_quantity}</td>
                          <td className="px-4 py-3 text-sm text-right">
                            ₺{product.revenue.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="px-4 py-3 text-sm text-right text-orange-400">
                            ₺{product.cost.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="px-4 py-3 text-sm text-right font-medium text-green-400">
                            ₺{product.profit.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="px-4 py-3 text-sm text-right">
                            <span className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${
                              product.profit_margin > 70 ? 'bg-green-500/20 text-green-400' :
                              product.profit_margin > 50 ? 'bg-yellow-500/20 text-yellow-400' :
                              'bg-red-500/20 text-red-400'
                            }`}>
                              {product.profit_margin.toFixed(1)}%
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* Personnel Tab */}
      {activeTab === 'personnel' && (
        <div className="space-y-4">
          {personnel.loading && (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-8 w-8 animate-spin text-primary-600" />
            </div>
          )}

          {personnel.error && (
            <div className="card border border-red-500/20 bg-red-500/10">
              <p className="text-sm text-red-400">Hata: {personnel.error.message}</p>
            </div>
          )}

          {!personnel.loading && !personnel.error && personnel.data && (
            <>
              {/* Performance Metrics */}
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <div className="card">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-blue-500/20 p-2">
                      <Users className="h-5 w-5 text-blue-400" />
                    </div>
                    <div>
                      <p className="text-xs text-white/60">Toplam Personel</p>
                      <p className="text-lg font-bold">
                        {personnel.data.personnel_count || 0}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-green-500/20 p-2">
                      <Award className="h-5 w-5 text-green-400" />
                    </div>
                    <div>
                      <p className="text-xs text-white/60">En İyi Performans</p>
                      <p className="text-sm font-bold truncate">
                        {personnel.data.top_performer?.name || '-'}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-purple-500/20 p-2">
                      <TrendingUp className="h-5 w-5 text-purple-400" />
                    </div>
                    <div>
                      <p className="text-xs text-white/60">Ort. Sipariş/Personel</p>
                      <p className="text-lg font-bold">
                        {personnel.data.avg_orders_per_person?.toFixed(1) || '0.0'}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Personnel Table */}
              <div className="card overflow-hidden">
                <h3 className="text-lg font-semibold mb-3 px-4 pt-4">Personel Performans Detayları</h3>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-white/5 border-b border-white/10">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-white/70">Personel</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-white/70">Sipariş Sayısı</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-white/70">Toplam Ciro</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-white/70">Ort. Sipariş</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-white/70">Performans</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {personnel.data.personnel?.map((person: any, idx: number) => (
                        <tr key={idx} className="hover:bg-white/5 transition">
                          <td className="px-4 py-3 text-sm font-medium">{person.name}</td>
                          <td className="px-4 py-3 text-sm text-right text-white/60">{person.order_count}</td>
                          <td className="px-4 py-3 text-sm text-right">
                            ₺{person.total_revenue?.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="px-4 py-3 text-sm text-right text-white/60">
                            ₺{person.avg_order_value?.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="px-4 py-3 text-sm text-right">
                            <span className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${
                              person.performance_score > 80 ? 'bg-green-500/20 text-green-400' :
                              person.performance_score > 60 ? 'bg-yellow-500/20 text-yellow-400' :
                              'bg-orange-500/20 text-orange-400'
                            }`}>
                              {person.performance_score?.toFixed(0) || 0}%
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Performance Chart */}
              {personnel.data.personnel?.length > 0 && (
                <div className="card">
                  <h3 className="text-lg font-semibold mb-3">Personel Ciro Karşılaştırması</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={personnel.data.personnel?.slice(0, 10)}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                      <XAxis
                        dataKey="name"
                        stroke="rgba(255,255,255,0.5)"
                        tick={{ fill: 'rgba(255,255,255,0.7)', fontSize: 11 }}
                        angle={-45}
                        textAnchor="end"
                        height={80}
                      />
                      <YAxis stroke="rgba(255,255,255,0.5)" tick={{ fill: 'rgba(255,255,255,0.7)' }} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'rgba(0,0,0,0.95)',
                          border: '1px solid rgba(255,255,255,0.3)',
                          borderRadius: '8px'
                        }}
                      />
                      <Legend />
                      <Bar dataKey="total_revenue" fill="#22c55e" name="Ciro (₺)" radius={[8, 8, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Customer Tab */}
      {activeTab === 'customer' && (
        <div className="space-y-4">
          {customer.loading && (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-8 w-8 animate-spin text-primary-600" />
            </div>
          )}

          {customer.error && (
            <div className="card border border-red-500/20 bg-red-500/10">
              <p className="text-sm text-red-400">Hata: {customer.error.message}</p>
            </div>
          )}

          {!customer.loading && !customer.error && customer.data && (
            <>
              {/* Customer Metrics */}
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div className="card">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-blue-500/20 p-2">
                      <ShoppingCart className="h-5 w-5 text-blue-400" />
                    </div>
                    <div>
                      <p className="text-xs text-white/60">Toplam Sipariş</p>
                      <p className="text-lg font-bold">
                        {customer.data.total_orders || 0}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-green-500/20 p-2">
                      <DollarSign className="h-5 w-5 text-green-400" />
                    </div>
                    <div>
                      <p className="text-xs text-white/60">Ort. Sipariş Değeri</p>
                      <p className="text-lg font-bold">
                        ₺{customer.data.avg_order_value?.toFixed(2) || '0.00'}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-purple-500/20 p-2">
                      <Users className="h-5 w-5 text-purple-400" />
                    </div>
                    <div>
                      <p className="text-xs text-white/60">Ort. Ürün/Sipariş</p>
                      <p className="text-lg font-bold">
                        {customer.data.avg_items_per_order?.toFixed(1) || '0.0'}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-orange-500/20 p-2">
                      <Activity className="h-5 w-5 text-orange-400" />
                    </div>
                    <div>
                      <p className="text-xs text-white/60">İptal Oranı</p>
                      <p className="text-lg font-bold">
                        {customer.data.cancellation_rate?.toFixed(1) || '0.0'}%
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Popular Items */}
              {customer.data.popular_items?.length > 0 && (
                <div className="card">
                  <h3 className="text-lg font-semibold mb-3">En Popüler Ürünler</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={customer.data.popular_items?.slice(0, 10)}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                      <XAxis
                        dataKey="item_name"
                        stroke="rgba(255,255,255,0.5)"
                        tick={{ fill: 'rgba(255,255,255,0.7)', fontSize: 11 }}
                        angle={-45}
                        textAnchor="end"
                        height={80}
                      />
                      <YAxis stroke="rgba(255,255,255,0.5)" tick={{ fill: 'rgba(255,255,255,0.7)' }} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'rgba(0,0,0,0.95)',
                          border: '1px solid rgba(255,255,255,0.3)',
                          borderRadius: '8px'
                        }}
                      />
                      <Legend />
                      <Bar dataKey="order_count" fill="#06b6d4" name="Sipariş Sayısı" radius={[8, 8, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Payment Methods */}
              {customer.data.payment_methods?.length > 0 && (
                <div className="card">
                  <h3 className="text-lg font-semibold mb-3">Ödeme Yöntemi Tercihleri</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie
                        data={customer.data.payment_methods}
                        dataKey="count"
                        nameKey="method"
                        cx="50%"
                        cy="50%"
                        outerRadius={100}
                        label={({ percent }) => `${(percent * 100).toFixed(0)}%`}
                      >
                        {customer.data.payment_methods?.map((_entry: any, index: number) => (
                          <Cell key={`payment-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'rgba(0,0,0,0.95)',
                          border: '1px solid rgba(255,255,255,0.3)',
                          borderRadius: '8px'
                        }}
                      />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Category Tab */}
      {activeTab === 'category' && (
        <div className="space-y-4">
          {category.loading && (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-8 w-8 animate-spin text-primary-600" />
            </div>
          )}

          {category.error && (
            <div className="card border border-red-500/20 bg-red-500/10">
              <p className="text-sm text-red-400">Hata: {category.error.message}</p>
            </div>
          )}

          {!category.loading && !category.error && category.data && (
            <>
              {/* Category Summary */}
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <div className="card">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-blue-500/20 p-2">
                      <BarChart3 className="h-5 w-5 text-blue-400" />
                    </div>
                    <div>
                      <p className="text-xs text-white/60">Toplam Kategori</p>
                      <p className="text-lg font-bold">
                        {category.data.category_count || 0}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-green-500/20 p-2">
                      <Award className="h-5 w-5 text-green-400" />
                    </div>
                    <div>
                      <p className="text-xs text-white/60">En Çok Satan</p>
                      <p className="text-sm font-bold truncate">
                        {category.data.top_category?.name || '-'}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-purple-500/20 p-2">
                      <TrendingUp className="h-5 w-5 text-purple-400" />
                    </div>
                    <div>
                      <p className="text-xs text-white/60">Toplam Ciro</p>
                      <p className="text-lg font-bold">
                        ₺{category.data.total_revenue?.toLocaleString('tr-TR', { minimumFractionDigits: 2 }) || '0.00'}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Category Table */}
              <div className="card overflow-hidden">
                <h3 className="text-lg font-semibold mb-3 px-4 pt-4">Kategori Detayları</h3>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-white/5 border-b border-white/10">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-white/70">Kategori</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-white/70">Satış Adedi</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-white/70">Ciro</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-white/70">Ort. Fiyat</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-white/70">Pay %</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {category.data.categories?.map((cat: any, idx: number) => (
                        <tr key={idx} className="hover:bg-white/5 transition">
                          <td className="px-4 py-3 text-sm font-medium">{cat.name}</td>
                          <td className="px-4 py-3 text-sm text-right text-white/60">{cat.quantity_sold}</td>
                          <td className="px-4 py-3 text-sm text-right">
                            ₺{cat.revenue?.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="px-4 py-3 text-sm text-right text-white/60">
                            ₺{cat.avg_price?.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="px-4 py-3 text-sm text-right">
                            <span className="inline-flex px-2 py-1 rounded-full text-xs font-medium bg-blue-500/20 text-blue-400">
                              {cat.revenue_share?.toFixed(1)}%
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Category Chart */}
              {category.data.categories?.length > 0 && (
                <div className="card">
                  <h3 className="text-lg font-semibold mb-3">Kategori Ciro Dağılımı</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie
                        data={category.data.categories}
                        dataKey="revenue"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        outerRadius={100}
                        label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                      >
                        {category.data.categories?.map((_entry: any, index: number) => (
                          <Cell key={`category-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(value: number) => `₺${value.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}`}
                        contentStyle={{
                          backgroundColor: 'rgba(0,0,0,0.95)',
                          border: '1px solid rgba(255,255,255,0.3)',
                          borderRadius: '8px'
                        }}
                      />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Time Tab */}
      {activeTab === 'time' && (
        <div className="space-y-4">
          {timeAnalysis.loading && (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-8 w-8 animate-spin text-primary-600" />
            </div>
          )}

          {timeAnalysis.error && (
            <div className="card border border-red-500/20 bg-red-500/10">
              <p className="text-sm text-red-400">Hata: {timeAnalysis.error.message}</p>
            </div>
          )}

          {!timeAnalysis.loading && !timeAnalysis.error && timeAnalysis.data && (
            <>
              {/* Time Summary */}
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div className="card">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-blue-500/20 p-2">
                      <Clock className="h-5 w-5 text-blue-400" />
                    </div>
                    <div>
                      <p className="text-xs text-white/60">En Yoğun Saat</p>
                      <p className="text-lg font-bold">
                        {timeAnalysis.data.peak_hour || '-'}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-green-500/20 p-2">
                      <TrendingUp className="h-5 w-5 text-green-400" />
                    </div>
                    <div>
                      <p className="text-xs text-white/60">Zirve Ciro Saati</p>
                      <p className="text-lg font-bold">
                        {timeAnalysis.data.peak_revenue_hour || '-'}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-purple-500/20 p-2">
                      <Activity className="h-5 w-5 text-purple-400" />
                    </div>
                    <div>
                      <p className="text-xs text-white/60">Ort. Sipariş/Saat</p>
                      <p className="text-lg font-bold">
                        {timeAnalysis.data.avg_orders_per_hour?.toFixed(1) || '0.0'}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-orange-500/20 p-2">
                      <BarChart3 className="h-5 w-5 text-orange-400" />
                    </div>
                    <div>
                      <p className="text-xs text-white/60">En Yoğun Gün</p>
                      <p className="text-sm font-bold">
                        {timeAnalysis.data.busiest_day || '-'}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Hourly Analysis Chart */}
              {timeAnalysis.data.hourly?.length > 0 && (
                <div className="card">
                  <h3 className="text-lg font-semibold mb-3">Saatlik Sipariş Dağılımı</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={timeAnalysis.data.hourly}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                      <XAxis
                        dataKey="hour"
                        stroke="rgba(255,255,255,0.5)"
                        tick={{ fill: 'rgba(255,255,255,0.7)' }}
                      />
                      <YAxis
                        yAxisId="left"
                        stroke="rgba(255,255,255,0.5)"
                        tick={{ fill: 'rgba(255,255,255,0.7)' }}
                      />
                      <YAxis
                        yAxisId="right"
                        orientation="right"
                        stroke="rgba(255,255,255,0.5)"
                        tick={{ fill: 'rgba(255,255,255,0.7)' }}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'rgba(0,0,0,0.95)',
                          border: '1px solid rgba(255,255,255,0.3)',
                          borderRadius: '8px'
                        }}
                      />
                      <Legend />
                      <Line
                        yAxisId="left"
                        type="monotone"
                        dataKey="order_count"
                        stroke="#0ea5e9"
                        strokeWidth={2}
                        name="Sipariş Sayısı"
                      />
                      <Line
                        yAxisId="right"
                        type="monotone"
                        dataKey="revenue"
                        stroke="#22c55e"
                        strokeWidth={2}
                        name="Ciro (₺)"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Daily Analysis */}
              {timeAnalysis.data.daily?.length > 0 && (
                <div className="card">
                  <h3 className="text-lg font-semibold mb-3">Günlük Performans</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={timeAnalysis.data.daily}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                      <XAxis
                        dataKey="day_name"
                        stroke="rgba(255,255,255,0.5)"
                        tick={{ fill: 'rgba(255,255,255,0.7)' }}
                      />
                      <YAxis stroke="rgba(255,255,255,0.5)" tick={{ fill: 'rgba(255,255,255,0.7)' }} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'rgba(0,0,0,0.95)',
                          border: '1px solid rgba(255,255,255,0.3)',
                          borderRadius: '8px'
                        }}
                      />
                      <Legend />
                      <Bar dataKey="order_count" fill="#06b6d4" name="Sipariş Sayısı" radius={[8, 8, 0, 0]} />
                      <Bar dataKey="revenue" fill="#22c55e" name="Ciro (₺)" radius={[8, 8, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Time Slots Table */}
              {timeAnalysis.data.hourly?.length > 0 && (
                <div className="card overflow-hidden">
                  <h3 className="text-lg font-semibold mb-3 px-4 pt-4">Saatlik Detaylar</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-white/5 border-b border-white/10">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-medium text-white/70">Saat Dilimi</th>
                          <th className="px-4 py-3 text-right text-xs font-medium text-white/70">Sipariş</th>
                          <th className="px-4 py-3 text-right text-xs font-medium text-white/70">Ciro</th>
                          <th className="px-4 py-3 text-right text-xs font-medium text-white/70">Ort. Sipariş</th>
                          <th className="px-4 py-3 text-right text-xs font-medium text-white/70">Yoğunluk</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {timeAnalysis.data.hourly?.map((slot: any, idx: number) => (
                          <tr key={idx} className="hover:bg-white/5 transition">
                            <td className="px-4 py-3 text-sm font-medium">{slot.hour}:00</td>
                            <td className="px-4 py-3 text-sm text-right text-white/60">{slot.order_count}</td>
                            <td className="px-4 py-3 text-sm text-right">
                              ₺{slot.revenue?.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}
                            </td>
                            <td className="px-4 py-3 text-sm text-right text-white/60">
                              ₺{slot.avg_order_value?.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}
                            </td>
                            <td className="px-4 py-3 text-sm text-right">
                              <span className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${
                                slot.order_count > timeAnalysis.data.avg_orders_per_hour ?
                                  'bg-green-500/20 text-green-400' :
                                  'bg-slate-500/20 text-slate-400'
                              }`}>
                                {slot.order_count > timeAnalysis.data.avg_orders_per_hour ? 'Yoğun' : 'Normal'}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
