import { useState, useEffect, useCallback } from 'react';
import { useAuthStore } from '../store/authStore';
import { superadminApi } from '../lib/api';
import { Building2, Check } from 'lucide-react';

interface Tenant {
  id: number;
  ad: string;
  aktif: boolean;
}

export default function TenantSwitcher() {
  const { user, selectedTenantId, setSelectedTenantId } = useAuthStore();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  // Sadece super admin için göster
  const userRole = user?.role?.toLowerCase();
  const username = user?.username?.toLowerCase();
  const isSuperAdmin = user && (userRole === 'super_admin' || username === 'super');

  const loadTenants = useCallback(async () => {
    if (!isSuperAdmin) return;
    
    setLoading(true);
    try {
      const response = await superadminApi.tenantsList();
      setTenants(response.data || []);
    } catch (err) {
      console.error('Tenant listesi yüklenemedi:', err);
    } finally {
      setLoading(false);
    }
  }, [isSuperAdmin]);

  useEffect(() => {
    if (isSuperAdmin) {
      loadTenants();
    }
  }, [isSuperAdmin, loadTenants]);

  // Seçili tenant bilgisi
  const selectedTenant = tenants.find(t => t.id === selectedTenantId);

  // Filtrelenmiş tenant listesi
  const filteredTenants = tenants.filter(t =>
    t.ad.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Tenant seç
  const handleSelectTenant = (tenantId: number | null) => {
    setSelectedTenantId(tenantId);
    setOpen(false);
    setSearchTerm('');
    // Sayfayı refresh et (tenant değişti)
    window.location.reload();
  };

  // Sadece super admin için render et
  if (!isSuperAdmin) {
    return null;
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 rounded-xl border border-white/20 bg-white/5 px-4 py-2 text-white/80 transition hover:bg-white/10"
      >
        <Building2 className="h-4 w-4" />
        <span className="text-sm font-medium">
          {selectedTenant ? selectedTenant.ad : 'Tüm İşletmeler'}
        </span>
        {selectedTenantId && (
          <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-xs text-emerald-200">
            Aktif
          </span>
        )}
      </button>

      {open && (
        <>
          {/* Overlay */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
          />

          {/* Dropdown */}
          <div className="absolute right-0 top-full mt-2 z-50 w-64 rounded-xl border border-white/20 bg-gradient-to-br from-emerald-950/95 via-primary-900/95 to-primary-950/95 shadow-xl backdrop-blur-md">
            <div className="p-3 border-b border-white/10">
              <input
                type="text"
                placeholder="İşletme ara..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full rounded-lg border border-white/20 bg-white/5 px-3 py-2 text-sm text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-emerald-400/50"
              />
            </div>

            <div className="max-h-64 overflow-y-auto">
              {/* Tüm İşletmeler seçeneği */}
              <button
                onClick={() => handleSelectTenant(null)}
                className={`w-full flex items-center gap-2 px-4 py-2 text-left text-sm transition ${
                  selectedTenantId === null
                    ? 'bg-emerald-500/20 text-emerald-200'
                    : 'text-white/80 hover:bg-white/10'
                }`}
              >
                {selectedTenantId === null && (
                  <Check className="h-4 w-4" />
                )}
                <span>Tüm İşletmeler</span>
              </button>

              {/* Tenant listesi */}
              {loading ? (
                <div className="px-4 py-2 text-sm text-white/60">
                  Yükleniyor...
                </div>
              ) : filteredTenants.length === 0 ? (
                <div className="px-4 py-2 text-sm text-white/60">
                  İşletme bulunamadı
                </div>
              ) : (
                filteredTenants.map((tenant) => (
                  <button
                    key={tenant.id}
                    onClick={() => handleSelectTenant(tenant.id)}
                    className={`w-full flex items-center justify-between gap-2 px-4 py-2 text-left text-sm transition ${
                      selectedTenantId === tenant.id
                        ? 'bg-emerald-500/20 text-emerald-200'
                        : 'text-white/80 hover:bg-white/10'
                    } ${!tenant.aktif ? 'opacity-50' : ''}`}
                  >
                    <span className="flex items-center gap-2">
                      {selectedTenantId === tenant.id && (
                        <Check className="h-4 w-4" />
                      )}
                      <span>{tenant.ad}</span>
                    </span>
                    {!tenant.aktif && (
                      <span className="text-xs text-white/40">Pasif</span>
                    )}
                  </button>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

