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
  BadgePercent,
  Gift,
  Users, 
  Sparkles,
  Zap,
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

  const axisColor = '#64748b';

  const stats = useMemo(() => {
    if (!summary) return [];
    const currentPeriodLabel = summary.period_label || PERIOD_LABELS[summaryPeriod];
    const topPersonnel = summary.top_personeller?.[0]?.display_name || 'Veri yok';

    return [
      { key: 'revenue', label: 'Toplam Ciro', value: `${formatCurrency(summary.toplam_ciro)} ₺`, helper: `${currentPeriodLabel} brüt gelir`, icon: DollarSign, color: 'text-emerald-400', bg: 'bg-emerald-500/10', trend: '+12.4%' },
      { key: 'orders', label: 'Sipariş Hacmi', value: summary.siparis_sayisi.toLocaleString('tr-TR'), helper: `${currentPeriodLabel} işlem adeti`, icon: ShoppingCart, color: 'text-blue-400', bg: 'bg-blue-500/10', trend: '+5.2%' },
      { key: 'avg_table', label: 'Sepet Ortalaması', value: `${formatCurrency(summary.ortalama_masa_tutari ?? summary.ortalama_sepet)} ₺`, helper: 'Masa başı harcama', icon: TrendingUp, color: 'text-purple-400', bg: 'bg-purple-500/10', trend: '+2.1%' },
      { key: 'discount', label: 'Uygulanan İskonto', value: `${formatCurrency(summary.toplam_iskonto)} ₺`, helper: 'Müşteri indirimleri', icon: BadgePercent, color: 'text-orange-400', bg: 'bg-orange-500/10', trend: '-1.5%' },
      { key: 'complimentary', label: 'İkram Tutarı', value: `${formatCurrency(summary.toplam_ikram)} ₺`, helper: 'Mutfak maliyetleri', icon: Gift, color: 'text-pink-400', bg: 'bg-pink-500/10', trend: '+0.8%' },
      { key: 'top_product', label: 'Yıldız Ürün', value: summary.en_populer_urun ?? 'Veri yok', helper: 'En çok satan kalem', icon: Package, color: 'text-amber-400', bg: 'bg-amber-500/10', trend: 'Lider' },
      { key: 'top_staff', label: 'Ayın Personeli', value: topPersonnel, helper: 'Satış lideri', icon: Users, color: 'text-indigo-400', bg: 'bg-indigo-500/10', trend: 'Zirve' },
    ];
  }, [summary, summaryPeriod, formatCurrency]);

  if (summaryQuery.isLoading && !summary) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6">
        <div className="relative">
          <div className="w-20 h-20 border-4 border-emerald-500/10 border-t-emerald-500 rounded-full animate-spin" />
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-10 h-10 bg-emerald-500/20 rounded-full animate-pulse" />
          </div>
        </div>
        <div className="text-center space-y-2">
          <h4 className="text-xl font-bold text-white tracking-widest uppercase">Veriler İşleniyor</h4>
          <p className="text-slate-500 animate-pulse">Analitik motoru bağlanıyor...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-10 pb-20 max-w-[1600px] mx-auto px-4 lg:px-8">
      {/* Dynamic Background Ornament */}
      <div className="bg-mesh" />

      {/* Hero Section */}
      <section className="relative overflow-hidden rounded-[40px] glass-panel p-10 md:p-14 group">
        <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-emerald-500/10 blur-[150px] rounded-full -mr-64 -mt-64 group-hover:bg-emerald-500/15 transition-all duration-700" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-cyan-500/10 blur-[120px] rounded-full -ml-32 -mb-32 group-hover:bg-cyan-500/15 transition-all duration-700" />
        
        <div className="relative flex flex-col lg:flex-row lg:items-end justify-between gap-10">
          <div className="space-y-6">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-black uppercase tracking-[0.2em] shadow-inner">
              <Sparkles className="w-3 h-3 animate-pulse" />
              Neso AI Intelligence Center
            </div>
            <h1 className="leading-[1.1]">
              <span className="text-slate-500 font-light block mb-2 text-2xl md:text-3xl">Hoş Geldiniz,</span>
              <span className="text-white font-extrabold">{businessName}</span>
              <span className="text-gradient ml-4">Analitik.</span>
            </h1>
            <p className="text-slate-400 text-lg md:text-xl max-w-2xl font-medium leading-relaxed">
              İşletmenizin geleceğini gerçek zamanlı verilerle şekillendirin. Stratejik büyüme ve operasyonel verimlilik tek panelde.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-center gap-6">
            <div className="flex p-2 bg-slate-950/60 rounded-[24px] border border-white/[0.05] backdrop-blur-2xl shadow-inner">
              {(['gunluk', 'haftalik', 'aylik'] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setSummaryPeriod(p)}
                  className={`px-8 py-3.5 rounded-2xl text-xs font-black uppercase tracking-widest transition-all duration-500 ${summaryPeriod === p ? 'bg-emerald-500 text-slate-950 shadow-2xl shadow-emerald-500/30' : 'text-slate-500 hover:text-white hover:bg-white/5'}`}
                >
                  {PERIOD_LABELS[p]}
                </button>
              ))}
            </div>
            <button onClick={handleRefresh} className="glow-button group shrink-0">
              <Zap className="w-5 h-5 group-hover:scale-125 transition-transform group-hover:rotate-12" />
              YENİLE
            </button>
          </div>
        </div>
      </section>

      {/* Main Stats Grid */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-8">
        {stats.map((s, idx) => (
          <div key={s.key} className="premium-card p-8 group">
             <div className="card-number-glow">0{idx + 1}</div>
             <div className="flex items-start justify-between mb-8">
              <div className={`p-4 rounded-[20px] ${s.bg} ${s.color} transition-all duration-700 group-hover:scale-110 group-active:scale-95 shadow-xl`}>
                <s.icon size={26} strokeWidth={2.5} />
              </div>
              <div className="flex flex-col items-end">
                <span className={`text-xs font-black px-3 py-1 rounded-full ${s.trend.startsWith('+') ? 'bg-emerald-500/10 text-emerald-400' : s.trend.startsWith('-') ? 'bg-rose-500/10 text-rose-400' : 'bg-slate-800 text-slate-400'} border border-white/5`}>
                  {s.trend}
                </span>
                <span className="text-[10px] text-slate-600 font-bold mt-1 uppercase tracking-widest">Trend</span>
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-[11px] font-black text-slate-500 uppercase tracking-[0.15em]">{s.label}</p>
              <h3 className="text-3xl font-bold text-white tracking-tight group-hover:text-emerald-400 transition-colors truncate">{s.value}</h3>
              <div className="flex items-center gap-2 pt-4 border-t border-white/[0.03] mt-4">
                <div className={`w-1 h-1 rounded-full ${s.color.split(' ')[0].replace('text-', 'bg-')}`} />
                <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">{s.helper}</p>
              </div>
            </div>
          </div>
        ))}
      </section>

      {/* Analytics Visualization Cluster */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-10">
        {/* Main Chart Section */}
        <div className="xl:col-span-8 premium-card p-10 rounded-[40px]">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6 mb-12">
            <div>
              <h3 className="text-2xl font-bold text-white flex items-center gap-3">
                <div className="w-2 h-8 bg-emerald-500 rounded-full" />
                Operasyonel Yoğunluk
              </h3>
              <p className="text-slate-500 font-medium mt-1">Saatlik sipariş dağılımı ve gelir performansı</p>
            </div>
            <div className="flex gap-4">
               <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-950/40 border border-white/5">
                 <div className="w-2 h-2 rounded-full bg-emerald-500" />
                 <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Gelir</span>
               </div>
               <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-slate-950/40 border border-white/5">
                 <div className="w-2 h-2 rounded-full bg-blue-500" />
                 <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Sipariş</span>
               </div>
            </div>
          </div>

          <div className="h-[450px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={hourlyData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.02)" vertical={false} />
                <XAxis 
                  dataKey="saat" 
                  stroke={axisColor} 
                  tick={{ fill: axisColor, fontSize: 11, fontWeight: 700 }} 
                  axisLine={false} 
                  tickLine={false}
                  tickFormatter={(v) => formatHour(v)}
                />
                <YAxis hide />
                <Tooltip 
                  cursor={{ stroke: 'rgba(16,185,129,0.2)', strokeWidth: 2 }}
                  contentStyle={{ backgroundColor: '#0f172a', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '24px', padding: '16px' }}
                  itemStyle={{ fontWeight: 800, fontSize: '12px', textTransform: 'uppercase' }}
                />
                <Area type="monotone" dataKey="toplam_tutar" stroke="#10b981" strokeWidth={4} fill="url(#chartGradient)" />
                <Bar dataKey="siparis_sayisi" fill="#3b82f6" radius={[4, 4, 0, 0]} maxBarSize={32} opacity={0.6} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* AI Insight Advisory Panel */}
        <div className="xl:col-span-4 flex flex-col gap-8">
           <div className="premium-card p-10 rounded-[40px] bg-gradient-to-br from-emerald-500/10 via-slate-900 to-indigo-500/10 border-emerald-500/20 group relative overflow-hidden flex-1">
             <div className="absolute top-0 right-0 p-8 opacity-10 scale-150 rotate-12 group-hover:scale-175 transition-transform duration-1000">
               <Sparkles className="text-emerald-400" size={120} />
             </div>

             <div className="relative space-y-8 h-full flex flex-col">
               <div className="space-y-4">
                 <div className="inline-flex items-center gap-3 px-4 py-1.5 rounded-full bg-white/10 border border-white/5 text-white text-[10px] font-black uppercase tracking-[0.2em]">
                   AI ADVISORY ENGINE
                 </div>
                 <h3 className="text-3xl font-extrabold text-white leading-[1.1]">Stratejik <br />Danışmanlık.</h3>
               </div>
               
               <div className="space-y-6 flex-1">
                 <div className="p-6 rounded-[24px] bg-slate-950/60 border border-white/[0.05] hover:border-emerald-500/30 transition-all duration-500">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-8 h-8 rounded-lg bg-emerald-500 text-slate-950 flex items-center justify-center font-black italic">!</div>
                      <p className="text-xs font-black text-emerald-400 uppercase tracking-widest">Verimlilik Analizi</p>
                    </div>
                    <p className="text-sm text-slate-300 font-medium leading-relaxed">
                      Dönem içindeki sipariş sayısı <span className="text-white font-bold">{summary?.siparis_sayisi}</span>. Ortalama sepet tutarı <span className="text-white font-bold">{formatCurrency(summary?.ortalama_sepet || 0)} ₺</span> olarak gerçekleşti.
                    </p>
                 </div>

                 <div className="p-6 rounded-[24px] bg-slate-950/60 border border-white/[0.05] hover:border-amber-500/30 transition-all duration-500">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="w-8 h-8 rounded-lg bg-amber-500 text-slate-950 flex items-center justify-center font-black italic">!</div>
                      <p className="text-xs font-black text-amber-500 uppercase tracking-widest">Trend Ürün</p>
                    </div>
                    <p className="text-sm text-slate-300 font-medium leading-relaxed">
                      <span className="text-white font-bold">{summary?.en_populer_urun || 'Veri yok'}</span> şu an en çok satanlar listesinde. Talebi karşılamak için stokları güncelleyin.
                    </p>
                 </div>
               </div>

               <button className="glow-button w-full">
                  DETAYLI ANALİZ RAPORU
                  <ArrowRight size={20} strokeWidth={3} />
               </button>
             </div>
           </div>
        </div>
      </div>

      {/* Product Intelligence Matrix */}
      <section className="premium-card p-10 rounded-[40px]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-8 mb-12">
           <div className="space-y-2">
             <h3 className="text-3xl font-bold text-white tracking-tight">Ürün Performans Matrisi</h3>
             <p className="text-slate-500 font-medium uppercase text-xs tracking-[0.2em]">En Değerli Ürünlerin Karşılaştırmalı Analizi</p>
           </div>
           <button onClick={() => navigate('/menu')} className="px-6 py-3 rounded-2xl bg-white/5 border border-white/5 text-slate-400 font-bold hover:text-emerald-400 hover:border-emerald-500/30 transition-all">
             KATALOG YÖNETİMİ
           </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {productData.slice(0, 6).map((p, idx) => (
            <div key={idx} className="p-8 rounded-[32px] bg-slate-950/40 border border-white/5 hover:border-emerald-500/30 hover:bg-slate-900/40 transition-all duration-700 group cursor-pointer relative overflow-hidden">
               <div className="absolute top-0 right-0 p-6 opacity-[0.03] group-hover:opacity-10 transition-opacity">
                <Package size={80} strokeWidth={1} />
              </div>
              <div className="flex justify-between items-start mb-6">
                <div className="w-12 h-12 rounded-2xl bg-slate-900 flex items-center justify-center text-emerald-500 font-black text-xl border border-white/5 group-hover:scale-110 transition-transform">
                  {idx + 1}
                </div>
                <div className="text-right">
                  <p className="text-[10px] text-slate-600 uppercase font-black tracking-[0.15em] mb-1">Brüt Satış</p>
                  <p className="text-2xl font-bold text-white group-hover:text-emerald-400 transition-colors tracking-tight">{formatCurrency(p.toplam_tutar)} ₺</p>
                </div>
              </div>
              <h4 className="text-xl font-bold text-white mb-6 truncate">{p.urun_adi}</h4>
              <div className="space-y-3">
                <div className="flex justify-between text-[10px] font-black uppercase tracking-widest text-slate-500">
                  <span>Satış Hacmi</span>
                  <span>{p.satis_adeti} ADET</span>
                </div>
                <div className="h-2 bg-slate-900 rounded-full overflow-hidden border border-white/[0.03]">
                  <div 
                    className="h-full bg-gradient-to-r from-emerald-500 via-emerald-400 to-cyan-500 rounded-full transition-all duration-1000" 
                    style={{ width: `${(p.satis_adeti / productData[0].satis_adeti) * 100}%` }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

