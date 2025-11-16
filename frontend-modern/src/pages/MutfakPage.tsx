import { useEffect, useState, useCallback } from 'react';
import { mutfakApi } from '../lib/api';
import { Clock, CheckCircle, Wifi, WifiOff } from 'lucide-react';
import { useWebSocket } from '../hooks/useWebSocket';

interface KitchenOrderItem {
  urun?: string;
  ad?: string;
  adet?: number;
  miktar?: number;
  fiyat?: number;
  toplam?: number;
  [key: string]: unknown;
}

interface KitchenOrder {
  id: number;
  masa: string;
  sepet: KitchenOrderItem[];
  durum: string;
  tutar: number;
  created_at: string;
}

export default function MutfakPage() {
  const [orders, setOrders] = useState<KitchenOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'yeni' | 'hazirlaniyor' | 'hazir' | 'tumu'>('tumu');
  
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
  
  const API_BASE_URL = (import.meta.env?.VITE_API_URL as string) || 'http://localhost:8000';
  const WS_URL = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://') + '/ws/connect/auth';
  
  // WebSocket connection
  const ws = useWebSocket({
    url: WS_URL,
    topics: ['kitchen', 'orders'],
    auth: true,
    onMessage: (data) => {
      console.log('WebSocket message:', data);
      if (data.type === 'new_order' || data.type === 'order_added' || data.type === 'order_update' || data.type === 'status_change') {
        loadOrders();
      }
    },
    onConnect: () => {
      console.log('WebSocket connected to kitchen');
    },
    onDisconnect: () => {
      console.log('WebSocket disconnected from kitchen');
    },
  });

  useEffect(() => {
    loadOrders();
    // WebSocket ile artık polling'e ihtiyacımız yok, sadece ilk yüklemede
  }, [loadOrders]);

  const handleStatusChange = async (id: number, newStatus: string) => {
    try {
      await mutfakApi.updateStatus(id, newStatus);
      loadOrders();
    } catch (err) {
      console.error('Durum güncellenemedi:', err);
      alert('Hata: Durum güncellenemedi');
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleTimeString('tr-TR', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getStatusColor = (durum: string) => {
    switch (durum) {
      case 'yeni':
        return 'bg-yellow-500/20 border-yellow-500/50 text-yellow-300';
      case 'hazirlaniyor':
        return 'bg-blue-500/20 border-blue-500/50 text-blue-300';
      case 'hazir':
        return 'bg-green-500/20 border-green-500/50 text-green-300';
      default:
        return 'bg-gray-500/20 border-gray-500/50';
    }
  };

  const filteredOrders = filter === 'tumu' 
    ? orders 
    : orders.filter((o) => o.durum === filter);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="text-3xl font-bold">Mutfak Kuyruğu</h2>
          {ws.connected ? (
            <div className="flex items-center gap-2 text-green-300">
              <Wifi className="w-4 h-4" />
              <span className="text-sm">Canlı</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-red-300">
              <WifiOff className="w-4 h-4" />
              <span className="text-sm">Bağlantı Yok</span>
            </div>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setFilter('tumu')}
            className={`px-4 py-2 rounded-lg transition-colors ${
              filter === 'tumu'
                ? 'bg-primary-600 text-white'
                : 'bg-white/10 hover:bg-white/20'
            }`}
          >
            Tümü
          </button>
          <button
            onClick={() => setFilter('yeni')}
            className={`px-4 py-2 rounded-lg transition-colors ${
              filter === 'yeni'
                ? 'bg-primary-600 text-white'
                : 'bg-white/10 hover:bg-white/20'
            }`}
          >
            Yeni
          </button>
          <button
            onClick={() => setFilter('hazirlaniyor')}
            className={`px-4 py-2 rounded-lg transition-colors ${
              filter === 'hazirlaniyor'
                ? 'bg-primary-600 text-white'
                : 'bg-white/10 hover:bg-white/20'
            }`}
          >
            Hazırlanıyor
          </button>
          <button
            onClick={() => setFilter('hazir')}
            className={`px-4 py-2 rounded-lg transition-colors ${
              filter === 'hazir'
                ? 'bg-primary-600 text-white'
                : 'bg-white/10 hover:bg-white/20'
            }`}
          >
            Hazır
          </button>
        </div>
      </div>

      {loading ? (
        <div className="card text-center py-12">
          <div className="text-white/50">Yükleniyor...</div>
        </div>
      ) : filteredOrders.length === 0 ? (
        <div className="card text-center py-12">
          <div className="text-white/50">Sipariş bulunamadı.</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredOrders.map((order) => (
            <div
              key={order.id}
              className={`card border-2 ${getStatusColor(order.durum)}`}
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="font-bold text-lg">Masa {order.masa}</h3>
                  <p className="text-sm text-white/70">
                    {formatDate(order.created_at)}
                  </p>
                </div>
                <span className={`px-2 py-1 rounded text-xs ${getStatusColor(order.durum)}`}>
                  {order.durum}
                </span>
              </div>

              <div className="space-y-2 mb-4">
                {Array.isArray(order.sepet) && order.sepet.length > 0 ? (
                  order.sepet.map((item, idx) => {
                    const quantityRaw = item.adet ?? item.miktar ?? 1;
                    const quantity = Number.isFinite(quantityRaw)
                      ? Number(quantityRaw)
                      : 1;
                    const unitPriceRaw =
                      item.fiyat ?? (item.toplam && quantity ? item.toplam / quantity : undefined);
                    const unitPrice = Number.isFinite(unitPriceRaw)
                      ? Number(unitPriceRaw)
                      : 0;
                    const lineTotalRaw = item.toplam ?? unitPrice * quantity;
                    const lineTotal = Number.isFinite(lineTotalRaw)
                      ? Number(lineTotalRaw)
                      : unitPrice * quantity;

                    return (
                      <div key={idx} className="flex justify-between text-sm">
                        <span>
                          {quantity}x {String(item.urun || item.ad || 'Ürün')}
                          {item.varyasyon ? (
                            <span className="ml-2 text-yellow-300">({String(item.varyasyon)})</span>
                          ) : null}
                        </span>
                        <span className="text-white/70">
                          {lineTotal.toFixed(2)} ₺
                        </span>
                      </div>
                    );
                  })
                ) : (
                  <div className="text-sm text-white/50">Sipariş detayı yok</div>
                )}
              </div>

              <div className="flex items-center justify-between pt-4 border-t border-white/10">
                <div className="font-bold">
                  Toplam: {order.tutar?.toFixed(2) || '0.00'} ₺
                </div>
                <div className="flex gap-2">
                  {order.durum === 'yeni' && (
                    <button
                      onClick={() => handleStatusChange(order.id, 'hazirlaniyor')}
                      className="px-3 py-1 bg-blue-500/20 hover:bg-blue-500/30 rounded text-sm flex items-center gap-1"
                    >
                      <Clock className="w-4 h-4" />
                      Başlat
                    </button>
                  )}
                  {order.durum === 'hazirlaniyor' && (
                    <button
                      onClick={() => handleStatusChange(order.id, 'hazir')}
                      className="px-3 py-1 bg-green-500/20 hover:bg-green-500/30 rounded text-sm flex items-center gap-1"
                    >
                      <CheckCircle className="w-4 h-4" />
                      Hazır
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

