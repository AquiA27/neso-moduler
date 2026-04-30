import { useState, useEffect } from 'react';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  BarChart, Bar, Cell
} from 'recharts';
import { 
  Brain, TrendingUp, ShoppingBag, Target, Info, RefreshCw, 
  ArrowUpRight, ArrowDownRight, Zap, Sparkles
} from 'lucide-react';
import apiClient from '../lib/api';

const COLORS = ['#10b881', '#0ea5e9', '#f59e0b', '#8b5cf6', '#ec4899', '#ef4444'];

export default function PredictiveAnalyticsPage() {
  const [loading, setLoading] = useState(true);
  const [forecast, setForecast] = useState<any[]>([]);
  const [affinity, setAffinity] = useState<any[]>([]);
  const [optimization, setOptimization] = useState<any[]>([]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [forecastRes, affinityRes, optimRes] = await Promise.all([
        apiClient.get('/analytics/predictive/demand-forecast'),
        apiClient.get('/analytics/predictive/product-affinity'),
        apiClient.get('/analytics/predictive/menu-optimization')
      ]);
      setForecast(forecastRes.data);
      setAffinity(affinityRes.data);
      setOptimization(optimRes.data);
    } catch (error) {
      console.error('Veriler yüklenirken hata oluştu:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col h-[80vh] items-center justify-center gap-4">
        <RefreshCw className="h-10 w-10 animate-spin text-emerald-500" />
        <p className="text-slate-400 font-medium animate-pulse">Yapay Zeka Verileri Analiz Ediyor...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12 animate-in fade-in duration-700">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
             <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-500">
                <Brain size={24} />
             </div>
             <h2 className="text-3xl font-black tracking-tight text-white italic">AKILLI ANALİTİK</h2>
          </div>
          <p className="text-slate-400 font-medium">Yapay zeka destekli tahminleme ve işletme optimizasyonu</p>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-2 px-6 py-3 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 rounded-2xl transition-all font-bold tracking-tight"
        >
          <RefreshCw className="h-4 w-4" />
          Yeniden Analiz Et
        </button>
      </div>

      {/* Grid: Forecast and Affinity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        
        {/* Demand Forecast Section */}
        <div className="glass-card p-8 rounded-[2.5rem] relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:opacity-20 transition-opacity">
            <TrendingUp size={80} />
          </div>
          <h3 className="text-xl font-bold text-white mb-6 flex items-center gap-3">
            <Zap className="text-amber-400" size={20} />
            7 Günlük Satış Tahmini
          </h3>
          
          <div className="space-y-6">
            {forecast.slice(0, 5).map((item, idx) => (
              <div key={idx} className="p-5 rounded-3xl bg-white/[0.03] border border-white/5 hover:border-emerald-500/20 transition-all">
                <div className="flex items-center justify-between mb-4">
                  <span className="font-bold text-white tracking-tight">{item.urun}</span>
                  <div className={`px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest
                    ${item.stock_status === 'yeterli' ? 'bg-emerald-500/10 text-emerald-400' : 
                      item.stock_status === 'riskli' ? 'bg-amber-500/10 text-amber-400' : 
                      'bg-rose-500/10 text-rose-400'}
                  `}>
                    Stok: {item.stock_status}
                  </div>
                </div>
                
                <div className="h-24 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={item.forecast}>
                      <Tooltip 
                        contentStyle={{ backgroundColor: '#0f172a', border: 'none', borderRadius: '12px', fontSize: '12px' }}
                        itemStyle={{ color: '#10b881' }}
                      />
                      <Line 
                        type="monotone" 
                        dataKey="predicted_sales" 
                        stroke="#10b881" 
                        strokeWidth={3} 
                        dot={false}
                        animationDuration={2000}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <div className="mt-2 text-right">
                  <span className="text-xs text-slate-500 font-bold uppercase tracking-widest">Beklenen Toplam:</span>
                  <span className="ml-2 text-lg font-black text-white">{item.total_predicted_7d} Adet</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Product Affinity Section */}
        <div className="glass-card p-8 rounded-[2.5rem] relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:opacity-20 transition-opacity">
            <ShoppingBag size={80} />
          </div>
          <h3 className="text-xl font-bold text-white mb-6 flex items-center gap-3">
            <Sparkles className="text-purple-400" size={20} />
            Akıllı Sepet Birliktelikleri
          </h3>
          
          <div className="space-y-4">
            {affinity.map((pair, idx) => (
              <div key={idx} className="relative p-6 rounded-3xl bg-gradient-to-br from-white/[0.03] to-transparent border border-white/5 overflow-hidden group/item">
                <div className="absolute right-0 top-0 h-full w-1 bg-emerald-500/40" style={{ height: `${pair.correlation_score * 100}%` }} />
                
                <div className="flex items-center justify-between relative z-10">
                  <div className="flex items-center gap-3">
                    <div className="flex flex-col">
                      <span className="text-sm font-bold text-white">{pair.product_a}</span>
                      <span className="text-[10px] text-slate-500 font-bold uppercase">ve</span>
                      <span className="text-sm font-bold text-white">{pair.product_b}</span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-black text-emerald-400">{Math.round(pair.correlation_score * 100)}%</div>
                    <div className="text-[10px] text-slate-500 font-bold uppercase tracking-tighter">Korelasyon Skoru</div>
                  </div>
                </div>
                
                <div className="mt-4 flex items-center gap-2">
                  <div className="h-1 flex-1 bg-white/5 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-gradient-to-r from-emerald-500 to-cyan-500 transition-all duration-1000" 
                      style={{ width: `${pair.correlation_score * 100}%` }} 
                    />
                  </div>
                  <span className="text-[10px] text-slate-400 font-bold whitespace-nowrap">{pair.co_occurrence_count} Ortak Satış</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Menu Optimization Section */}
      <div className="glass-card p-10 rounded-[3rem]">
        <div className="flex items-center gap-3 mb-8">
          <Target className="text-rose-500" size={28} />
          <h3 className="text-2xl font-black text-white italic tracking-tight">MENÜ OPTİMİZASYON STRATEJİSİ</h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {optimization.map((item, idx) => (
            <div key={idx} className="p-6 rounded-[2rem] bg-white/[0.02] border border-white/5 hover:bg-white/[0.04] transition-all flex flex-col h-full">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h4 className="font-black text-lg text-white leading-tight uppercase">{item.urun}</h4>
                  <span className="text-xs text-slate-500 font-bold uppercase tracking-widest">{item.kategori}</span>
                </div>
                <div className={`px-4 py-1.5 rounded-2xl text-[10px] font-black uppercase tracking-[0.2em]
                  ${item.tip === 'hero' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/20' : 
                    item.tip === 'sleeping' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/20' : 
                    item.tip === 'underperformer' ? 'bg-rose-500/20 text-rose-400 border border-rose-500/20' : 
                    'bg-slate-500/10 text-slate-400 border border-white/5'}
                `}>
                  {item.tip === 'hero' ? '⭐ YILDIZ' : 
                   item.tip === 'sleeping' ? '💤 UYUYAN' : 
                   item.tip === 'underperformer' ? '⚠️ RİSKLİ' : 'STANDART'}
                </div>
              </div>

              <p className="text-sm text-slate-400 font-medium mb-6 flex-1 italic leading-relaxed">
                "{item.oneri}"
              </p>

              <div className="grid grid-cols-2 gap-4 mt-auto">
                <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/5">
                  <div className="text-[10px] text-slate-500 font-black uppercase mb-1">Kar Marjı</div>
                  <div className={`text-xl font-black ${item.metrikler.kar_marji > 40 ? 'text-emerald-400' : 'text-white'}`}>
                    %{item.metrikler.kar_marji}
                  </div>
                </div>
                <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/5">
                  <div className="text-[10px] text-slate-500 font-black uppercase mb-1">Aylık Satış</div>
                  <div className="text-xl font-black text-white">
                    {item.metrikler.adet} <span className="text-[10px] font-bold text-slate-600">ADET</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Info Banner */}
      <div className="p-6 rounded-[2rem] bg-gradient-to-r from-emerald-500/10 via-cyan-500/5 to-transparent border border-emerald-500/10 flex items-center gap-4">
        <div className="p-3 rounded-2xl bg-emerald-500/20 text-emerald-500">
          <Info size={20} />
        </div>
        <p className="text-sm text-slate-300 font-medium leading-relaxed">
          <strong className="text-emerald-400">Not:</strong> Bu analizler son 60 günlük gerçek işletme verileriniz kullanılarak yapay zeka algoritmaları tarafından oluşturulmuştur. Tahminlerin doğruluğu veri hacmi arttıkça yükselecektir.
        </p>
      </div>
    </div>
  );
}
