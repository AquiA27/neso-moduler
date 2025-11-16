import { useState } from 'react';
import { useAuthStore } from '../store/authStore';
import { useCache } from '../hooks/useCache';
import { performanceUtils } from '../hooks/usePerformance';
import {
  TrendingUp,
  Users,
  ShoppingCart,
  BarChart3,
  Clock,
  DollarSign,
  Award,
  Activity,
  RefreshCw,
  Download,
} from 'lucide-react';

interface ProductProfitability {
  urun: string;
  total_quantity: number;
  revenue: number;
  cost: number;
  profit: number;
  profit_margin: number;
}

interface PersonnelPerformance {
  username: string;
  total_orders: number;
  total_revenue: number;
  avg_order_value: number;
  cancelled_orders: number;
  cancellation_rate: number;
  performance_score: number;
}

export default function AdvancedAnalyticsPage() {
  const token = useAuthStore((state) => state.accessToken);
  const [activeTab, setActiveTab] = useState<'profitability' | 'personnel' | 'customer' | 'category' | 'time'>('profitability');
  const [dateRange, setDateRange] = useState({ start: '', end: '' });

  // API fetchers
  const fetchProfitability = async () => {
    const params = new URLSearchParams();
    if (dateRange.start) params.append('start_date', dateRange.start);
    if (dateRange.end) params.append('end_date', dateRange.end);

    return performanceUtils.measure('fetch_profitability', async () => {
      const response = await fetch(
        `http://localhost:8000/analytics/advanced/product-profitability?${params}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!response.ok) throw new Error('Failed to fetch profitability data');
      return response.json();
    });
  };

  const fetchPersonnel = async () => {
    const params = new URLSearchParams();
    if (dateRange.start) params.append('start_date', dateRange.start);
    if (dateRange.end) params.append('end_date', dateRange.end);

    return performanceUtils.measure('fetch_personnel', async () => {
      const response = await fetch(
        `http://localhost:8000/analytics/advanced/personnel-performance?${params}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!response.ok) throw new Error('Failed to fetch personnel data');
      return response.json();
    });
  };

  const fetchCustomer = async () => {
    const params = new URLSearchParams();
    if (dateRange.start) params.append('start_date', dateRange.start);
    if (dateRange.end) params.append('end_date', dateRange.end);

    return performanceUtils.measure('fetch_customer', async () => {
      const response = await fetch(
        `http://localhost:8000/analytics/advanced/customer-behavior?${params}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!response.ok) throw new Error('Failed to fetch customer data');
      return response.json();
    });
  };

  const fetchCategory = async () => {
    const params = new URLSearchParams();
    if (dateRange.start) params.append('start_date', dateRange.start);
    if (dateRange.end) params.append('end_date', dateRange.end);

    return performanceUtils.measure('fetch_category', async () => {
      const response = await fetch(
        `http://localhost:8000/analytics/advanced/category-analysis?${params}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!response.ok) throw new Error('Failed to fetch category data');
      return response.json();
    });
  };

  const fetchTime = async () => {
    const params = new URLSearchParams();
    if (dateRange.start) params.append('start_date', dateRange.start);
    if (dateRange.end) params.append('end_date', dateRange.end);

    return performanceUtils.measure('fetch_time', async () => {
      const response = await fetch(
        `http://localhost:8000/analytics/advanced/time-based-analysis?${params}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!response.ok) throw new Error('Failed to fetch time data');
      return response.json();
    });
  };

  // Use cache hooks
  const profitability = useCache(
    `profitability_${dateRange.start}_${dateRange.end}`,
    fetchProfitability,
    { ttl: 5 * 60 * 1000 } // 5 minutes
  );

  const personnel = useCache(
    `personnel_${dateRange.start}_${dateRange.end}`,
    fetchPersonnel,
    { ttl: 5 * 60 * 1000 }
  );

  const customer = useCache(
    `customer_${dateRange.start}_${dateRange.end}`,
    fetchCustomer,
    { ttl: 5 * 60 * 1000 }
  );

  const category = useCache(
    `category_${dateRange.start}_${dateRange.end}`,
    fetchCategory,
    { ttl: 5 * 60 * 1000 }
  );

  const timeAnalysis = useCache(
    `time_${dateRange.start}_${dateRange.end}`,
    fetchTime,
    { ttl: 5 * 60 * 1000 }
  );

  // Get active data
  const getActiveData = () => {
    switch (activeTab) {
      case 'profitability':
        return profitability;
      case 'personnel':
        return personnel;
      case 'customer':
        return customer;
      case 'category':
        return category;
      case 'time':
        return timeAnalysis;
      default:
        return profitability;
    }
  };

  const activeData = getActiveData();

  const handleRefresh = () => {
    activeData.refresh();
  };

  const handleExport = () => {
    // TODO: Implement export to Excel
    alert('Excel export özelliği yakında eklenecek!');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-slate-900">
            Gelişmiş Raporlama
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Karlılık, personel performans ve müşteri davranış analizi
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={handleRefresh}
            disabled={activeData.loading}
            className="flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-700 disabled:opacity-50 transition"
          >
            <RefreshCw className={`h-4 w-4 ${activeData.loading ? 'animate-spin' : ''}`} />
            Yenile
          </button>
          <button
            onClick={handleExport}
            className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 transition"
          >
            <Download className="h-4 w-4" />
            Export
          </button>
        </div>
      </div>

      {/* Date Range Filter */}
      <div className="glass rounded-xl p-4 shadow-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <label className="text-sm font-medium text-slate-700">Tarih Aralığı:</label>
          <input
            type="date"
            value={dateRange.start}
            onChange={(e) => setDateRange((prev) => ({ ...prev, start: e.target.value }))}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
          />
          <span className="text-slate-500">-</span>
          <input
            type="date"
            value={dateRange.end}
            onChange={(e) => setDateRange((prev) => ({ ...prev, end: e.target.value }))}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
          />
        </div>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-slate-200">
        {[
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
              className={`flex items-center gap-2 border-b-2 px-4 py-2 text-sm font-medium transition ${
                activeTab === tab.id
                  ? 'border-primary-600 text-primary-600'
                  : 'border-transparent text-slate-600 hover:border-slate-300 hover:text-slate-900'
              }`}
            >
              <Icon className="h-4 w-4" />
              <span className="hidden sm:inline">{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Content */}
      {activeData.loading && (
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <RefreshCw className="mx-auto h-8 w-8 animate-spin text-primary-600" />
            <p className="mt-2 text-sm text-slate-600">Veriler yükleniyor...</p>
          </div>
        </div>
      )}

      {activeData.error && (
        <div className="glass rounded-xl border border-red-200 bg-red-50 p-6">
          <p className="text-sm text-red-600">
            Hata: {activeData.error.message}
          </p>
        </div>
      )}

      {!activeData.loading && !activeData.error && activeData.data && (
        <div className="space-y-6">
          {/* Profitability Tab */}
          {activeTab === 'profitability' && activeData.data && (
            <div className="space-y-4">
              {/* Summary Cards */}
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div className="glass rounded-xl p-4 shadow-sm">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-green-100 p-2">
                      <DollarSign className="h-5 w-5 text-green-600" />
                    </div>
                    <div>
                      <p className="text-xs text-slate-600">Toplam Gelir</p>
                      <p className="text-lg font-bold text-slate-900">
                        ₺{activeData.data.total_revenue?.toLocaleString('tr-TR', { minimumFractionDigits: 2 }) || '0.00'}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="glass rounded-xl p-4 shadow-sm">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-orange-100 p-2">
                      <Activity className="h-5 w-5 text-orange-600" />
                    </div>
                    <div>
                      <p className="text-xs text-slate-600">Toplam Maliyet</p>
                      <p className="text-lg font-bold text-slate-900">
                        ₺{activeData.data.total_cost?.toLocaleString('tr-TR', { minimumFractionDigits: 2 }) || '0.00'}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="glass rounded-xl p-4 shadow-sm">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-blue-100 p-2">
                      <TrendingUp className="h-5 w-5 text-blue-600" />
                    </div>
                    <div>
                      <p className="text-xs text-slate-600">Toplam Kar</p>
                      <p className="text-lg font-bold text-slate-900">
                        ₺{activeData.data.total_profit?.toLocaleString('tr-TR', { minimumFractionDigits: 2 }) || '0.00'}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="glass rounded-xl p-4 shadow-sm">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-purple-100 p-2">
                      <Award className="h-5 w-5 text-purple-600" />
                    </div>
                    <div>
                      <p className="text-xs text-slate-600">Kar Marjı</p>
                      <p className="text-lg font-bold text-slate-900">
                        {activeData.data.profit_margin?.toFixed(1) || '0.0'}%
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Products Table */}
              <div className="glass rounded-xl overflow-hidden shadow-sm">
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-slate-50 border-b border-slate-200">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-slate-700">Ürün</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-slate-700">Adet</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-slate-700">Gelir</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-slate-700">Maliyet</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-slate-700">Kar</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-slate-700">Marj %</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      {activeData.data.products?.map((product: ProductProfitability, idx: number) => (
                        <tr key={idx} className="hover:bg-slate-50 transition">
                          <td className="px-4 py-3 text-sm font-medium text-slate-900">{product.urun}</td>
                          <td className="px-4 py-3 text-sm text-right text-slate-600">{product.total_quantity}</td>
                          <td className="px-4 py-3 text-sm text-right text-slate-900">
                            ₺{product.revenue.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="px-4 py-3 text-sm text-right text-orange-600">
                            ₺{product.cost.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="px-4 py-3 text-sm text-right font-medium text-green-600">
                            ₺{product.profit.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="px-4 py-3 text-sm text-right">
                            <span className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${
                              product.profit_margin > 70 ? 'bg-green-100 text-green-700' :
                              product.profit_margin > 50 ? 'bg-yellow-100 text-yellow-700' :
                              'bg-red-100 text-red-700'
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
            </div>
          )}

          {/* Personnel Tab */}
          {activeTab === 'personnel' && activeData.data?.personnel && (
            <div className="glass rounded-xl overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-slate-50 border-b border-slate-200">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-slate-700">Personel</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-slate-700">Sipariş</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-slate-700">Gelir</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-slate-700">Ort. Tutar</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-slate-700">İptal %</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-slate-700">Skor</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {activeData.data.personnel.map((person: PersonnelPerformance, idx: number) => (
                      <tr key={idx} className="hover:bg-slate-50 transition">
                        <td className="px-4 py-3 text-sm font-medium text-slate-900">{person.username}</td>
                        <td className="px-4 py-3 text-sm text-right text-slate-600">{person.total_orders}</td>
                        <td className="px-4 py-3 text-sm text-right text-slate-900">
                          ₺{person.total_revenue.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-4 py-3 text-sm text-right text-slate-600">
                          ₺{person.avg_order_value.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-4 py-3 text-sm text-right text-slate-600">
                          {person.cancellation_rate.toFixed(1)}%
                        </td>
                        <td className="px-4 py-3 text-sm text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="h-2 w-20 bg-slate-200 rounded-full overflow-hidden">
                              <div
                                className={`h-full ${
                                  person.performance_score > 80 ? 'bg-green-500' :
                                  person.performance_score > 60 ? 'bg-yellow-500' :
                                  'bg-red-500'
                                }`}
                                style={{ width: `${person.performance_score}%` }}
                              />
                            </div>
                            <span className="text-xs font-medium text-slate-700">
                              {person.performance_score.toFixed(0)}
                            </span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Customer Tab */}
          {activeTab === 'customer' && activeData.data && (
            <div className="space-y-4">
              {/* Summary */}
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="glass rounded-xl p-4 shadow-sm">
                  <p className="text-sm text-slate-600">Toplam Müşteri</p>
                  <p className="text-2xl font-bold text-slate-900 mt-1">
                    {activeData.data.total_unique_tables || 0}
                  </p>
                </div>
                <div className="glass rounded-xl p-4 shadow-sm">
                  <p className="text-sm text-slate-600">Ortalama Hesap</p>
                  <p className="text-2xl font-bold text-slate-900 mt-1">
                    ₺{activeData.data.avg_check_per_table?.toLocaleString('tr-TR', { minimumFractionDigits: 2 }) || '0.00'}
                  </p>
                </div>
              </div>

              {/* Segments */}
              {activeData.data.customer_segments && (
                <div className="glass rounded-xl p-6 shadow-sm">
                  <h3 className="text-lg font-semibold text-slate-900 mb-4">Müşteri Segmentasyonu</h3>
                  <div className="space-y-3">
                    {activeData.data.customer_segments.map((segment: any, idx: number) => (
                      <div key={idx} className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
                        <div>
                          <p className="font-medium text-slate-900">{segment.segment}</p>
                          <p className="text-sm text-slate-600">{segment.description}</p>
                          <p className="text-xs text-slate-500 mt-1">{segment.count} müşteri</p>
                        </div>
                        <div className="text-right">
                          <p className="text-lg font-bold text-slate-900">
                            ₺{segment.total_revenue.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}
                          </p>
                          <p className="text-xs text-slate-600">
                            Ort: ₺{segment.avg_revenue.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Peak Hours */}
              {activeData.data.peak_hours && activeData.data.peak_hours.length > 0 && (
                <div className="glass rounded-xl p-6 shadow-sm">
                  <h3 className="text-lg font-semibold text-slate-900 mb-4">Yoğun Saatler</h3>
                  <div className="flex flex-wrap gap-2">
                    {activeData.data.peak_hours.slice(0, 5).map((hour: any, idx: number) => (
                      <div key={idx} className="px-4 py-2 bg-primary-100 text-primary-700 rounded-lg text-sm font-medium">
                        {hour.hour}:00 ({hour.order_count} sipariş)
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Category Tab */}
          {activeTab === 'category' && activeData.data?.categories && (
            <div className="space-y-4">
              {activeData.data.categories.map((cat: any, idx: number) => (
                <div key={idx} className="glass rounded-xl p-6 shadow-sm">
                  <div className="flex items-start justify-between mb-4">
                    <div>
                      <h3 className="text-lg font-semibold text-slate-900">{cat.kategori || 'Diğer'}</h3>
                      <p className="text-sm text-slate-600 mt-1">
                        {cat.total_quantity} adet • Ortalama: ₺{cat.avg_price.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xl font-bold text-slate-900">
                        ₺{cat.total_revenue.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}
                      </p>
                      <span className="inline-flex px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-700 mt-1">
                        {cat.revenue_share.toFixed(1)}%
                      </span>
                    </div>
                  </div>

                  {/* Top Products */}
                  {cat.top_products && cat.top_products.length > 0 && (
                    <div className="border-t border-slate-200 pt-4">
                      <p className="text-sm font-medium text-slate-700 mb-2">En Çok Satanlar:</p>
                      <div className="space-y-2">
                        {cat.top_products.slice(0, 3).map((product: any, pidx: number) => (
                          <div key={pidx} className="flex items-center justify-between text-sm">
                            <span className="text-slate-600">{product.urun}</span>
                            <span className="font-medium text-slate-900">
                              {product.quantity} adet • ₺{product.revenue.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Time Tab */}
          {activeTab === 'time' && activeData.data && (
            <div className="space-y-6">
              {/* Hourly Distribution */}
              {activeData.data.hourly_distribution && (
                <div className="glass rounded-xl p-6 shadow-sm">
                  <h3 className="text-lg font-semibold text-slate-900 mb-4">Saatlik Dağılım</h3>
                  <div className="grid grid-cols-4 sm:grid-cols-6 lg:grid-cols-12 gap-2">
                    {activeData.data.hourly_distribution.map((item: any, idx: number) => (
                      <div
                        key={idx}
                        className="text-center p-2 bg-slate-50 rounded-lg hover:bg-slate-100 transition"
                      >
                        <p className="text-xs font-medium text-slate-700">{item.hour}:00</p>
                        <p className="text-sm font-bold text-slate-900 mt-1">{item.order_count}</p>
                        <p className="text-xs text-slate-600">
                          ₺{(item.revenue || 0).toLocaleString('tr-TR', { maximumFractionDigits: 0 })}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Weekday Distribution */}
              {activeData.data.weekday_distribution && (
                <div className="glass rounded-xl p-6 shadow-sm">
                  <h3 className="text-lg font-semibold text-slate-900 mb-4">Haftalık Dağılım</h3>
                  <div className="space-y-3">
                    {activeData.data.weekday_distribution.map((item: any, idx: number) => (
                      <div key={idx} className="flex items-center gap-4">
                        <div className="w-24 text-sm font-medium text-slate-700">{item.weekday}</div>
                        <div className="flex-1">
                          <div className="h-8 bg-slate-100 rounded-lg overflow-hidden">
                            <div
                              className="h-full bg-gradient-to-r from-primary-500 to-primary-600 flex items-center justify-end px-2"
                              style={{
                                width: `${Math.min(
                                  (item.order_count /
                                    Math.max(...activeData.data.weekday_distribution.map((d: any) => d.order_count))) *
                                    100,
                                  100
                                )}%`,
                              }}
                            >
                              <span className="text-xs font-medium text-white">
                                {item.order_count}
                              </span>
                            </div>
                          </div>
                        </div>
                        <div className="w-32 text-right text-sm font-medium text-slate-900">
                          ₺{item.revenue.toLocaleString('tr-TR', { minimumFractionDigits: 2 })}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
