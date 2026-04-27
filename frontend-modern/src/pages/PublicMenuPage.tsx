import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, ShoppingCart } from 'lucide-react';
import { publicMenuApi, normalizeApiUrl } from '../lib/api';
import logo from '../assets/neso-logo.jpg';

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
  aciklama?: string;
  gorsel_url?: string;
  varyasyonlar?: Varyasyon[];
}

export default function PublicMenuPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const qrCode = searchParams.get('qr');
  const initialMasa = searchParams.get('masa') || '';
  const initialSubeId = searchParams.get('sube_id');

  const [masa, setMasa] = useState(initialMasa);
  const [subeId, setSubeId] = useState<number | undefined>(
    initialSubeId ? Number.parseInt(initialSubeId, 10) : undefined
  );
  const [isBlocked, setIsBlocked] = useState(false);
  const [subeAdi, setSubeAdi] = useState<string | null>(null);
  const [subeSayisi, setSubeSayisi] = useState<number>(0);
  const [tableStatus, setTableStatus] = useState<string | null>(null);

  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [categories, setCategories] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [customization, setCustomization] = useState<{app_name?: string; logo_url?: string} | null>(null);

  useEffect(() => {
    const loadMasaFromQR = async () => {
      if (!qrCode) return;
      try {

        const API_BASE_URL = normalizeApiUrl(import.meta.env.VITE_API_URL as string);
        // QR kod'u URL encode et (özel karakterler için)
        const encodedQRCode = encodeURIComponent(qrCode);
        console.log('[QR] Loading masa info for QR code:', qrCode.substring(0, 20) + '...');
        const response = await fetch(`${API_BASE_URL}/public/masa/${encodedQRCode}`);
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: 'Masa bulunamadı' }));
          console.error('[QR] Masa API error:', response.status, errorData);
          throw new Error(errorData.detail || 'Masa bulunamadı');
        }
        const data = await response.json();
        console.log('[QR] Masa bilgisi yüklendi:', data);
        setMasa(data.masa_adi || initialMasa);
        setSubeId(data.sube_id ? Number(data.sube_id) : 1);
        setSubeAdi(data.sube_adi);
        setSubeSayisi(data.sube_sayisi || 0);
        // Customization bilgisini de kaydet
        if (data.customization) {
          setCustomization(data.customization);
        }
        
        // Masa durumu kontrolü (rezerve, dolu, temizlik durumlarında uyarı ver)
        if (['rezerve', 'dolu', 'temizlik'].includes(data.durum)) {
          setIsBlocked(true);
          setTableStatus(data.durum);
        }
      } catch (err) {
        console.error('QR Masa Yükleme Hatası:', err);
      }
    };

    loadMasaFromQR();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qrCode]);

  useEffect(() => {
    if (subeId === undefined) return;
    loadMenu();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subeId]);

  const loadMenu = async () => {
    if (subeId === undefined) return;
    try {
      setLoading(true);
      const response = await publicMenuApi.list(subeId);
      // Public API direkt aktif ürünleri döndürüyor, aktif filtrelemeye gerek yok
      const items = (response.data || []).map((item: any) => {
        console.log('Menu item loaded:', item.id, item.ad, 'gorsel_url:', item.gorsel_url, 'varyasyonlar:', item.varyasyonlar?.length || 0);
        return {
          id: item.id,
          ad: item.ad,
          fiyat: item.fiyat,
          kategori: item.kategori || '',
          aktif: true, // Public API sadece aktif ürünleri döndürür
          aciklama: item.aciklama,
          gorsel_url: item.gorsel_url,
          varyasyonlar: item.varyasyonlar || [], // Varyasyonları da ekle
        };
      });
      console.log('Total menu items loaded:', items.length, 'Items with images:', items.filter((i: MenuItem) => i.gorsel_url).length, 'Items with variations:', items.filter((i: MenuItem) => i.varyasyonlar && i.varyasyonlar.length > 0).length);
      setMenuItems(items);
      
      // Kategorileri çıkar
      const cats = Array.from(new Set(items.map((item: MenuItem) => item.kategori).filter(Boolean))) as string[];
      setCategories(cats);
    } catch (err) {
      console.error('Menü yüklenemedi:', err);
      // Hata detaylarını göster
      if (err instanceof Error) {
        console.error('Hata mesajı:', err.message);
      }
      if ((err as any).response) {
        console.error('API yanıtı:', (err as any).response.data);
        console.error('HTTP status:', (err as any).response.status);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    navigate(-1);
  };

  const handleOrderViaChat = () => {
    const params = new URLSearchParams();
    if (qrCode) {
      params.set('qr', qrCode);
    } else {
      if (masa) params.set('masa', masa);
      if (subeId) params.set('sube_id', subeId?.toString() || '1');
    }
    navigate(`/musteri/chat?${params.toString()}`);
  };

  const filteredItems = selectedCategory
    ? menuItems.filter((item) => item.kategori === selectedCategory)
    : menuItems;

  const groupedItems = filteredItems.reduce((acc, item) => {
    const cat = item.kategori || 'Diğer';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(item);
    return acc;
  }, {} as Record<string, MenuItem[]>);

  const API_BASE_URL = normalizeApiUrl(import.meta.env.VITE_API_URL as string);
  const resolveImageUrl = (url?: string) => {
    if (!url) return '';
    if (url.startsWith('http://') || url.startsWith('https://')) return url;
    const base = API_BASE_URL.replace(/\/$/, '');
    const path = url.startsWith('/') ? url : `/${url}`;
    return `${base}${path}`;
  };

  return (
    <div className="min-h-screen bg-[#050c0a] text-white font-outfit relative overflow-hidden">
      {/* Background Decorative Elemets */}
      <div className="fixed top-0 right-0 w-[500px] h-[500px] bg-emerald-500/5 blur-[120px] rounded-full -translate-y-1/2 translate-x-1/2 pointer-events-none" />
      <div className="fixed bottom-0 left-0 w-[400px] h-[400px] bg-emerald-600/5 blur-[100px] rounded-full translate-y-1/2 -translate-x-1/2 pointer-events-none" />

      {/* Header */}
      <div className="relative border-b border-white/5 bg-white/[0.02] backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-6 py-8 md:py-12 flex flex-col gap-8">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="flex items-center gap-6">
              <button
                onClick={handleBack}
                className="w-12 h-12 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center hover:bg-white/10 transition-all group"
                aria-label="Geri dön"
              >
                <ArrowLeft className="w-5 h-5 text-white/50 group-hover:text-white transition-colors" />
              </button>
              
              <div className="space-y-1">
                 {(customization?.logo_url || logo) && (
                    <img
                      src={customization?.logo_url ? resolveImageUrl(customization.logo_url) : logo}
                      alt={customization?.app_name || 'Logo'}
                      className="h-16 w-16 object-cover rounded-xl border border-white/10 mb-4"
                    />
                  )}
                 <h1 className="text-4xl md:text-5xl font-black text-white tracking-tighter">
                    {customization?.app_name ? customization.app_name : 'NESO'} <span className="text-emerald-500">MENÜ</span>
                 </h1>
                 <p className="text-slate-400 font-medium tracking-wide uppercase text-sm">Gurme Lezzetler & Özel Sunumlar</p>
              </div>
            </div>

            {!isBlocked && (
              <button
                onClick={handleOrderViaChat}
                className="glow-button px-8 py-4 rounded-2xl font-bold flex items-center justify-center gap-3 shadow-2xl transition-all hover:scale-[1.02] active:scale-95"
              >
                <ShoppingCart className="w-5 h-5" />
                Siparişinizi Verin
              </button>
            )}
          </div>

          <div className="flex flex-wrap gap-3">
             {masa && (
                <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-bold text-xs">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  MASA: {masa}
                </div>
              )}
              {subeSayisi > 1 && subeAdi && (
                <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-slate-400 font-bold text-xs uppercase tracking-wider">
                   ŞUBE: {subeAdi}
                </div>
              )}
          </div>
        </div>
      </div>

      {/* Category Filter */}
      {categories.length > 0 && (
        <div className="sticky top-0 z-20 bg-[#050c0a]/80 backdrop-blur-xl border-b border-white/5">
          <div className="max-w-6xl mx-auto px-6 py-4">
            <div className="flex gap-3 overflow-x-auto hide-scrollbar">
              <button
                onClick={() => setSelectedCategory(null)}
                className={`flex-shrink-0 px-6 py-2.5 rounded-xl font-bold text-sm transition-all ${
                  selectedCategory === null
                    ? 'bg-emerald-500 text-white shadow-[0_0_15px_rgba(16,185,129,0.3)]'
                    : 'bg-white/5 text-slate-400 hover:text-white hover:bg-white/10 border border-white/5'
                }`}
              >
                TÜMÜ
              </button>
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={`flex-shrink-0 px-6 py-2.5 rounded-xl font-bold text-sm transition-all uppercase tracking-wide ${
                    selectedCategory === cat
                      ? 'bg-emerald-500 text-white shadow-[0_0_15px_rgba(16,185,129,0.3)]'
                      : 'bg-white/5 text-slate-400 hover:text-white hover:bg-white/10 border border-white/5'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Menu Content */}
      <div className="px-4 py-8">
        <div className="max-w-6xl mx-auto space-y-12">
          {isBlocked ? (
            <div className="flex flex-col items-center justify-center py-20 px-4 text-center space-y-6">
              <div className="w-24 h-24 rounded-full bg-amber-500/20 flex items-center justify-center border border-amber-500/40 shadow-[0_0_30px_rgba(245,158,11,0.3)]">
                <span className="text-amber-400 font-extrabold text-5xl">!</span>
              </div>
              <h2 className="text-3xl font-bold text-white tracking-tight">
                {tableStatus === 'rezerve' && "Masa Rezerve Edilmiştir"}
                {tableStatus === 'dolu' && "Masa Doludur"}
                {tableStatus === 'temizlik' && "Masa Hazırlanıyor"}
              </h2>
              <p className="text-white/60 text-lg max-w-md">
                {tableStatus === 'rezerve' && "Bu masa rezervasyonlu olarak işaretlenmiştir. Lütfen farklı boş bir masaya geçebilir veya ilgili görevliye danışarak durum hakkında bilgi alabilirsiniz."}
                {tableStatus === 'dolu' && "Bu masa şu anda başka bir müşterimiz tarafından kullanılmaktadır. Eğer masada oturuyorsanız ve bir hata olduğunu düşünüyorsanız lütfen kasanın yanındaki görevliye başvurunuz."}
                {tableStatus === 'temizlik' && "Bu masa şu anda temizlik ve hazırlık aşamasındadır. Sizlere en hijyenik hizmeti sunabilmek için kısa süre sonra kullanıma açılacaktır. Lütfen bekleyiniz veya başka bir masaya geçiniz."}
              </p>
            </div>
          ) : loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {Array.from({ length: 6 }).map((_, idx) => (
                <div
                  key={idx}
                  className="h-40 rounded-2xl bg-white/5 border border-white/10 animate-pulse"
                />
              ))}
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="text-center py-12">
              <div className="text-white/60 text-lg">Menü bulunamadı</div>
            </div>
          ) : (
            Object.entries(groupedItems).map(([category, items]) => (
              <div key={category} className="space-y-6">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-[2px] bg-gradient-to-r from-secondary-400 to-transparent" />
                  <h2 className="text-2xl font-bold tracking-wide text-secondary-100 uppercase">
                    {category}
                  </h2>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                  {items.map((item) => (
                    <div
                      key={item.id}
                      className="premium-card group rounded-3xl overflow-hidden flex flex-col h-full transition-all duration-500 hover:scale-[1.02] active:scale-95"
                    >
                      {item.gorsel_url ? (
                        <div className="relative h-56 overflow-hidden">
                          <img
                            src={resolveImageUrl(item.gorsel_url)}
                            alt={item.ad}
                            className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                          />
                          <div className="absolute inset-0 bg-gradient-to-t from-[#050c0a] via-transparent to-transparent opacity-60" />
                        </div>
                      ) : (
                        <div className="h-56 bg-slate-900/50 flex items-center justify-center">
                           <ShoppingCart className="w-12 h-12 text-slate-700" />
                        </div>
                      )}
                      
                      <div className="p-8 flex-1 flex flex-col">
                        <div className="flex justify-between items-start gap-4 mb-4">
                          <h3 className="text-2xl font-bold text-white tracking-tight">{item.ad}</h3>
                          <span className="shrink-0 px-4 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-bold">
                            {item.fiyat.toFixed(2)} ₺
                          </span>
                        </div>
                        
                        {item.aciklama && (
                          <p className="text-slate-400 font-medium text-sm leading-relaxed mb-6 line-clamp-2">
                            {item.aciklama}
                          </p>
                        )}

                        {item.varyasyonlar && item.varyasyonlar.length > 0 && (
                          <div className="mt-auto pt-6 border-t border-white/5 flex flex-wrap gap-2">
                             {item.varyasyonlar.map((v) => (
                               <span key={v.id} className="text-[10px] font-bold uppercase tracking-wider px-2 py-1 bg-white/5 border border-white/10 text-slate-500 rounded-md">
                                 {v.ad} (+{v.ek_fiyat}₺)
                               </span>
                             ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Floating CTA */}
      {!isBlocked && (
        <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-30 md:hidden pb-safe">
           <button
            onClick={handleOrderViaChat}
            className="glow-button px-10 py-5 rounded-full font-bold text-shadow-lg shadow-2xl flex items-center gap-3 active:scale-90 transition-transform"
          >
            <ShoppingCart className="w-6 h-6" />
            Sipariş Ver
          </button>
        </div>
      )}
    </div>
  );
}

