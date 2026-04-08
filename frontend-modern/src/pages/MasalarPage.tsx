import { useEffect, useState, useRef } from 'react';
import { masalarApi, normalizeApiUrl } from '../lib/api';
import { useWebSocket } from '../hooks/useWebSocket';
import { Edit, Trash2, LayoutGrid, List, GripHorizontal, Check, QrCode } from 'lucide-react';

interface MasaItem {
  id: number;
  masa_adi: string;
  qr_code: string | null;
  durum: string;
  kapasite: number;
  pozisyon_x: number | null;
  pozisyon_y: number | null;
}

export default function MasalarPage() {
  const [masaItems, setMasaItems] = useState<MasaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<MasaItem | null>(null);
  const [viewMode, setViewMode] = useState<'canvas' | 'list'>('canvas');
  const [isEditMode, setIsEditMode] = useState(false);
  
  const [formData, setFormData] = useState({
    masa_adi: '',
    kapasite: '4',
    pozisyon_x: '',
    pozisyon_y: '',
  });

  const canvasRef = useRef<HTMLDivElement>(null);
  const [draggedMasa, setDraggedMasa] = useState<MasaItem | null>(null);
  const [offset, setOffset] = useState({ x: 0, y: 0 });

  const API_BASE_URL = normalizeApiUrl(import.meta.env.VITE_API_URL as string);
  const WS_URL = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://') + '/ws/connect/auth';

  useWebSocket({
    url: WS_URL,
    topics: ['kitchen', 'orders', 'cashier'],
    auth: true,
    onMessage: (data) => {
      // Sipariş eklendiğinde, durum değiştiğinde (masa dolu/boş/rezerve vs.) tabloyu canlı yenile
      if (data.type === 'new_order' || data.type === 'status_change' || data.type === 'table_transfer' || data.type === 'masa_status_change') {
        loadMasalar();
      }
    }
  });

  useEffect(() => {
    loadMasalar();
  }, []);

  const loadMasalar = async () => {
    try {
      setLoading(true);
      const response = await masalarApi.list();
      setMasaItems(response.data || []);
    } catch (err) {
      console.error('Masalar yüklenemedi:', err);
    } finally {
      setLoading(false);
    }
  };

  const savePositions = async () => {
    try {
      // Toplu kaydetme simülasyonu
      const promises = masaItems.map((masa) =>
        masalarApi.update({
          id: masa.id,
          pozisyon_x: masa.pozisyon_x === null ? undefined : masa.pozisyon_x,
          pozisyon_y: masa.pozisyon_y === null ? undefined : masa.pozisyon_y,
          durum: masa.durum,
        })
      );
      await Promise.all(promises);
      setIsEditMode(false);
      alert('Kroki başarıyla kaydedildi!');
    } catch (err) {
      console.error('Kroki kaydedilemedi', err);
      alert('Kroki kaydedilirken hata oluştu.');
    }
  };

  const handleMouseDown = (e: React.MouseEvent, masa: MasaItem) => {
    if (!isEditMode) return;
    
    // Default drag behavior'u engelle
    e.preventDefault();
    
    const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
    const parentRect = canvasRef.current?.getBoundingClientRect();
    
    if (!parentRect) return;

    // Farenin kart içindeki tıklandığı noktanın offsetsi
    setOffset({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
    setDraggedMasa(masa);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isEditMode || !draggedMasa || !canvasRef.current) return;
    
    const parentRect = canvasRef.current.getBoundingClientRect();
    
    // Yeni koordinatları hesapla (Yüzdeliğe vurarak duyarlı hale getiriyoruz)
    let newX = ((e.clientX - parentRect.left - offset.x) / parentRect.width) * 100;
    let newY = ((e.clientY - parentRect.top - offset.y) / parentRect.height) * 100;

    // Sınırları aşmasını engelle
    newX = Math.max(0, Math.min(newX, 90)); // %90 cıvarından fazla gitmesin
    newY = Math.max(0, Math.min(newY, 90));

    setMasaItems((prev) =>
      prev.map((m) =>
        m.id === draggedMasa.id
          ? { ...m, pozisyon_x: newX, pozisyon_y: newY }
          : m
      )
    );
  };

  const handleMouseUp = () => {
    setDraggedMasa(null);
  };

  // Kroki sınırları dışına çıkıldığında bırak
  const handleMouseLeave = () => {
    if (draggedMasa) setDraggedMasa(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await masalarApi.add({
        masa_adi: formData.masa_adi,
        kapasite: parseInt(formData.kapasite),
        // Yeni eklenen masayı ekranın ortasına koy
        pozisyon_x: formData.pozisyon_x ? parseFloat(formData.pozisyon_x) : 40 + Math.random() * 10,
        pozisyon_y: formData.pozisyon_y ? parseFloat(formData.pozisyon_y) : 40 + Math.random() * 10,
      });
      resetForm();
      loadMasalar();
    } catch (err: any) {
      console.error('Masa eklenemedi:', err);
      alert(err.response?.data?.detail || 'Hata: Masa eklenemedi');
    }
  };

  const handleEdit = (item: MasaItem) => {
    setEditing(item);
    setFormData({
      masa_adi: item.masa_adi,
      kapasite: String(item.kapasite),
      pozisyon_x: item.pozisyon_x ? String(item.pozisyon_x) : '',
      pozisyon_y: item.pozisyon_y ? String(item.pozisyon_y) : '',
    });
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editing) return;
    try {
      await masalarApi.update({
        id: editing.id,
        masa_adi: formData.masa_adi,
        kapasite: parseInt(formData.kapasite),
        pozisyon_x: formData.pozisyon_x ? parseFloat(formData.pozisyon_x) : undefined,
        pozisyon_y: formData.pozisyon_y ? parseFloat(formData.pozisyon_y) : undefined,
      });
      resetForm();
      loadMasalar();
    } catch (err: any) {
      console.error('Masa güncellenemedi:', err);
      alert(err.response?.data?.detail || 'Hata: Masa güncellenemedi');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Bu masayı silmek istediğinizden emin misiniz?')) return;
    try {
      await masalarApi.delete(id);
      loadMasalar();
    } catch (err) {
      console.error('Masa silinemedi:', err);
    }
  };

  const handleDurumChange = async (masa: MasaItem, yeniDurum: string) => {
    try {
      await masalarApi.update({ id: masa.id, durum: yeniDurum });
      loadMasalar();
    } catch (err) {
      console.error('Masa durumu güncellenemedi:', err);
    }
  };

  const resetForm = () => {
    setEditing(null);
    setFormData({ masa_adi: '', kapasite: '4', pozisyon_x: '', pozisyon_y: '' });
  };

  const getQRCodeURL = (qr_code: string | null) => {
    if (!qr_code) return null;
    const baseURL = window.location.origin;
    return `${baseURL}/musteri?qr=${qr_code}`;
  };

  const copyQRCodeURL = (qr_code: string | null) => {
    const url = getQRCodeURL(qr_code);
    if (url) {
      navigator.clipboard.writeText(url);
      alert("QR Kod bağlantısı başarıyla panoya kopyalandı!");
    }
  };

  const getDurumTheme = (durum: string) => {
    switch (durum) {
      case 'dolu':
        return { 
          bg: 'bg-rose-500/20', border: 'border-rose-500/40', text: 'text-rose-300', shadow: 'shadow-[0_0_15px_rgba(244,63,94,0.3)]', indicator: 'bg-rose-500' 
        };
      case 'rezerve':
        return { 
          bg: 'bg-amber-500/20', border: 'border-amber-500/40', text: 'text-amber-300', shadow: 'shadow-[0_0_15px_rgba(245,158,11,0.3)]', indicator: 'bg-amber-500' 
        };
      case 'temizlik':
        return { 
          bg: 'bg-cyan-500/20', border: 'border-cyan-500/40', text: 'text-cyan-300', shadow: 'shadow-[0_0_15px_rgba(6,182,212,0.3)]', indicator: 'bg-cyan-500' 
        };
      default: // bos
        return { 
          bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-300', shadow: 'hover:shadow-[0_0_15px_rgba(16,185,129,0.2)]', indicator: 'bg-emerald-500' 
        };
    }
  };

  return (
    <div className="space-y-8">
      
      {/* ÜST GÖSTERGE VE KONTROLLER (GLASSMORPHISM) */}
      <div className="premium-card relative overflow-hidden rounded-3xl p-8 md:p-10">
        <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/10 blur-[100px] rounded-full -mr-32 -mt-32" />
        <div className="relative flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <h2 className="text-4xl font-bold text-white tracking-tight">Kroki & <span className="text-gradient">Yerleşim</span></h2>
            <p className="text-slate-400 font-medium">İşletmenizin fiziksel yapısını ve masa durumlarını gerçek zamanlı tasarlayın.</p>
          </div>
        
          <div className="flex bg-slate-900/50 p-1.5 rounded-2xl border border-slate-700/50">
            <button 
              onClick={() => setViewMode('canvas')}
              className={`flex items-center gap-2 px-6 py-2.5 rounded-xl transition-all duration-300 font-bold ${viewMode === 'canvas' ? 'bg-emerald-500 text-white shadow-[0_0_20px_rgba(16,185,129,0.3)]' : 'text-slate-400 hover:text-white hover:bg-white/5'}`}
            >
              <LayoutGrid className="w-5 h-5" />
              Kroki
            </button>
            <button 
              onClick={() => setViewMode('list')}
              className={`flex items-center gap-2 px-6 py-2.5 rounded-xl transition-all duration-300 font-bold ${viewMode === 'list' ? 'bg-emerald-500 text-white shadow-[0_0_20px_rgba(16,185,129,0.3)]' : 'text-slate-400 hover:text-white hover:bg-white/5'}`}
            >
              <List className="w-5 h-5" />
              Liste
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
        
        {/* SOL: MASA EKLEME / KONTROL PANELİ */}
        <div className="xl:col-span-1 space-y-6">
          <div className="premium-card rounded-2xl p-8">
            <h3 className="text-xl font-bold text-white mb-8 flex items-center gap-3">
              <span className="w-1.5 h-6 bg-emerald-500 rounded-full"></span>
              {editing ? 'Masayı Düzenle' : 'Masa Oluştur'}
            </h3>
            
            <form onSubmit={editing ? handleUpdate : handleSubmit} className="space-y-5">
              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase tracking-widest mb-3">Masa Adı / Kodu</label>
                <input
                  type="text"
                  value={formData.masa_adi}
                  onChange={(e) => setFormData({ ...formData, masa_adi: e.target.value })}
                  required
                  className="w-full"
                  placeholder="Örn: M-01"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-white/70 mb-2">Maksimum Kapasite</label>
                <div className="flex items-center bg-black/30 border border-white/10 rounded-xl px-2">
                  <input
                    type="number"
                    min="1"
                    max="20"
                    value={formData.kapasite}
                    onChange={(e) => setFormData({ ...formData, kapasite: e.target.value })}
                    required
                    className="w-full px-2 py-3 bg-transparent focus:outline-none text-white text-center font-bold text-lg"
                  />
                  <span className="text-white/40 font-medium pr-3">Kişi</span>
                </div>
              </div>
              
              <div className="pt-4 flex gap-4">
                <button
                  type="submit"
                  className="glow-button flex-1 py-3 rounded-xl font-bold text-white transition-all"
                >
                  {editing ? 'Güncelle' : 'Ekle'}
                </button>
                {editing && (
                  <button
                    type="button"
                    onClick={resetForm}
                    className="flex-1 py-3 bg-white/5 hover:bg-white/10 border border-slate-700 rounded-xl font-bold text-slate-300 transition-all"
                  >
                    İptal
                  </button>
                )}
              </div>
            </form>
          </div>

          {/* İstatistikler */}
          <div className="premium-card rounded-2xl p-6">
            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-6">Masa Stok Durumu</h4>
            <div className="space-y-6">
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-3">
                  <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.8)]"></div>
                  <span className="text-slate-300 font-medium">Müsait</span>
                </div>
                <span className="text-2xl font-bold text-white">{masaItems.filter(m=>m.durum === 'bos').length}</span>
              </div>
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-3">
                  <div className="w-2.5 h-2.5 rounded-full bg-rose-500 shadow-[0_0_10px_rgba(244,63,94,0.8)]"></div>
                  <span className="text-slate-300 font-medium">Dolu</span>
                </div>
                <span className="text-2xl font-bold text-white">{masaItems.filter(m=>m.durum === 'dolu').length}</span>
              </div>
            </div>
          </div>
        </div>

        {/* SAĞ: KROKİ VEYA LİSTE ALANI */}
        <div className="xl:col-span-3">
          {loading ? (
            <div className="w-full h-96 flex items-center justify-center bg-white/[0.02] border border-white/5 rounded-2xl">
              <div className="text-primary-400 font-medium animate-pulse text-lg">Yükleniyor...</div>
            </div>
          ) : viewMode === 'canvas' ? (
            
            /* KROKİ (SPATIAL CANVAS) VIEW */
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <div className="text-white/70 text-sm">
                  {isEditMode 
                    ? "Tasarım Modu: Masaları sürükleyip bırakarak dükkan yerleşimini tasarlayabilirsiniz."
                    : "Canlı İzleme: Masaların üzerindeki durumları anında takip edin."
                  }
                </div>
                <button
                  onClick={() => isEditMode ? savePositions() : setIsEditMode(true)}
                  className={`flex items-center gap-2 px-6 py-2.5 rounded-xl font-bold transition-all ${
                    isEditMode 
                    ? 'bg-amber-500 hover:bg-amber-400 text-slate-900 shadow-lg shadow-amber-500/30 animate-pulse-slight' 
                    : 'bg-white/10 hover:bg-white/20 text-white'
                  }`}
                >
                  {isEditMode ? <Check className="w-5 h-5"/> : <GripHorizontal className="w-5 h-5"/>}
                  {isEditMode ? 'Yerleşimi Kaydet' : 'Krokiyi Düzenle'}
                </button>
              </div>

              {/* KROKİ ALANI */}
              <div 
                ref={canvasRef}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseLeave}
                className="relative bg-[#0b0f19] border border-white/10 rounded-2xl shadow-2xl overflow-hidden touch-none"
                style={{ height: '700px', backgroundImage: 'radial-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px)', backgroundSize: '30px 30px' }}
              >
                {/* Zemin Işığı */}
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-3/4 h-3/4 bg-primary-500/5 blur-[120px] rounded-full pointer-events-none"></div>

                {masaItems.map((masa) => {
                  const theme = getDurumTheme(masa.durum);
                  const isDragging = draggedMasa?.id === masa.id;
                  
                  return (
                    <div
                      key={masa.id}
                      onMouseDown={(e) => handleMouseDown(e, masa)}
                      className={`absolute select-none transition-all ${isEditMode ? 'cursor-grab active:cursor-grabbing hover:scale-105' : 'cursor-pointer hover:-translate-y-1'} ${
                        isDragging ? 'scale-110 z-50 opacity-90' : 'z-10'
                      }`}
                      style={{
                        left: `${masa.pozisyon_x ?? 10}%`,
                        top: `${masa.pozisyon_y ?? 10}%`,
                        // Transition smooth effect unless dragging
                        transitionDuration: isDragging ? '0ms' : '300ms',
                        transitionProperty: 'top, left, transform',
                      }}
                    >
                      {/* 3D Glass Masa Kartı */}
                      <div className={`relative flex flex-col w-28 sm:w-32 bg-black/40 backdrop-blur-xl border rounded-2xl overflow-hidden ${theme.border} ${isEditMode ? 'shadow-2xl' : theme.shadow}`}>
                        
                        {/* Durum Renk Bıçağı (Üst Çizgi) */}
                        <div className={`h-1 w-full ${theme.indicator}`}></div>

                        <div className="p-3 pb-4 text-center">
                          <h4 className="font-extrabold text-white text-lg tracking-tight truncate drop-shadow-md pr-4">
                            {masa.masa_adi}
                          </h4>
                          
                          <div className={`mt-1 text-xs font-semibold px-2 py-0.5 rounded-full inline-block ${theme.bg} ${theme.text}`}>
                            {masa.durum.toUpperCase()}
                          </div>
                          
                          {masa.qr_code && !isEditMode && (
                            <button
                              onClick={(e) => { e.stopPropagation(); copyQRCodeURL(masa.qr_code); }}
                              className="absolute top-1 right-1 text-white/30 hover:text-white transition-colors p-1"
                              title="QR Link Kopyala"
                            >
                              <QrCode className="w-5 h-5" />
                            </button>
                          )}

                          {/* Kapasite */}
                          <div className="absolute bottom-1 right-2 text-[10px] font-bold text-white/30">
                            {masa.kapasite}P
                          </div>
                        </div>

                        {/* Canlı Sistemse Durum Seçici Göster (Eğer düzenleme modunda değilse) */}
                        {!isEditMode && (
                          <div className="px-2 pb-2">
                             <select
                                value={masa.durum}
                                onChange={(e) => handleDurumChange(masa, e.target.value)}
                                className={`w-full text-xs font-bold bg-white/5 border border-white/10 rounded px-1 py-1 focus:outline-none ${theme.text} cursor-pointer appearance-none text-center`}
                                style={{ textAlignLast: 'center' }}
                              >
                                <option value="bos" className="text-black">Boş</option>
                                <option value="dolu" className="text-black">Dolu</option>
                                <option value="rezerve" className="text-black">Rezerve</option>
                                <option value="temizlik" className="text-black">Temizlik</option>
                              </select>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            
            /* LİSTE GÖRÜNÜMÜ */
            <div className="premium-card rounded-2xl p-8">
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="border-b border-slate-700/50">
                      <th className="py-4 px-4 text-xs font-bold text-slate-500 uppercase tracking-widest">Masa Adı</th>
                      <th className="py-4 px-4 text-xs font-bold text-slate-500 uppercase tracking-widest">Durum</th>
                      <th className="py-4 px-4 text-xs font-bold text-slate-500 uppercase tracking-widest">Kapasite</th>
                      <th className="py-4 px-4 text-xs font-bold text-slate-500 uppercase tracking-widest">QR Kod</th>
                      <th className="py-4 px-4 text-xs font-bold text-slate-500 uppercase tracking-widest text-right">İşlemler</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/30">
                    {masaItems.map((masa) => {
                      const theme = getDurumTheme(masa.durum);
                      return (
                        <tr key={masa.id} className="border-b border-white/5 hover:bg-white/5 transition-colors group">
                          <td className="py-4 px-4">
                            <span className="font-bold text-white text-lg">{masa.masa_adi}</span>
                          </td>
                          <td className="py-4 px-4">
                            <select
                              value={masa.durum}
                              onChange={(e) => handleDurumChange(masa, e.target.value)}
                              className={`px-3 py-1.5 rounded-lg border font-semibold text-sm ${theme.bg} ${theme.text} ${theme.border} focus:outline-none cursor-pointer appearance-none text-center`}
                            >
                              <option value="bos" className="text-black">Boş</option>
                              <option value="dolu" className="text-black">Dolu</option>
                              <option value="rezerve" className="text-black">Rezerve</option>
                              <option value="temizlik" className="text-black">Temizlik</option>
                            </select>
                          </td>
                          <td className="py-4 px-4 text-white/70 font-medium">{masa.kapasite} Kişilik</td>
                          <td className="py-4 px-4">
                            {masa.qr_code ? (
                              <button onClick={() => copyQRCodeURL(masa.qr_code)} className="flex items-center gap-2 px-3 py-1.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg transition-colors text-white/70" title="QR Kopyala">
                                <QrCode className="w-4 h-4" />
                              </button>
                            ) : (
                              <span className="text-white/30 text-sm">-</span>
                            )}
                          </td>
                          <td className="py-4 px-4">
                            <div className="flex items-center justify-center gap-3 opacity-50 group-hover:opacity-100 transition-opacity">
                              <button onClick={() => handleEdit(masa)} className="p-2 bg-white/5 hover:bg-blue-500/20 text-blue-400 rounded-lg transition-colors">
                                <Edit className="w-4 h-4" />
                              </button>
                              <button onClick={() => handleDelete(masa.id)} className="p-2 bg-white/5 hover:bg-rose-500/20 text-rose-400 rounded-lg transition-colors">
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
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
