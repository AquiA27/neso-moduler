import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, FileText, Shield, Scale, ChevronRight } from 'lucide-react';
import logo from '../assets/neso-logo.jpg';

type LegalDocType = 'kvkk' | 'terms' | 'privacy' | 'cookies';

interface LegalDoc {
  title: string;
  icon: any;
  content: JSX.Element;
}

export default function LegalPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const type = (searchParams.get('type') as LegalDocType) || 'kvkk';
  
  const [activeTab, setActiveTab] = useState<LegalDocType>(type);

  useEffect(() => {
    setActiveTab(type);
  }, [type]);

  const docs: Record<LegalDocType, LegalDoc> = {
    kvkk: {
      title: 'KVKK Aydınlatma Metni',
      icon: Shield,
      content: (
        <div className="space-y-6 text-slate-300 leading-relaxed">
          <p className="font-bold text-white text-lg">1. Veri Sorumlusu</p>
          <p>
            Neso Intelligent Systems ("Şirket") olarak, kişisel verilerinizin güvenliği hususuna azami hassasiyet göstermekteyiz. 6698 sayılı Kişisel Verilerin Korunması Kanunu ("KVKK") uyarınca, veri sorumlusu sıfatıyla kişisel verilerinizi aşağıda açıklanan çerçevede işlemekteyiz.
          </p>
          
          <p className="font-bold text-white text-lg">2. Kişisel Verilerin İşlenme Amacı</p>
          <ul className="list-disc pl-6 space-y-2">
            <li>Platform hizmetlerinin sunulması ve iyileştirilmesi,</li>
            <li>Sistem güvenliğinin sağlanması ve hata takibi,</li>
            <li>Yasal yükümlülüklerin yerine getirilmesi,</li>
            <li>İşletme sahipleriyle iletişim süreçlerinin yürütülmesi.</li>
          </ul>

          <p className="font-bold text-white text-lg">3. İşlenen Kişisel Veriler</p>
          <p>
            Ad-soyad, e-posta adresi, telefon numarası, IP adresi ve kullanım logları gibi verileriniz, platformun işleyişi için zorunlu olarak işlenmektedir.
          </p>

          <p className="font-bold text-white text-lg">4. Veri Sahiplerinin Hakları</p>
          <p>
            Kanun'un 11. maddesi uyarınca; verilerinizin işlenip işlenmediğini öğrenme, işlenmişse bilgi talep etme, verilerin düzeltilmesini veya silinmesini isteme haklarına sahipsiniz.
          </p>
        </div>
      )
    },
    terms: {
      title: 'Kullanım Koşulları',
      icon: Scale,
      content: (
        <div className="space-y-6 text-slate-300 leading-relaxed">
          <p className="font-bold text-white text-lg">1. Hizmet Tanımı</p>
          <p>
            Neso Modüler, restoran ve kafeler için bulut tabanlı bir yönetim yazılımıdır. Hizmet, abonelik bazlı (SaaS) olarak sunulmaktadır.
          </p>

          <p className="font-bold text-white text-lg">2. Hesap Güvenliği</p>
          <p>
            Kullanıcılar, kendi şifre ve hesap bilgilerinin güvenliğinden bizzat sorumludur. Hesabın yetkisiz kullanımı durumunda Şirket sorumlu tutulamaz.
          </p>

          <p className="font-bold text-white text-lg">3. Veri Yedekleme</p>
          <p>
            Neso, verileri düzenli olarak yedeklemekle birlikte, mücbir sebeplerden kaynaklanan veri kayıplarından doğrudan sorumlu değildir. İşletmelerin kendi kritik verilerini periyodik olarak raporlaması önerilir.
          </p>

          <p className="font-bold text-white text-lg">4. Fikri Mülkiyet</p>
          <p>
            Yazılımın tüm kod, tasarım ve içerik hakları Neso Intelligent Systems'a aittir. İzinsiz kopyalanması veya tersine mühendislik yapılması yasaktır.
          </p>
        </div>
      )
    },
    privacy: {
      title: 'Gizlilik Politikası',
      icon: FileText,
      content: (
        <div className="space-y-6 text-slate-300 leading-relaxed">
          <p className="font-bold text-white text-lg">1. Veri Toplama</p>
          <p>
            Uygulamamızı kullanırken sağladığınız bilgiler, yalnızca size daha iyi hizmet sunmak ve yasal yükümlülüklerimizi yerine getirmek amacıyla kullanılır.
          </p>

          <p className="font-bold text-white text-lg">2. Veri Paylaşımı</p>
          <p>
            Kişisel verileriniz, yasal mercilerin talebi veya hizmetin ifası için gerekli olan iş ortakları (ödeme sistemleri vb.) dışında üçüncü şahıslarla asla paylaşılmaz.
          </p>

          <p className="font-bold text-white text-lg">3. Güvenlik Önlemleri</p>
          <p>
            Verileriniz SSL sertifikalı sunucularda, endüstri standardı şifreleme yöntemleri ile korunmaktadır.
          </p>
        </div>
      )
    },
    cookies: {
      title: 'Çerez Politikası',
      icon: Shield,
      content: (
        <div className="space-y-6 text-slate-300 leading-relaxed">
          <p className="font-bold text-white text-lg">1. Çerezlerin Kullanımı</p>
          <p>
            Neso Modüler, oturum yönetimi ve kullanıcı tercihlerini hatırlamak amacıyla teknik çerezler kullanmaktadır.
          </p>
          <p className="font-bold text-white text-lg">2. Çerez Türleri</p>
          <ul className="list-disc pl-6 space-y-2">
            <li><strong>Zorunlu Çerezler:</strong> Sistemin çalışması için gereklidir.</li>
            <li><strong>Analitik Çerezler:</strong> Performans takibi için isimsiz veri toplar.</li>
          </ul>
        </div>
      )
    }
  };

  const handleBack = () => navigate(-1);

  return (
    <div className="min-h-screen bg-slate-950 text-white font-outfit relative overflow-hidden">
      {/* Background Ornaments */}
      <div className="absolute top-0 left-0 w-[50%] h-[50%] bg-emerald-500/5 blur-[120px] rounded-full pointer-events-none" />
      <div className="absolute bottom-0 right-0 w-[50%] h-[50%] bg-cyan-500/5 blur-[120px] rounded-full pointer-events-none" />

      <div className="max-w-6xl mx-auto px-6 py-12 relative z-10">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-8 mb-12">
          <div className="flex items-center gap-6">
            <button
              onClick={handleBack}
              className="w-12 h-12 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center hover:bg-white/10 transition-all group"
            >
              <ArrowLeft className="w-5 h-5 text-white/50 group-hover:text-white transition-colors" />
            </button>
            <div className="flex items-center gap-4">
              <img src={logo} className="h-12 w-12 rounded-xl object-cover border border-white/10" alt="Logo" />
              <div>
                <h1 className="text-3xl font-black tracking-tight">Hukuki Belgeler</h1>
                <p className="text-slate-500 text-sm font-medium uppercase tracking-widest">Neso Bilgi Sistemleri</p>
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
          {/* Sidebar Navigation */}
          <div className="lg:col-span-4 space-y-4">
            {(Object.keys(docs) as LegalDocType[]).map((key) => {
              const doc = docs[key];
              const Icon = doc.icon;
              return (
                <button
                  key={key}
                  onClick={() => navigate(`?type=${key}`)}
                  className={`w-full flex items-center justify-between p-6 rounded-3xl transition-all duration-300 border ${
                    activeTab === key
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-white shadow-lg shadow-emerald-500/5'
                      : 'bg-white/5 border-white/5 text-slate-400 hover:bg-white/10'
                  }`}
                >
                  <div className="flex items-center gap-4">
                    <div className={`p-2 rounded-xl ${activeTab === key ? 'bg-emerald-500 text-slate-950' : 'bg-white/5'}`}>
                      <Icon size={20} />
                    </div>
                    <span className="font-bold text-sm tracking-tight">{doc.title}</span>
                  </div>
                  <ChevronRight size={18} className={`transition-transform duration-300 ${activeTab === key ? 'translate-x-0 opacity-100' : '-translate-x-2 opacity-0'}`} />
                </button>
              );
            })}
          </div>

          {/* Content Area */}
          <div className="lg:col-span-8">
            <div className="glass-panel p-10 md:p-14 rounded-[40px] border border-white/10 shadow-2xl animate-in fade-in slide-in-from-bottom duration-700">
              <div className="flex items-center gap-4 mb-10 pb-10 border-b border-white/5">
                <div className="p-4 rounded-2xl bg-emerald-500/20 text-emerald-400">
                  {(() => {
                    const Icon = docs[activeTab].icon;
                    return <Icon size={32} />;
                  })()}
                </div>
                <div>
                  <h2 className="text-4xl font-black tracking-tighter">{docs[activeTab].title}</h2>
                  <p className="text-slate-500 text-xs font-bold uppercase tracking-[0.2em] mt-1">Son Güncelleme: 21 Nisan 2026</p>
                </div>
              </div>
              
              {docs[activeTab].content}

              <div className="mt-12 p-8 rounded-3xl bg-white/[0.02] border border-white/5 text-center">
                <p className="text-slate-500 text-sm italic">
                  Bu belge bilgilendirme amaçlıdır. Daha fazla bilgi için <span className="text-emerald-400 font-bold">hukuk@neso.com</span> adresinden bize ulaşabilirsiniz.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
