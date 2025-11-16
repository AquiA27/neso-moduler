import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShoppingCart, Plus, Minus, Trash2, ArrowRight, Home, X } from 'lucide-react';
import { menuApi, siparisApi, masalarApi } from '../lib/api';

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

  useEffect(() => {
    loadMenu();
    loadMasalar();
  }, []);

  const loadMenu = async () => {
    try {
      const response = await menuApi.list({ limit: 200, sadece_aktif: true, varyasyonlar_dahil: true });
      const items = (response.data || []).filter((item: MenuItem) => item.aktif);
      setMenuItems(items);
    } catch (err) {
      console.error('Menü yüklenemedi:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadMasalar = async () => {
    try {
      const response = await masalarApi.list();
      setMasalar(response.data || []);
    } catch (err) {
      console.error('Masalar yüklenemedi:', err);
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

      await siparisApi.add({
        masa: masa.trim(),
        sepet: sepet,
        tutar: getTotal(),
      });

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
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-emerald-950 to-teal-950">
      {/* Header */}
      <div className="bg-white/10 backdrop-blur-md border-b border-white/20 p-4 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/dashboard')}
              className="p-2 hover:bg-white/10 rounded-lg transition-colors"
              title="Ana Sayfa"
            >
              <Home className="w-6 h-6 text-white" />
            </button>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-emerald-300 via-cyan-300 to-teal-300 bg-clip-text text-transparent">
              El Terminali
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
                className="w-48 px-4 py-2 bg-white/20 border border-white/30 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 text-white text-lg font-semibold"
              >
                <option value="">Masa Seçin</option>
                {masalar.map((m) => (
                  <option key={m.id} value={m.masa_adi}>{m.masa_adi}</option>
                ))}
              </select>
              {masaError && <p className="text-red-400 text-xs mt-1">{masaError}</p>}
            </div>
            
            <div className="flex items-center gap-2 px-4 py-2 bg-emerald-600/30 border border-emerald-500/50 rounded-lg">
              <ShoppingCart className="w-6 h-6 text-emerald-300" />
              <span className="text-2xl font-bold text-emerald-200">{cart.length}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-4">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Menü */}
          <div className="lg:col-span-2">
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xl font-semibold">Menü</h3>
                <div className="flex items-center gap-2">
                  <label className="text-sm text-white/70">Kategori:</label>
                  <select
                    value={selectedCategory}
                    onChange={(e) => setSelectedCategory(e.target.value)}
                    className="px-4 py-2 bg-white/10 border border-white/20 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
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
                      className="p-4 bg-gradient-to-br from-white/5 to-white/10 border border-white/10 rounded-xl hover:border-emerald-500/50 hover:bg-gradient-to-br hover:from-emerald-500/10 hover:to-cyan-500/10 transition-all text-left group"
                    >
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
                        <span className="text-lg font-bold text-emerald-300">
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
            <div className="card sticky top-24">
              <h3 className="text-xl font-semibold mb-4 flex items-center justify-between">
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
                        className="flex items-center gap-3 p-3 bg-white/5 rounded-lg border border-white/10"
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
                      className="w-full px-6 py-4 bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-700 hover:to-cyan-700 rounded-xl transition-colors flex items-center justify-center gap-2 text-white font-bold text-lg shadow-lg shadow-emerald-500/30"
                    >
                      <ArrowRight className="w-6 h-6" />
                      Sipariş Ver
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

