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
  const { setUser, setTokens } = useAuthStore();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const tokenData = await authApi.login(username, password);
      
      if (!tokenData.access_token) {
        throw new Error('Token alınamadı');
      }

      setTokens(tokenData.access_token, tokenData.refresh_token);

      const meResponse = await authApi.me();
      const userData = meResponse.data || meResponse;

      // Sadece super_admin rolü giriş yapabilir
      if (userData.role !== 'super_admin') {
        throw new Error('Bu panele sadece super admin kullanıcıları giriş yapabilir');
      }

      setUser({
        id: userData.id,
        username: userData.username || username,
        role: userData.role,
        aktif: userData.aktif,
      });

      navigate('/dashboard');
    } catch (err: any) {
      console.error('Login error:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Giriş başarısız';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Super Admin Panel</h1>
          <p className="text-gray-600">Platform Yönetim Paneli</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Kullanıcı Adı
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Kullanıcı adınız"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Şifre
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Şifreniz"
            />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-600">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Giriş yapılıyor...' : 'Giriş Yap'}
          </button>
        </form>

        <div className="mt-6 text-center text-sm text-gray-500">
          <p>Sadece super_admin rolüne sahip kullanıcılar giriş yapabilir</p>
        </div>
      </div>
    </div>
  );
}


