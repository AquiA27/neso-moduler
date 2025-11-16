import { useState, useEffect } from 'react';
import { assistantApi } from '../lib/api';
import { Settings, Save } from 'lucide-react';

interface VoicePreset {
  id: string;
  provider: string;
  label: string;
  tone?: string;
  description?: string;
  language?: string;
  enabled: boolean;
}

interface AssistantSettings {
  tts_voice_id: string;
  tts_speech_rate: number;
  tts_provider: string;
}

export default function AssistantPage() {
  const [settings, setSettings] = useState<AssistantSettings>({
    tts_voice_id: 'system_tr_default',
    tts_speech_rate: 1.0,
    tts_provider: 'system',
  });
  const [availableVoices, setAvailableVoices] = useState<VoicePreset[]>([]);
  const [supportedProviders, setSupportedProviders] = useState<string[]>([]);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [loading, setLoading] = useState(true);

  // Load settings on mount
  useEffect(() => {
    loadSettings();
  }, []);

  useEffect(() => {
    if (availableVoices.length === 0) {
      return;
    }
    const providerVoices = availableVoices.filter(v => v.provider === settings.tts_provider);
    if (providerVoices.length === 0) {
      const fallback = availableVoices[0];
      if (fallback && fallback.id !== settings.tts_voice_id) {
        setSettings(prev => ({ ...prev, tts_provider: fallback.provider, tts_voice_id: fallback.id }));
      }
      return;
    }
    if (!providerVoices.some(v => v.id === settings.tts_voice_id)) {
      setSettings(prev => ({ ...prev, tts_voice_id: providerVoices[0].id }));
    }
  }, [settings.tts_provider, availableVoices]);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const response = await assistantApi.getSettings();
      const data = response.data || {};
      const voices: VoicePreset[] = data.available_voices || [];
      const providers: string[] = data.supported_providers || [];

      setAvailableVoices(voices);
      setSupportedProviders(providers);

      let provider: string = data.tts_provider || 'system';
      let voiceId: string | undefined = data.tts_voice_id;
      const speechRate: number = typeof data.tts_speech_rate === 'number' ? data.tts_speech_rate : parseFloat(data.tts_speech_rate || '1');

      if (voices.length > 0) {
        const voiceMatch = voiceId ? voices.find(v => v.id === voiceId) : undefined;
        if (voiceMatch) {
          provider = voiceMatch.provider;
          voiceId = voiceMatch.id;
        } else {
          const providerMatch = voices.find(v => v.provider === provider) || voices[0];
          voiceId = providerMatch?.id || voices[0].id;
          provider = providerMatch?.provider || provider;
        }
      } else {
        voiceId = voiceId || 'system_tr_default';
      }

      setSettings({
        tts_voice_id: voiceId || 'system_tr_default',
        tts_speech_rate: Number.isFinite(speechRate) ? speechRate : 1.0,
        tts_provider: provider,
      });
    } catch (err) {
      console.error('Failed to load settings:', err);
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
    setSettingsLoading(true);
    try {
      await assistantApi.updateSettings({
        tts_voice_id: settings.tts_voice_id,
        tts_speech_rate: settings.tts_speech_rate,
        tts_provider: settings.tts_provider,
      });
      alert('Ayarlar başarıyla kaydedildi!');
    } catch (err: any) {
      console.error('Failed to save settings:', err);
      alert(`Ayarlar kaydedilemedi: ${err.response?.data?.detail || err.message}`);
    } finally {
      setSettingsLoading(false);
    }
  };

  const providerMeta: Record<string, { label: string; envHint?: string }> = {
    system: { label: 'Sistem - Düşük Kalite (Sadece Test İçin)' },
    google: { label: 'Google Cloud TTS - En İyi Kalite (Önerilen)', envHint: 'GOOGLE_TTS_API_KEY' },
    azure: { label: 'Azure Speech - Yüksek Kalite', envHint: 'AZURE_SPEECH_KEY & AZURE_SPEECH_REGION' },
    openai: { label: 'OpenAI TTS - Yüksek Kalite', envHint: 'OPENAI_API_KEY' },
    aws: { label: 'AWS Polly - Yüksek Kalite', envHint: 'AWS_ACCESS_KEY_ID & AWS_SECRET_ACCESS_KEY' },
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-white/60">Ayarlar yükleniyor...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Settings className="w-8 h-8 text-primary-500" />
          <h2 className="text-3xl font-bold">Müşteri Asistanı Ayarları</h2>
        </div>
      </div>

      <div className="card p-6 space-y-8">
        {/* Model Seçimi */}
        <div className="space-y-3">
          <label className="block text-lg font-semibold">Ses Motoru (TTS Servisi)</label>
          <p className="text-sm text-white/60 mb-4">
            Müşteri asistanının ses kalitesini belirler. Premium sağlayıcılar daha doğal ses üretir; ancak ilgili API anahtarlarının tanımlanmış olması gerekir.
          </p>
          <select
            value={settings.tts_provider}
            onChange={(e) => {
              const nextProvider = e.target.value;
              const providerVoices = availableVoices.filter(v => v.provider === nextProvider);
              setSettings(prev => ({
                ...prev,
                tts_provider: nextProvider,
                tts_voice_id: providerVoices.length > 0 ? providerVoices[0].id : prev.tts_voice_id,
              }));
            }}
            className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-white"
          >
            {Object.entries(providerMeta).map(([key, meta]) => {
              const enabled = supportedProviders.includes(key);
              const prefix = enabled ? '✅ ' : '⚠️ ';
              return (
                <option key={key} value={key} className="bg-gray-800">
                  {prefix}{meta.label}
                </option>
              );
            })}
          </select>
          {!supportedProviders.includes(settings.tts_provider) && (
            <div className="mt-2 p-4 bg-yellow-500/20 border border-yellow-500/30 rounded-lg text-sm text-yellow-200">
              <strong>API anahtarı gerekli:</strong> {providerMeta[settings.tts_provider]?.envHint || 'İlgili ortam değişkenlerini backend/.env dosyasına ekleyin.'}
            </div>
          )}
        </div>

        {/* Voice Preset Selection */}
        <div className="space-y-3">
          <label className="block text-lg font-semibold">Ses Karakteri</label>
          <p className="text-sm text-white/60">
            Asistanın tonunu seçin. Karakter seçimi karşılama cümleleri ve kampanya duyurularında hissedilir.
          </p>
          {availableVoices.filter(v => v.provider === settings.tts_provider).length === 0 ? (
            <div className="mt-2 p-4 bg-white/5 border border-white/10 rounded-lg text-sm text-white/60">
              Bu sağlayıcı için tanımlı ses karakteri bulunamadı. Başka bir sağlayıcı seçin.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {availableVoices
                .filter(v => v.provider === settings.tts_provider)
                .map((voice) => {
                  const isActive = settings.tts_voice_id === voice.id;
                  return (
                    <button
                      key={voice.id}
                      type="button"
                      disabled={!voice.enabled}
                      onClick={() => setSettings(prev => ({ ...prev, tts_voice_id: voice.id }))}
                      className={`text-left p-4 rounded-xl border transition-all duration-200 ${
                        isActive ? 'border-primary-400 bg-primary-900/30 shadow-lg shadow-primary-900/30' : 'border-white/15 bg-white/5 hover:border-primary-400/60'
                      } ${voice.enabled ? '' : 'opacity-60 cursor-not-allowed'}`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div>
                          <h4 className="text-base font-semibold text-white">{voice.label}</h4>
                          {voice.tone && (
                            <span className="text-xs text-primary-200 block mt-1">{voice.tone}</span>
                          )}
                        </div>
                        <span className="text-xs uppercase tracking-wide text-white/50">{voice.language || 'TR'}</span>
                      </div>
                      {voice.description && (
                        <p className="mt-3 text-sm text-white/70 leading-relaxed">{voice.description}</p>
                      )}
                      {!voice.enabled && (
                        <div className="mt-3 text-xs text-yellow-300">
                          API anahtarı bulunamadı. {providerMeta[voice.provider]?.envHint || 'İlgili sağlayıcıyı yapılandırın.'}
                        </div>
                      )}
                    </button>
                  );
                })}
            </div>
          )}
        </div>

        {/* Speech Rate */}
        <div className="space-y-3">
          <label className="block text-lg font-semibold">
            Konuşma Hızı: {settings.tts_speech_rate.toFixed(2)}x
          </label>
          <p className="text-sm text-white/60">
            Asistanın konuşma hızını ayarlayın. 1.0x normal hızdır.
          </p>
          <input
            type="range"
            min="0.25"
            max="2.0"
            step="0.05"
            value={settings.tts_speech_rate}
            onChange={(e) => setSettings({ ...settings, tts_speech_rate: parseFloat(e.target.value) })}
            className="w-full h-3 bg-white/10 rounded-lg appearance-none cursor-pointer accent-primary-600"
          />
          <div className="flex justify-between text-xs text-white/60">
            <span>Yavaş (0.25x)</span>
            <span>Normal (1.0x)</span>
            <span>Hızlı (2.0x)</span>
          </div>
        </div>

        {/* Save Button */}
        <div className="flex justify-end pt-4 border-t border-white/10">
          <button
            onClick={saveSettings}
            disabled={settingsLoading}
            className="px-8 py-3 bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 text-lg font-medium"
          >
            <Save className="w-5 h-5" />
            {settingsLoading ? 'Kaydediliyor...' : 'Ayarları Kaydet'}
          </button>
        </div>
      </div>
    </div>
  );
}
