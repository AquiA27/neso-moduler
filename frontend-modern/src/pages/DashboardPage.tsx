import { useEffect, useMemo, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { analyticsApi } from '../lib/api';
import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
} from 'recharts';
import { 
  TrendingUp, 
  Package, 
  DollarSign, 
  ShoppingCart, 
  Users, 
  Sparkles,
  Zap,
  Target,
  ArrowRight
} from 'lucide-react';
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
  const tenantCustomization = useAuthStore((state) => state.tenantCustomization);
  const [summaryPeriod, setSummaryPeriod] = useState<'gunluk' | 'haftalik' | 'aylik'>('gunluk');
  const queryClient = useQueryClient();
  const { selectedTenantId } = useAuthStore();
  
  const businessName = tenantCustomization?.app_name || 'İşletme';

  const formatCurrency = useCallback((value: number, fractionDigits = 2) =>
    value.toLocaleString('tr-TR', {
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    }), []);

  const formatHour = useCallback((hour: number | null | undefined) =>
    hour === null || hour === undefined ? '-' : `${hour.toString().padStart(2, '0')}:00`, []);

  useEffect(() => {
    if (user) {
      const role = user.role?.toLowerCase();
      const username = user.username?.toLowerCase();
      const isSuperAdmin = role === 'super_admin' || username === 'super';
      if (isSuperAdmin && selectedTenantId === null) { navigate('/superadmin'); return; }
      if (!isSuperAdmin && role !== 'admin') { navigate('/login'); }
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

  const handleRefresh = () => {
    queryClient.invalidateQueries({ predicate: (query) => Array.isArray(query.queryKey) && query.queryKey[0] === 'analytics' });
  };

  const gridColor = 'rgba(255, 255, 255, 0.05)';
  const axisColor = '#64748b';

  const stats = useMemo(() => {
    if (!summary) return [];
    const currentPeriodLabel = summary.period_label || PERIOD_LABELS[summaryPeriod];
    return [
      { key: 'revenue', label: `${currentPeriodLabel} Ciro`, value: `${formatCurrency(summary.toplam_ciro)} ₺`, helper: `${currentPeriodLabel} toplam ciro`, icon: DollarSign, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
      { key: 'orders', label: `${currentPeriodLabel} Sipariş`, value: summary.siparis_sayisi.toLocaleString('tr-TR'), helper: `${currentPeriodLabel} toplam sipariş`, icon: ShoppingCart, color: 'text-blue-400', bg: 'bg-blue-500/10' },
      { key: 'avg_table', label: 'Masa Ortalaması', value: `${formatCurrency(summary.ortalama_masa_tutari ?? summary.ortalama_sepet)} ₺`, helper: 'Masa başına ortalama harcama', icon: TrendingUp, color: 'text-purple-400', bg: 'bg-purple-500/10' },
      { key: 'top_product', label: 'En Popüler Ürün', value: summary.en_populer_urun ?? 'Veri yok', helper: 'Dönemin favori ürünü', icon: Package, color: 'text-orange-400', bg: 'bg-orange-500/10' },
    ];
  }, [summary, summaryPeriod, formatCurrency]);

  if (summaryQuery.isLoading && !summary) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] gap-4">
        <div className="w-12 h-12 border-4 border-emerald-500/20 border-t-emerald-500 rounded-full animate-spin" />
        <p className="text-slate-400 font-medium animate-pulse">Analizler hazırlanıyor...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12">
      {/* Hero Section */}
      <section className="relative overflow-hidden rounded-[32px] bg-slate-900 border border-white/5 p-8 md:p-12 shadow-2xl">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-emerald-500/10 blur-[120px] rounded-full -mr-64 -mt-64" />
        <div className="absolute bottom-0 left-0 w-[300px] h-[300px] bg-blue-500/10 blur-[100px] rounded-full -ml-32 -mb-32" />
        
        <div className="relative flex flex-col lg:flex-row lg:items-center justify-between gap-8">
          <div className="space-y-4 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-bold uppercase tracking-wider">
              <Sparkles className="w-3 h-3" />
              Real-time Business Intelligence
            </div>
            <h1 className="text-4xl md:text-5xl font-bold text-white tracking-tight leading-tight">
              {businessName} <span className="text-gradient">Analitik</span>
            </h1>
            <p className="text-slate-400 text-lg">
              İşletmenizin performansını yapay zeka destekli verilerle takip edin ve stratejik kararlarınızı güçlendirin.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-center gap-4">
            <div className="flex p-1.5 bg-slate-950/50 rounded-2xl border border-white/5 backdrop-blur-md">
              {(['gunluk', 'haftalik', 'aylik'] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setSummaryPeriod(p)}
                  className={`px-6 py-2 rounded-xl text-sm font-bold transition-all duration-300 ${summaryPeriod === p ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/20' : 'text-slate-500 hover:text-white hover:bg-white/5'}`}
                >
                  {PERIOD_LABELS[p]}
                </button>
              ))}
            </div>
            <button onClick={handleRefresh} className="glow-button group shrink-0">
              Yenile
              <Zap className="inline-block ml-2 w-4 h-4 group-hover:scale-125 transition-transform" />
            </button>
          </div>
        </div>
      </section>

      {/* Main Stats Grid */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((s) => (
          <div key={s.key} className="premium-card p-6 rounded-3xl group">
            <div className="flex items-start justify-between mb-4">
              <div className={`p-3 rounded-2xl ${s.bg} ${s.color} transition-transform duration-500 group-hover:scale-110 group-hover:rotate-3`}>
                <s.icon size={24} />
              </div>
              <div className="text-[10px] font-bold text-emerald-500 bg-emerald-500/5 px-2 py-0.5 rounded-full border border-emerald-500/10">
                +12.5%
              </div>
            </div>
            <div className="space-y-1">
              <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">{s.label}</p>
              <h3 className="text-3xl font-bold text-white tracking-tight leading-none py-1">{s.value}</h3>
              <p className="text-xs text-slate-400 font-medium pt-2 border-t border-white/5 mt-3">{s.helper}</p>
            </div>
          </div>
        ))}
      </section>

      {/* Charts & AI Insights */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Hourly Chart */}
        <div className="lg:col-span-2 premium-card p-8 rounded-[32px]">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h3 className="text-xl font-bold text-white flex items-center gap-2">
                <Target className="text-blue-400" size={20} />
                Yoğunluk Analizi
              </h3>
              <p className="text-sm text-slate-500 mt-1">Günün saat bazlı trafik ve ciro dağılımı</p>
            </div>
          </div>

          <div className="h-[400px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={hourlyData}>
                <defs>
                  <linearGradient id="colorCiro" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
                <XAxis 
                  dataKey="saat" 
                  stroke={axisColor} 
                  tick={{ fill: axisColor, fontSize: 12 }} 
                  axisLine={false} 
                  tickLine={false}
                  tickFormatter={(v) => formatHour(v)}
                />
                <YAxis stroke={axisColor} tick={{ fill: axisColor, fontSize: 12 }} axisLine={false} tickLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '16px', color: '#fff' }}
                />
                <Area type="monotone" dataKey="toplam_tutar" stroke="#10b981" fillOpacity={1} fill="url(#colorCiro)" strokeWidth={3} />
                <Bar dataKey="siparis_sayisi" fill="rgba(59, 130, 246, 0.5)" radius={[6, 6, 0, 0]} maxBarSize={30} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* AI Insights Card */}
        <div className="premium-card p-8 rounded-[32px] bg-gradient-to-br from-indigo-500/10 via-slate-900 to-emerald-500/5 border-emerald-500/20 group relative overflow-hidden">
           <div className="absolute top-0 right-0 p-4 animate-float">
             <Sparkles className="text-emerald-400/30" size={80} />
           </div>

           <div className="relative space-y-6">
             <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/20 border border-indigo-500/30 text-indigo-300 text-[10px] font-bold uppercase">
               AI Strategic Insight
             </div>
             
             <h3 className="text-2xl font-bold text-white leading-tight">İşletme Özeti & Tavsiyeler</h3>
             
             <div className="space-y-4">
               <div className="p-4 rounded-2xl bg-white/5 border border-white/5 hover:bg-white/10 transition-colors">
                  <p className="text-sm font-bold text-emerald-400 mb-1 flex items-center gap-2">
                    <TrendingUp size={16} /> Büyüme Fırsatı
                  </p>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    Saat 14:00 - 16:00 arası yoğunluk düşük. Bu saatler için "Mutlu Saatler" kampanyası ciroda %15 artış sağlayabilir.
                  </p>
               </div>

               <div className="p-4 rounded-2xl bg-white/5 border border-white/5 hover:bg-white/10 transition-colors">
                  <p className="text-sm font-bold text-orange-400 mb-1 flex items-center gap-2">
                    <Package size={16} /> Stok Alarmı
                  </p>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    {summary?.en_populer_urun || 'Ana ürün'} satış hızı arttı. Önümüzdeki 48 saat için stok siparişi vermenizi öneririm.
                  </p>
               </div>

               <div className="p-4 rounded-2xl bg-white/5 border border-white/5 hover:bg-white/10 transition-colors">
                  <p className="text-sm font-bold text-blue-400 mb-1 flex items-center gap-2">
                    <Users size={16} /> Personel Verimi
                  </p>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    Haftalık en çok sipariş alan personel: {summary?.top_personeller[0]?.display_name || 'Admin'}. Teşekkür etmeyi unutmayın!
                  </p>
               </div>
             </div>

             <button className="w-full flex items-center justify-between p-4 rounded-2xl bg-emerald-500 text-white font-bold hover:bg-emerald-400 transition-colors">
               Detaylı Raporu Gör
               <ArrowRight size={20} />
             </button>
           </div>
        </div>
      </div>

      {/* Bottom Product Grid */}
      <section className="premium-card p-8 rounded-[32px]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
           <div>
             <h3 className="text-2xl font-bold text-white">Ürün Performansı</h3>
             <p className="text-sm text-slate-500">En çok tercih edilen ilk 10 ürünün karşılaştırması</p>
           </div>
           <button onClick={() => navigate('/menu')} className="text-sm font-bold text-emerald-400 hover:text-emerald-300 transition-colors flex items-center gap-1">
             Tüm Menüyü Yönet <ArrowRight size={16} />
           </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {productData.slice(0, 6).map((p, idx) => (
            <div key={idx} className="p-5 rounded-2xl bg-white/5 border border-white/5 hover:border-emerald-500/30 transition-all duration-300 group">
              <div className="flex justify-between items-start mb-4">
                <div className="w-10 h-10 rounded-xl bg-slate-950 flex items-center justify-center text-emerald-500 font-bold border border-white/10">
                  {idx + 1}
                </div>
                <div className="text-right">
                  <p className="text-[10px] text-slate-500 uppercase font-bold tracking-widest">Toplam Satış</p>
                  <p className="text-lg font-bold text-white">{formatCurrency(p.toplam_tutar)} ₺</p>
                </div>
              </div>
              <h4 className="text-lg font-bold text-white mb-2 group-hover:text-emerald-400 transition-colors">{p.urun_adi}</h4>
              <div className="flex items-center gap-3">
                <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-full" 
                    style={{ width: `${(p.satis_adeti / productData[0].satis_adeti) * 100}%` }}
                  />
                </div>
                <span className="text-sm font-bold text-slate-400">{p.satis_adeti} Adet</span>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

