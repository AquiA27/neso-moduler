import { useEffect, useState, useCallback } from 'react';
import { mutfakApi, normalizeApiUrl } from '../lib/api';
import { Clock, CheckCircle, Wifi, WifiOff, AlertTriangle, Play, Check, BarChart3 } from 'lucide-react';
import { useWebSocket } from '../hooks/useWebSocket';

interface KitchenOrderItem {
  urun?: string;
  ad?: string;
  adet?: number;
  miktar?: number;
  fiyat?: number;
  toplam?: number;
  varyasyon?: string;
  [key: string]: unknown;
}

interface KitchenOrder {
  id: number;
  masa: string;
  sepet: KitchenOrderItem[];
  durum: string;
  tutar: number;
  created_at: string;
  started_at?: string;
  hazir_at?: string;
}

interface KitchenStats {
  total_orders: number;
  ready_orders: number;
  in_prep_orders: number;
  new_orders: number;
  avg_prep_time_minutes: number;
}

export default function MutfakPage() {
  const [orders, setOrders] = useState<KitchenOrder[]>([]);
  const [stats, setStats] = useState<KitchenStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'yeni' | 'hazirlaniyor' | 'hazir' | 'tumu'>('tumu');
  const [currentTime, setCurrentTime] = useState(new Date());

  // Timer refresh
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 10000); // Her 10sn'de bir
    return () => clearInterval(timer);
  }, []);
  
  const loadOrders = useCallback(async () => {
    try {
      const durum = filter === 'tumu' ? 'tumu' : filter;
      const response = await mutfakApi.kuyruk({ limit: 50, durum });
      setOrders(response.data || []);
    } catch (err) {
      console.error('Mutfak kuyruğu yüklenemedi:', err);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  const loadStats = useCallback(async () => {
    try {
      const response = await mutfakApi.stats();
      setStats(response.data);
    } catch (err) {
      console.error('Mutfak istatistikleri yüklenemedi:', err);
    }
  }, []);
  
  const API_BASE_URL = normalizeApiUrl(import.meta.env.VITE_API_URL as string);
  const WS_URL = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://') + '/ws/connect/auth';
  
  const ws = useWebSocket({
    url: WS_URL,
    topics: ['kitchen', 'orders'],
    auth: true,
    onMessage: (data) => {
      if (['new_order', 'order_added', 'order_update', 'status_change'].includes(data.type)) {
        loadOrders();
        loadStats();
      }
    },
  });

  useEffect(() => {
    loadOrders();
    loadStats();
  }, [loadOrders, loadStats]);

  const handleStatusChange = async (id: number, newStatus: string) => {
    try {
      await mutfakApi.updateStatus(id, newStatus);
      loadOrders();
      loadStats();
    } catch (err) {
      console.error('Durum güncellenemedi:', err);
    }
  };

  const getWaitTime = (createdAt: string) => {
    const start = new Date(createdAt);
    const diff = Math.floor((currentTime.getTime() - start.getTime()) / 60000);
    return diff;
  };

  const getPrepTime = (startedAt: string, hazirAt: string) => {
    const start = new Date(startedAt);
    const end = new Date(hazirAt);
    return Math.floor((end.getTime() - start.getTime()) / 60000);
  };

  const getCardStyle = (order: KitchenOrder) => {
    if (order.durum === 'hazir') return 'border-emerald-500/30 bg-emerald-500/5';
    
    const waitTime = getWaitTime(order.created_at);
    if (waitTime >= 20) return 'border-rose-500/50 bg-rose-500/10 animate-pulse';
    if (waitTime >= 10) return 'border-amber-500/40 bg-amber-500/5';
    
    return 'border-white/10 bg-white/5';
  };

  const filteredOrders = filter === 'tumu' 
    ? orders 
    : orders.filter((o) => o.durum === filter);

  return (
    <div className="space-y-8 pb-10">
      {/* Metrics Header */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="glass-card p-6 rounded-3xl border border-white/5 flex items-center gap-4">
          <div className="p-3 rounded-2xl bg-blue-500/10 text-blue-400">
            <Clock size={24} />
          </div>
          <div>
            <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">Bekleyen</p>
            <p className="text-2xl font-black text-white">{stats?.new_orders || 0}</p>
          </div>
        </div>
        <div className="glass-card p-6 rounded-3xl border border-white/5 flex items-center gap-4">
          <div className="p-3 rounded-2xl bg-amber-500/10 text-amber-400">
            <Play size={24} />
          </div>
          <div>
            <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">Hazırlanıyor</p>
            <p className="text-2xl font-black text-white">{stats?.in_prep_orders || 0}</p>
          </div>
        </div>
        <div className="glass-card p-6 rounded-3xl border border-white/5 flex items-center gap-4">
          <div className="p-3 rounded-2xl bg-emerald-500/10 text-emerald-400">
            <Check size={24} />
          </div>
          <div>
            <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">Tamamlanan (24s)</p>
            <p className="text-2xl font-black text-white">{stats?.ready_orders || 0}</p>
          </div>
        </div>
        <div className="glass-card p-6 rounded-3xl border border-white/5 flex items-center gap-4">
          <div className="p-3 rounded-2xl bg-purple-500/10 text-purple-400">
            <BarChart3 size={24} />
          </div>
          <div>
            <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">Ort. Hazırlama</p>
            <p className="text-2xl font-black text-white">{stats?.avg_prep_time_minutes ? `${Math.round(stats.avg_prep_time_minutes)} dk` : '-'}</p>
          </div>
        </div>
      </div>

      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <h2 className="text-4xl font-black tracking-tight text-white italic">MUTFAK KDS</h2>
          {ws.connected ? (
            <div className="flex items-center gap-2 px-3 py-1 bg-emerald-500/10 text-emerald-400 rounded-full border border-emerald-500/20">
              <Wifi size={14} />
              <span className="text-[10px] font-black uppercase tracking-widest">CANLI</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 px-3 py-1 bg-rose-500/10 text-rose-400 rounded-full border border-rose-500/20">
              <WifiOff size={14} />
              <span className="text-[10px] font-black uppercase tracking-widest">BAĞLANTI YOK</span>
            </div>
          )}
        </div>

        <div className="flex bg-slate-900/80 p-1 rounded-2xl border border-white/5">
          {['tumu', 'yeni', 'hazirlaniyor', 'hazir'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f as any)}
              className={`px-6 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all ${
                filter === f 
                  ? 'bg-white/10 text-white shadow-lg' 
                  : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              {f === 'tumu' ? 'Tümü' : f === 'hazirlaniyor' ? 'Hazırlanıyor' : f}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="h-64 flex items-center justify-center">
          <RefreshCw className="w-10 h-10 animate-spin text-slate-700" />
        </div>
      ) : filteredOrders.length === 0 ? (
        <div className="h-64 flex flex-col items-center justify-center gap-4 bg-white/[0.02] border border-dashed border-white/10 rounded-[3rem]">
          <CheckCircle size={48} className="text-slate-800" />
          <p className="text-slate-500 font-bold uppercase tracking-widest text-sm">Aktif sipariş bulunmuyor</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-6">
          {filteredOrders.map((order) => {
            const waitTime = getWaitTime(order.created_at);
            const isLate = waitTime >= 15;
            
            return (
              <div
                key={order.id}
                className={`flex flex-col rounded-[2.5rem] border transition-all duration-500 ${getCardStyle(order)}`}
              >
                {/* Card Header */}
                <div className="p-6 pb-4 flex items-start justify-between">
                  <div>
                    <h3 className="text-2xl font-black text-white italic">Masa {order.masa}</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <Clock size={12} className="text-slate-500" />
                      <span className="text-[10px] font-bold text-slate-500 uppercase">
                        {new Date(order.created_at).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  </div>
                  
                  <div className="flex flex-col items-end gap-2">
                    {order.durum !== 'hazir' && (
                      <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border ${
                        isLate ? 'bg-rose-500/20 border-rose-500/30 text-rose-400' : 'bg-white/5 border-white/10 text-white'
                      }`}>
                        {isLate && <AlertTriangle size={14} className="animate-bounce" />}
                        <span className="text-lg font-black tracking-tighter">{waitTime}</span>
                        <span className="text-[10px] font-black uppercase">DK</span>
                      </div>
                    )}
                    {order.durum === 'hazir' && order.started_at && order.hazir_at && (
                      <div className="px-3 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                         <span className="text-xs font-black uppercase tracking-tighter">{getPrepTime(order.started_at, order.hazir_at)} DK HAZIRLANDI</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Card Content - Items */}
                <div className="flex-1 px-6 py-4 space-y-3">
                  {order.sepet.map((item, idx) => (
                    <div key={idx} className="flex items-start justify-between group">
                      <div className="flex gap-3">
                        <div className="w-6 h-6 rounded-lg bg-white/5 flex items-center justify-center text-xs font-black text-white shrink-0">
                          {item.adet || item.miktar || 1}
                        </div>
                        <div className="flex flex-col">
                          <span className="text-sm font-bold text-slate-200 group-hover:text-white transition-colors uppercase">
                            {item.urun || item.ad}
                          </span>
                          {item.varyasyon && (
                            <span className="text-[10px] font-black text-amber-500/80 uppercase tracking-widest mt-0.5">
                              {item.varyasyon}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Card Footer - Actions */}
                <div className="p-4 border-t border-white/5 mt-auto">
                  {order.durum === 'yeni' && (
                    <button
                      onClick={() => handleStatusChange(order.id, 'hazirlaniyor')}
                      className="w-full flex items-center justify-center gap-2 py-4 bg-blue-500 text-white rounded-[1.5rem] font-black text-xs uppercase tracking-[0.2em] shadow-lg shadow-blue-500/20 hover:scale-[1.02] active:scale-95 transition-all"
                    >
                      <Play size={16} fill="currentColor" />
                      HAZIRLIĞA BAŞLA
                    </button>
                  )}
                  {order.durum === 'hazirlaniyor' && (
                    <button
                      onClick={() => handleStatusChange(order.id, 'hazir')}
                      className="w-full flex items-center justify-center gap-2 py-4 bg-emerald-500 text-white rounded-[1.5rem] font-black text-xs uppercase tracking-[0.2em] shadow-lg shadow-emerald-500/20 hover:scale-[1.02] active:scale-95 transition-all"
                    >
                      <CheckCircle size={16} />
                      TAMAMLANDI
                    </button>
                  )}
                  {order.durum === 'hazir' && (
                    <div className="py-4 flex items-center justify-center gap-2 text-emerald-500/60 font-black text-[10px] uppercase tracking-widest">
                      <Check size={14} />
                      TESLİME HAZIR
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
