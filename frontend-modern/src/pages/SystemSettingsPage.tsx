import { useState } from 'react';
import { useAuthStore } from '../store/authStore';

interface SettingGroup {
  title: string;
  description?: string;
  items: Array<{
    id: string;
    label: string;
    description?: string;
    type: 'toggle' | 'link';
    href?: string;
    defaultValue?: boolean;
  }>;
}

const SETTINGS: SettingGroup[] = [
  {
    title: 'Genel Ayarlar',
    description: 'Kafe bilgileriniz ve marka kimliğiniz',
    items: [
      {
        id: 'branding',
        label: 'Marka & Tema Yönetimi',
        description: 'Logo, renk paleti ve uygulama başlığı',
        type: 'link',
        href: '/superadmin',
      },
      {
        id: 'notifications',
        label: 'Bildirimleri Aktif Tut',
        description: 'Yeni sipariş ve ödeme bildirimlerini al',
        type: 'toggle',
        defaultValue: true,
      },
    ],
  },
  {
    title: 'Operasyon',
    description: 'Şube ve kullanıcı yönetimi seçenekleri',
    items: [
      {
        id: 'shift-reminders',
        label: 'Vardiya Hatırlatmaları',
        description: 'Personel vardiya bildirimlerini otomatik gönder',
        type: 'toggle',
        defaultValue: false,
      },
      {
        id: 'staff',
        label: 'Personel Erişimleri',
        description: 'Rolleri ve yetkileri düzenle',
        type: 'link',
        href: '/personeller',
      },
    ],
  },
];

export default function SystemSettingsPage() {
  const { theme, setTheme, tenantCustomization } = useAuthStore((state) => ({ 
    theme: state.theme, 
    setTheme: state.setTheme,
    tenantCustomization: state.tenantCustomization,
  }));
  const businessName = tenantCustomization?.app_name || 'İşletme';
  const [toggles, setToggles] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {};
    SETTINGS.forEach((group) => {
      group.items.forEach((item) => {
        if (item.type === 'toggle') {
          initial[item.id] = item.defaultValue ?? false;
        }
      });
    });
    return initial;
  });

  const handleToggle = (id: string, value: boolean) => {
    setToggles((prev) => ({ ...prev, [id]: value }));
  };

  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold text-white">Ayarlar</h1>
        <p className="text-white/70 max-w-2xl">
          {businessName} deneyimini işletmenize göre şekillendirin. Tema, bildirim ve operasyonel
          ayarlarınızı buradan yönetebilirsiniz.
        </p>
      </header>

      <section className="rounded-2xl border border-white/10 bg-white/5 p-6 shadow-lg shadow-primary-950/20">
        <header className="mb-4 space-y-1">
          <h2 className="text-xl font-semibold text-white">Görünüm</h2>
          <p className="text-sm text-white/60">Panel temasını tercihlerinize göre ayarlayın.</p>
        </header>
        <div className="flex flex-wrap gap-4">
          <button
            type="button"
            onClick={() => setTheme('light')}
            className={`flex flex-1 min-w-[160px] items-center gap-3 rounded-2xl border px-4 py-3 transition ${
              theme === 'light'
                ? 'border-amber-300 bg-white text-primary-900 shadow-lg shadow-amber-500/30'
                : 'border-white/10 bg-white/5 text-white/70 hover:bg-white/10'
            }`}
          >
            <span className="text-lg">🌞</span>
            <div className="text-left">
              <p className="font-semibold">Açık Tema</p>
              <p className="text-xs text-white/60">Aydınlık ve ferah görünüm</p>
            </div>
          </button>
          <button
            type="button"
            onClick={() => setTheme('dark')}
            className={`flex flex-1 min-w-[160px] items-center gap-3 rounded-2xl border px-4 py-3 transition ${
              theme === 'dark'
                ? 'border-emerald-300 bg-emerald-500/20 text-white shadow-lg shadow-emerald-500/40'
                : 'border-white/10 bg-white/5 text-white/70 hover:bg-white/10'
            }`}
          >
            <span className="text-lg">🌙</span>
            <div className="text-left">
              <p className="font-semibold">Koyu Tema</p>
              <p className="text-xs text-white/60">Göz yormayan gece modu</p>
            </div>
          </button>
        </div>
      </section>

      <div className="grid gap-6">
        {SETTINGS.map((group) => (
          <section key={group.title} className="rounded-2xl border border-white/10 bg-white/5 p-6 shadow-lg shadow-primary-950/20">
            <header className="mb-4 space-y-1">
              <h2 className="text-xl font-semibold text-white">{group.title}</h2>
              {group.description && <p className="text-sm text-white/60">{group.description}</p>}
            </header>

            <div className="space-y-4">
              {group.items.map((item) => (
                <div
                  key={item.id}
                  className="flex flex-col gap-2 rounded-xl border border-white/10 bg-white/5 p-4 md:flex-row md:items-center md:justify-between"
                >
                  <div>
                    <p className="text-white font-medium">{item.label}</p>
                    {item.description && <p className="text-sm text-white/60">{item.description}</p>}
                  </div>

                  {item.type === 'toggle' ? (
                    <button
                      type="button"
                      onClick={() => handleToggle(item.id, !toggles[item.id])}
                      className={`flex h-7 w-14 items-center rounded-full border border-white/15 px-1 transition ${
                        toggles[item.id] ? 'bg-emerald-500/90 justify-end' : 'bg-white/15 justify-start'
                      }`}
                    >
                      <span className="inline-block h-5 w-5 rounded-full bg-white shadow" />
                    </button>
                  ) : (
                    <a
                      href={item.href}
                      className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/10 px-3 py-2 text-sm text-white/90 transition hover:bg-white/15"
                    >
                      Aç
                    </a>
                  )}
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

