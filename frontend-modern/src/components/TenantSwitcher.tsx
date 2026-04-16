import { useState, useEffect, useCallback } from 'react';
import { useAuthStore } from '../store/authStore';
import { superadminApi } from '../lib/api';
import { Building2, Check, ChevronDown, Search } from 'lucide-react';

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

  const selectedTenant = tenants.find(t => t.id === selectedTenantId);
  const filteredTenants = tenants.filter(t => t.ad.toLowerCase().includes(searchTerm.toLowerCase()));

  const handleSelectTenant = async (tenantId: number | null) => {
    setSelectedTenantId(tenantId);
    setOpen(false);
    setSearchTerm('');
    const { setSubeId } = useAuthStore.getState();
    if (tenantId) {
      try {
        const detailRes = await superadminApi.tenantDetail(tenantId);
        const subeler = detailRes.data?.subeler || [];
        setSubeId(subeler.length > 0 ? subeler[0].id : 1);
      } catch (err) {
        console.error('Tenant şubeleri yüklenemedi:', err);
        setSubeId(1);
      }
    } else {
      setSubeId(1);
    }
    window.location.reload();
  };

  if (!isSuperAdmin) return null;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-3 rounded-2xl border border-white/5 bg-white/5 px-4 py-2.5 text-white/90 transition-all duration-300 hover:bg-white/10 hover:border-emerald-500/30 group shadow-lg"
      >
        <div className="p-1 px-1.5 rounded-lg bg-emerald-500/20 text-emerald-400">
          <Building2 size={16} />
        </div>
        <div className="flex flex-col items-start translate-y-[1px]">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest leading-none mb-1">Aktif İşletme</span>
          <span className="text-sm font-bold truncate max-w-[120px]">
            {selectedTenant ? selectedTenant.ad : 'Tüm İşletmeler'}
          </span>
        </div>
        <ChevronDown size={14} className={`text-slate-500 transition-transform duration-300 ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-3 z-50 w-72 glass-panel rounded-3xl overflow-hidden shadow-2xl animate-in fade-in zoom-in slide-in-from-top-4 duration-300">
            <div className="p-4 border-b border-white/5 bg-white/5">
              <div className="relative group">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-emerald-400 transition-colors" size={16} />
                <input
                  type="text"
                  placeholder="İşletme ara..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full rounded-xl border border-white/5 bg-slate-950/50 pl-10 pr-4 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 transition-all"
                />
              </div>
            </div>

            <div className="max-h-80 overflow-y-auto p-2 space-y-1">
              <button
                onClick={() => handleSelectTenant(null)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left text-sm font-medium transition-all duration-200 ${selectedTenantId === null ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'text-slate-400 hover:bg-white/5 hover:text-white'}`}
              >
                <div className={`p-1.5 rounded-lg ${selectedTenantId === null ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/30' : 'bg-slate-800 text-slate-500'}`}>
                  {selectedTenantId === null ? <Check size={14} strokeWidth={3} /> : <Building2 size={14} />}
                </div>
                <span>Tüm İşletmeler</span>
              </button>

              <div className="py-2 px-4">
                 <p className="text-[10px] font-bold text-slate-600 uppercase tracking-widest">İşletme Listesi</p>
              </div>

              {loading ? (
                <div className="px-4 py-8 flex flex-col items-center justify-center gap-2">
                   <div className="w-5 h-5 border-2 border-emerald-500/20 border-t-emerald-500 rounded-full animate-spin" />
                   <p className="text-xs text-slate-500 font-medium">Yükleniyor...</p>
                </div>
              ) : filteredTenants.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-slate-500 font-medium">İşletme bulunamadı</div>
              ) : (
                filteredTenants.map((tenant) => (
                  <button
                    key={tenant.id}
                    onClick={() => handleSelectTenant(tenant.id)}
                    className={`w-full flex items-center justify-between gap-3 px-4 py-3 rounded-xl text-left text-sm font-medium transition-all duration-200 ${selectedTenantId === tenant.id ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'text-slate-400 hover:bg-white/5 hover:text-white'} ${!tenant.aktif && 'opacity-40 grayscale pointer-events-none'}`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className={`p-1.5 rounded-lg shrink-0 ${selectedTenantId === tenant.id ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/30' : 'bg-slate-800 text-slate-500'}`}>
                        {selectedTenantId === tenant.id ? <Check size={14} strokeWidth={3} /> : <Building2 size={14} />}
                      </div>
                      <span className="truncate">{tenant.ad}</span>
                    </div>
                    {!tenant.aktif && <span className="text-[10px] font-bold bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded uppercase tracking-tighter">İnaktif</span>}
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


