import { useEffect, useMemo, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { analyticsApi } from '../lib/api';
import {
  ComposedChart,
  Line,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { TrendingUp, Package, DollarSign, ShoppingCart, BadgePercent, Gift, Users, TrendingDown } from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';

const PERIOD_LABELS: Record<'gunluk' | 'haftalik' | 'aylik', string> = {
  gunluk: 'Günlük',
  haftalik: 'Haftalık',
  aylik: 'Aylık',
};

interface HourlyData {
  saat: number;
  siparis_sayisi: number;
  toplam_tutar: number;
}

interface ProductData {
  urun_adi: string;
  satis_adeti: number;
  toplam_tutar: number;
  kategori?: string;
}

interface SummaryData {
  period: 'gunluk' | 'haftalik' | 'aylik';
  period_label: string;
  start_tarih: string;
  end_tarih: string;
  siparis_sayisi: number;
  toplam_ciro: number;
  toplam_gider: number;
  ortalama_sepet: number;
  ortalama_masa_tutari: number;
  en_populer_urun?: string;
  odeme_dagilim?: Record<string, number>;
  toplam_iskonto: number;
  toplam_ikram: number;
  en_cok_ikram?: {
    urun_adi: string;
    adet: number;
    tutar: number;
  } | null;
  top_personeller: Array<{
    username: string;
    display_name: string;
    role?: string;
    siparis_sayisi: number;
    toplam_ciro: number;
  }>;
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const theme = useAuthStore((state) => state.theme);
  const tenantCustomization = useAuthStore((state) => state.tenantCustomization);
  const [summaryPeriod, setSummaryPeriod] = useState<'gunluk' | 'haftalik' | 'aylik'>('gunluk');
  const queryClient = useQueryClient();
  
  // İşletme adını belirle
  const businessName = tenantCustomization?.app_name || 'İşletme';

  const formatCurrency = useCallback((value: number, fractionDigits = 2) =>
    value.toLocaleString('tr-TR', {
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    }), []);

  const formatHour = useCallback((hour: number | null | undefined) =>
    hour === null || hour === undefined ? '-' : `${hour.toString().padStart(2, '0')}:00`, []);

  const { selectedTenantId } = useAuthStore();
  
  useEffect(() => {
    // Yetki kontrolü - sadece tenant admin erişebilir
    // Super admin tenant seçtiğinde dashboard'u görebilir
    if (user) {
      const role = user.role?.toLowerCase();
      const username = user.username?.toLowerCase();
      const isSuperAdmin = role === 'super_admin' || username === 'super';
      
      // Super admin "Tüm İşletmeler" modundaysa Super Admin paneline yönlendir
      // (TenantRequiredGuard zaten bunu yapıyor ama ekstra güvenlik için)
      if (isSuperAdmin && selectedTenantId === null) {
        navigate('/superadmin');
        return;
      }
      
      // Super admin tenant seçtiğinde dashboard'u görebilir
      // Normal admin'ler her zaman görebilir
      if (!isSuperAdmin && role !== 'admin') {
        navigate('/login');
      }
    }
  }, [user, selectedTenantId, navigate]);

  const summaryQuery = useQuery<SummaryData>({
    queryKey: ['analytics', 'summary', summaryPeriod],
    queryFn: async () => {
      const { data } = await analyticsApi.ozet({ period: summaryPeriod });
      return data;
    },
    keepPreviousData: true,
    staleTime: 1000 * 60 * 5,
  });

  const hourlyQuery = useQuery<HourlyData[]>({
    queryKey: ['analytics', 'hourly', summaryPeriod],
    queryFn: async () => {
      const { data } = await analyticsApi.saatlikYogunluk(summaryPeriod);
      return data || [];
    },
    keepPreviousData: true,
    staleTime: 1000 * 60 * 5,
  });

  const productQuery = useQuery<ProductData[]>({
    queryKey: ['analytics', 'products', summaryPeriod],
    queryFn: async () => {
      const { data } = await analyticsApi.enCokTercihEdilenUrunler(10, summaryPeriod);
      return data || [];
    },
    keepPreviousData: true,
    staleTime: 1000 * 60 * 5,
  });

  const summary = summaryQuery.data ?? null;
  const hourlyData = hourlyQuery.data ?? [];
  const productData = productQuery.data ?? [];

  const hourlyInsights = useMemo(() => {
    if (!hourlyData || hourlyData.length === 0) {
      return {
        peakHour: null as number | null,
        peakHourIndex: -1,
        peakOrdersValue: 0,
        peakRevenueHour: null as number | null,
        peakRevenueValue: 0,
        avgOrders: 0,
        avgRevenue: 0,
      };
    }

    let peakOrdersIndex = 0;
    let peakRevenueIndex = 0;
    let totalOrders = 0;
    let totalRevenue = 0;

    hourlyData.forEach((entry, index) => {
      totalOrders += entry.siparis_sayisi;
      totalRevenue += entry.toplam_tutar;
      if (entry.siparis_sayisi > hourlyData[peakOrdersIndex].siparis_sayisi) {
        peakOrdersIndex = index;
      }
      if (entry.toplam_tutar > hourlyData[peakRevenueIndex].toplam_tutar) {
        peakRevenueIndex = index;
      }
    });

    const avgOrders = totalOrders / hourlyData.length;
    const avgRevenue = totalRevenue / hourlyData.length;

    return {
      peakHour: hourlyData[peakOrdersIndex]?.saat ?? null,
      peakHourIndex: peakOrdersIndex,
      peakOrdersValue: hourlyData[peakOrdersIndex]?.siparis_sayisi ?? 0,
      peakRevenueHour: hourlyData[peakRevenueIndex]?.saat ?? null,
      peakRevenueValue: hourlyData[peakRevenueIndex]?.toplam_tutar ?? 0,
      avgOrders,
      avgRevenue,
    };
  }, [hourlyData]);

  const isInitialLoading = summaryQuery.isLoading && !summary;
  const hourlyLoading = hourlyQuery.isFetching;
  const productLoading = productQuery.isFetching;

  const handleRefresh = () => {
    queryClient.invalidateQueries({
      predicate: (query) => Array.isArray(query.queryKey) && query.queryKey[0] === 'analytics',
    });
  };

  const textMuted = theme === 'dark' ? 'text-emerald-100/70' : 'text-[#285247]/70';
  const tableRowHover = theme === 'dark' ? 'hover:bg-white/5' : 'hover:bg-[#EAF7F1]';
  const axisColor = theme === 'dark' ? 'rgba(210, 235, 226, 0.75)' : 'rgba(27, 63, 55, 0.75)';
  const gridColor = theme === 'dark' ? 'rgba(210, 235, 226, 0.12)' : 'rgba(27, 63, 55, 0.08)';
  const tooltipBg = theme === 'dark' ? 'rgba(9,25,28,0.95)' : '#FFFFFF';
  const tooltipColor = theme === 'dark' ? '#E9FBF3' : '#12302C';
  const legendColor = theme === 'dark' ? '#D2EBE2' : '#16423B';
  const referenceLineColor = theme === 'dark' ? '#64748B' : '#94A3B8';

  const renderHourlyTooltip = useCallback(
    ({ active, payload, label }: any) => {
      if (!active || !payload || payload.length === 0) return null;
      const orders = payload.find((item: any) => item.dataKey === 'siparis_sayisi');
      const revenue = payload.find((item: any) => item.dataKey === 'toplam_tutar');

      return (
        <div
          className={`rounded-xl border px-3 py-2 shadow-lg ${
            theme === 'dark'
              ? 'border-emerald-800/60 bg-emerald-950/85 text-emerald-50'
              : 'border-[#CCEBDD] bg-white text-[#0C3832]'
          }`}
        >
          <p className="text-xs font-semibold">{formatHour(label)}</p>
          {orders && (
            <p className="text-sm font-semibold text-[#0F5132] dark:text-emerald-200">
              {orders.value} sipariş
            </p>
          )}
          {revenue && (
            <p className="text-xs text-[#104239] dark:text-emerald-100/85">
              Ciro: {formatCurrency(Number(revenue.value))} ₺
            </p>
          )}
        </div>
      );
    },
    [theme],
  );

  const stats = useMemo(() => {
    if (!summary) return [];
    const currentPeriodLabel = summary.period_label || PERIOD_LABELS[summaryPeriod];
    const topIkram = summary.en_cok_ikram;
    const topPersonnelLines =
      summary.top_personeller?.map((person, idx) => {
        const rank = idx + 1;
        return `${rank}. ${person.display_name} · ${person.siparis_sayisi.toLocaleString('tr-TR')} sipariş · ${formatCurrency(
          person.toplam_ciro,
        )} ₺`;
      }) ?? [];

    const topPersonnelValue =
      summary.top_personeller.find((person) => person.role === 'ai')?.display_name ??
      summary.top_personeller[0]?.display_name ??
      'Veri bekleniyor';

    return [
      {
        key: 'revenue',
        label: `${currentPeriodLabel} Ciro`,
        value: `${formatCurrency(summary.toplam_ciro)} ₺`,
        helper: `${currentPeriodLabel} toplam ciro`,
        icon: DollarSign,
        iconColor: '#0EA5E9',
        accent: 'from-[#0EA5E9]/35 via-[#0EA5E9]/10 to-transparent',
        dropdown: summary.odeme_dagilim,
        dropdownLabel: `${currentPeriodLabel} ödeme dağılımı`,
      },
      {
        key: 'expense',
        label: `${currentPeriodLabel} Gider`,
        value: `${formatCurrency(summary.toplam_gider)} ₺`,
        helper:
          summary.toplam_gider > 0
            ? `${currentPeriodLabel} boyunca kaydedilen toplam gider`
            : `${currentPeriodLabel} gider kaydı bulunamadı`,
        icon: TrendingDown,
        iconColor: '#EF4444',
        accent: 'from-[#EF4444]/30 via-[#EF4444]/10 to-transparent',
      },
      {
        key: 'orders',
        label: `${currentPeriodLabel} Sipariş`,
        value: summary.siparis_sayisi.toLocaleString('tr-TR'),
        helper: `${currentPeriodLabel} toplam sipariş sayısı`,
        icon: ShoppingCart,
        iconColor: '#10B981',
        accent: 'from-[#00C67F]/25 via-transparent to-transparent',
      },
      {
        key: 'avg_table',
        label: 'Ortalama Masa Tutarı',
        value: `${formatCurrency(summary.ortalama_masa_tutari ?? summary.ortalama_sepet)} ₺`,
        helper: `Sepet ortalaması: ${formatCurrency(summary.ortalama_sepet)} ₺`,
        icon: TrendingUp,
        iconColor: '#2563EB',
        accent: 'from-[#2563EB]/25 via-transparent to-transparent',
      },
      {
        key: 'top_product',
        label: 'En Popüler Ürün',
        value: summary.en_populer_urun ?? 'Veri bekleniyor',
        helper: `${currentPeriodLabel} dönemi en çok tercih edilen ürün`,
        icon: Package,
        iconColor: '#F59E0B',
        accent: 'from-[#FFD166]/35 via-transparent to-transparent',
      },
      {
        key: 'discount',
        label: `${currentPeriodLabel} İskonto`,
        value: `${formatCurrency(summary.toplam_iskonto)} ₺`,
        helper:
          summary.toplam_iskonto > 0
            ? `${currentPeriodLabel} boyunca uygulanan toplam indirim`
            : `${currentPeriodLabel} indirim uygulanmadı`,
        icon: BadgePercent,
        iconColor: '#F97316',
        accent: 'from-[#F97316]/30 via-transparent to-transparent',
      },
      {
        key: 'complimentary',
        label: `${currentPeriodLabel} İkram`,
        value: `${formatCurrency(summary.toplam_ikram)} ₺`,
        helperLines: topIkram
          ? [
              `${topIkram.urun_adi}`,
              `${topIkram.adet.toLocaleString('tr-TR')} adet · ${formatCurrency(topIkram.tutar)} ₺`,
            ]
          : [`${currentPeriodLabel} döneminde ikram kaydı bulunamadı`],
        icon: Gift,
        iconColor: '#6366F1',
        accent: 'from-[#6366F1]/25 via-transparent to-transparent',
      },
      {
        key: 'top_personnel',
        label: 'En Çok Performans Gösteren Personel',
        value: topPersonnelValue,
        helperLines:
          topPersonnelLines.length > 0 ? topPersonnelLines : [`${currentPeriodLabel} döneminde personel kaydı yok`],
        icon: Users,
        iconColor: '#14B8A6',
        accent: 'from-[#14B8A6]/25 via-transparent to-transparent',
      },
    ];
  }, [summary, summaryPeriod]);

  if (isInitialLoading) {
    return (
      <div className="flex items-center justify-center h-72">
        <div className={`${textMuted}`}>Veriler hazırlanıyor...</div>
      </div>
    );
  }

  return (
    <div className="space-y-8 md:space-y-10">
      <section
        className="premium-card relative overflow-hidden rounded-3xl p-8 md:p-12"
      >
        <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/10 blur-[100px] rounded-full -mr-32 -mt-32" />
        <div className="relative flex flex-col gap-8 md:flex-row md:items-center md:justify-between">
          <div className="space-y-4">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-bold uppercase tracking-wider">
              <TrendingUp className="w-3 h-3" />
              {PERIOD_LABELS[summaryPeriod]} Performans Analizi
            </div>
            <h2 className="text-4xl md:text-5xl font-bold tracking-tight text-white">
              {businessName} <span className="text-gradient">Analitik</span>
            </h2>
            <p className="text-slate-400 text-lg max-w-xl">
              İşletmenizin gerçek zamanlı performans verilerini ve büyüme analizlerini buradan takip edebilirsiniz.
            </p>
          </div>
          <div className="flex flex-col sm:flex-row gap-4">
            <select
              value={summaryPeriod}
              onChange={(e) => setSummaryPeriod(e.target.value as 'gunluk' | 'haftalik' | 'aylik')}
              className="min-w-[160px]"
            >
              <option value="gunluk">{PERIOD_LABELS.gunluk}</option>
              <option value="haftalik">{PERIOD_LABELS.haftalik}</option>
              <option value="aylik">{PERIOD_LABELS.aylik}</option>
            </select>
            <button 
              onClick={handleRefresh} 
              className="glow-button px-8 py-3 rounded-xl text-white font-bold flex items-center justify-center gap-2"
            >
              Verileri Güncelle
            </button>
          </div>
        </div>
      </section>

      {summary && (
        <section className="grid grid-cols-1 gap-6 sm:gap-6 md:grid-cols-2 xl:grid-cols-4">
          {stats.map(
            ({ key, label, value, helper, helperLines, icon: Icon, iconColor, dropdown, dropdownLabel }) => (
              <div key={key} className="premium-card group relative overflow-hidden p-6 rounded-2xl">
                <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                  <Icon className="w-12 h-12" style={{ color: iconColor }} />
                </div>
                <div className="relative space-y-4">
                  <div>
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">{label}</p>
                    <p className="mt-2 text-3xl font-bold text-white tracking-tight">
                      {value ?? '—'}
                    </p>
                  </div>
                  
                  {dropdown ? (
                    <div className="pt-4 border-t border-slate-700/50 space-y-3">
                      <p className="text-xs font-semibold text-emerald-500/80">{dropdownLabel}</p>
                      <div className="grid gap-2">
                        {Object.entries(dropdown).map(([method, val]) => (
                          <div key={method} className="flex items-center justify-between text-sm">
                            <span className="capitalize text-slate-400">{method}</span>
                            <span className="font-bold text-slate-200">{(val as number).toFixed(2)} ₺</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="pt-4 border-t border-slate-700/50">
                       {helperLines ? (
                        <div className="space-y-1">
                          {helperLines.map((line, idx) => (
                            <p key={idx} className="text-sm text-slate-400 font-medium">{line}</p>
                          ))}
                        </div>
                       ) : (
                        <p className="text-sm text-slate-400 font-medium">{helper}</p>
                       )}
                    </div>
                  )}
                </div>
              </div>
            )
          )}
        </section>
      )}
      {summary && (
        <p className={`px-1 text-xs sm:text-sm ${textMuted}`}>
          Dönem aralığı: {new Date(summary.start_tarih).toLocaleDateString('tr-TR')} -{' '}
          {new Date(summary.end_tarih).toLocaleDateString('tr-TR')}
        </p>
      )}

      <section className="premium-card rounded-2xl p-8">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6 pb-8">
          <div>
            <h3 className="text-2xl font-bold text-white">Saatlik Yoğunluk</h3>
            <p className="text-slate-400 mt-1">
              Sipariş ve ciro bazlı trafik analizi
            </p>
          </div>
        </div>

        {!hourlyLoading && hourlyData.length > 0 && (
          <div className="grid grid-cols-1 gap-3 pb-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-[#CCEBDD]/60 bg-white/60 px-4 py-3 shadow-sm dark:border-emerald-900/50 dark:bg-emerald-950/40">
              <span className={`text-xs uppercase tracking-wide ${textMuted}`}>En Yoğun Saat</span>
              <span className="mt-1 block text-lg font-semibold text-[#0F5132] dark:text-emerald-200">
                {formatHour(hourlyInsights.peakHour)}
              </span>
              <span className={`text-sm ${textMuted}`}>
                {hourlyInsights.peakOrdersValue.toLocaleString('tr-TR')} sipariş
              </span>
            </div>
            <div className="rounded-xl border border-[#CCEBDD]/60 bg-white/60 px-4 py-3 shadow-sm dark:border-emerald-900/50 dark:bg-emerald-950/40">
              <span className={`text-xs uppercase tracking-wide ${textMuted}`}>En Yüksek Ciro Saati</span>
              <span className="mt-1 block text-lg font-semibold text-[#0F5132] dark:text-emerald-200">
                {formatHour(hourlyInsights.peakRevenueHour)}
              </span>
              <span className={`text-sm ${textMuted}`}>
                {formatCurrency(hourlyInsights.peakRevenueValue)} ₺
              </span>
            </div>
            <div className="rounded-xl border border-[#CCEBDD]/60 bg-white/60 px-4 py-3 shadow-sm dark:border-emerald-900/50 dark:bg-emerald-950/40">
              <span className={`text-xs uppercase tracking-wide ${textMuted}`}>Ortalama Saatlik Sipariş</span>
              <span className="mt-1 block text-lg font-semibold text-[#0F5132] dark:text-emerald-200">
                {hourlyInsights.avgOrders.toFixed(1)}
              </span>
              <span className={`text-sm ${textMuted}`}>Saat başına</span>
            </div>
            <div className="rounded-xl border border-[#CCEBDD]/60 bg-white/60 px-4 py-3 shadow-sm dark:border-emerald-900/50 dark:bg-emerald-950/40">
              <span className={`text-xs uppercase tracking-wide ${textMuted}`}>Ortalama Saatlik Ciro</span>
              <span className="mt-1 block text-lg font-semibold text-[#0F5132] dark:text-emerald-200">
                {formatCurrency(hourlyInsights.avgRevenue)} ₺
              </span>
              <span className={`text-sm ${textMuted}`}>Saat başına</span>
            </div>
          </div>
        )}

        {hourlyLoading ? (
          <div className={`h-64 flex items-center justify-center ${textMuted}`}>Yükleniyor...</div>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <ComposedChart data={hourlyData}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
              <XAxis
                dataKey="saat"
                stroke={axisColor}
                tick={{ fill: axisColor }}
                tickFormatter={(value: number) => formatHour(value)}
              />
              <YAxis
                yAxisId="left"
                stroke={axisColor}
                tick={{ fill: axisColor }}
                tickFormatter={(value: number) => value.toLocaleString('tr-TR')}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                stroke={axisColor}
                tick={{ fill: axisColor }}
                tickFormatter={(value: number) => `${formatCurrency(value)} ₺`}
              />
              <Tooltip content={renderHourlyTooltip} />
              <Legend
                verticalAlign="top"
                height={36}
                wrapperStyle={{ color: legendColor, paddingTop: 8, fontSize: 12 }}
              />
              <Bar
                yAxisId="left"
                dataKey="siparis_sayisi"
                name="Sipariş Sayısı"
                maxBarSize={28}
                radius={[8, 8, 2, 2]}
              >
                {hourlyData.map((_, index) => (
                  <Cell
                    key={`orders-${index}`}
                    fill={index === hourlyInsights.peakHourIndex ? '#0EA5E9' : 'rgba(14,165,233,0.28)'}
                  />
                ))}
              </Bar>
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="toplam_tutar"
                name="Toplam Tutar (₺)"
                stroke="#22C55E"
                strokeWidth={2.5}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
              />
              {hourlyInsights.avgOrders > 0 && (
                <ReferenceLine
                  yAxisId="left"
                  y={hourlyInsights.avgOrders}
                  stroke={referenceLineColor}
                  strokeDasharray="4 4"
                  label={{
                    value: `Ort. ${hourlyInsights.avgOrders.toFixed(1)}`,
                    position: 'left',
                    fill: referenceLineColor,
                    fontSize: 11,
                  }}
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </section>

      <section className="card">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-4">
          <div>
            <h3 className="text-xl font-semibold text-[#0C3832] dark:text-emerald-50">En Çok Tercih Edilen Ürünler</h3>
            <p className={`text-sm ${textMuted}`}>
              {PERIOD_LABELS[summaryPeriod]} döneminde satış adetlerine göre sıralanmış ürün performansı
            </p>
          </div>
        </div>

        {productLoading ? (
          <div className={`h-64 flex items-center justify-center ${textMuted}`}>Yükleniyor...</div>
        ) : productData.length === 0 ? (
          <div className={`h-64 flex items-center justify-center ${textMuted}`}>Veri bulunamadı</div>
        ) : (
          <ResponsiveContainer width="100%" height={360}>
            <BarChart data={productData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
              <XAxis type="number" stroke={axisColor} tick={{ fill: axisColor }} />
              <YAxis
                type="category"
                dataKey="urun_adi"
                width={160}
                stroke={axisColor}
                tick={{ fill: axisColor, fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: tooltipBg,
                  color: tooltipColor,
                  border: `1px solid ${theme === 'dark' ? 'rgba(0,198,127,0.25)' : '#CCEBDD'}`,
                  borderRadius: 12,
                }}
              />
              <Legend wrapperStyle={{ color: legendColor, paddingTop: 16 }} />
              <Bar dataKey="satis_adeti" fill="#0EA5E9" name="Satış Adedi" radius={[0, 12, 12, 0]} maxBarSize={22} />
              <Bar dataKey="toplam_tutar" fill="#00C67F" name="Toplam Tutar (₺)" radius={[0, 12, 12, 0]} maxBarSize={22} />
            </BarChart>
          </ResponsiveContainer>
        )}

        {productData.length > 0 && (
          <div className="divider" />
        )}

        {productData.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className={`${theme === 'dark' ? 'border-b border-[#1C3A36]' : 'border-b border-[#D6EDE2]'}`}>
                  <th className={`text-left py-3 px-4 font-medium ${textMuted}`}>Ürün</th>
                  <th className={`text-left py-3 px-4 font-medium ${textMuted}`}>Kategori</th>
                  <th className={`text-right py-3 px-4 font-medium ${textMuted}`}>Satış Adedi</th>
                  <th className={`text-right py-3 px-4 font-medium ${textMuted}`}>Toplam Tutar</th>
                </tr>
              </thead>
              <tbody>
                {productData.map((product: ProductData, idx: number) => (
                  <tr
                    key={idx}
                    className={`${theme === 'dark' ? 'border-b border-[#16302F]/60' : 'border-b border-[#E5F3ED]'} ${tableRowHover}`}
                  >
                    <td className="py-3 px-4 font-medium text-[#104239] dark:text-emerald-50">{product.urun_adi}</td>
                    <td className={`py-3 px-4 text-left ${textMuted}`}>{product.kategori || '-'}</td>
                    <td className="py-3 px-4 text-right text-[#104239] dark:text-emerald-100">{product.satis_adeti}</td>
                    <td className="py-3 px-4 text-right font-semibold text-[#0F5132] dark:text-emerald-200">
                      {product.toplam_tutar.toFixed(2)} ₺
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
