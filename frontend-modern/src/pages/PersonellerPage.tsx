import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { superadminApi, adminApi } from '../lib/api';
import { Plus, Edit, Trash2, UserPlus, Shield, X } from 'lucide-react';

interface Personel {
  id: number;
  username: string;
  role: string;
  aktif: boolean;
  created_at?: string;
}

interface PersonelPerformans {
  user_id: number | null;
  username: string;
  role: string;
  siparis_adedi: number;
  toplam_ciro: number;
}

export default function PersonellerPage() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const [personeller, setPersoneller] = useState<Personel[]>([]);
  const [performans, setPerformans] = useState<PersonelPerformans[]>([]);
  const [performancePeriod, setPerformancePeriod] = useState<'week' | 'month'>('week');
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Personel | null>(null);
  const [formData, setFormData] = useState({
    username: '',
    role: 'operator',
    password: '',
    aktif: true,
  });
  const [permissionModal, setPermissionModal] = useState<{ open: boolean; username: string; role: string } | null>(null);
  const [availablePermissions, setAvailablePermissions] = useState<Record<string, string>>({});
  const [userPermissions, setUserPermissions] = useState<Record<string, boolean>>({});
  const [loadingPermissions, setLoadingPermissions] = useState(false);

  const { selectedTenantId } = useAuthStore();
  
  const loadPersoneller = useCallback(async () => {
    try {
      // Super admin tenant switching yapıyorsa (selectedTenantId varsa), 
      // /admin/personeller endpoint'ini kullan (tenant filtresi yapıyor)
      // Super admin "Tüm İşletmeler" modundaysa (selectedTenantId null), 
      // /admin/personeller endpoint'ini kullan (tüm personelleri gösteriyor)
      // Normal admin için de /admin/personeller endpoint'ini kullan
      const response = await adminApi.personellerList();
      setPersoneller(response.data || []);
    } catch (err) {
      console.error('Personeller yüklenemedi:', err);
    } finally {
      setLoading(false);
    }
  }, [selectedTenantId]); // Tenant değiştiğinde personelleri yeniden yükle

  const loadPerformans = useCallback(async () => {
    try {
      const days = performancePeriod === 'week' ? 7 : 30;
      const response = await adminApi.personelAnaliz(days, 50);
      setPerformans(response.data || []);
    } catch (err) {
      console.error('Performans verileri yüklenemedi:', err);
    }
  }, [performancePeriod]);

  useEffect(() => {
    loadPerformans();
  }, [loadPerformans]);

  useEffect(() => {
    // Yetki kontrolü - super_admin ve admin erişebilir
    if (user) {
      const role = user.role?.toLowerCase();
      const isSuperAdmin = role === 'super_admin' || user.username?.toLowerCase() === 'super';
      const isAdmin = role === 'admin';
      
      if (!isSuperAdmin && !isAdmin) {
        navigate('/login');
        return;
      }
    }
    loadPersoneller();
    loadPerformans();
  }, [user, navigate, loadPerformans, loadPersoneller]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      // Super admin için superadmin endpoint'i, admin için admin endpoint'i kullan
      const currentUser = useAuthStore.getState().user;
      const role = currentUser?.role?.toLowerCase();
      const isSuperAdmin = role === 'super_admin' || currentUser?.username?.toLowerCase() === 'super';
      
      if (isSuperAdmin) {
        await superadminApi.userUpsert({
          username: formData.username,
          role: formData.role,
          aktif: formData.aktif,
          password: formData.password || undefined,
        });
      } else {
        // Admin için tenant bazlı personel ekleme
        await adminApi.personelUpsert({
          username: formData.username,
          role: formData.role,
          aktif: formData.aktif,
          password: formData.password || undefined,
        });
      }
      resetForm();
      loadPersoneller();
    } catch (err) {
      console.error('Personel kaydedilemedi:', err);
      alert('Hata: Personel kaydedilemedi');
    }
  };

  const handleEdit = (personel: Personel) => {
    setEditing(personel);
    setFormData({
      username: personel.username,
      role: personel.role,
      password: '',
      aktif: personel.aktif,
    });
  };

  const handleDelete = async (_id: number, username: string) => {
    if (!confirm(`"${username}" kullanıcısını silmek istediğinizden emin misiniz?`)) return;
    try {
      await superadminApi.userUpsert({
        username,
        role: 'operator',
        aktif: false,
      });
      loadPersoneller();
    } catch (err) {
      console.error('Personel silinemedi:', err);
      alert('Hata: Personel silinemedi');
    }
  };

  const resetForm = () => {
    setEditing(null);
    setFormData({ username: '', role: 'operator', password: '', aktif: true });
  };

  const getRoleLabel = (role: string) => {
    const labels: Record<string, string> = {
      super_admin: 'Süper Admin',
      admin: 'Admin',
      operator: 'Kasiyer',
      barista: 'Barista',
      mutfak: 'Mutfak',
      garson: 'Garson',
    };
    return labels[role] || role;
  };

  const loadAvailablePermissions = useCallback(async () => {
    try {
      const response = await superadminApi.getAvailablePermissions();
      setAvailablePermissions(response.data || {});
    } catch (err) {
      console.error('İzinler yüklenemedi:', err);
    }
  }, []);

  const openPermissionModal = async (personel: Personel) => {
    if (personel.role === 'super_admin') {
      alert('Süper admin rolü tüm izinlere sahiptir.');
      return;
    }
    setPermissionModal({ open: true, username: personel.username, role: personel.role });
    setLoadingPermissions(true);
    try {
      const response = await superadminApi.getUserPermissions(personel.username);
      setUserPermissions(response.data?.permissions || {});
      if (!availablePermissions || Object.keys(availablePermissions).length === 0) {
        await loadAvailablePermissions();
      }
    } catch (err) {
      console.error('İzinler yüklenemedi:', err);
      alert('İzinler yüklenirken hata oluştu');
    } finally {
      setLoadingPermissions(false);
    }
  };

  const closePermissionModal = () => {
    setPermissionModal(null);
    setUserPermissions({});
  };

  const handlePermissionToggle = (permissionKey: string) => {
    setUserPermissions(prev => ({
      ...prev,
      [permissionKey]: !prev[permissionKey],
    }));
  };

  const handleSavePermissions = async () => {
    if (!permissionModal) return;
    try {
      await superadminApi.updateUserPermissions(permissionModal.username, userPermissions);
      alert('İzinler başarıyla güncellendi');
      closePermissionModal();
    } catch (err) {
      console.error('İzinler güncellenemedi:', err);
      alert('İzinler güncellenirken hata oluştu');
    }
  };

  useEffect(() => {
    loadAvailablePermissions();
  }, [loadAvailablePermissions]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold">Personel Yönetimi</h2>
        <button
          onClick={loadPersoneller}
          className="px-4 py-2 bg-primary-900/40 hover:bg-primary-800/40 rounded-lg transition-colors text-accent-mist"
        >
          Yenile
        </button>
      </div>

      {/* Form */}
      <div className="card">
        <h3 className="text-xl font-semibold mb-4 flex items-center gap-2">
          {editing ? <Edit className="w-5 h-5" /> : <UserPlus className="w-5 h-5" />}
          {editing ? 'Personel Güncelle' : 'Yeni Personel Ekle'}
        </h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Kullanıcı Adı</label>
              <input
                type="text"
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                required
                disabled={!!editing}
                className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors disabled:opacity-50"
                placeholder="kullanici_adi"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">Rol</label>
              <select
                value={formData.role}
                onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                required
                className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
              >
                <option value="operator">Kasiyer</option>
                <option value="barista">Barista</option>
                <option value="mutfak">Mutfak</option>
                <option value="garson">Garson</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">
                {editing ? 'Yeni Şifre (boş bırakırsanız değişmez)' : 'Şifre'}
              </label>
              <input
                type="password"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                required={!editing}
                className="w-full px-4 py-2 bg-primary-900/40 border border-primary-500/25 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-400 text-accent-mist placeholder-accent-mist/40 transition-colors"
                placeholder={editing ? 'Boş bırak = değiştirme' : '••••••'}
              />
            </div>
          </div>
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
              {editing ? <Edit className="w-4 h-4" /> : <Plus className="w-4 h-4" />}
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

      {/* Liste */}
      <div className="card">
        <h3 className="text-xl font-semibold mb-4">Personel Listesi</h3>
        {loading ? (
          <div className="text-center py-8 text-white/50">Yükleniyor...</div>
        ) : personeller.length === 0 ? (
          <div className="text-center py-8 text-white/50">Henüz personel eklenmemiş.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/20">
                  <th className="text-left py-3 px-4">Kullanıcı Adı</th>
                  <th className="text-left py-3 px-4">Rol</th>
                  <th className="text-center py-3 px-4">Durum</th>
                  <th className="text-right py-3 px-4">İşlemler</th>
                </tr>
              </thead>
              <tbody>
                {personeller.map((personel) => (
                  <tr key={personel.id} className="border-b border-white/10 hover:bg-white/5">
                    <td className="py-3 px-4 font-medium">{personel.username}</td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-1 rounded text-xs bg-quaternary-400/20 text-quaternary-100">
                        {getRoleLabel(personel.role)}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span
                        className={`px-2 py-1 rounded text-xs ${
                          personel.aktif
                            ? 'bg-green-500/20 text-green-300'
                            : 'bg-tertiary-500/20 text-tertiary-100'
                        }`}
                      >
                        {personel.aktif ? 'Aktif' : 'Pasif'}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex justify-end gap-2">
                        {personel.role !== 'super_admin' && (
                          <button
                            onClick={() => openPermissionModal(personel)}
                            className="p-1 hover:bg-primary-800/30 rounded transition-colors"
                            title="İzinleri Düzenle"
                          >
                            <Shield className="w-4 h-4" />
                          </button>
                        )}
                        <button
                          onClick={() => handleEdit(personel)}
                          className="p-1 hover:bg-primary-800/30 rounded transition-colors"
                          title="Düzenle"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(personel.id, personel.username)}
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
        )}
      </div>

      {/* Personel Performans Raporu */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-semibold">
            Personel Performans Raporu ({performancePeriod === 'week' ? 'Son 7 Gün' : 'Son 30 Gün'})
          </h3>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPerformancePeriod('week')}
              className={`px-3 py-1 rounded-lg text-sm transition-colors ${
                performancePeriod === 'week'
                  ? 'bg-primary-600 text-white'
                  : 'bg-primary-900/40 text-accent-mist hover:bg-primary-800/40'
              }`}
            >
              Haftalık
            </button>
            <button
              onClick={() => setPerformancePeriod('month')}
              className={`px-3 py-1 rounded-lg text-sm transition-colors ${
                performancePeriod === 'month'
                  ? 'bg-primary-600 text-white'
                  : 'bg-primary-900/40 text-accent-mist hover:bg-primary-800/40'
              }`}
            >
              Aylık
            </button>
          </div>
        </div>
        {performans.length === 0 ? (
          <div className="text-center py-8 text-white/50">Henüz performans verisi bulunmuyor.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/20">
                  <th className="text-left py-3 px-4">Personel</th>
                  <th className="text-left py-3 px-4">Rol</th>
                  <th className="text-right py-3 px-4">Sipariş Adedi</th>
                  <th className="text-right py-3 px-4">Toplam Ciro</th>
                </tr>
              </thead>
              <tbody>
                {performans.map((p) => (
                  <tr key={p.user_id || p.username} className="border-b border-white/10 hover:bg-white/5">
                    <td className="py-3 px-4 font-medium">{p.username}</td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-1 rounded text-xs ${
                        p.role === 'ai' 
                          ? 'bg-purple-500/20 text-purple-300'
                          : 'bg-quaternary-400/20 text-quaternary-100'
                      }`}>
                        {p.role === 'ai' ? 'Yapay Zeka' : getRoleLabel(p.role)}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">{p.siparis_adedi}</td>
                    <td className="py-3 px-4 text-right text-green-300 font-semibold">{p.toplam_ciro.toFixed(2)} ₺</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* İzin Yönetimi Modal */}
      {permissionModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-primary-900 rounded-lg p-6 max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-2xl font-bold flex items-center gap-2">
                <Shield className="w-6 h-6" />
                İzin Yönetimi: {permissionModal.username}
              </h3>
              <button
                onClick={closePermissionModal}
                className="p-2 hover:bg-primary-800/30 rounded transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="mb-4">
              <span className="text-sm text-white/70">Rol: </span>
              <span className="px-2 py-1 rounded text-sm bg-quaternary-400/20 text-quaternary-100">
                {getRoleLabel(permissionModal.role)}
              </span>
            </div>

            {loadingPermissions ? (
              <div className="text-center py-8 text-white/50">Yükleniyor...</div>
            ) : (
              <>
                <div className="space-y-4 mb-6">
                  {Object.entries(availablePermissions).map(([key, label]) => {
                    const isChecked = userPermissions[key] === true;
                    return (
                      <div key={key} className="flex items-center gap-3 p-3 bg-primary-800/20 rounded-lg hover:bg-primary-800/30 transition-colors">
                        <input
                          type="checkbox"
                          id={`perm-${key}`}
                          checked={isChecked}
                          onChange={() => handlePermissionToggle(key)}
                          className="w-5 h-5 rounded border-primary-500/50 bg-primary-900 text-primary-500 focus:ring-2 focus:ring-primary-400"
                        />
                        <label
                          htmlFor={`perm-${key}`}
                          className="flex-1 cursor-pointer text-sm font-medium"
                        >
                          {label}
                        </label>
                      </div>
                    );
                  })}
                </div>

                <div className="flex gap-2 justify-end">
                  <button
                    onClick={closePermissionModal}
                    className="px-6 py-2 bg-primary-900/40 hover:bg-primary-800/40 rounded-lg transition-colors text-accent-mist"
                  >
                    İptal
                  </button>
                  <button
                    onClick={handleSavePermissions}
                    className="px-6 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors flex items-center gap-2"
                  >
                    <Shield className="w-4 h-4" />
                    İzinleri Kaydet
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

