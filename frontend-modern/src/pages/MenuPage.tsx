import { ChangeEvent, FormEvent, useEffect, useState, useRef } from 'react';
import { menuApi, menuVaryasyonlarApi } from '../lib/api';
import { useAuthStore } from '../store/authStore';
import { Plus, Edit, Trash2, Settings, X, ChevronDown, Search, Tag, Image, Loader2, MinusCircle } from 'lucide-react';

interface MenuItem {
  id: number;
  ad: string;
  fiyat: number;
  kategori: string;
  aktif: boolean;
  aciklama?: string;
  gorsel_url?: string;
}

interface Varyasyon {
  id: number;
  menu_id: number;
  ad: string;
  ek_fiyat: number;
  sira: number;
  aktif: boolean;
}

export default function MenuPage() {
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<MenuItem | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('Tümü');
  const [formData, setFormData] = useState({
    ad: '',
    fiyat: '',
    kategori: '',
    aktif: true,
  });
  const [showNewCategoryInput, setShowNewCategoryInput] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [categoryDropdownOpen, setCategoryDropdownOpen] = useState(false);
  const [categorySearch, setCategorySearch] = useState('');
  const categoryDropdownRef = useRef<HTMLDivElement>(null);
  const [varyasyonModalOpen, setVaryasyonModalOpen] = useState<number | null>(null);
  const [varyasyonlar, setVaryasyonlar] = useState<Varyasyon[]>([]);
  const [varyasyonForm, setVaryasyonForm] = useState({ ad: '', ek_fiyat: '0' });
  const fileInputRefs = useRef<Record<number, HTMLInputElement | null>>({});
  const [uploadingId, setUploadingId] = useState<number | null>(null);
  const [tempVariations, setTempVariations] = useState<Array<{ ad: string; ek_fiyat: string }>>([]);
  const [variationDraft, setVariationDraft] = useState<{ ad: string; ek_fiyat: string }>({ ad: '', ek_fiyat: '0' });

  const API_BASE_URL = (import.meta.env?.VITE_API_URL as string) || 'http://localhost:8000';

  const resolveImageUrl = (url?: string) => {
    if (!url) return '';
    if (url.startsWith('http://') || url.startsWith('https://')) return url;
    const formattedBase = API_BASE_URL.replace(/\/$/, '');
    const formattedPath = url.startsWith('/') ? url : `/${url}`;
    return `${formattedBase}${formattedPath}`;
  };

  const { selectedTenantId } = useAuthStore();
  
  useEffect(() => {
    loadMenu();
  }, [selectedTenantId]); // Tenant değiştiğinde menu'yi yeniden yükle

  // Kategori dropdown dışına tıklandığında kapat
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (categoryDropdownRef.current && !categoryDropdownRef.current.contains(event.target as Node)) {
        setCategoryDropdownOpen(false);
        setCategorySearch('');
      }
    };
    if (categoryDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [categoryDropdownOpen]);

  const loadMenu = async () => {
    try {
      const response = await menuApi.list({ limit: 200 });
      setMenuItems(response.data || []);
    } catch (err) {
      console.error('Menü yüklenemedi:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleImageButtonClick = (id: number) => {
    const input = fileInputRefs.current[id];
    if (input) {
      input.click();
    }
  };

  const handleImageChange = async (id: number, event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploadingId(id);
    try {
      await menuApi.uploadImage(id, file);
      await loadMenu();
    } catch (err) {
      console.error('Görsel yüklenemedi:', err);
      alert('Hata: Görsel yüklenemedi');
    } finally {
      setUploadingId(null);
      event.target.value = '';
    }
  };

  const handleTempVariationAdd = () => {
    if (!variationDraft.ad.trim()) return;
    setTempVariations(prev => [
      ...prev,
      {
        ad: variationDraft.ad.trim(),
        ek_fiyat: variationDraft.ek_fiyat || '0',
      },
    ]);
    setVariationDraft({ ad: '', ek_fiyat: '0' });
  };

  const handleTempVariationRemove = (index: number) => {
    setTempVariations(prev => prev.filter((_, idx) => idx !== index));
  };

  const handleImageRemove = async (id: number) => {
    if (!confirm('Görseli kaldırmak istediğinize emin misiniz?')) return;
    setUploadingId(id);
    try {
      await menuApi.deleteImage(id);
      await loadMenu();
    } catch (err) {
      console.error('Görsel silinemedi:', err);
      alert('Hata: Görsel silinemedi');
    } finally {
      setUploadingId(null);
    }
  };

  const categories = ['Tümü', ...Array.from(new Set(menuItems.map(item => item.kategori).filter(Boolean)))];
  
  // Form için kullanılacak kategoriler (boş olmayanlar)
  const availableCategories = Array.from(new Set(menuItems.map(item => item.kategori).filter(Boolean))).sort();
  
  // Kategori arama filtresi
  const filteredCategories = availableCategories.filter(cat =>
    cat.toLowerCase().includes(categorySearch.toLowerCase())
  );

  const filteredItems = selectedCategory === 'Tümü'
    ? menuItems
    : menuItems.filter(item => item.kategori === selectedCategory);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    
    // Kategori kontrolü
    if (!formData.kategori || !formData.kategori.trim()) {
      alert('Lütfen bir kategori seçin veya yeni kategori ekleyin');
      setCategoryDropdownOpen(true);
      return;
    }
    
    // Dropdown'ı kapat
    setCategoryDropdownOpen(false);
    setCategorySearch('');
    
    try {
      if (editing && editing.id) {
        await menuApi.update(editing.id, {
          ad: formData.ad,
          fiyat: parseFloat(formData.fiyat),
          kategori: formData.kategori.trim(),
          aktif: formData.aktif,
        });
      } else {
        const response = await menuApi.add({
          ad: formData.ad,
          fiyat: parseFloat(formData.fiyat),
          kategori: formData.kategori.trim(),
          aktif: formData.aktif,
        });
        const created = response.data;
        if (created?.id && tempVariations.length > 0) {
          for (let i = 0; i < tempVariations.length; i += 1) {
            const variation = tempVariations[i];
            try {
              await menuVaryasyonlarApi.add({
                menu_id: created.id,
                ad: variation.ad,
                ek_fiyat: parseFloat(variation.ek_fiyat || '0'),
                sira: i,
              });
            } catch (varErr) {
              console.error('Varyasyon eklenemedi:', varErr);
            }
          }
        }
      }
      resetForm();
      loadMenu();
    } catch (err) {
      console.error('Menü kaydedilemedi:', err);
      alert('Hata: Menü kaydedilemedi');
    }
  };

  const handleEdit = (item: MenuItem) => {
    setEditing(item);
    setFormData({
      ad: item.ad,
      fiyat: String(item.fiyat),
      kategori: item.kategori,
      aktif: item.aktif,
    });
    setShowNewCategoryInput(false);
    setNewCategoryName('');
    setCategoryDropdownOpen(false);
    setCategorySearch('');
    setTempVariations([]);
    setVariationDraft({ ad: '', ek_fiyat: '0' });
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Bu ürünü silmek istediğinizden emin misiniz?')) return;
    try {
      await menuApi.delete(id);
      loadMenu();
    } catch (err) {
      console.error('Menü silinemedi:', err);
      alert('Hata: Menü silinemedi');
    }
  };

  const resetForm = () => {
    setEditing(null);
    setFormData({ ad: '', fiyat: '', kategori: '', aktif: true });
    setShowNewCategoryInput(false);
    setNewCategoryName('');
    setCategoryDropdownOpen(false);
    setCategorySearch('');
    setTempVariations([]);
    setVariationDraft({ ad: '', ek_fiyat: '0' });
  };

  const handleVaryasyonAç = async (menuId: number) => {
    setVaryasyonModalOpen(menuId);
    try {
      const response = await menuVaryasyonlarApi.list(menuId);
      setVaryasyonlar(response.data || []);
    } catch (err) {
      console.error('Varyasyonlar yüklenemedi:', err);
    }
  };

  const handleVaryasyonKapat = () => {
    setVaryasyonModalOpen(null);
    setVaryasyonlar([]);
    setVaryasyonForm({ ad: '', ek_fiyat: '0' });
  };

  const handleVaryasyonEkle = async () => {
    if (!varyasyonModalOpen || !varyasyonForm.ad) return;
    try {
      await menuVaryasyonlarApi.add({
        menu_id: varyasyonModalOpen,
        ad: varyasyonForm.ad,
        ek_fiyat: parseFloat(varyasyonForm.ek_fiyat) || 0,
        sira: 0,
      });
      setVaryasyonForm({ ad: '', ek_fiyat: '0' });
      await handleVaryasyonAç(varyasyonModalOpen);
    } catch (err) {
      console.error('Varyasyon eklenemedi:', err);
      alert('Hata: Varyasyon eklenemedi');
    }
  };

  const handleVaryasyonSil = async (varyasyonId: number) => {
    if (!confirm('Bu varyasyonu silmek istediğinizden emin misiniz?')) return;
    try {
      await menuVaryasyonlarApi.delete(varyasyonId);
      if (varyasyonModalOpen) {
        await handleVaryasyonAç(varyasyonModalOpen);
      }
    } catch (err) {
      console.error('Varyasyon silinemedi:', err);
      alert('Hata: Varyasyon silinemedi');
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('tr-TR', {
      style: 'currency',
      currency: 'TRY',
    }).format(value);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold">Menü Yönetimi</h2>
        <button
          onClick={loadMenu}
          className="px-4 py-2 bg-primary-900/40 hover:bg-primary-800/40 rounded-lg transition-colors text-accent-mist"
        >
          Yenile
        </button>
      </div>

      {/* Form */}
      <div className="card relative z-20">
        <h3 className="text-xl font-semibold mb-4">
          {editing ? 'Ürün Güncelle' : 'Yeni Ürün Ekle'}
        </h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Ürün Adı</label>
              <input
                type="text"
                value={formData.ad}
                onChange={(e) => setFormData({ ...formData, ad: e.target.value })}
                required
                className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
                placeholder="Örn: Latte"
              />
            </div>
            <div className="relative z-10">
              <label className="block text-sm font-medium mb-2">Kategori</label>
              <div className="relative" ref={categoryDropdownRef}>
                {/* Kategori Seçici Butonu */}
                <button
                  type="button"
                  onClick={() => {
                    setCategoryDropdownOpen(!categoryDropdownOpen);
                    setCategorySearch('');
                  }}
                  className={`w-full px-4 py-2.5 bg-primary-900/40 border ${
                    formData.kategori 
                      ? 'border-primary-400/50' 
                      : 'border-primary-500/25'
                  } rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist transition-all flex items-center justify-between hover:bg-primary-900/60 ${
                    categoryDropdownOpen ? 'ring-2 ring-primary-400 border-primary-400/50' : ''
                  }`}
                >
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    {formData.kategori ? (
                      <>
                        <Tag className="w-4 h-4 text-primary-400 flex-shrink-0" />
                        <span className="truncate font-medium">{formData.kategori}</span>
                      </>
                    ) : (
                      <span className="text-accent-mist/50">Kategori seçin veya yeni ekleyin</span>
                    )}
                  </div>
                  <ChevronDown 
                    className={`w-4 h-4 text-accent-mist/50 flex-shrink-0 transition-transform ${
                      categoryDropdownOpen ? 'rotate-180' : ''
                    }`} 
                  />
                </button>

                {/* Dropdown Menü */}
                {categoryDropdownOpen && (
                  <div className="absolute z-[9999] w-full mt-2 bg-primary-800 border border-primary-500/30 rounded-lg shadow-2xl overflow-hidden">
                    {/* Arama Kutusu */}
                    <div className="p-3 border-b border-primary-500/20">
                      <div className="relative">
                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-accent-mist/40" />
                        <input
                          type="text"
                          value={categorySearch}
                          onChange={(e) => setCategorySearch(e.target.value)}
                          onKeyDown={(e) => {
                            // Escape ile dropdown'ı kapat
                            if (e.key === 'Escape') {
                              setCategoryDropdownOpen(false);
                              setCategorySearch('');
                            }
                            // Enter ile ilk kategoriyi seç
                            if (e.key === 'Enter' && filteredCategories.length > 0 && !showNewCategoryInput) {
                              e.preventDefault();
                              setFormData({ ...formData, kategori: filteredCategories[0] });
                              setCategoryDropdownOpen(false);
                              setCategorySearch('');
                            }
                          }}
                          placeholder="Kategori ara..."
                          className="w-full pl-10 pr-4 py-2 bg-primary-900/60 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 text-sm"
                          autoFocus
                        />
                      </div>
                    </div>

                    {/* Kategori Listesi */}
                    <div className="max-h-60 overflow-y-auto">
                      {filteredCategories.length > 0 ? (
                        <div className="p-2">
                          {filteredCategories.map((cat) => (
                            <button
                              key={cat}
                              type="button"
                              onClick={() => {
                                setFormData({ ...formData, kategori: cat });
                                setCategoryDropdownOpen(false);
                                setCategorySearch('');
                              }}
                              className={`w-full px-3 py-2.5 rounded-lg text-left transition-all flex items-center gap-2 group ${
                                formData.kategori === cat
                                  ? 'bg-primary-600/50 text-white'
                                  : 'hover:bg-primary-700/40 text-accent-mist'
                              }`}
                            >
                              <Tag className={`w-4 h-4 flex-shrink-0 ${
                                formData.kategori === cat 
                                  ? 'text-primary-200' 
                                  : 'text-accent-mist/50 group-hover:text-primary-400'
                              }`} />
                              <span className="flex-1 truncate">{cat}</span>
                              {formData.kategori === cat && (
                                <div className="w-2 h-2 rounded-full bg-primary-300 flex-shrink-0" />
                              )}
                            </button>
                          ))}
                        </div>
                      ) : (
                        <div className="p-4 text-center text-accent-mist/50 text-sm">
                          {categorySearch ? (
                            <div className="space-y-2">
                              <p>Kategori bulunamadı</p>
                              <button
                                type="button"
                                onClick={() => {
                                  setShowNewCategoryInput(true);
                                  setNewCategoryName(categorySearch);
                                  setCategorySearch('');
                                }}
                                className="text-primary-400 hover:text-primary-300 text-sm underline"
                              >
                                "{categorySearch}" olarak yeni kategori ekle
                              </button>
                            </div>
                          ) : (
                            'Henüz kategori yok'
                          )}
                        </div>
                      )}

                      {/* Yeni Kategori Ekleme */}
                      {showNewCategoryInput ? (
                        <div className="p-3 border-t border-primary-500/20 bg-primary-900/30">
                          <div className="flex items-center gap-2 mb-2">
                            <Tag className="w-4 h-4 text-primary-400" />
                            <span className="text-sm font-medium text-accent-mist">Yeni Kategori</span>
                          </div>
                          <input
                            type="text"
                            value={newCategoryName}
                            onChange={(e) => setNewCategoryName(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && newCategoryName.trim()) {
                                e.preventDefault();
                                setFormData({ ...formData, kategori: newCategoryName.trim() });
                                setShowNewCategoryInput(false);
                                setNewCategoryName('');
                                setCategoryDropdownOpen(false);
                                setCategorySearch('');
                              } else if (e.key === 'Escape') {
                                setShowNewCategoryInput(false);
                                setNewCategoryName('');
                              }
                            }}
                            placeholder="Kategori adı girin..."
                            autoFocus
                            className="w-full px-3 py-2 bg-primary-900/60 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 text-sm mb-2"
                          />
                          <div className="flex gap-2">
                            <button
                              type="button"
                              onClick={() => {
                                if (newCategoryName.trim()) {
                                  setFormData({ ...formData, kategori: newCategoryName.trim() });
                                }
                                setShowNewCategoryInput(false);
                                setNewCategoryName('');
                                setCategoryDropdownOpen(false);
                                setCategorySearch('');
                              }}
                              className="flex-1 px-3 py-1.5 bg-primary-600 hover:bg-primary-700 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-1"
                            >
                              <Plus className="w-3 h-3" />
                              Ekle
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setShowNewCategoryInput(false);
                                setNewCategoryName('');
                              }}
                              className="px-3 py-1.5 bg-primary-900/40 hover:bg-primary-800/40 rounded-lg text-sm transition-colors"
                            >
                              <X className="w-3 h-3" />
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="p-2 border-t border-primary-500/20">
                          <button
                            type="button"
                            onClick={() => {
                              setShowNewCategoryInput(true);
                              setNewCategoryName('');
                              setCategorySearch('');
                            }}
                            className="w-full px-3 py-2.5 rounded-lg text-left transition-all flex items-center gap-2 hover:bg-primary-700/40 text-primary-400 hover:text-primary-300 group"
                          >
                            <div className="w-8 h-8 rounded-lg bg-primary-600/20 flex items-center justify-center group-hover:bg-primary-600/30 transition-colors">
                              <Plus className="w-4 h-4" />
                            </div>
                            <span className="font-medium">Yeni Kategori Ekle</span>
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
              
              {/* Seçili Kategoriyi Göster ve Kaldır */}
              {formData.kategori && !categoryDropdownOpen && (
                <div className="mt-2 flex items-center gap-2">
                  <div className="flex items-center gap-2 px-3 py-1.5 bg-primary-600/20 border border-primary-500/30 rounded-lg">
                    <Tag className="w-3.5 h-3.5 text-primary-400" />
                    <span className="text-sm text-accent-mist font-medium">{formData.kategori}</span>
                    <button
                      type="button"
                      onClick={() => setFormData({ ...formData, kategori: '' })}
                      className="ml-1 p-0.5 hover:bg-primary-700/40 rounded transition-colors"
                      title="Kategoriyi kaldır"
                    >
                      <X className="w-3 h-3 text-accent-mist/60 hover:text-accent-mist" />
                    </button>
                  </div>
                </div>
              )}
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Fiyat (TL)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={formData.fiyat}
                onChange={(e) => setFormData({ ...formData, fiyat: e.target.value })}
                required
                className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
                placeholder="0.00"
              />
            </div>
          </div>
          {!editing && (
            <div className="p-4 border border-primary-500/20 rounded-lg bg-primary-900/20 space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-semibold text-accent-mist">
                  Varyasyonlar (İsteğe bağlı)
                </h4>
                <span className="text-xs text-accent-mist/60">
                  Ürün kaydedildikten sonra varyasyonlar otomatik eklenir.
                </span>
              </div>
              <div className="flex flex-col md:flex-row gap-3">
                <input
                  type="text"
                  value={variationDraft.ad}
                  onChange={(e) => setVariationDraft({ ...variationDraft, ad: e.target.value })}
                  className="flex-1 px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
                  placeholder="Örn: Sade"
                />
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={variationDraft.ek_fiyat}
                  onChange={(e) => setVariationDraft({ ...variationDraft, ek_fiyat: e.target.value })}
                  className="w-full md:w-40 px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
                  placeholder="Ek fiyat"
                />
                <button
                  type="button"
                  onClick={handleTempVariationAdd}
                  className="px-4 py-2 bg-secondary-500/80 hover:bg-secondary-500 rounded-lg transition-colors flex items-center gap-2 text-primary-950 font-semibold"
                >
                  <Plus className="w-4 h-4" />
                  Varyasyon Ekle
                </button>
              </div>
              {tempVariations.length > 0 && (
                <div className="space-y-2">
                  {tempVariations.map((variation, index) => (
                    <div
                      key={`${variation.ad}-${variation.ek_fiyat}-${index}`}
                      className="flex items-center justify-between px-4 py-2 bg-primary-900/30 border border-primary-500/30 rounded-lg"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-medium text-accent-mist">{variation.ad}</span>
                        <span className="text-xs text-accent-mist/60">
                          {Number.parseFloat(variation.ek_fiyat || '0').toFixed(2)} ₺
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleTempVariationRemove(index)}
                        className="text-accent-mist/60 hover:text-accent-mist transition-colors"
                        title="Varyasyonu kaldır"
                      >
                        <MinusCircle className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="aktif"
              checked={formData.aktif}
              onChange={(e) => setFormData({ ...formData, aktif: e.target.checked })}
              className="w-4 h-4"
            />
            <label htmlFor="aktif" className="text-sm">Aktif</label>
          </div>
          <div className="flex gap-2">
            <button
              type="submit"
              className="px-6 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              {editing ? 'Güncelle' : 'Ekle'}
            </button>
            {editing && (
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

      {/* Menu List */}
      <div className="card relative z-0">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-semibold">Menü Listesi</h3>
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
            {selectedCategory === 'Tümü' ? 'Menü henüz güncellenmedi.' : `${selectedCategory} kategorisinde ürün bulunamadı.`}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/20">
                  <th className="text-left py-3 px-4">Ürün Adı</th>
                  <th className="text-left py-3 px-4">Kategori</th>
                  <th className="text-left py-3 px-4">Görsel</th>
                  <th className="text-right py-3 px-4">Fiyat</th>
                  <th className="text-center py-3 px-4">Durum</th>
                  <th className="text-right py-3 px-4">İşlemler</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item) => (
                  <tr key={item.id} className="border-b border-white/10 hover:bg-white/5">
                    <td className="py-3 px-4">{item.ad}</td>
                    <td className="py-3 px-4">{item.kategori}</td>
                    <td className="py-3 px-4">
                      {item.gorsel_url ? (
                        <img
                          src={resolveImageUrl(item.gorsel_url)}
                          alt={`${item.ad} görseli`}
                          className="w-14 h-14 rounded-lg object-cover border border-white/10"
                        />
                      ) : (
                        <span className="text-xs text-white/50">Görsel yok</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">{formatCurrency(item.fiyat)}</td>
                    <td className="py-3 px-4 text-center">
                      <span
                        className={`px-2 py-1 rounded text-xs ${
                          item.aktif
                            ? 'bg-green-500/20 text-green-300'
                            : 'bg-tertiary-500/20 text-tertiary-100'
                        }`}
                      >
                        {item.aktif ? 'Aktif' : 'Pasif'}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex justify-end gap-2">
                        <input
                          type="file"
                          accept="image/*"
                          className="hidden"
                          ref={(el) => {
                            fileInputRefs.current[item.id] = el;
                          }}
                          onChange={(e) => handleImageChange(item.id, e)}
                        />
                        <button
                          onClick={() => handleImageButtonClick(item.id)}
                          className="p-1 hover:bg-primary-800/30 rounded"
                          title="Görsel Yükle"
                        >
                          {uploadingId === item.id ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Image className="w-4 h-4" />
                          )}
                        </button>
                        {item.gorsel_url && (
                          <button
                            onClick={() => handleImageRemove(item.id)}
                            className="p-1 hover:bg-tertiary-500/20 rounded text-tertiary-100"
                            title="Görseli Sil"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                        <button
                          onClick={() => handleEdit(item)}
                          className="p-1 hover:bg-primary-800/30 rounded"
                          title="Düzenle"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleVaryasyonAç(item.id)}
                          className="p-1 hover:bg-blue-800/30 rounded"
                          title="Varyasyonlar"
                        >
                          <Settings className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(item.id)}
                          className="p-1 hover:bg-tertiary-500/20 rounded text-tertiary-100"
                          title="Sil"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Varyasyon Modal */}
      {varyasyonModalOpen && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={handleVaryasyonKapat}>
          <div className="card max-w-2xl w-full m-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-xl font-semibold mb-4">Varyasyonlar</h3>
            
            {/* Varyasyon Ekleme Formu */}
            <div className="mb-4 p-4 bg-primary-900/20 rounded-lg space-y-3">
              <div className="grid grid-cols-3 gap-3">
                <input
                  type="text"
                  value={varyasyonForm.ad}
                  onChange={(e) => setVaryasyonForm({ ...varyasyonForm, ad: e.target.value })}
                  className="col-span-2 px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist"
                  placeholder="Varyasyon adı (örn: Sade, Orta, Şekerli)"
                />
                <input
                  type="number"
                  step="0.01"
                  value={varyasyonForm.ek_fiyat}
                  onChange={(e) => setVaryasyonForm({ ...varyasyonForm, ek_fiyat: e.target.value })}
                  className="px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist"
                  placeholder="Ek Fiyat"
                />
              </div>
              <button
                onClick={handleVaryasyonEkle}
                className="w-full px-4 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors flex items-center justify-center gap-2"
              >
                <Plus className="w-4 h-4" />
                Varyasyon Ekle
              </button>
            </div>

            {/* Varyasyon Listesi */}
            <div className="space-y-2">
              {varyasyonlar.length === 0 ? (
                <div className="text-center py-4 text-white/50">Henüz varyasyon eklenmedi.</div>
              ) : (
                varyasyonlar.map((varia) => (
                  <div key={varia.id} className="flex items-center justify-between p-3 bg-primary-900/20 rounded-lg">
                    <div>
                      <span className="font-medium">{varia.ad}</span>
                      {varia.ek_fiyat > 0 && (
                        <span className="ml-2 text-sm text-green-300">+{formatCurrency(varia.ek_fiyat)}</span>
                      )}
                    </div>
                    <button
                      onClick={() => handleVaryasyonSil(varia.id)}
                      className="p-1 hover:bg-tertiary-500/20 rounded text-tertiary-100"
                      title="Sil"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))
              )}
            </div>

            <button
              onClick={handleVaryasyonKapat}
              className="mt-4 w-full px-4 py-2 bg-primary-900/40 hover:bg-primary-800/40 rounded-lg transition-colors text-accent-mist"
            >
              Kapat
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

