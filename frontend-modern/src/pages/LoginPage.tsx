import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { authApi } from '../lib/api';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  
  const navigate = useNavigate();
  const { setUser, setTokens, setSubeId } = useAuthStore();

  const resolvePanel = (username: string, role: string): string => {
    const u = username.toLowerCase();
    const r = role.toLowerCase();
    
    // Super admin sadece super admin panelini görebilir
    if (r === 'super_admin' || u === 'super') {
      return '/superadmin';
    }
    
    // Mutfak kullanıcıları ve barista mutfak ekranını görebilir
    if (u === 'mutfak' || r === 'mutfak' || r === 'barista') {
      return '/mutfak';
    }
    
    // Garson terminal kullanabilir
    if (r === 'garson') {
      return '/terminal';
    }
    
    // Kasa/Operator yetkileri
    if (r === 'operator' || u === 'kasiyer') {
      return '/kasa';
    }
    
    // Admin yetkileri (tenant admin)
    if (r === 'admin' || u === 'admin') {
      return '/dashboard';
    }
    
    // Varsayılan olarak dashboard
    return '/dashboard';
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // Login
      const tokenData = await authApi.login(username, password);
      
      if (!tokenData.access_token) {
        throw new Error('Token alınamadı');
      }

      // Token'ı önce store'a kaydet (me() çağrısı için gerekli)
      setTokens(tokenData.access_token, tokenData.refresh_token);

      // Kullanıcı bilgilerini al (token artık store'da)
      const meResponse = await authApi.me();
      const userData = meResponse.data || meResponse;

      // Kullanıcı bilgilerini store'a kaydet
      setUser({
        id: userData.id,
        username: userData.username || username,
        role: userData.role || 'operator',
        aktif: userData.aktif,
      });
      setSubeId(Number(localStorage.getItem('neso.subeId') || '1'));

      // Panel'e yönlendir (kullanıcı tipine göre)
      const targetPath = resolvePanel(userData.username || username, userData.role || 'operator');
      navigate(targetPath);
    } catch (err: any) {
      console.error('Login error:', err);
      const errorMessage = err.response?.data?.detail || err.response?.data?.message || err.message || 'Giriş başarısız';
      setError(errorMessage);
      console.error('Full error:', JSON.stringify(err.response?.data || err, null, 2));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="card max-w-md w-full">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">Neso Modüler</h1>
          <p className="text-white/70">Personel Girişi</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium mb-2">
              Kullanıcı Adı
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoComplete="username"
              className="w-full px-4 py-2 bg-white/10 border border-white/20 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="Kullanıcı adınız"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              Şifre
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="w-full px-4 py-2 bg-white/10 border border-white/20 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="Şifreniz"
            />
          </div>

          {error && (
            <div className="bg-red-500/20 border border-red-500/50 rounded-lg p-3 text-sm text-red-200">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-primary-600 hover:bg-primary-700 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Giriş yapılıyor...' : 'Giriş Yap'}
          </button>
        </form>

        <div className="mt-6 text-center text-sm text-white/60">
          <p>Fistik Kafe (c) 2025</p>
        </div>
      </div>
    </div>
  );
}

