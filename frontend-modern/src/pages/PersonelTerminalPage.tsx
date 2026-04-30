import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  ShoppingCart, Plus, Minus, Trash2, ArrowRight, Home, X, 
  Search, Utensils, Coffee, Pizza, LayoutGrid, CheckCircle2, ChevronRight,
  User, Hash, Clock
} from 'lucide-react';
import { menuApi, siparisApi, masalarApi } from '../lib/api';
import { useAuthStore } from '../store/authStore';

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
  gorsel_url?: string;
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
  const user = useAuthStore((state) => state.user);
  
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [masalar, setMasalar] = useState<Masa[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string>('Tümü');
  const [searchQuery, setSearchQuery] = useState('');
  const [cart, setCart] = useState<CartItem[]>([]);
  const [selectedMasa, setSelectedMasa] = useState<string>('');
  const [showCart, setShowCart] = useState(false);
  
  const [variationModal, setVariationModal] = useState<MenuItem | null>(null);
  const [variationQuantity, setVariationQuantity] = useState<number>(1);

  useEffect(() => {
    loadMenu();
    loadMasalar();
  }, []);

  const loadMenu = async () => {
    try {
      const response = await menuApi.list({ limit: 500, sadece_aktif: true, varyasyonlar_dahil: true });
      setMenuItems(response.data || []);
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

  const categories = useMemo(() => {
    const cats = Array.from(new Set(menuItems.map(item => item.kategori).filter(Boolean)));
    return ['Tümü', ...cats];
  }, [menuItems]);

  const filteredItems = useMemo(() => {
    return menuItems.filter(item => {
      const matchesCategory = selectedCategory === 'Tümü' || item.kategori === selectedCategory;
      const matchesSearch = item.ad.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesCategory && matchesSearch;
    });
  }, [menuItems, selectedCategory, searchQuery]);

  const addToCart = (item: MenuItem) => {
    if (item.varyasyonlar && item.varyasyonlar.length > 0) {
      setVariationModal(item);
      setVariationQuantity(1);
      return;
    }

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
    setVariationQuantity(1);
  };

  const updateQuantity = (id: number, delta: number, variationId?: number) => {
    setCart(prev => prev.map(c => {
      if (c.id === id && (!variationId || c.varyasyon?.id === variationId)) {
        const newAdet = Math.max(0, c.adet + delta);
        return { ...c, adet: newAdet };
      }
      return c;
    }).filter(c => c.adet > 0));
  };

  const cartTotal = cart.reduce((sum, item) => sum + (item.fiyat * item.adet), 0);

  const handleOrder = async () => {
    if (!selectedMasa) {
      alert('Lütfen bir masa seçin!');
      return;
    }
    if (cart.length === 0) return;

    try {
      const sepet = cart.map(item => ({
        urun: item.ad,
        adet: item.adet,
        fiyat: item.fiyat,
        ...(item.varyasyon && { varyasyon: item.varyasyon.ad }),
      }));

      await siparisApi.add({
        masa: selectedMasa,
        sepet: sepet,
        tutar: cartTotal,
      });

      alert('✅ Sipariş başarıyla mutfağa iletildi!');
      setCart([]);
      setSelectedMasa('');
      setShowCart(false);
    } catch (err: any) {
      alert(`Hata: ${err.response?.data?.detail || 'Sipariş gönderilemedi'}`);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-neso-dark overflow-hidden">
      {/* Top Header */}
      <div className="bg-slate-900/50 border-b border-white/5 p-4 flex items-center justify-between z-20">
        <div className="flex items-center gap-4">
          <button onClick={() => navigate('/dashboard')} className="p-2 bg-white/5 rounded-xl hover:bg-white/10 transition-all">
            <Home size={20} className="text-neso-gold" />
          </button>
          <div>
            <h1 className="text-lg font-black text-white italic tracking-tighter uppercase leading-none">Garson Terminali</h1>
            <div className="flex items-center gap-2 mt-1">
              <User size={10} className="text-slate-500" />
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{user?.username}</span>
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="relative">
            <select
              value={selectedMasa}
              onChange={(e) => setSelectedMasa(e.target.value)}
              className="bg-neso-gold/10 border border-neso-gold/30 rounded-xl px-4 py-2 text-sm font-black text-neso-gold focus:outline-none appearance-none pr-8 min-w-[120px]"
            >
              <option value="" className="bg-slate-900">Masa Seç</option>
              {masalar.map(m => (
                <option key={m.id} value={m.masa_adi} className="bg-slate-900">Masa {m.masa_adi}</option>
              ))}
            </select>
            <Hash size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-neso-gold pointer-events-none" />
          </div>
          
          <button 
            onClick={() => setShowCart(true)}
            className="relative p-3 bg-neso-gold rounded-xl shadow-lg shadow-neso-gold/20"
          >
            <ShoppingCart size={20} className="text-neso-dark" />
            {cart.length > 0 && (
              <span className="absolute -top-1 -right-1 w-5 h-5 bg-white text-neso-dark text-[10px] font-black rounded-full flex items-center justify-center">
                {cart.length}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden relative">
        {/* Search & Categories */}
        <div className="p-4 space-y-4 bg-neso-dark">
          <div className="relative">
            <input
              type="text"
              placeholder="Ürün Ara..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-2xl px-12 py-3.5 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-neso-gold/50"
            />
            <Search size={20} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
          </div>

          <div className="flex gap-2 overflow-x-auto pb-2 custom-scrollbar">
            {categories.map(cat => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-6 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest whitespace-nowrap transition-all ${
                  selectedCategory === cat 
                    ? 'bg-neso-gold text-neso-dark' 
                    : 'bg-white/5 text-slate-400 border border-white/5'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* Menu Grid */}
        <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-full gap-4">
              <div className="w-10 h-10 border-2 border-neso-gold border-t-transparent rounded-full animate-spin"></div>
              <p className="text-xs font-bold text-slate-500 uppercase">Menü Yükleniyor...</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-4">
              {filteredItems.map(item => (
                <button
                  key={item.id}
                  onClick={() => addToCart(item)}
                  className="group relative flex flex-col bg-slate-900/40 border border-white/5 rounded-3xl p-4 text-left hover:border-neso-gold/30 hover:bg-neso-gold/5 transition-all active:scale-95 overflow-hidden h-full"
                >
                  <div className="flex flex-col h-full">
                    <div className="flex justify-between items-start mb-3">
                       <div className="p-2 rounded-xl bg-white/5 text-slate-400 group-hover:text-neso-gold transition-colors">
                          {item.kategori.toLowerCase().includes('kahve') ? <Coffee size={18} /> : 
                           item.kategori.toLowerCase().includes('yemek') ? <Utensils size={18} /> :
                           item.kategori.toLowerCase().includes('pizza') ? <Pizza size={18} /> : <LayoutGrid size={18} />}
                       </div>
                       {item.varyasyonlar && item.varyasyonlar.length > 0 && (
                         <div className="px-2 py-0.5 rounded-lg bg-neso-gold/10 text-neso-gold text-[8px] font-black uppercase">Varyant</div>
                       )}
                    </div>
                    
                    <h4 className="font-bold text-white text-sm uppercase leading-tight mb-auto">{item.ad}</h4>
                    
                    <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between">
                       <span className="text-lg font-black text-white">{item.fiyat}₺</span>
                       <div className="p-1.5 rounded-lg bg-neso-gold text-neso-dark">
                          <Plus size={14} />
                       </div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Mobile Cart Summary Bar */}
      {cart.length > 0 && !showCart && (
        <button 
          onClick={() => setShowCart(true)}
          className="m-4 p-5 bg-neso-gold rounded-3xl flex items-center justify-between shadow-2xl shadow-neso-gold/40 animate-in slide-in-from-bottom-8 duration-500"
        >
          <div className="flex items-center gap-4 text-neso-dark">
             <div className="w-10 h-10 rounded-2xl bg-white/20 flex items-center justify-center font-black">
                {cart.length}
             </div>
             <div>
                <p className="text-[10px] font-black uppercase tracking-widest opacity-60">Sipariş Toplamı</p>
                <p className="text-xl font-black">{cartTotal.toFixed(2)}₺</p>
             </div>
          </div>
          <div className="flex items-center gap-2 font-black text-sm uppercase tracking-widest text-neso-dark">
             İNCELE <ChevronRight size={20} />
          </div>
        </button>
      )}

      {/* Cart Modal / Side Sheet */}
      {showCart && (
        <div className="fixed inset-0 z-50 flex flex-col md:items-end">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowCart(false)} />
          <div className="relative w-full md:w-[450px] h-full bg-neso-dark border-l border-white/10 flex flex-col animate-in slide-in-from-right duration-300">
            {/* Cart Header */}
            <div className="p-6 border-b border-white/10 flex items-center justify-between bg-slate-900/50">
               <div>
                  <h2 className="text-2xl font-black text-white italic tracking-tighter uppercase">Sepetiniz</h2>
                  <div className="flex items-center gap-2 mt-1">
                     <Hash size={12} className="text-neso-gold" />
                     <span className="text-[10px] font-bold text-neso-gold uppercase">MASA: {selectedMasa || 'SEÇİLMEDİ'}</span>
                  </div>
               </div>
               <button onClick={() => setShowCart(false)} className="p-2 bg-white/5 rounded-xl text-slate-400 hover:text-white">
                  <X size={24} />
               </button>
            </div>

            {/* Cart Items */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4 custom-scrollbar">
               {cart.map((item, idx) => (
                  <div key={idx} className="p-4 bg-white/5 border border-white/5 rounded-3xl flex items-center gap-4 group">
                     <div className="flex-1">
                        <h5 className="font-bold text-white uppercase text-sm">{item.ad}</h5>
                        {item.varyasyon && <p className="text-[10px] font-black text-neso-gold uppercase mt-0.5">{item.varyasyon.ad}</p>}
                        <p className="text-lg font-black text-white mt-2">{item.fiyat}₺</p>
                     </div>
                     <div className="flex items-center bg-black/30 rounded-2xl p-1 gap-2 border border-white/5">
                        <button onClick={() => updateQuantity(item.id, -1, item.varyasyon?.id)} className="p-2 text-slate-500 hover:text-white transition-colors"><Minus size={16} /></button>
                        <span className="w-8 text-center font-black text-neso-gold">{item.adet}</span>
                        <button onClick={() => updateQuantity(item.id, 1, item.varyasyon?.id)} className="p-2 text-neso-gold hover:text-white transition-colors"><Plus size={16} /></button>
                     </div>
                  </div>
               ))}
            </div>

            {/* Cart Footer */}
            <div className="p-8 bg-slate-900/80 border-t border-white/10 rounded-t-[3rem]">
               <div className="flex justify-between items-center mb-6">
                  <span className="text-slate-500 font-black uppercase tracking-widest text-xs">Genel Toplam</span>
                  <span className="text-3xl font-black text-white tracking-tighter">{cartTotal.toFixed(2)}₺</span>
               </div>
               <button 
                onClick={handleOrder}
                className="w-full flex items-center justify-center gap-4 py-5 bg-neso-gold text-neso-dark rounded-[2rem] font-black text-lg uppercase tracking-widest shadow-2xl shadow-neso-gold/30 hover:scale-[1.02] active:scale-95 transition-all disabled:opacity-50"
                disabled={cart.length === 0}
               >
                  MUTFAĞA GÖNDER <ArrowRight size={24} />
               </button>
            </div>
          </div>
        </div>
      )}

      {/* Variation Modal */}
      {variationModal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/80 backdrop-blur-md" onClick={() => setVariationModal(null)} />
          <div className="relative w-full max-w-md bg-neso-dark border border-white/10 rounded-[3rem] overflow-hidden p-8 animate-in zoom-in-95 duration-300">
             <div className="flex justify-between items-start mb-8">
                <div>
                   <h3 className="text-2xl font-black text-white italic uppercase tracking-tighter">{variationModal.ad}</h3>
                   <p className="text-xs font-bold text-slate-500 uppercase mt-1">Lütfen Varyasyon Seçin</p>
                </div>
                <button onClick={() => setVariationModal(null)} className="p-2 bg-white/5 rounded-xl text-slate-400">
                   <X size={20} />
                </button>
             </div>

             <div className="space-y-3">
                {variationModal.varyasyonlar?.map(v => (
                   <button
                    key={v.id}
                    onClick={() => addToCartWithVariation(variationModal, v)}
                    className="w-full p-6 bg-white/5 border border-white/5 rounded-3xl flex justify-between items-center hover:border-neso-gold/30 hover:bg-neso-gold/5 transition-all group"
                   >
                      <span className="font-bold text-white uppercase group-hover:text-neso-gold transition-colors">{v.ad}</span>
                      <div className="flex flex-col items-end">
                         <span className="text-lg font-black text-white">{variationModal.fiyat + v.ek_fiyat}₺</span>
                         {v.ek_fiyat > 0 && <span className="text-[10px] font-black text-emerald-400 uppercase">+{v.ek_fiyat}₺ FARK</span>}
                      </div>
                   </button>
                ))}
             </div>
          </div>
        </div>
      )}
    </div>
  );
}
