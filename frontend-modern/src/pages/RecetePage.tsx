import { useEffect, useState } from 'react';
import { receteApi, menuApi, stokApi } from '../lib/api';
import { Plus, Trash2 } from 'lucide-react';

interface ReceteItem {
  id: number;
  urun: string;
  stok: string;
  miktar: number;
  birim: string;
}

interface MenuItem {
  id: number;
  ad: string;
}

interface StokItem {
  id: number;
  ad: string;
}

export default function RecetePage() {
  const [receteItems, setReceteItems] = useState<ReceteItem[]>([]);
  const [menuItems, setMenuItems] = useState<MenuItem[]>([]);
  const [stokItems, setStokItems] = useState<StokItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [formData, setFormData] = useState({
    urun: '',
    stok: '',
    miktar: '',
    birim: '',
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [receteRes, menuRes, stokRes] = await Promise.all([
        receteApi.list({ limit: 200 }),
        menuApi.list({ limit: 200 }),
        stokApi.list({ limit: 200 }),
      ]);
      setReceteItems(receteRes.data || []);
      setMenuItems(menuRes.data || []);
      setStokItems(stokRes.data || []);
    } catch (err) {
      console.error('Veriler yüklenemedi:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await receteApi.add({
        urun: formData.urun,
        stok: formData.stok,
        miktar: parseFloat(formData.miktar),
        birim: formData.birim,
      });
      resetForm();
      loadData();
    } catch (err: any) {
      console.error('Reçete eklenemedi:', err);
      alert(err.response?.data?.detail || 'Hata: Reçete eklenemedi');
    }
  };

  const handleDelete = async (id: number, urun: string, stok: string) => {
    if (!confirm(`"${urun}" için "${stok}" reçetesini silmek istediğinizden emin misiniz?`)) {
      return;
    }
    try {
      await receteApi.delete(id);
      loadData();
    } catch (err) {
      console.error('Reçete silinemedi:', err);
      alert('Hata: Reçete silinemedi');
    }
  };

  const resetForm = () => {
    setFormData({
      urun: '',
      stok: '',
      miktar: '',
      birim: '',
    });
  };

  // Ürün bazında gruplanmış reçeteler
  const groupedRecipes = receteItems.reduce((acc, item) => {
    if (!acc[item.urun]) {
      acc[item.urun] = [];
    }
    acc[item.urun].push(item);
    return acc;
  }, {} as Record<string, ReceteItem[]>);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold">Reçete Yönetimi</h2>
        <button
          onClick={loadData}
          className="px-4 py-2 bg-primary-900/40 hover:bg-primary-800/40 rounded-lg transition-colors text-accent-mist"
        >
          Yenile
        </button>
      </div>

      {/* Form */}
      <div className="card">
        <h3 className="text-xl font-semibold mb-4">Yeni Reçete Ekle</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Ürün (Menü)</label>
              <select
                value={formData.urun}
                onChange={(e) => setFormData({ ...formData, urun: e.target.value })}
                required
                className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
              >
                <option value="">Seçiniz...</option>
                {menuItems.map((item) => (
                  <option key={item.id} value={item.ad}>
                    {item.ad}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Stok Kalemi</label>
              <select
                value={formData.stok}
                onChange={(e) => setFormData({ ...formData, stok: e.target.value })}
                required
                className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
              >
                <option value="">Seçiniz...</option>
                {stokItems.map((item) => (
                  <option key={item.id} value={item.ad}>
                    {item.ad}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Miktar</label>
              <input
                type="number"
                step="0.001"
                min="0.001"
                value={formData.miktar}
                onChange={(e) => setFormData({ ...formData, miktar: e.target.value })}
                required
                className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
                placeholder="Örn: 100"
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
                placeholder="Örn: ml, gr, adet"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button
              type="submit"
              className="px-6 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Ekle
            </button>
            <button
              type="button"
              onClick={resetForm}
              className="px-6 py-2 bg-primary-900/40 hover:bg-primary-800/40 rounded-lg transition-colors text-accent-mist"
            >
              Temizle
            </button>
          </div>
        </form>
      </div>

      {/* Reçete Listesi - Ürün bazında gruplanmış */}
      <div className="card">
        <h3 className="text-xl font-semibold mb-4">Reçete Listesi</h3>
        {loading ? (
          <div className="text-center py-8 text-white/50">Yükleniyor...</div>
        ) : Object.keys(groupedRecipes).length === 0 ? (
          <div className="text-center py-8 text-white/50">Henüz reçete tanımlanmamış.</div>
        ) : (
          <div className="space-y-6">
            {Object.entries(groupedRecipes).map(([urun, items]) => (
              <div key={urun} className="border-b border-white/10 pb-4 last:border-b-0">
                <h4 className="text-lg font-semibold mb-3 text-primary-300">{urun}</h4>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-white/20">
                        <th className="text-left py-2 px-4">Stok Kalemi</th>
                        <th className="text-right py-2 px-4">Miktar</th>
                        <th className="text-left py-2 px-4">Birim</th>
                        <th className="text-right py-2 px-4">İşlemler</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item) => (
                        <tr key={item.id} className="border-b border-white/5 hover:bg-white/5">
                          <td className="py-2 px-4">{item.stok}</td>
                          <td className="py-2 px-4 text-right">{item.miktar}</td>
                          <td className="py-2 px-4">{item.birim}</td>
                          <td className="py-2 px-4">
                            <div className="flex justify-end">
                              <button
                                onClick={() => handleDelete(item.id, item.urun, item.stok)}
                                className="p-1 hover:bg-tertiary-500/20 rounded transition-colors text-tertiary-100"
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
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}





