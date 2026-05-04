import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShoppingCart, Plus, Minus, Trash2, ArrowRight, Home, X } from 'lucide-react';
import { menuApi, siparisApi, masalarApi } from '../lib/api';
import { offlineManager } from '../lib/offlineManager';
import { useOfflineSync } from '../lib/useOfflineSync';

interface Varyasyon {
  id: number;
  ad: string;
  ek_fiyat: number;
  sira: number;
}

interface MenuItem {
  id: number;
  ad: string;
  fiyat: number;
  kategori: string;
  aktif: boolean;
  varyasyonlar?: Varyasyon[];
}

interface CartItem {
  id: number;
  ad: string;
  fiyat: number;
  adet: number;
  varyasyon?: Varyasyon;
}

interface Masa {
  id: number;
  masa_adi: string;
  durum: string;
  kapasite: number;
}

export default function PersonelTerminalPage() {
  const navigate = useNavigate();
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [masalar, setMasalar] = useState<Masa[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string>('Tümü');
  const [cart, setCart] = useState<CartItem[]>([]);
  const [masa, setMasa] = useState<string>('');
  const [masaError, setMasaError] = useState<string>('');
  const [variationModal, setVariationModal] = useState<MenuItem | null>(null);
  const [variationQuantity, setVariationQuantity] = useState<number>(1);

  const { isOnline, syncing, queueCount } = useOfflineSync();

  useEffect(() => {
    loadMenu();
    loadMasalar();
  }, [isOnline]);

  const loadMenu = async () => {
    try {
      let items;
      if (!isOnline) {
         const cached = offlineManager.getFromCache('terminal_menu');
         items = cached || [];
      } else {
         const response = await menuApi.list({ limit: 200, sadece_aktif: true, varyasyonlar_dahil: true });
         items = (response.data || []).filter((item: MenuItem) => item.aktif);
         offlineManager.saveToCache('terminal_menu', items);
      }
      setMenuItems(items);
    } catch (err) {
      console.error('Menü yüklenemedi:', err);
      const cached = offlineManager.getFromCache('terminal_menu');
      if (cached) setMenuItems(cached);
    } finally {
      setLoading(false);
    }
  };

  const loadMasalar = async () => {
    try {
      let data;
      if (!isOnline) {
        data = offlineManager.getFromCache('terminal_masalar') || [];
      } else {
        const response = await masalarApi.list();
        data = response.data || [];
        offlineManager.saveToCache('terminal_masalar', data);
      }
      setMasalar(data);
    } catch (err) {
      console.error('Masalar yüklenemedi:', err);
      const cached = offlineManager.getFromCache('terminal_masalar');
      if (cached) setMasalar(cached);
    }
  };

  const categories = ['Tümü', ...Array.from(new Set(menuItems.map(item => item.kategori).filter(Boolean)))];

  const filteredItems = selectedCategory === 'Tümü'
    ? menuItems
    : menuItems.filter(item => item.kategori === selectedCategory);

  const addToCart = (item: MenuItem) => {
    // Eğer varyasyon varsa, varyasyon seçimi modal'ını aç
    if (item.varyasyonlar && item.varyasyonlar.length > 0) {
      setVariationModal(item);
      setVariationQuantity(1); // Reset quantity when opening modal
      return;
    }

    // Varyasyon yoksa direkt sepete ekle
    setCart(prev => {
      const existing = prev.find(c => c.id === item.id && !c.varyasyon);
      if (existing) {
        return prev.map(c => c.id === item.id && !c.varyasyon ? { ...c, adet: c.adet + 1 } : c);
      }
      return [...prev, { id: item.id, ad: item.ad, fiyat: item.fiyat, adet: 1 }];
    });
  };

  const addToCartWithVariation = (item: MenuItem, variation: Varyasyon) => {
    const finalPrice = item.fiyat + variation.ek_fiyat;
    setCart(prev => {
      const existing = prev.find(c => c.id === item.id && c.varyasyon?.id === variation.id);
      if (existing) {
        return prev.map(c =>
          c.id === item.id && c.varyasyon?.id === variation.id
            ? { ...c, adet: c.adet + variationQuantity }
            : c
        );
      }
      return [...prev, {
        id: item.id,
        ad: item.ad,
        fiyat: finalPrice,
        adet: variationQuantity,
        varyasyon: variation
      }];
    });
    setVariationModal(null);
    setVariationQuantity(1); // Reset quantity after adding
  };

  const removeFromCart = (id: number, variationId?: number) => {
    setCart(prev => prev.filter(c => 
      !(c.id === id && (!variationId || c.varyasyon?.id === variationId))
    ));
  };

  const updateCartQuantity = (id: number, delta: number, variationId?: number) => {
    setCart(prev => prev.map(c => {
      if (c.id === id && (!variationId || c.varyasyon?.id === variationId)) {
        const newAdet = Math.max(1, c.adet + delta);
        return { ...c, adet: newAdet };
      }
      return c;
    }));
  };

  const getTotal = () => {
    return cart.reduce((sum, item) => sum + (item.fiyat * item.adet), 0);
  };

  const handleOrder = async () => {
    if (!masa.trim()) {
      setMasaError('Lütfen masa numarası girin');
      return;
    }

    if (cart.length === 0) {
      alert('Sepetiniz boş');
      return;
    }

    try {
      const sepet = cart.map(item => ({
        urun: item.ad,
        adet: item.adet,
        fiyat: item.fiyat,
        ...(item.varyasyon && { varyasyon: item.varyasyon.ad }),
      }));

      const payload = {
        masa: masa.trim(),
        sepet: sepet,
        tutar: getTotal(),
      };

      if (!isOnline) {
        offlineManager.addAction('NEW_ORDER', payload);
        alert('✅ Sipariş kaydedildi (Çevrimdışı). İnternet geldiğinde mutfağa iletilecek!');
        setCart([]);
        setMasa('');
        setMasaError('');
        return;
      }

      await siparisApi.add(payload);

      alert('✅ Sipariş başarıyla oluşturuldu!');
      setCart([]);
      setMasa('');
      setMasaError('');
    } catch (err: any) {
      console.error('Sipariş oluşturulamadı:', err);
      alert(`Hata: ${err.response?.data?.detail || 'Sipariş oluşturulamadı'}`);
    }
  };

  return (
    <div className="min-h-screen">
      {/* Header */}
      <div className="glass-panel border-b border-emerald-500/20 p-4 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/dashboard')}
              className="p-2 hover:bg-white/10 rounded-lg transition-colors"
              title="Ana Sayfa"
            >
              <Home className="w-6 h-6 text-white" />
            </button>
            <h1 className="text-2xl font-bold text-gradient flex items-center gap-2">
              El Terminali
              {!isOnline && (
                <span className="bg-rose-500/20 text-rose-400 text-xs px-2 py-0.5 rounded-full border border-rose-500/30 animate-pulse font-medium">
                  Çevrimdışı
                </span>
              )}
              {isOnline && syncing && (
                <span className="bg-amber-500/20 text-amber-400 text-xs px-2 py-0.5 rounded-full border border-amber-500/30 animate-pulse font-medium">
                  Senkronize ({queueCount})
                </span>
              )}
            </h1>
          </div>
          
          {/* Masa Seçimi */}
          <div className="flex items-center gap-4">
            <div>
              <select
                value={masa}
                onChange={(e) => {
                  setMasa(e.target.value);
                  setMasaError('');
                }}
                className="w-48"
              >
                <option value="">Masa Seçin</option>
                {masalar.map((m) => (
                  <option key={m.id} value={m.masa_adi} className="bg-slate-900">{m.masa_adi}</option>
                ))}
              </select>
              {masaError && <p className="text-red-400 text-xs mt-1">{masaError}</p>}
            </div>
            
            <div className="flex items-center gap-2 px-6 py-2 bg-emerald-500/10 border border-emerald-500/30 rounded-xl">
              <ShoppingCart className="w-5 h-5 text-emerald-400" />
              <span className="text-xl font-bold text-emerald-400">{cart.length}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-4">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Menü */}
          <div className="lg:col-span-2">
            <div className="premium-card rounded-2xl p-6 h-full">
              <div className="flex items-center justify-between mb-8">
                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                  <span className="w-8 h-1 bg-emerald-500 rounded-full"></span>
                  Günün Menüsü
                </h3>
                <div className="flex items-center gap-3">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-widest">Kategori</span>
                  <select
                    value={selectedCategory}
                    onChange={(e) => setSelectedCategory(e.target.value)}
                    className="min-w-[140px]"
                  >
                    {categories.map(cat => (
                      <option key={cat} value={cat}>{cat}</option>
                    ))}
                  </select>
                </div>
              </div>
              
              {loading ? (
                <div className="text-center py-8 text-white/50">Yükleniyor...</div>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  {filteredItems.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => addToCart(item)}
                      className="group p-5 bg-white/5 border border-slate-700/50 rounded-2xl hover:border-emerald-500/50 hover:bg-emerald-500/5 transition-all duration-300 text-left relative overflow-hidden"
                    >
                      <div className="absolute top-0 right-0 p-3 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Plus className="w-5 h-5 text-emerald-400" />
                      </div>
                      <div className="flex justify-between items-start mb-2">
                        <h4 className="font-semibold text-white group-hover:text-emerald-200 transition-colors">
                          {item.ad}
                        </h4>
                        {item.varyasyonlar && item.varyasyonlar.length > 0 && (
                          <span className="text-xs text-emerald-300 bg-emerald-500/20 px-2 py-1 rounded">
                            Varyasyonlu
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-white/50 mb-3">{item.kategori}</p>
                      <div className="flex justify-between items-center">
                        <span className="text-xl font-bold text-white group-hover:text-emerald-400 transition-colors">
                          {item.fiyat.toFixed(2)} ₺
                        </span>
                        <Plus className="w-5 h-5 text-white/50 group-hover:text-emerald-300 transition-colors" />
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Sepet */}
          <div className="lg:col-span-1">
            <div className="premium-card rounded-2xl p-6 sticky top-24">
              <h3 className="text-xl font-bold mb-6 flex items-center justify-between">
                <span>Sepet</span>
                {cart.length > 0 && (
                  <button
                    onClick={() => setCart([])}
                    className="text-xs text-red-400 hover:text-red-300 flex items-center gap-1"
                  >
                    <Trash2 className="w-4 h-4" />
                    Temizle
                  </button>
                )}
              </h3>
              
              {cart.length === 0 ? (
                <div className="text-center py-8 text-white/50">
                  Sepetiniz boş
                </div>
              ) : (
                <>
                  <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2">
                    {cart.map((item, index) => (
                        <div
                          key={`${item.id}-${item.varyasyon?.id || 'none'}-${index}`}
                          className="flex items-center gap-3 p-4 bg-slate-900/50 rounded-xl border border-slate-800"
                        >
                        <div className="flex-1">
                          <p className="font-medium text-white">{item.ad}</p>
                          {item.varyasyon && (
                            <p className="text-xs text-emerald-300">Varyasyon: {item.varyasyon.ad}</p>
                          )}
                          <p className="text-sm text-emerald-300">
                            {item.fiyat.toFixed(2)} ₺ x {item.adet}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => updateCartQuantity(item.id, -1, item.varyasyon?.id)}
                            className="p-1 bg-white/10 hover:bg-white/20 rounded transition-colors"
                          >
                            <Minus className="w-4 h-4" />
                          </button>
                          <span className="w-8 text-center font-bold">{item.adet}</span>
                          <button
                            onClick={() => updateCartQuantity(item.id, 1, item.varyasyon?.id)}
                            className="p-1 bg-white/10 hover:bg-white/20 rounded transition-colors"
                          >
                            <Plus className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => removeFromCart(item.id, item.varyasyon?.id)}
                            className="p-1 bg-red-500/20 hover:bg-red-500/30 rounded transition-colors text-red-300 ml-2"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                  
                  <div className="mt-6 pt-6 border-t border-white/20">
                    <div className="flex justify-between items-center mb-4">
                      <span className="text-xl font-bold">Toplam:</span>
                      <span className="text-2xl font-bold text-emerald-300">
                        {getTotal().toFixed(2)} ₺
                      </span>
                    </div>
                    <button
                      onClick={handleOrder}
                      className="glow-button w-full px-6 py-4 rounded-xl flex items-center justify-center gap-3 text-white font-bold text-lg"
                    >
                      <ArrowRight className="w-6 h-6" />
                      Siparişi Tamamla
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Varyasyon Seçim Modal */}
      {variationModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-900 border border-white/20 rounded-xl p-6 max-w-md w-full max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-bold text-white">{variationModal.ad} - Varyasyon Seçin</h3>
              <button
                onClick={() => {
                  setVariationModal(null);
                  setVariationQuantity(1);
                }}
                className="p-2 hover:bg-white/10 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-white" />
              </button>
            </div>

            {/* Adet Seçimi */}
            <div className="mb-4 p-4 bg-white/5 rounded-lg border border-white/10">
              <label className="block text-sm font-medium text-white/70 mb-2">Adet</label>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setVariationQuantity(Math.max(1, variationQuantity - 1))}
                  className="p-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
                >
                  <Minus className="w-5 h-5 text-white" />
                </button>
                <input
                  type="number"
                  min="1"
                  value={variationQuantity}
                  onChange={(e) => setVariationQuantity(Math.max(1, parseInt(e.target.value) || 1))}
                  className="flex-1 px-4 py-2 bg-white/10 border border-white/20 rounded-lg text-center text-xl font-bold text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
                <button
                  onClick={() => setVariationQuantity(variationQuantity + 1)}
                  className="p-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
                >
                  <Plus className="w-5 h-5 text-white" />
                </button>
              </div>
            </div>

            <div className="space-y-2">
              {variationModal.varyasyonlar?.map((variation) => {
                const finalPrice = variationModal.fiyat + variation.ek_fiyat;
                const totalPrice = finalPrice * variationQuantity;
                return (
                  <button
                    key={variation.id}
                    onClick={() => addToCartWithVariation(variationModal, variation)}
                    className="w-full p-4 bg-white/5 border border-white/10 rounded-lg hover:border-emerald-500/50 hover:bg-emerald-500/10 transition-all text-left"
                  >
                    <div className="flex justify-between items-center">
                      <div>
                        <p className="font-semibold text-white">{variation.ad}</p>
                        {variation.ek_fiyat > 0 && (
                          <p className="text-xs text-white/50">+{variation.ek_fiyat.toFixed(2)} ₺</p>
                        )}
                        {variationQuantity > 1 && (
                          <p className="text-xs text-emerald-300 mt-1">{finalPrice.toFixed(2)} ₺ x {variationQuantity}</p>
                        )}
                      </div>
                      <div className="text-right">
                        <p className="font-bold text-emerald-300">{totalPrice.toFixed(2)} ₺</p>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

