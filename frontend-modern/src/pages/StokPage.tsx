import { useEffect, useState, useCallback } from 'react';
import { stokApi } from '../lib/api';
import { useWebSocket } from '../hooks/useWebSocket';
import { Plus, Edit, Trash2, AlertTriangle } from 'lucide-react';

interface StokItem {
  id: number;
  ad: string;
  kategori: string;
  birim: string;
  mevcut: number;
  min: number;
  alis_fiyat: number;
}

interface StokAlert {
  id: number;
  ad: string;
  kategori: string;
  birim: string;
  mevcut: number;
  min: number;
  durum: 'kritik' | 'tukendi';
}

export default function StokPage() {
  const [stokItems, setStokItems] = useState<StokItem[]>([]);
  const [alerts, setAlerts] = useState<StokAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<StokItem | null>(null);
  const [addingStock, setAddingStock] = useState(false);
  const [selectedStock, setSelectedStock] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('Tümü');
  const [showAlerts, setShowAlerts] = useState(true);
  const [formData, setFormData] = useState({
    ad: '',
    kategori: '',
    birim: '',
    mevcut: '',
    min: '',
    alis_fiyat: '',
  });

  const loadAlerts = useCallback(async () => {
    try {
      const response = await stokApi.alerts();
      setAlerts(response.data || []);
    } catch (err) {
      console.error('Stok uyarıları yüklenemedi:', err);
    }
  }, []);

  const loadStok = useCallback(async () => {
    try {
      const response = await stokApi.list({ limit: 200 });
      setStokItems(response.data || []);
    } catch (err) {
      console.error('Stok yüklenemedi:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const getStockStatus = (mevcut: number, min: number) => {
    if (mevcut <= 0) return { text: 'Tükendi', color: 'bg-red-500/20 text-red-300 border-red-500/30' };
    if (mevcut <= min) return { text: 'Kritik', color: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30' };
    return { text: 'Normal', color: 'bg-green-500/20 text-green-300 border-green-500/30' };
  };

  // WebSocket message handler
  const handleWebSocketMessage = useCallback((data: any) => {
    if (data.type === 'stock_alert') {
      // Yeni uyarı geldi, uyarıları yeniden yükle
      loadAlerts();
      // Stok listesini de güncelle
      loadStok();
      
      // Tarayıcı bildirimi göster (eğer izin verildiyse)
      if ('Notification' in window && Notification.permission === 'granted') {
        const durumText = data.item.durum === 'tukendi' ? 'Tükendi' : 'Kritik Seviye';
        new Notification(`Stok Uyarısı: ${data.item.ad}`, {
          body: `${data.item.ad} - ${durumText} (Mevcut: ${data.item.mevcut} ${data.item.birim})`,
          icon: '/favicon.ico',
        });
      }
    }
  }, [loadAlerts, loadStok]);

  useEffect(() => {
    loadStok();
    loadAlerts();
    
    // Bildirim izni iste
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, []);

  // WebSocket connection for real-time stock alerts
  const API_BASE_URL = (import.meta.env?.VITE_API_URL as string) || 'http://localhost:8000';
  const WS_URL = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://') + '/ws/connect/auth';
  
  useWebSocket({
    url: WS_URL,
    topics: ['stock'],
    auth: true,
    onMessage: handleWebSocketMessage,
    onConnect: () => {
      console.log('WebSocket connected to stock alerts');
    },
    onDisconnect: () => {
      console.log('WebSocket disconnected from stock alerts');
    },
  });


  const categories = ['Tümü', ...Array.from(new Set(stokItems.map(item => item.kategori)))];

  const filteredItems = selectedCategory === 'Tümü'
    ? stokItems
    : stokItems.filter(item => item.kategori === selectedCategory);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editing) {
        // Güncelleme: sadece bilgileri güncelle
        await stokApi.update(editing.ad, {
          yeni_ad: formData.ad !== editing.ad ? formData.ad : undefined,
          kategori: formData.kategori,
          birim: formData.birim,
          mevcut: parseFloat(formData.mevcut),
          min: parseFloat(formData.min),
          alis_fiyat: parseFloat(formData.alis_fiyat),
        });
      } else if (addingStock) {
        // Mevcut stoka ekle: miktar ve maliyet verilirse ağırlıklı ortalama
        if (!selectedStock) {
          alert('Lütfen bir stok seçin');
          return;
        }
        await stokApi.update(selectedStock, {
          mevcut: parseFloat(formData.mevcut),
          alis_fiyat: parseFloat(formData.alis_fiyat),
        });
      } else {
        // Yeni stok kalemi ekle
        await stokApi.add({
          ad: formData.ad,
          kategori: formData.kategori,
          birim: formData.birim,
          mevcut: parseFloat(formData.mevcut),
          min: parseFloat(formData.min),
          alis_fiyat: parseFloat(formData.alis_fiyat),
        });
      }
      resetForm();
      await loadStok();
    } catch (err) {
      console.error('Stok kaydedilemedi:', err);
      alert('Hata: Stok kaydedilemedi');
    }
  };

  const handleEdit = (item: StokItem) => {
    setEditing(item);
    setFormData({
      ad: item.ad,
      kategori: item.kategori,
      birim: item.birim,
      mevcut: String(item.mevcut),
      min: String(item.min),
      alis_fiyat: String(item.alis_fiyat),
    });
  };

  const resetForm = () => {
    setEditing(null);
    setAddingStock(false);
    setSelectedStock('');
    setFormData({
      ad: '',
      kategori: '',
      birim: '',
      mevcut: '',
      min: '',
      alis_fiyat: '',
    });
  };

  const handleDelete = async (ad: string) => {
    if (!confirm(`"${ad}" stokunu silmek istediğinizden emin misiniz?`)) {
      return;
    }
    try {
      await stokApi.delete(ad);
      loadStok();
    } catch (err) {
      console.error('Stok silinemedi:', err);
      alert('Hata: Stok silinemedi');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold">Stok Yönetimi</h2>
        <button
          onClick={loadStok}
          className="px-4 py-2 bg-primary-900/40 hover:bg-primary-800/40 rounded-lg transition-colors text-accent-mist"
        >
          Yenile
        </button>
      </div>

      {/* Stok Uyarıları */}
      {alerts.length > 0 && showAlerts && (
        <div className="card border-l-4 border-yellow-500">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-yellow-500" />
              <h3 className="text-xl font-semibold">Stok Uyarıları ({alerts.length})</h3>
            </div>
            <button
              onClick={() => setShowAlerts(false)}
              className="text-white/50 hover:text-white"
            >
              ✕
            </button>
          </div>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                className={`p-3 rounded-lg border ${
                  alert.durum === 'tukendi'
                    ? 'bg-red-500/10 border-red-500/30'
                    : 'bg-yellow-500/10 border-yellow-500/30'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-semibold">{alert.ad}</div>
                    <div className="text-sm text-white/70">
                      {alert.kategori} • Mevcut: {alert.mevcut} {alert.birim} • Min: {alert.min} {alert.birim}
                    </div>
                  </div>
                  <span
                    className={`px-2 py-1 rounded text-xs font-semibold ${
                      alert.durum === 'tukendi'
                        ? 'bg-red-500/20 text-red-300'
                        : 'bg-yellow-500/20 text-yellow-300'
                    }`}
                  >
                    {alert.durum === 'tukendi' ? 'Tükendi' : 'Kritik'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Form */}
      <div className="card">
        <h3 className="text-xl font-semibold mb-4">
          {editing ? 'Stok Güncelle' : addingStock ? 'Mevcut Stoka Ekle' : 'Yeni Stok Kalemi Ekle'}
        </h3>
        
        {/* Stok Ekle/Güncelle Modu Seçimi */}
        {!editing && !addingStock && (
          <div className="mb-4 flex gap-2">
            <button
              type="button"
              onClick={() => {
                setAddingStock(false);
                setEditing(null);
                setSelectedStock('');
                setFormData({
                  ad: '',
                  kategori: '',
                  birim: '',
                  mevcut: '',
                  min: '',
                  alis_fiyat: '',
                });
              }}
              className="px-4 py-2 bg-primary-600/50 hover:bg-primary-600 rounded-lg transition-colors text-accent-mist"
            >
              Yeni Kalem
            </button>
            <button
              type="button"
              onClick={() => {
                setAddingStock(true);
                setEditing(null);
                setSelectedStock('');
                setFormData({
                  ad: '',
                  kategori: '',
                  birim: '',
                  mevcut: '',
                  min: '',
                  alis_fiyat: '',
                });
              }}
              className="px-4 py-2 bg-primary-900/40 hover:bg-primary-800/40 rounded-lg transition-colors text-accent-mist"
            >
              Mevcut Stoka Ekle
            </button>
          </div>
        )}
        
        <form onSubmit={handleSubmit} className="space-y-4">
          {addingStock ? (
            // Mevcut Stoka Ekleme Modu
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">Stok Seç</label>
                <select
                  value={selectedStock}
                  onChange={(e) => setSelectedStock(e.target.value)}
                  required
                  className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist"
                >
                  <option value="">Stok seçin...</option>
                  {stokItems.map(item => (
                    <option key={item.id} value={item.ad}>
                      {item.ad} ({item.mevcut} {item.birim})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Eklenecek Miktar</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={formData.mevcut}
                  onChange={(e) => setFormData({ ...formData, mevcut: e.target.value })}
                  required
                  className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
                  placeholder="0"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Son Alış Fiyatı (TL)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={formData.alis_fiyat}
                  onChange={(e) => setFormData({ ...formData, alis_fiyat: e.target.value })}
                  required
                  className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
                  placeholder="0.00"
                />
              </div>
            </div>
          ) : (
            // Yeni Kalem Ekleme veya Güncelleme Modu
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">Stok Adı</label>
                <input
                  type="text"
                  value={formData.ad}
                  onChange={(e) => setFormData({ ...formData, ad: e.target.value })}
                  required={editing === null}
                  disabled={editing !== null}
                  className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors disabled:opacity-50"
                  placeholder="Örn: Kola"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Kategori</label>
                <input
                  type="text"
                  value={formData.kategori}
                  onChange={(e) => setFormData({ ...formData, kategori: e.target.value })}
                  required
                  className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
                  placeholder="Örn: İçecek"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Birim</label>
                <input
                  type="text"
                  value={formData.birim}
                  onChange={(e) => setFormData({ ...formData, birim: e.target.value })}
                  required
                  className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
                  placeholder="Örn: adet, kg, lt"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Mevcut Miktar</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={formData.mevcut}
                  onChange={(e) => setFormData({ ...formData, mevcut: e.target.value })}
                  required
                  className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
                  placeholder="0"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Minimum Stok</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={formData.min}
                  onChange={(e) => setFormData({ ...formData, min: e.target.value })}
                  required
                  className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
                  placeholder="0"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Maliyet (TL)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={formData.alis_fiyat}
                  onChange={(e) => setFormData({ ...formData, alis_fiyat: e.target.value })}
                  required
                  className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
                  placeholder="0.00"
                />
              </div>
            </div>
          )}
          <div className="flex gap-2">
            <button
              type="submit"
              className="px-6 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              {editing ? 'Güncelle' : 'Ekle'}
            </button>
            {(editing || addingStock) && (
              <button
                type="button"
                onClick={resetForm}
                className="px-6 py-2 bg-primary-900/40 hover:bg-primary-800/40 rounded-lg transition-colors text-accent-mist"
              >
                İptal
              </button>
            )}
          </div>
        </form>
      </div>

      {/* Stok Listesi */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-semibold">Stok Listesi</h3>
          <div className="flex items-center gap-2">
            <label className="text-sm text-white/70">Kategori:</label>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
            >
              {categories.map(cat => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>
          </div>
        </div>
        {loading ? (
          <div className="text-center py-8 text-white/50">Yükleniyor...</div>
        ) : filteredItems.length === 0 ? (
          <div className="text-center py-8 text-white/50">
            {selectedCategory === 'Tümü' ? 'Stok henüz tanımlanmamış.' : `${selectedCategory} kategorisinde stok bulunamadı.`}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/20">
                  <th className="text-left py-3 px-4">Stok Adı</th>
                  <th className="text-left py-3 px-4">Kategori</th>
                  <th className="text-left py-3 px-4">Birim</th>
                  <th className="text-right py-3 px-4">Mevcut</th>
                  <th className="text-right py-3 px-4">Minimum</th>
                  <th className="text-right py-3 px-4">Maliyet</th>
                  <th className="text-center py-3 px-4">Durum</th>
                  <th className="text-right py-3 px-4">İşlemler</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item) => {
                  const status = getStockStatus(item.mevcut, item.min);
                  return (
                    <tr key={item.id} className="border-b border-white/10 hover:bg-white/5">
                      <td className="py-3 px-4">{item.ad}</td>
                      <td className="py-3 px-4">{item.kategori}</td>
                      <td className="py-3 px-4">{item.birim}</td>
                      <td className="py-3 px-4 text-right">{item.mevcut}</td>
                      <td className="py-3 px-4 text-right">{item.min}</td>
                      <td className="py-3 px-4 text-right">{item.alis_fiyat?.toFixed(2) || '0.00'} ₺</td>
                      <td className="py-3 px-4 text-center">
                        <span className={`px-2 py-1 rounded text-xs ${status.color}`}>
                          {status.text}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => handleEdit(item)}
                            className="p-1 hover:bg-primary-800/30 rounded transition-colors"
                            title="Düzenle"
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDelete(item.ad)}
                            className="p-1 hover:bg-tertiary-500/20 rounded transition-colors text-tertiary-100"
                            title="Sil"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
