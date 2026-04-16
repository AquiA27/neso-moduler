import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { authApi } from '../lib/api';
import logo from '../assets/neso-logo.svg';
import { Lock, User, ArrowRight, ShieldCheck } from 'lucide-react';

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
    if (r === 'super_admin' || u === 'super') return '/superadmin';
    if (u === 'mutfak' || r === 'mutfak' || r === 'barista') return '/mutfak';
    if (r === 'garson') return '/terminal';
    if (r === 'operator' || u === 'kasiyer') return '/kasa';
    return '/dashboard';
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const tokenData = await authApi.login(username, password);
      if (!tokenData.access_token) throw new Error('Token alınamadı');
      setTokens(tokenData.access_token, tokenData.refresh_token);
      const meResponse = await authApi.me();
      const userData = meResponse.data || meResponse;
      setUser({
        id: userData.id,
        username: userData.username || username,
        role: userData.role || 'operator',
        aktif: userData.aktif,
      });
      setSubeId(Number(localStorage.getItem('neso.subeId') || '1'));
      const targetPath = resolvePanel(userData.username || username, userData.role || 'operator');
      navigate(targetPath);
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.response?.data?.message || err.message || 'Giriş başarısız';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center p-6 overflow-hidden bg-slate-950">
      {/* Background with Image and Gradients */}
      <div className="absolute inset-0 z-0">
        <img 
          src="https://images.unsplash.com/photo-1620121692029-d088224ddc74?q=80&w=2064&auto=format&fit=crop" 
          className="w-full h-full object-cover opacity-20 scale-110"
          alt="Background"
        />
        <div className="absolute inset-0 bg-gradient-to-br from-slate-950 via-slate-950/90 to-emerald-950/30" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-emerald-500/10 blur-[120px] rounded-full" />
      </div>

      {/* Main Container */}
      <div className="relative z-10 w-full max-w-[1000px] grid md:grid-cols-2 glass-panel rounded-[32px] overflow-hidden shadow-2xl border border-white/10 animate-in fade-in zoom-in duration-700">
        
        {/* Left Side: Illustration / Brand */}
        <div className="hidden md:flex flex-col justify-between p-12 bg-emerald-500/5 relative overflow-hidden text-white">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.1),_transparent_70%)]" />
          
          <div className="space-y-6">
            <img src={logo} className="h-16 w-16 drop-shadow-[0_0_15px_rgba(16,185,129,0.5)]" alt="Neso Logo" />
            <h1 className="text-5xl font-bold tracking-tight leading-tight">
              Yönetimi <br />
              <span className="text-gradient">Akıllandırın.</span>
            </h1>
            <p className="text-slate-400 text-lg font-medium">
              Neso Modüler ile restoran operasyonlarınızı tek platformdan yönetin, verimliliği artırın.
            </p>
          </div>

          <div className="flex items-center gap-4 text-emerald-400 font-semibold bg-emerald-500/10 p-4 rounded-2xl border border-emerald-500/20">
            <ShieldCheck size={28} />
            <div>
              <p className="text-sm">Güvenli Bağlantı</p>
              <p className="text-[10px] uppercase tracking-widest text-emerald-500/60">Enterprise Grade Security</p>
            </div>
          </div>
        </div>

        {/* Right Side: Login Form */}
        <div className="p-8 md:p-12 flex flex-col justify-center">
          <div className="mb-10 block md:hidden">
             <img src={logo} className="h-12 w-12 mx-auto mb-4" alt="Neso Logo" />
             <h2 className="text-2xl font-bold text-center text-white">Neso Modüler</h2>
          </div>

          <div className="space-y-1 mb-8">
            <h2 className="text-3xl font-bold text-white tracking-tight">Hoş Geldiniz</h2>
            <p className="text-slate-500 font-medium">Lütfen kimlik bilgilerinizle giriş yapın.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <label className="text-sm font-semibold text-slate-400 ml-1">Kullanıcı Adı</label>
              <div className="relative group">
                <User className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-emerald-500 transition-colors" size={20} />
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  className="w-full pl-12 pr-4 py-4"
                  placeholder="Kullanıcı adınızı yazın"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-semibold text-slate-400 ml-1">Şifre</label>
              <div className="relative group">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-emerald-500 transition-colors" size={20} />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full pl-12 pr-4 py-4"
                  placeholder="••••••••"
                />
              </div>
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-sm text-red-400 flex items-center gap-3 animate-shake">
                <div className="w-1.5 h-1.5 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]" />
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="glow-button w-full flex items-center justify-center gap-2 mt-4"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Giriş yapılıyor...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  Panel'e Giriş Yap <ArrowRight size={18} />
                </span>
              )}
            </button>
          </form>

          <div className="mt-12 text-center text-[10px] font-bold uppercase tracking-widest text-slate-600">
            Powered by Neso Intelligent Systems &copy; 2026
          </div>
        </div>
      </div>
    </div>
  );
}


