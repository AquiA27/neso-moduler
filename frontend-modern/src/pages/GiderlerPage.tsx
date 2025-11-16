import { useEffect, useState } from 'react';
import { giderlerApi } from '../lib/api';
import { Plus, Edit, Trash2 } from 'lucide-react';

interface GiderItem {
  id: number;
  kategori: string;
  aciklama: string | null;
  tutar: number;
  tarih: string;
  fatura_no: string | null;
  created_at: string;
}

export default function GiderlerPage() {
  const [giderItems, setGiderItems] = useState<GiderItem[]>([]);
  const [kategoriler, setKategoriler] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<GiderItem | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('Tümü');
  const [baslangicTarih, setBaslangicTarih] = useState<string>('');
  const [bitisTarih, setBitisTarih] = useState<string>('');
  const [formData, setFormData] = useState({
    kategori: '',
    aciklama: '',
    tutar: '',
    tarih: new Date().toISOString().split('T')[0],
    fatura_no: '',
  });

  useEffect(() => {
    loadGiderler();
    loadKategoriler();
  }, []);

  const loadGiderler = async () => {
    try {
      const params: any = {};
      if (baslangicTarih) params.baslangic_tarih = baslangicTarih;
      if (bitisTarih) params.bitis_tarih = bitisTarih;
      if (selectedCategory !== 'Tümü') params.kategori = selectedCategory;
      
      const response = await giderlerApi.list(params);
      setGiderItems(response.data || []);
    } catch (err) {
      console.error('Giderler yüklenemedi:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadKategoriler = async () => {
    try {
      const response = await giderlerApi.kategoriler();
      setKategoriler(response.data || []);
    } catch (err) {
      console.error('Kategoriler yüklenemedi:', err);
    }
  };

  useEffect(() => {
    loadGiderler();
  }, [selectedCategory, baslangicTarih, bitisTarih]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editing) {
        await giderlerApi.update({
          id: editing.id,
          kategori: formData.kategori,
          aciklama: formData.aciklama || undefined,
          tutar: parseFloat(formData.tutar),
          tarih: formData.tarih,
          fatura_no: formData.fatura_no || undefined,
        });
      } else {
        await giderlerApi.add({
          kategori: formData.kategori,
          aciklama: formData.aciklama || undefined,
          tutar: parseFloat(formData.tutar),
          tarih: formData.tarih,
          fatura_no: formData.fatura_no || undefined,
        });
      }
      resetForm();
      loadGiderler();
      loadKategoriler();
    } catch (err: any) {
      console.error('Gider eklenemedi:', err);
      alert(err.response?.data?.detail || 'Hata: Gider kaydedilemedi');
    }
  };

  const handleEdit = (item: GiderItem) => {
    setEditing(item);
    setFormData({
      kategori: item.kategori,
      aciklama: item.aciklama || '',
      tutar: String(item.tutar),
      tarih: item.tarih,
      fatura_no: item.fatura_no || '',
    });
  };

  const resetForm = () => {
    setEditing(null);
    setFormData({
      kategori: '',
      aciklama: '',
      tutar: '',
      tarih: new Date().toISOString().split('T')[0],
      fatura_no: '',
    });
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Bu gideri silmek istediğinizden emin misiniz?')) {
      return;
    }
    try {
      await giderlerApi.delete(id);
      loadGiderler();
    } catch (err) {
      console.error('Gider silinemedi:', err);
      alert('Hata: Gider silinemedi');
    }
  };

  const filteredKategoriler = ['Tümü', ...kategoriler];

  const toplamGider = giderItems.reduce((sum, item) => sum + item.tutar, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold">Gider Yönetimi</h2>
        <button
          onClick={loadGiderler}
          className="px-4 py-2 bg-primary-900/40 hover:bg-primary-800/40 rounded-lg transition-colors text-accent-mist"
        >
          Yenile
        </button>
      </div>

      {/* Form */}
      <div className="card">
        <h3 className="text-xl font-semibold mb-4">
          {editing ? 'Gider Güncelle' : 'Yeni Gider Ekle'}
        </h3>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Kategori *</label>
              <input
                type="text"
                value={formData.kategori}
                onChange={(e) => setFormData({ ...formData, kategori: e.target.value })}
                required
                className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
                placeholder="Örn: Kira, Malzeme, Maaş"
                list="kategori-list"
              />
              <datalist id="kategori-list">
                {kategoriler.map(kat => (
                  <option key={kat} value={kat} />
                ))}
              </datalist>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Tarih *</label>
              <input
                type="date"
                value={formData.tarih}
                onChange={(e) => setFormData({ ...formData, tarih: e.target.value })}
                required
                className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist transition-colors"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Tutar (TL) *</label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={formData.tutar}
                onChange={(e) => setFormData({ ...formData, tutar: e.target.value })}
                required
                className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
                placeholder="0.00"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Fatura No</label>
              <input
                type="text"
                value={formData.fatura_no}
                onChange={(e) => setFormData({ ...formData, fatura_no: e.target.value })}
                className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
                placeholder="Opsiyonel"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium mb-2">Açıklama</label>
              <input
                type="text"
                value={formData.aciklama}
                onChange={(e) => setFormData({ ...formData, aciklama: e.target.value })}
                className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
                placeholder="Gider açıklaması (opsiyonel)"
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

      {/* Filtreler */}
      <div className="card">
        <h3 className="text-lg font-semibold mb-4">Filtreler</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium mb-2">Kategori</label>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist"
            >
              {filteredKategoriler.map(kat => (
                <option key={kat} value={kat}>{kat}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Başlangıç Tarihi</label>
            <input
              type="date"
              value={baslangicTarih}
              onChange={(e) => setBaslangicTarih(e.target.value)}
              className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist transition-colors"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Bitiş Tarihi</label>
            <input
              type="date"
              value={bitisTarih}
              onChange={(e) => setBitisTarih(e.target.value)}
              className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist transition-colors"
            />
          </div>
        </div>
      </div>

      {/* Özet */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Gider Listesi</h3>
          <div className="text-xl font-bold text-neso-gold">
            Toplam: {toplamGider.toFixed(2)} ₺
          </div>
        </div>

        {loading ? (
          <div className="text-center py-8 text-accent-mist/70">Yükleniyor...</div>
        ) : giderItems.length === 0 ? (
          <div className="text-center py-8 text-accent-mist/70">Henüz gider kaydı yok.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-primary-500/25">
                  <th className="py-3 px-4">Tarih</th>
                  <th className="py-3 px-4">Kategori</th>
                  <th className="py-3 px-4">Açıklama</th>
                  <th className="py-3 px-4">Fatura No</th>
                  <th className="py-3 px-4 text-right">Tutar</th>
                  <th className="py-3 px-4 text-center">İşlemler</th>
                </tr>
              </thead>
              <tbody>
                {giderItems.map((item) => (
                  <tr key={item.id} className="border-b border-primary-500/10 hover:bg-primary-900/20">
                    <td className="py-3 px-4">{new Date(item.tarih).toLocaleDateString('tr-TR')}</td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-1 bg-primary-600/20 rounded text-xs">
                        {item.kategori}
                      </span>
                    </td>
                    <td className="py-3 px-4">{item.aciklama || '-'}</td>
                    <td className="py-3 px-4">{item.fatura_no || '-'}</td>
                    <td className="py-3 px-4 text-right font-semibold">{item.tutar.toFixed(2)} ₺</td>
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-center gap-2">
                        <button
                          onClick={() => handleEdit(item)}
                          className="p-1 hover:bg-primary-600/20 rounded transition-colors"
                          title="Düzenle"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(item.id)}
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


