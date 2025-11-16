import { useEffect, useState } from 'react';
import { masalarApi } from '../lib/api';
import { Plus, Edit, Trash2, QrCode } from 'lucide-react';

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
  const [formData, setFormData] = useState({
    masa_adi: '',
    kapasite: '4',
    pozisyon_x: '',
    pozisyon_y: '',
  });

  useEffect(() => {
    loadMasalar();
  }, []);

  const loadMasalar = async () => {
    try {
      const response = await masalarApi.list();
      setMasaItems(response.data || []);
    } catch (err) {
      console.error('Masalar yüklenemedi:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await masalarApi.add({
        masa_adi: formData.masa_adi,
        kapasite: parseInt(formData.kapasite),
        pozisyon_x: formData.pozisyon_x ? parseFloat(formData.pozisyon_x) : undefined,
        pozisyon_y: formData.pozisyon_y ? parseFloat(formData.pozisyon_y) : undefined,
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
    if (!confirm('Bu masayı silmek istediğinizden emin misiniz?')) {
      return;
    }
    try {
      await masalarApi.delete(id);
      loadMasalar();
    } catch (err) {
      console.error('Masa silinemedi:', err);
      alert('Hata: Masa silinemedi');
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
    setFormData({
      masa_adi: '',
      kapasite: '4',
      pozisyon_x: '',
      pozisyon_y: '',
    });
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
      alert('QR kod URL\'si kopyalandı!');
    }
  };

  const getDurumRenk = (durum: string) => {
    switch (durum) {
      case 'bos':
        return 'bg-green-500/20 text-green-300 border-green-500/30';
      case 'dolu':
        return 'bg-red-500/20 text-red-300 border-red-500/30';
      case 'rezerve':
        return 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30';
      case 'temizlik':
        return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
      default:
        return 'bg-gray-500/20 text-gray-300 border-gray-500/30';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold">Masa Yönetimi</h2>
        <button
          onClick={loadMasalar}
          className="px-4 py-2 bg-primary-900/40 hover:bg-primary-800/40 rounded-lg transition-colors text-accent-mist"
        >
          Yenile
        </button>
      </div>

      {/* Form */}
      <div className="card">
        <h3 className="text-xl font-semibold mb-4">
          {editing ? 'Masa Güncelle' : 'Yeni Masa Ekle'}
        </h3>
        
        <form onSubmit={editing ? handleUpdate : handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Masa Adı *</label>
              <input
                type="text"
                value={formData.masa_adi}
                onChange={(e) => setFormData({ ...formData, masa_adi: e.target.value })}
                required
                className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
                placeholder="Örn: Masa 1"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Kapasite *</label>
              <input
                type="number"
                min="1"
                max="20"
                value={formData.kapasite}
                onChange={(e) => setFormData({ ...formData, kapasite: e.target.value })}
                required
                className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
                placeholder="4"
              />
            </div>
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

      {/* Masa Listesi */}
      <div className="card">
        <h3 className="text-lg font-semibold mb-4">Masa Listesi ({masaItems.length} masa)</h3>

        {loading ? (
          <div className="text-center py-8 text-accent-mist/70">Yükleniyor...</div>
        ) : masaItems.length === 0 ? (
          <div className="text-center py-8 text-accent-mist/70">Henüz masa kaydı yok.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-primary-500/25">
                  <th className="py-3 px-4">Masa Adı</th>
                  <th className="py-3 px-4">Durum</th>
                  <th className="py-3 px-4">Kapasite</th>
                  <th className="py-3 px-4">QR Kod</th>
                  <th className="py-3 px-4 text-center">İşlemler</th>
                </tr>
              </thead>
              <tbody>
                {masaItems.map((masa) => (
                  <tr key={masa.id} className="border-b border-primary-500/10 hover:bg-primary-900/20">
                    <td className="py-3 px-4 font-semibold">{masa.masa_adi}</td>
                    <td className="py-3 px-4">
                      <select
                        value={masa.durum}
                        onChange={(e) => handleDurumChange(masa, e.target.value)}
                        className={`px-2 py-1 rounded border ${getDurumRenk(masa.durum)} focus:outline-none focus:ring-2 focus:ring-primary-400 cursor-pointer`}
                      >
                        <option value="bos">Boş</option>
                        <option value="dolu">Dolu</option>
                        <option value="rezerve">Rezerve</option>
                        <option value="temizlik">Temizlik</option>
                      </select>
                    </td>
                    <td className="py-3 px-4">{masa.kapasite} kişi</td>
                    <td className="py-3 px-4">
                      {masa.qr_code && (
                        <button
                          onClick={() => copyQRCodeURL(masa.qr_code)}
                          className="flex items-center gap-2 px-2 py-1 bg-primary-900/40 hover:bg-primary-800/40 rounded transition-colors"
                          title="QR kodu kopyala"
                        >
                          <QrCode className="w-4 h-4" />
                          <span className="text-xs">{masa.qr_code.substring(0, 8)}...</span>
                        </button>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-center gap-2">
                        <button
                          onClick={() => handleEdit(masa)}
                          className="p-1 hover:bg-primary-600/20 rounded transition-colors"
                          title="Düzenle"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(masa.id)}
                          className="p-1 hover:bg-tertiary-500/20 rounded transition-colors text-tertiary-300"
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
    </div>
  );
}

