import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { MessageCircle, Menu as MenuIcon } from 'lucide-react';

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

  useEffect(() => {
    const loadMasaFromQR = async () => {
      if (!qrCode) return;
      try {
        setLoading(true);
        setError('');
        const API_BASE_URL = (import.meta.env?.VITE_API_URL as string) || 'http://localhost:8000';
        const response = await fetch(`${API_BASE_URL}/public/masa/${qrCode}`);
        if (!response.ok) {
          throw new Error('Masaya ulaşılamadı');
        }
        const data = await response.json();
        setMasa(data.masa_adi || initialMasa);
        if (data.sube_id) {
          setSubeId(String(data.sube_id));
        } else if (!subeId) {
          setSubeId('1');
        }
      } catch (err) {
        console.error('QR kod masa bilgisi yüklenemedi:', err);
        setError('Masa bilgisi alınamadı. Lütfen tekrar deneyin.');
        if (!subeId) {
          setSubeId('1');
        }
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
    <div className="min-h-screen bg-gradient-to-br from-primary-900 via-primary-800 to-primary-900 flex items-center justify-center p-4">
      <div className="max-w-md w-full space-y-8">
        {/* Logo/Brand */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">Neso</h1>
          <p className="text-white/70">Sipariş Asistanı</p>
        </div>

        {/* Main Card */}
        <div className="card p-8 space-y-6">
          <div className="text-center mb-6">
            <h2 className="text-2xl font-semibold mb-2">Hoş Geldiniz!</h2>
            <p className="text-white/70">
              {loading
                ? 'Masa bilgileriniz yükleniyor...'
                : 'Size nasıl yardımcı olabiliriz?'}
            </p>
            {masa && !loading && (
              <p className="text-sm text-primary-300 mt-2">Masa: {masa}</p>
            )}
            {error && (
              <p className="text-xs text-tertiary-300 mt-2">{error}</p>
            )}
          </div>

          {/* Action Buttons */}
          <div className="space-y-4">
            <button
              onClick={handleAsistan}
              disabled={loading}
              className="w-full flex items-center justify-center gap-3 px-6 py-4 bg-gradient-to-r from-secondary-600 to-secondary-500 hover:from-secondary-600/90 hover:to-secondary-500/90 rounded-lg transition-colors text-accent-mist font-semibold text-lg shadow-lg shadow-secondary-900/30 hover:shadow-secondary-800/40 transform hover:scale-[1.02]"
            >
              <MessageCircle className="w-6 h-6" />
              <span>{loading ? 'Bekleyin...' : 'Asistana Bağlan'}</span>
            </button>

            <button
              onClick={handleMenu}
              disabled={loading}
              className="w-full flex items-center justify-center gap-3 px-6 py-4 bg-primary-900/40 hover:bg-primary-800/40 rounded-lg transition-colors text-accent-mist font-semibold text-lg border border-primary-500/25"
            >
              <MenuIcon className="w-6 h-6" />
              <span>{loading ? 'Bekleyin...' : 'Menüyü Gör'}</span>
            </button>
          </div>

          {/* Info */}
          <div className="text-center text-sm text-white/50 pt-4 border-t border-white/10">
            <p>QR kodunu okutarak hızlıca sipariş verebilirsiniz</p>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center text-white/40 text-xs">
          <p>Herhangi bir kimlik bilgisi gerektirmez</p>
        </div>
      </div>
    </div>
  );
}




