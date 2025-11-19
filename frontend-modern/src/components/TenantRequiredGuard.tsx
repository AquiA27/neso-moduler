import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

/**
 * Super Admin "Tüm İşletmeler" modundayken veri sayfalarına erişimi engeller
 * ve Super Admin paneline yönlendirir.
 */
export default function TenantRequiredGuard({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const { user, selectedTenantId } = useAuthStore();

  useEffect(() => {
    // Super admin kontrolü
    const userRole = user?.role?.toLowerCase();
    const username = user?.username?.toLowerCase();
    const isSuperAdmin = user && (userRole === 'super_admin' || username === 'super');

    // Super admin "Tüm İşletmeler" modundaysa Super Admin paneline yönlendir
    if (isSuperAdmin && selectedTenantId === null) {
      navigate('/superadmin', { replace: true });
    }
  }, [user, selectedTenantId, navigate]);

  // Super admin "Tüm İşletmeler" modundaysa hiçbir şey render etme (yönlendirme yapılacak)
  const userRole = user?.role?.toLowerCase();
  const username = user?.username?.toLowerCase();
  const isSuperAdmin = user && (userRole === 'super_admin' || username === 'super');
  
  if (isSuperAdmin && selectedTenantId === null) {
    return null; // Yönlendirme yapılırken boş render
  }

  return <>{children}</>;
}

