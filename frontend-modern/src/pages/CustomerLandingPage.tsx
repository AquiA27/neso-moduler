import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { MessageCircle, Menu as MenuIcon } from 'lucide-react';
import { normalizeApiUrl } from '../lib/api';

export default function CustomerLandingPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const qrCode = searchParams.get('qr');
  const initialMasa = searchParams.get('masa') || '';
  const initialSubeId = searchParams.get('sube_id') || '';

  const [masa, setMasa] = useState(initialMasa);
  const [subeId, setSubeId] = useState(initialSubeId);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [tableStatus, setTableStatus] = useState<string | null>(null);
  const [isBlocked, setIsBlocked] = useState(false);

  useEffect(() => {
    const loadMasaFromQR = async () => {
      if (!qrCode) return;
      try {
        setLoading(true);
        setError('');
        const API_BASE_URL = normalizeApiUrl(import.meta.env.VITE_API_URL as string);
        const encodedQrCode = encodeURIComponent(qrCode);
        const response = await fetch(`${API_BASE_URL}/public/masa/${encodedQrCode}`);
        if (!response.ok) {
          const detail = await response.json().catch(() => ({}));
          const msg = detail?.detail || `HTTP ${response.status}`;
          throw new Error(msg);
        }
        const data = await response.json();
        setMasa(data.masa_adi || initialMasa);
        if (data.sube_id) {
          setSubeId(String(data.sube_id));
        }

        // Masa durumu kontrolü
        if (['rezerve', 'dolu', 'temizlik'].includes(data.durum)) {
          setTableStatus(data.durum);
          setIsBlocked(true);
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        console.error('QR kod masa bilgisi yüklenemedi:', msg);
        setError(`Masa bilgisi alınamadı: ${msg}`);
      } finally {
        setLoading(false);
      }
    };

    loadMasaFromQR();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qrCode]);

  const buildParams = () => {
    const params = new URLSearchParams();
    if (qrCode) {
      params.set('qr', qrCode);
    } else {
      if (masa) params.set('masa', masa);
      if (subeId) params.set('sube_id', subeId);
    }
    return params;
  };

  const handleAsistan = () => {
    const params = buildParams();
    navigate(`/musteri/chat?${params.toString()}`);
  };

  const handleMenu = () => {
    const params = buildParams();
    navigate(`/musteri/menu?${params.toString()}`);
  };

  return (
    <div className="min-h-screen bg-[#050c0a] flex items-center justify-center p-6 relative overflow-hidden font-outfit">
      {/* Premium Background Elements */}
      <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-emerald-500/10 blur-[120px] rounded-full animate-pulse-slow" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-emerald-600/5 blur-[100px] rounded-full animate-pulse-slow delay-700" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full bg-[radial-gradient(circle_at_center,rgba(16,185,129,0.03)_0%,transparent_70%)] pointer-events-none" />

      <div className="max-w-md w-full relative z-10 space-y-12">
        {/* Brand Identity */}
        <div className="text-center space-y-4 animate-fade-in-down">
          <div className="inline-block px-4 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-bold uppercase tracking-[0.2em] mb-4">
            Neso Intelligence
          </div>
          <h1 className="text-6xl font-black text-white tracking-tighter">
            NESO<span className="text-emerald-500">.</span>
          </h1>
          <p className="text-slate-400 font-medium text-lg tracking-wide uppercase">Dijital Sipariş Deneyimi</p>
        </div>

        {/* Main Interface Card */}
        <div className="glass-panel p-10 rounded-[2.5rem] border border-white/5 shadow-2xl space-y-10 relative group overflow-hidden animate-fade-in-up">
          <div className="absolute inset-0 bg-gradient-to-br from-white/[0.02] to-transparent pointer-events-none" />
          
          <div className="text-center space-y-3 relative">
            <h2 className="text-3xl font-bold text-white tracking-tight">Hoş Geldiniz</h2>
            <div className="h-1 w-12 bg-emerald-500 mx-auto rounded-full" />
            <p className="text-slate-400 font-medium pt-2">
              {loading
                ? 'Masa kimliğiniz doğrulanıyor...'
                : 'Dijital asistanımız sizi bekliyor.'}
            </p>
            
            {masa && !loading && (
              <div className="mt-6 inline-flex items-center gap-2 px-6 py-2 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-bold text-sm">
                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                MASA: {masa}
              </div>
            )}
            
            {error && (
              <div className="mt-4 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium">
                {error}
              </div>
            )}
          </div>

          {/* Premium Actions or Warning */}
          <div className="space-y-4 relative">
            {isBlocked ? (
              <div className="p-6 rounded-[1.5rem] bg-amber-500/10 border border-amber-500/20 text-center space-y-4">
                <div className="w-12 h-12 rounded-full bg-amber-500/20 flex items-center justify-center mx-auto border border-amber-500/40">
                  <span className="text-amber-400 font-black text-xl">!</span>
                </div>
                <h3 className="text-xl font-bold text-white">
                  {tableStatus === 'rezerve' && "Masa Rezerve Edilmiştir"}
                  {tableStatus === 'dolu' && "Masa Doludur"}
                  {tableStatus === 'temizlik' && "Masa Hazırlanıyor"}
                </h3>
                <p className="text-slate-400 text-sm font-medium">
                  {tableStatus === 'rezerve' && "Bu masa rezervasyonlu olarak işaretlenmiştir. Lütfen farklı boş bir masaya geçebilir veya görevliye danışarak bilgi alabilirsiniz."}
                  {tableStatus === 'dolu' && "Bu masa şu anda başka bir müşterimiz tarafından kullanılmaktadır. Lütfen boş bir masaya geçmeyi deneyiniz."}
                  {tableStatus === 'temizlik' && "Bu masa şu anda temizlik ve hazırlık aşamasındadır. Lütfen bekleyiniz veya başka bir masaya geçiniz."}
                </p>
                <div className="pt-2">
                   <p className="text-[10px] text-amber-500/50 uppercase font-black tracking-widest">Durum Kodu: {tableStatus?.toUpperCase()}</p>
                </div>
              </div>
            ) : (
              <>
                <button
                  onClick={handleAsistan}
                  disabled={loading}
                  className="glow-button w-full group flex items-center justify-between px-8 py-5 rounded-[1.5rem] text-white font-bold text-lg transition-all duration-500 hover:scale-[1.02] active:scale-95 disabled:opacity-50 disabled:grayscale"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-2xl bg-white/10 flex items-center justify-center group-hover:bg-white/20 transition-colors">
                      <MessageCircle className="w-6 h-6 text-emerald-300" />
                    </div>
                    <span>{loading ? 'Hazırlanıyor...' : 'Asistanı Başlat'}</span>
                  </div>
                  <div className="opacity-0 group-hover:opacity-100 transition-all duration-300 transform translate-x-2 group-hover:translate-x-0">
                    →
                  </div>
                </button>

                <button
                  onClick={handleMenu}
                  disabled={loading}
                  className="w-full group flex items-center justify-between px-8 py-5 bg-white/5 border border-white/10 hover:bg-white/10 hover:border-white/20 rounded-[1.5rem] text-slate-200 font-bold text-lg transition-all duration-500 hover:scale-[1.02] active:scale-95 disabled:opacity-50"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-2xl bg-white/5 flex items-center justify-center group-hover:bg-white/10 transition-colors">
                      <MenuIcon className="w-6 h-6 text-slate-400" />
                    </div>
                    <span>Menüyü Keşfet</span>
                  </div>
                  <div className="opacity-0 group-hover:opacity-100 transition-all duration-300 transform translate-x-2 group-hover:translate-x-0">
                    →
                  </div>
                </button>
              </>
            )}
          </div>

          {/* Visual Trust Indicator */}
          <div className="text-center pt-4 opacity-30 group-hover:opacity-60 transition-opacity">
             <div className="flex justify-center gap-3">
                <div className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                <div className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                <div className="w-1.5 h-1.5 rounded-full bg-slate-400" />
             </div>
          </div>
        </div>

        {/* Global Branding Footer */}
        <div className="text-center space-y-4 animate-fade-in opacity-50">
          <p className="text-slate-500 text-sm font-medium tracking-widest uppercase">
            Powered by Neso Advanced AI
          </p>
          <div className="text-[10px] text-slate-600 font-bold uppercase tracking-[0.3em]">
            Zero Identity Tracking • Secure Session
          </div>
        </div>
      </div>
    </div>
  );
}




