import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, ShoppingCart } from 'lucide-react';
import { publicMenuApi } from '../lib/api';

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
  const [masaLoading, setMasaLoading] = useState(false);
  const [masaError, setMasaError] = useState('');

  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [categories, setCategories] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  useEffect(() => {
    const loadMasaFromQR = async () => {
      if (!qrCode) return;
      try {
        setMasaLoading(true);
        setMasaError('');
        const API_BASE_URL = (import.meta.env?.VITE_API_URL as string) || 'http://localhost:8000';
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
      } catch (err) {
        console.error('QR kod masa bilgisi yüklenemedi:', err);
        setMasaError('Masa bilgisi alınamadı. Varsayılan menü gösteriliyor.');
        if (subeId === undefined) {
          setSubeId(1);
        }
      } finally {
        setMasaLoading(false);
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

  const API_BASE_URL = (import.meta.env?.VITE_API_URL as string) || 'http://localhost:8000';
  const resolveImageUrl = (url?: string) => {
    if (!url) return '';
    if (url.startsWith('http://') || url.startsWith('https://')) return url;
    const base = API_BASE_URL.replace(/\/$/, '');
    const path = url.startsWith('/') ? url : `/${url}`;
    return `${base}${path}`;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-900 via-primary-800 to-primary-900 text-white">
      {/* Header */}
      <div className="relative overflow-hidden border-b border-white/10">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.15),_transparent_55%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_bottom,_rgba(56,189,248,0.12),_transparent_60%)]" />
        <div className="relative max-w-6xl mx-auto px-3 py-3 md:px-4 md:py-6 flex flex-col gap-3 md:gap-6">
          <div className="flex items-start gap-2 md:gap-4">
            <button
              onClick={handleBack}
              className="p-1.5 md:p-2 rounded-full bg-white/10 hover:bg-white/20 transition-colors"
              aria-label="Geri dön"
            >
              <ArrowLeft className="w-4 h-4 md:w-5 md:h-5" />
            </button>
            <div className="flex-1 space-y-2 md:space-y-3">
              <div className="flex flex-wrap items-center gap-2 md:gap-3">
                <h1 className="text-xl md:text-3xl lg:text-4xl font-bold tracking-tight">Neso Menü</h1>
                <span className="px-2 py-0.5 md:px-3 md:py-1 text-xs font-semibold rounded-full bg-white/10 border border-white/15">
                  Şefin Önerileri
                </span>
              </div>
              <p className="text-xs md:text-sm lg:text-base text-white/70 leading-relaxed max-w-3xl hidden md:block">
                Günün en sevilen lezzetlerini keşfedin. Seçtiğiniz ürünleri doğrudan asistanımıza ileterek sipariş verebilir veya menüyü incelemeye devam edebilirsiniz.
              </p>
              <div className="flex flex-wrap gap-1.5 md:gap-3 text-xs">
                {masaLoading ? (
                  <span className="px-3 py-1 rounded-full bg-white/5 border border-white/10">
                    Masa bilgisi yükleniyor...
                  </span>
                ) : (
                  masa && (
                    <span className="px-3 py-1 rounded-full bg-primary-900/60 border border-primary-400/40 text-primary-100">
                      Masa: {masa}
                    </span>
                  )
                )}
                {subeId && (
                  <span className="px-3 py-1 rounded-full bg-white/5 border border-white/10 text-white/70">
                    Şube #{subeId}
                  </span>
                )}
                {masaError && (
                  <span className="px-3 py-1 rounded-full bg-tertiary-500/20 border border-tertiary-400/40 text-tertiary-200">
                    {masaError}
                  </span>
                )}
              </div>
            </div>
            <button
              onClick={handleOrderViaChat}
              className="px-5 py-3 bg-gradient-to-r from-secondary-500 via-secondary-400 to-quaternary-400 hover:from-secondary-500/90 hover:to-quaternary-400/90 rounded-xl transition-all shadow-xl shadow-secondary-900/30 flex items-center gap-2 font-semibold"
            >
              <ShoppingCart className="w-5 h-5" />
              Sipariş Ver
            </button>
          </div>
        </div>
      </div>

      {/* Category Filter */}
      {categories.length > 0 && (
        <div className="bg-white/5 border-b border-white/10 backdrop-blur-sm">
          <div className="max-w-6xl mx-auto px-4 py-4">
            <div className="flex gap-2 overflow-x-auto hide-scrollbar pb-1">
              <button
                onClick={() => setSelectedCategory(null)}
                className={`flex-shrink-0 px-4 py-2 rounded-full transition-all border ${
                  selectedCategory === null
                    ? 'bg-gradient-to-r from-secondary-500 via-secondary-400 to-quaternary-400 text-primary-950 border-transparent shadow-lg shadow-secondary-900/30'
                    : 'bg-white/10 text-white/80 border-white/10 hover:bg-white/15'
                }`}
              >
                Tümü
              </button>
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={`flex-shrink-0 px-4 py-2 rounded-full transition-all border ${
                    selectedCategory === cat
                      ? 'bg-gradient-to-r from-secondary-500 via-secondary-400 to-quaternary-400 text-primary-950 border-transparent shadow-lg shadow-secondary-900/30'
                      : 'bg-white/10 text-white/80 border-white/10 hover:bg-white/15'
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
          {loading ? (
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
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                  {items.map((item) => (
                    <div
                      key={item.id}
                      className="group relative overflow-hidden rounded-2xl border border-white/10 bg-white/5 backdrop-blur-sm transition-all hover:-translate-y-1 hover:border-secondary-400/80 hover:bg-secondary-900/30"
                    >
                      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.12),_transparent_55%)]" />
                      <div className="relative p-6 space-y-4">
                        {item.gorsel_url && (
                          <div className="overflow-hidden rounded-xl border border-white/10">
                            <img
                              src={resolveImageUrl(item.gorsel_url)}
                              alt={`${item.ad} görseli`}
                              className="w-full h-40 object-cover transition-transform duration-300 group-hover:scale-105"
                              loading="lazy"
                              onError={(e) => {
                                console.error('Görsel yüklenemedi:', item.gorsel_url, 'Resolved URL:', resolveImageUrl(item.gorsel_url));
                                (e.target as HTMLImageElement).style.display = 'none';
                              }}
                            />
                          </div>
                        )}
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <h3 className="text-xl font-semibold tracking-tight text-white">
                              {item.ad}
                            </h3>
                            {item.aciklama && (
                              <p className="text-sm text-white/60 mt-1 leading-relaxed">
                                {item.aciklama}
                              </p>
                            )}
                          </div>
                          <span className="px-3 py-1 rounded-full bg-secondary-500/20 text-secondary-100 font-semibold border border-secondary-400/40">
                            {item.fiyat.toFixed(2)} ₺
                          </span>
                        </div>
                        {item.varyasyonlar && item.varyasyonlar.length > 0 && (
                          <div className="space-y-2 pt-2 border-t border-white/10">
                            <div className="text-xs font-semibold text-white/70 uppercase tracking-wide">
                              Varyasyonlar:
                            </div>
                            <div className="flex flex-wrap gap-2">
                              {item.varyasyonlar.map((variation: Varyasyon) => (
                                <span
                                  key={variation.id}
                                  className="px-2 py-1 rounded-lg bg-white/10 text-white/90 text-xs border border-white/20"
                                >
                                  {variation.ad} (+{variation.ek_fiyat.toFixed(2)} ₺)
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                        <div className="flex items-center justify-between text-xs text-white/50">
                          <span className="flex items-center gap-1">
                            <span className="inline-block h-2 w-2 rounded-full bg-secondary-300" />
                            Hazırlanma süresi: 5-10 dk
                          </span>
                          <span className="uppercase tracking-widest text-white/40">
                            {category}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Bottom CTA */}
      <div className="fixed bottom-4 right-4">
        <button
          onClick={handleOrderViaChat}
          className="px-6 py-3 bg-gradient-to-r from-secondary-500 via-secondary-400 to-quaternary-400 hover:from-secondary-500/90 hover:to-quaternary-400/90 rounded-full shadow-2xl shadow-secondary-900/30 flex items-center gap-2 font-semibold transition-transform hover:scale-105"
        >
          <ShoppingCart className="w-5 h-5" />
          Sipariş Ver
        </button>
      </div>
    </div>
  );
}

