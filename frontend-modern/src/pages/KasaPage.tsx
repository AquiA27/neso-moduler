import { useEffect, useState, useCallback, useRef } from 'react';
import { kasaApi, adisyonApi } from '../lib/api';
import { useWebSocket } from '../hooks/useWebSocket';

interface Table {
  masa: string;
  tutar?: number; // Backend'den bakiye geliyor
  bakiye?: number;
  siparis_toplam?: number;
  odeme_toplam?: number;
  adisyon_id?: number;
  hazir_count?: number;
}

interface Adisyon {
  id: number;
  masa: string;
  acilis_zamani: string;
  kapanis_zamani?: string;
  durum: string;
  toplam_tutar: number;
  odeme_toplam: number;
  bakiye: number;
  iskonto_orani: number;
  iskonto_tutari: number;
}

interface PaymentSummary {
  masa: string;
  toplam?: number;
  bakiye?: number;
  siparis_toplam?: number;
  odeme_toplam?: number;
  odemeler?: Array<{
    id: number;
    tutar: number;
    yontem: string;
    created_at: string;
    tip?: number;
  }>;
  siparisler?: any[];
  ozet?: {
    masa: string;
    siparis_toplam: number;
    odeme_toplam: number;
    bakiye: number;
  };
}

export default function KasaPage() {
  const [tables, setTables] = useState<Table[]>([]);
  const [selectedMasa, setSelectedMasa] = useState('');
  const [summary, setSummary] = useState<PaymentSummary | null>(null);
  const [paymentData, setPaymentData] = useState({
    tutar: '',
    yontem: 'nakit',
    iskonto_orani: '',
  });
  const [loading, setLoading] = useState(false);
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set()); // Format: "siparis_id-item_index"
  const selectedMasaRef = useRef<string>('');
  const [showMasaModal, setShowMasaModal] = useState(false);
  const [newMasa, setNewMasa] = useState('');
  const [allTables, setAllTables] = useState<Table[]>([]);
  const [adisyons, setAdisyons] = useState<Adisyon[]>([]);
  const [activeTab, setActiveTab] = useState<'masalar' | 'hesaplar'>('masalar');
  const [adisyonFilter, setAdisyonFilter] = useState<'acik' | 'kapali' | 'tumu'>('acik');
  const [paymentFeedback, setPaymentFeedback] = useState<string | null>(null);
  const [showAdisyonDetay, setShowAdisyonDetay] = useState(false);
  const [selectedAdisyonDetay, setSelectedAdisyonDetay] = useState<any>(null);

  const loadTables = useCallback(async () => {
    try {
      console.log('Kasa: Masalar yükleniyor...', new Date().toISOString());
      const response = await kasaApi.masalar({ limit: 200 });
      console.log('Kasa: Masalar yüklendi, response:', response.data);
      console.log('Kasa: Response data length:', response.data?.length || 0);
      // Backend'den gelen masalar zaten bakiye > 0 olanlar (hazir durumda)
      // Response'da 'bakiye' veya 'tutar' olabilir
      const tablesWithBalance = (response.data || []).map((table: any) => ({
        masa: table.masa,
        tutar: table.bakiye || table.tutar || 0, // bakiye varsa onu kullan
        bakiye: table.bakiye || table.tutar || 0,
        siparis_toplam: table.siparis_toplam || 0,
        odeme_toplam: table.odeme_toplam || 0,
        adisyon_id: table.adisyon_id,
        hazir_count: table.hazir_count || 0,
      }));
      console.log('Kasa: Masalar işlendi, toplam masa sayısı:', tablesWithBalance.length);
      if (tablesWithBalance.length > 0) {
        console.log('Kasa: Masalar listesi:', tablesWithBalance.map((t: any) => ({ masa: t.masa, bakiye: t.bakiye })));
      }
      setTables(tablesWithBalance);
    } catch (err) {
      console.error('Masalar yüklenemedi:', err);
    }
  }, []);

  const loadAdisyons = useCallback(async () => {
    try {
      const params = adisyonFilter === 'tumu' ? undefined : adisyonFilter;
      const response = await adisyonApi.acik(200, params);
      setAdisyons(response.data || []);
    } catch (err) {
      console.error('Adisyonlar yüklenemedi:', err);
    }
  }, [adisyonFilter]);

  useEffect(() => {
    loadTables();
    loadAdisyons();
    const interval = setInterval(() => {
      loadTables();
      loadAdisyons();
    }, 10000);
    return () => clearInterval(interval);
  }, [loadTables, loadAdisyons]);
  
  // Adisyon filtresi değiştiğinde adisyonları yeniden yükle
  useEffect(() => {
    if (activeTab === 'hesaplar') {
      loadAdisyons();
    }
  }, [adisyonFilter, activeTab, loadAdisyons]);

  const API_BASE_URL = (import.meta.env?.VITE_API_URL as string) || 'http://localhost:8000';
  const WS_URL = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://') + '/ws/connect/auth';

  // WebSocket connection for real-time updates
  useWebSocket({
    url: WS_URL,
    topics: ['kitchen', 'orders', 'cashier'],
    auth: true,
    onMessage: (data) => {
      console.log('Kasa WebSocket message:', data);
      if (data.type === 'new_order' || data.type === 'order_added' || data.type === 'order_update' || data.type === 'status_change' || data.type === 'table_transfer') {
        console.log('Kasa: WebSocket mesajı alındı, masalar yenileniyor...', data);
        // Özellikle 'status_change' ve 'hazir' durumu için masaları yenile
        if (data.type === 'status_change' && data.new_status === 'hazir') {
          console.log('Kasa: Sipariş hazır durumuna geçti, masalar ve seçili masa özeti yenileniyor...', data);
          // Biraz daha uzun gecikme - backend'deki durum güncellemesi ve bakiye hesaplaması tamamlansın
          setTimeout(() => {
            loadTables();
            loadAdisyons();
            // Eğer seçili masa varsa, özetini de yenile
            if (selectedMasaRef.current) {
              loadSummary(selectedMasaRef.current);
            }
          }, 500);
        } else {
          // Diğer durumlar için normal gecikme
          setTimeout(() => {
            loadTables();
            loadAdisyons();
          }, 200);
        }

        // Table transfer için özel işlem: hem kaynak hem hedef masayı yenile
        if (data.type === 'table_transfer') {
          if (data.from_masa && selectedMasaRef.current === data.from_masa) {
            console.log('Kasa: Kaynak masa özeti yenileniyor (table_transfer):', data.from_masa);
            setTimeout(() => {
              loadSummary(data.from_masa);
            }, 100);
          }
          if (data.to_masa && selectedMasaRef.current === data.to_masa) {
            console.log('Kasa: Hedef masa özeti yenileniyor (table_transfer):', data.to_masa);
            setTimeout(() => {
              loadSummary(data.to_masa);
            }, 100);
          }
        }
        // Eğer mesajda masa bilgisi varsa ve seçili masa o masaysa, özetini yenile
        else if (data.masa && selectedMasaRef.current === data.masa) {
          console.log('Kasa: Seçili masa özeti yenileniyor (WebSocket mesajından):', data.masa);
          // Kısa bir gecikme ile yenile ki backend'deki güncelleme tamamlansın
          setTimeout(() => {
            loadSummary(data.masa);
          }, 100);
        }
        // Eğer seçili masa varsa ama mesajdaki masa farklıysa da yenile (genel güncelleme)
        else if (selectedMasaRef.current) {
          console.log('Kasa: Seçili masa özeti yenileniyor (genel güncelleme):', selectedMasaRef.current);
          setTimeout(() => {
            loadSummary(selectedMasaRef.current);
          }, 100);
        }
      }
    },
    onConnect: () => {
      console.log('Kasa WebSocket connected');
    },
    onDisconnect: () => {
      console.log('Kasa WebSocket disconnected');
    },
  });

  // selectedMasa state'i değiştiğinde ref'i güncelle
  useEffect(() => {
    selectedMasaRef.current = selectedMasa;
  }, [selectedMasa]);

  const loadSummary = useCallback(async (masa: string) => {
    if (!masa) return;
    setLoading(true);
    try {
      // Detaylı bilgi için hesap/detay endpoint'ini kullan
      const response = await kasaApi.hesapDetay(masa);
      console.log('Hesap detay response:', response);
      console.log('Response data:', response.data);
      console.log('Response data.siparisler:', response.data?.siparisler);
      if (response.data?.siparisler) {
        response.data.siparisler.forEach((siparis: any, idx: number) => {
          console.log(`Siparis #${siparis.id} (index ${idx}):`, {
            id: siparis.id,
            durum: siparis.durum,
            tutar: siparis.tutar,
            sepet: siparis.sepet,
            sepet_tip: typeof siparis.sepet,
            sepet_length: Array.isArray(siparis.sepet) ? siparis.sepet.length : 'N/A',
            tüm_alanlar: Object.keys(siparis),
          });
        });
      }
      setSummary(response.data);
      setSelectedMasa(masa);
      // Yeni masa seçildiğinde önceki seçimleri temizle
      setSelectedItems(new Set());
      // İskonto oranını sıfırla, tutar useEffect tarafından otomatik güncellenecek
      const incomingBalance = response.data?.ozet?.bakiye ?? response.data?.bakiye ?? 0;
      setPaymentData(prev => ({ 
        ...prev, 
        iskonto_orani: '',
        tutar: incomingBalance > 0 ? incomingBalance.toFixed(2) : '',
      }));
      setPaymentFeedback(null);
    } catch (err) {
      console.error('Hesap detayı yüklenemedi:', err);
      // Fallback olarak basit özeti kullan
      try {
        const fallbackResponse = await kasaApi.hesapOzet(masa);
        setSummary(fallbackResponse.data);
        setSelectedMasa(masa);
      } catch (fallbackErr) {
        alert('Hesap bilgisi alınamadı');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const toggleItemSelection = (siparisId: number, itemIndex: number) => {
    const key = `${siparisId}-${itemIndex}`;
    setSelectedItems(prev => {
      const newSet = new Set(prev);
      if (newSet.has(key)) {
        newSet.delete(key);
      } else {
        newSet.add(key);
      }
      return newSet;
    });
  };

  const getSelectedItemsTotal = (): number => {
    if (!summary?.siparisler || selectedItems.size === 0) {
      return 0;
    }

    let total = 0;
    selectedItems.forEach((key) => {
      const [siparisId, itemIndex] = key.split('-').map(Number);
      const siparis = summary.siparisler?.find((s: any) => s.id === siparisId);
      if (siparis && siparis.sepet && Array.isArray(siparis.sepet)) {
        const item = siparis.sepet[itemIndex];
        if (item) {
          // İkram olup olmadığını kontrol et (fiyat 0 olabilir)
          const itemPrice = item.ikram ? 0 : (item.fiyat || item.toplam || 0);
          const itemAdet = item.adet || item.miktar || 1;
          total += itemPrice * itemAdet;
        }
      }
    });
    return total;
  };

  // Seçilen ürünler değiştiğinde tutarı otomatik güncelle
  useEffect(() => {
    const selectedTotal = getSelectedItemsTotal();
    if (selectedTotal > 0) {
      // Seçilen ürünler varsa, onların tutarını kullan
      const iskonto_orani = parseFloat(paymentData.iskonto_orani || '0');
      if (iskonto_orani > 0 && !isNaN(iskonto_orani) && iskonto_orani >= 0 && iskonto_orani <= 100) {
        const iskonto_tutari = (selectedTotal * iskonto_orani) / 100;
        const odenecek_tutar = Math.max(0, selectedTotal - iskonto_tutari);
        setPaymentData(prev => ({ ...prev, tutar: odenecek_tutar.toFixed(2) }));
      } else {
        setPaymentData(prev => ({ ...prev, tutar: selectedTotal.toFixed(2) }));
      }
    } else if (summary?.bakiye !== undefined) {
      // Seçilen ürün yoksa, masa bakiyesini kullan
      const iskonto_orani = parseFloat(paymentData.iskonto_orani || '0');
      if (iskonto_orani > 0 && !isNaN(iskonto_orani) && iskonto_orani >= 0 && iskonto_orani <= 100) {
        const bakiye = summary.bakiye || 0;
        const iskonto_tutari = (bakiye * iskonto_orani) / 100;
        const odenecek_tutar = Math.max(0, bakiye - iskonto_tutari);
        setPaymentData(prev => ({ ...prev, tutar: odenecek_tutar.toFixed(2) }));
      } else {
        setPaymentData(prev => ({ ...prev, tutar: (summary.bakiye || 0).toFixed(2) }));
      }
    }
  }, [selectedItems, summary?.siparisler, paymentData.iskonto_orani, summary?.bakiye]);

  const loadAllTables = useCallback(async () => {
    try {
      const response = await kasaApi.masalar({ limit: 200, tumu: true });
      const tablesWithBalance = (response.data || []).map((table: any) => ({
        masa: table.masa,
        tutar: table.bakiye || table.tutar || 0,
        bakiye: table.bakiye || table.tutar || 0,
        siparis_toplam: table.siparis_toplam || 0,
        odeme_toplam: table.odeme_toplam || 0,
      }));
      setAllTables(tablesWithBalance);
    } catch (err) {
      console.error('Tüm masalar yüklenemedi:', err);
    }
  }, []);

  useEffect(() => {
    if (showMasaModal) {
      loadAllTables();
    }
  }, [showMasaModal, loadAllTables]);

  const handleMasaDegistir = async () => {
    if (!newMasa.trim() || selectedItems.size === 0) {
      alert('Masa seçin ve ürün seçin');
      return;
    }
    try {
      setLoading(true);
      for (const key of selectedItems) {
        const [siparisId, itemIndex] = key.split('-').map(Number);
        await kasaApi.itemMasaDegistir({
          siparis_id: siparisId,
          item_index: itemIndex,
          yeni_masa: newMasa.trim(),
        });
      }
      setSelectedItems(new Set());
      setShowMasaModal(false);
      setNewMasa('');

      // Biraz bekleyip tabloları yenile (database transaction tamamlansın)
      setTimeout(() => {
        loadTables();
        if (selectedMasa) {
          loadSummary(selectedMasa);
        }
      }, 300);
    } catch (err) {
      console.error('Masa değiştirilemedi:', err);
      alert('Masa değiştirilemedi');
    } finally {
      setLoading(false);
    }
  };

  const handleIkram = async () => {
    if (selectedItems.size === 0) {
      alert('İkram yapmak için ürün seçin');
      return;
    }
    try {
      setLoading(true);
      for (const key of selectedItems) {
        const [siparisId, itemIndex] = key.split('-').map(Number);
        await kasaApi.itemIkram({
          siparis_id: siparisId,
          item_index: itemIndex,
        });
      }
      setSelectedItems(new Set());
      if (selectedMasa) {
        loadSummary(selectedMasa);
      }
      loadTables();
    } catch (err) {
      console.error('İkram yapılamadı:', err);
      alert('İkram yapılamadı');
    } finally {
      setLoading(false);
    }
  };

  const handlePayment = async () => {
     if (!selectedMasa || !paymentData.tutar) {
       alert('Masa seçin ve tutar girin');
       return;
     }
    try {
      setLoading(true);
      const iskonto_orani = paymentData.iskonto_orani ? parseFloat(paymentData.iskonto_orani) : 0;
      const response = await kasaApi.odemeEkle({
        masa: selectedMasa,
        tutar: parseFloat(paymentData.tutar),
        yontem: paymentData.yontem,
        iskonto_orani,
      });
      const paymentResult = response.data as {
        remaining_balance?: number;
        auto_closed?: boolean;
        tip?: number;
      };

      setSelectedItems(new Set());
      setPaymentFeedback(null);

      if (paymentResult?.auto_closed) {
        setSummary(null);
        setSelectedMasa('');
        setPaymentData({ tutar: '', yontem: 'nakit', iskonto_orani: '' });
        setPaymentFeedback('Hesap tamamen kapandı ve adisyon kapatıldı.');
        await loadTables();
        await loadAdisyons();
      } else {
        const remaining = paymentResult?.remaining_balance ?? summary?.bakiye ?? 0;
        setPaymentData({
          tutar: remaining > 0 ? remaining.toFixed(2) : '',
          yontem: paymentData.yontem,
          iskonto_orani: '',
        });
        setPaymentFeedback(
          remaining > 0
            ? `Kalan bakiye: ${remaining.toFixed(2)} TL`
            : 'Ödeme alındı.'
        );
        await loadSummary(selectedMasa);
        await loadTables();
      }

      if (paymentResult?.tip && paymentResult.tip > 0) {
        setPaymentFeedback(prev => `${prev ? `${prev} - ` : ''}Tip kaydedildi: ${paymentResult.tip.toFixed(2)} TL.`);
      }
    } catch (err) {
      console.error('Ödeme eklenemedi:', err);
      const message = (err as any)?.response?.data?.detail || 'Ödeme eklenemedi';
      alert(message);
    } finally {
      setLoading(false);
    }
  };

  const handleCloseAccount = async () => {
    if (!selectedMasa) return;
    if (!confirm('Hesabı kapatmak istediğinizden emin misiniz?')) return;
    try {
      await kasaApi.hesapKapat(selectedMasa);
      setSelectedMasa('');
      setSummary(null);
      loadTables();
    } catch (err) {
      console.error('Hesap kapatılamadı:', err);
      alert('Hesap kapatılamadı');
    }
  };

  const handleAdisyonKapat = async (adisyonId: number, masa: string) => {
    if (!confirm(`Masa ${masa} hesabını kapatmak istediğinizden emin misiniz?`)) return;
    try {
      await adisyonApi.kapat(adisyonId);
      loadAdisyons();
      loadTables();
      if (selectedMasa === masa) {
        setSelectedMasa('');
        setSummary(null);
      }
      alert('Hesap başarıyla kapatıldı');
    } catch (err: any) {
      console.error('Hesap kapatılamadı:', err);
      alert(err.response?.data?.detail || 'Hesap kapatılamadı');
    }
  };

  const handleShowAdisyonDetay = async (adisyonId: number) => {
    try {
      const response = await adisyonApi.detayli(adisyonId);
      setSelectedAdisyonDetay(response.data);
      setShowAdisyonDetay(true);
    } catch (err) {
      console.error('Adisyon detayı yüklenemedi:', err);
      alert('Adisyon detayı yüklenemedi');
    }
  };

  const currentBalance = summary?.ozet?.bakiye ?? summary?.bakiye ?? 0;

  return (
    <div className="space-y-6 sm:space-y-8">
      <h2 className="text-3xl font-bold">Kasa Yönetimi</h2>

      {/* Tab Sistemi */}
      <div className="flex flex-wrap gap-2 border-b border-white/10 pb-1">
        <button
          onClick={() => setActiveTab('masalar')}
          className={`w-full rounded-lg px-4 py-2 font-semibold transition-colors sm:w-auto ${
            activeTab === 'masalar'
              ? 'text-primary-300 border-b-2 border-primary-500'
              : 'text-white/60 hover:text-white/80'
          }`}
        >
          Masalar
        </button>
        <button
          onClick={() => setActiveTab('hesaplar')}
          className={`w-full rounded-lg px-4 py-2 font-semibold transition-colors sm:w-auto ${
            activeTab === 'hesaplar'
              ? 'text-primary-300 border-b-2 border-primary-500'
              : 'text-white/60 hover:text-white/80'
          }`}
        >
          Hesaplar (Adisyonlar)
        </button>
      </div>

      {activeTab === 'masalar' && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Masalar Tablosu */}
          <div className="card space-y-4 p-4 sm:p-6">
            <h3 className="text-xl font-semibold">Ödeme Bekleyen Masalar</h3>
            {tables.length === 0 ? (
              <div className="py-8 text-center text-white/50">Açık masa yok</div>
            ) : (
              <div className="max-h-96 overflow-x-auto overflow-y-auto rounded-lg border border-white/10">
                <table className="w-full min-w-[540px]">
                  <thead>
                    <tr className="border-b border-white/10">
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-white/70">
                        Masa
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-white/70">
                        Sipariş Toplam
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-white/70">
                        Ödeme Toplam
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-white/70">
                        Bakiye
                      </th>
                      <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wide text-white/70">
                        Hazır
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {tables.map((table, idx) => (
                      <tr
                        key={idx}
                        onClick={() => loadSummary(table.masa)}
                        className={`cursor-pointer border-b border-white/5 transition-colors hover:bg-white/5 ${
                          selectedMasa === table.masa ? 'bg-primary-600/20' : ''
                        }`}
                      >
                        <td className="px-4 py-3 font-medium">Masa {table.masa}</td>
                        <td className="px-4 py-3 text-right">{(table.siparis_toplam || 0).toFixed(2)} ₺</td>
                        <td className="px-4 py-3 text-right text-green-300">{(table.odeme_toplam || 0).toFixed(2)} ₺</td>
                        <td className="px-4 py-3 text-right font-bold text-primary-300">
                          {(table.bakiye || table.tutar || 0).toFixed(2)} ₺
                        </td>
                        <td className="px-4 py-3 text-center">
                          {table.hazir_count && table.hazir_count > 0 ? (
                            <span className="rounded px-2 py-1 text-xs text-green-300">{table.hazir_count}</span>
                          ) : (
                            <span className="text-white/30">-</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Hesap Özeti ve Ödeme */}
          <div className="card space-y-6 p-4 sm:p-6">
            <h3 className="text-xl font-semibold">Masa Hesabı</h3>

            {!selectedMasa ? (
              <div className="py-12 text-center text-white/50">Masa seçin</div>
            ) : (
              <>
                <div className="space-y-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <span className="text-sm text-white/70">Seçili Masa</span>
                      <h4 className="text-2xl font-bold">Masa {selectedMasa}</h4>
                    </div>
                    {summary && (
                      <div className="rounded-lg bg-white/5 px-4 py-2 text-center sm:text-right">
                        <span className="text-xs text-white/70">Bakiye</span>
                        <div className="text-xl font-bold text-primary-300">
                          {(summary.ozet?.bakiye ?? summary.bakiye ?? summary.toplam ?? 0).toFixed(2)} ₺
                        </div>
                      </div>
                    )}
                  </div>

                  {summary && (
                    <div className="space-y-4">
                      <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
                        <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                          <div className="text-white/60">Toplam Sipariş</div>
                          <div className="text-lg font-semibold text-white">{(summary.ozet?.siparis_toplam ?? summary.siparis_toplam ?? 0).toFixed(2)} TL</div>
                        </div>
                        <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                          <div className="text-white/60">Ödenen</div>
                          <div className="text-lg font-semibold text-white">{(summary.ozet?.odeme_toplam ?? summary.odeme_toplam ?? 0).toFixed(2)} TL</div>
                        </div>
                        <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                          <div className="text-white/60">Kalan Bakiye</div>
                          <div className={`text-lg font-semibold ${currentBalance > 0 ? 'text-amber-300' : 'text-emerald-300'}`}>{currentBalance.toFixed(2)} TL</div>
                        </div>
                      </div>
                      {/* Siparişler */}
                      <div className="bg-white/5 rounded-lg p-4">
                        <h5 className="text-sm font-semibold mb-3 text-white/90">Siparişler</h5>
                        {summary.siparisler && summary.siparisler.length > 0 ? (
                          <div className="space-y-3">
                            {summary.siparisler.map((siparis: any, idx: number) => {
                              const sepet = Array.isArray(siparis.sepet) ? siparis.sepet : [];
                              return (
                                <div key={idx} className="border-b border-white/10 pb-3 last:border-b-0 last:pb-0">
                                  <div className="mb-2 flex items-start justify-between">
                                    <div className="flex flex-1 items-center gap-2">
                                      <span className="text-xs text-white/50">Sipariş #{siparis.id}</span>
                                      <span
                                        className={`rounded px-2 py-0.5 text-xs ${
                                          siparis.durum === 'hazir'
                                            ? 'bg-green-500/20 text-green-300'
                                            : siparis.durum === 'odendi'
                                            ? 'bg-blue-500/20 text-blue-300'
                                            : 'bg-yellow-500/20 text-yellow-300'
                                        }`}
                                      >
                                        {siparis.durum || 'yeni'}
                                      </span>
                                    </div>
                                    <span className="font-semibold">{(Number(siparis.tutar) || 0).toFixed(2)} ₺</span>
                                  </div>
                                  {sepet.length > 0 ? (
                                    <div className="mt-2 space-y-1 border-l-2 border-primary-500/30 pl-2">
                                      {sepet.map((item: any, itemIdx: number) => {
                                        const quantityRaw = item.adet ?? item.miktar ?? 1;
                                        const quantity = Number.isFinite(quantityRaw) ? Number(quantityRaw) : 1;
                                        const unitPriceRaw =
                                          item.fiyat ?? (item.toplam && quantity ? item.toplam / quantity : undefined);
                                        const unitPrice = Number.isFinite(unitPriceRaw) ? Number(unitPriceRaw) : 0;
                                        const lineTotalRaw = item.toplam ?? unitPrice * quantity;
                                        const lineTotal = Number.isFinite(lineTotalRaw)
                                          ? Number(lineTotalRaw)
                                          : unitPrice * quantity;

                                        const itemKey = `${siparis.id}-${itemIdx}`;
                                        const isSelected = selectedItems.has(itemKey);
                                        return (
                                          <div key={itemIdx} className="flex items-center gap-2 text-sm text-white/80">
                                            <input
                                              type="checkbox"
                                              checked={isSelected}
                                              onChange={() => toggleItemSelection(siparis.id, itemIdx)}
                                              className="h-4 w-4 rounded border-white/30 bg-white/10 text-primary-500 focus:ring-primary-500"
                                            />
                                            <span className="flex-1">
                                              {item.urun || item.ad || 'Ürün'} × {quantity}
                                              {item.varyasyon && (
                                                <span className="ml-2 text-yellow-300">({item.varyasyon})</span>
                                              )}
                                              {item.ikram && <span className="ml-2 text-green-300">(İkram)</span>}
                                            </span>
                                            <span className="font-medium">{lineTotal.toFixed(2)} ₺</span>
                                          </div>
                                        );
                                      })}
                                    </div>
                                  ) : (
                                    <div className="mt-2 text-xs italic text-white/50">Sipariş içeriği bulunamadı</div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <div className="py-4 text-center text-sm text-white/50">Sipariş bulunamadı</div>
                        )}
                      </div>

                      {/* Ödemeler */}
                      {summary.odemeler && summary.odemeler.length > 0 && (
                        <div className="bg-white/5 rounded-lg p-4">
                          <h5 className="text-sm font-semibold mb-3 text-white/90">Ödemeler</h5>
                          <div className="space-y-2">
                            {summary.odemeler.map((odeme: any, idx: number) => (
                              <div key={idx} className="flex justify-between text-sm">
                                <div>
                                  <span className="text-white/70">{odeme.yontem || 'Ödeme'}</span>
                                  <span className="ml-2 text-xs text-white/50">
                                    {odeme.created_at ? new Date(odeme.created_at).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }) : ''}
                                  </span>
                                </div>
                                <div className="text-right">
                                  <span>{(odeme.tutar ?? 0).toFixed(2)} TL</span>
                                  {odeme.tip && odeme.tip > 0 && (
                                    <div className="text-xs text-emerald-300">Tip: {odeme.tip.toFixed(2)} TL</div>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Seçili Ürünler İçin İşlemler */}
                {selectedItems.size > 0 && (
                  <div className="rounded-lg border border-primary-500/30 bg-primary-500/20 p-4">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                      <span className="text-sm font-medium">{selectedItems.size} ürün seçildi</span>
                      <button
                        onClick={() => setSelectedItems(new Set())}
                        className="text-left text-xs text-white/70 transition-colors hover:text-white sm:text-right"
                      >
                        Seçimi Temizle
                      </button>
                    </div>
                    <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                      <button
                        onClick={() => setShowMasaModal(true)}
                        disabled={loading}
                        className="flex-1 rounded-lg bg-blue-600/20 px-4 py-2 text-sm transition-colors hover:bg-blue-600/30 disabled:opacity-50"
                      >
                        Masa Değiştir
                      </button>
                      <button
                        onClick={handleIkram}
                        disabled={loading}
                        className="flex-1 rounded-lg bg-green-600/20 px-4 py-2 text-sm transition-colors hover:bg-green-600/30 disabled:opacity-50"
                      >
                        İkram Yap
                      </button>
                    </div>
                  </div>
                )}

                {/* Ödeme Formu */}
                <div className="space-y-4">
                  {paymentFeedback && (
                    <div className="rounded-lg border border-white/10 bg-white/10 px-4 py-2 text-sm text-white/80">
                      {paymentFeedback}
                    </div>
                  )}
                  <div>
                    <label className="block text-sm font-medium mb-2">Ödeme Yöntemi</label>
                    <select
                      value={paymentData.yontem}
                      onChange={(e) => setPaymentData({ ...paymentData, yontem: e.target.value })}
                      className="w-full px-4 py-2 bg-white/10 border border-white/20 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                    >
                      <option value="nakit">Nakit</option>
                      <option value="kart">Kart</option>
                      <option value="havale">Havale</option>
                      <option value="iyzico">İyzico</option>
                      <option value="papara">Papara</option>
                      <option value="diger">Diğer</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">İskonto Oranı (%)</label>
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      max="100"
                      value={paymentData.iskonto_orani}
                      onChange={(e) => setPaymentData({ ...paymentData, iskonto_orani: e.target.value })}
                      className="w-full rounded-lg border border-white/20 bg-white/10 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
                      placeholder="0.0"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Tutar</label>
                    <input
                      type="number"
                      step="0.01"
                      value={paymentData.tutar}
                      onChange={(e) => setPaymentData({ ...paymentData, tutar: e.target.value })}
                      className="w-full rounded-lg border border-white/20 bg-white/10 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
                      placeholder="0.00"
                    />
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-white/60">
                      {currentBalance > 0 && [0.25, 0.5, 1].map((ratio) => {
                        const amount = (currentBalance * ratio);
                        const label = ratio === 1 ? 'Kalan Tutar' : ratio === 0.5 ? 'Yarısı' : 'Çeyreği';
                        return (
                          <button
                            key={ratio}
                            type="button"
                            onClick={() => setPaymentData(prev => ({ ...prev, tutar: amount.toFixed(2) }))}
                            className="rounded-full border border-white/15 bg-white/10 px-3 py-1 transition hover:bg-white/20"
                          >
                            {label} ({amount.toFixed(2)} TL)
                          </button>
                        );
                      })}
                      {[50, 100, 200].map((preset) => (
                        <button
                          key={preset}
                          type="button"
                          onClick={() => setPaymentData(prev => ({ ...prev, tutar: preset.toFixed(2) }))}
                          className="rounded-full border border-white/15 bg-white/10 px-3 py-1 transition hover:bg-white/20"
                        >
                          {preset} TL
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <button
                      onClick={handlePayment}
                      disabled={loading}
                      className="flex-1 rounded-lg bg-primary-600 px-4 py-2 transition-colors hover:bg-primary-700 disabled:opacity-50"
                    >
                      Ödeme Al
                    </button>
                    <button
                      onClick={handleCloseAccount}
                      disabled={loading}
                      className="rounded-lg bg-red-500/20 px-4 py-2 transition-colors hover:bg-red-500/30 disabled:opacity-50"
                    >
                      Hesabı Kapat
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {activeTab === 'hesaplar' && (
        <div className="card space-y-4 p-4 sm:p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <h3 className="text-xl font-semibold">Hesaplar (Adisyonlar)</h3>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setAdisyonFilter('acik')}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                  adisyonFilter === 'acik'
                    ? 'bg-primary-600 text-white'
                    : 'bg-white/10 text-white/70 hover:bg-white/20'
                }`}
              >
                Açık
              </button>
              <button
                onClick={() => setAdisyonFilter('kapali')}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                  adisyonFilter === 'kapali'
                    ? 'bg-primary-600 text-white'
                    : 'bg-white/10 text-white/70 hover:bg-white/20'
                }`}
              >
                Kapalı
              </button>
              <button
                onClick={() => setAdisyonFilter('tumu')}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                  adisyonFilter === 'tumu'
                    ? 'bg-primary-600 text-white'
                    : 'bg-white/10 text-white/70 hover:bg-white/20'
                }`}
              >
                Tümü
              </button>
            </div>
          </div>
          {adisyons.length === 0 ? (
            <div className="py-8 text-center text-white/50">
              {adisyonFilter === 'acik'
                ? 'Açık hesap yok'
                : adisyonFilter === 'kapali'
                ? 'Kapalı hesap yok'
                : 'Hesap yok'}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[680px]">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-white/70">
                      Adisyon ID
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-white/70">
                      Masa
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-white/70">
                      Durum
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-white/70">
                      Açılış
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-white/70">
                      Kapanış
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-white/70">
                      Toplam
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-white/70">
                      Ödeme
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-white/70">
                      Bakiye
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-white/70">
                      İskonto
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wide text-white/70">
                      İşlemler
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {adisyons.map((adisyon) => {
                    const acilisTarihi = new Date(adisyon.acilis_zamani);
                    const acilisStr = acilisTarihi.toLocaleString('tr-TR', {
                      day: '2-digit',
                      month: '2-digit',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    });
                    const kapanisTarihi = adisyon.kapanis_zamani ? new Date(adisyon.kapanis_zamani) : null;
                    const kapanisStr = kapanisTarihi
                      ? kapanisTarihi.toLocaleString('tr-TR', {
                          day: '2-digit',
                          month: '2-digit',
                          year: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })
                      : '-';

                    return (
                      <tr
                        key={adisyon.id}
                        className={`border-b border-white/5 transition-colors hover:bg-white/5 ${
                          adisyon.durum === 'kapali' ? 'opacity-75' : ''
                        }`}
                      >
                        <td className="px-4 py-3">#{adisyon.id}</td>
                        <td className="px-4 py-3 font-medium">Masa {adisyon.masa}</td>
                        <td className="px-4 py-3">
                          <span
                            className={`rounded px-2 py-1 text-xs ${
                              adisyon.durum === 'acik'
                                ? 'bg-green-500/20 text-green-300'
                                : 'bg-gray-500/20 text-gray-300'
                            }`}
                          >
                            {adisyon.durum === 'acik' ? 'Açık' : 'Kapalı'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-white/70">{acilisStr}</td>
                        <td className="px-4 py-3 text-sm text-white/70">{kapanisStr}</td>
                        <td className="px-4 py-3 text-right">{adisyon.toplam_tutar.toFixed(2)} ₺</td>
                        <td className="px-4 py-3 text-right text-green-300">{adisyon.odeme_toplam.toFixed(2)} ₺</td>
                        <td className="px-4 py-3 text-right font-bold text-primary-300">
                          {adisyon.bakiye.toFixed(2)} ₺
                        </td>
                        <td className="px-4 py-3 text-right">
                          {adisyon.iskonto_orani > 0 ? (
                            <span className="text-orange-300">{adisyon.iskonto_orani.toFixed(1)}%</span>
                          ) : (
                            <span className="text-white/30">-</span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex justify-center gap-2">
                            {adisyon.durum === 'acik' ? (
                              <>
                                <button
                                  onClick={() => {
                                    setActiveTab('masalar');
                                    loadSummary(adisyon.masa);
                                  }}
                                  className="rounded bg-primary-600/50 px-3 py-1 text-sm transition-colors hover:bg-primary-600"
                                >
                                  Görüntüle
                                </button>
                                <button
                                  onClick={() => handleAdisyonKapat(adisyon.id, adisyon.masa)}
                                  disabled={adisyon.bakiye > 0.01}
                                  className="rounded bg-red-600/50 px-3 py-1 text-sm transition-colors hover:bg-red-600 disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                  Kapat
                                </button>
                              </>
                            ) : (
                              <button
                                onClick={() => handleShowAdisyonDetay(adisyon.id)}
                                className="rounded bg-blue-600/50 px-3 py-1 text-sm transition-colors hover:bg-blue-600"
                              >
                                Görüntüle
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Masa Değiştir Modal */}
      {showMasaModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div className="w-full max-w-md rounded-lg bg-gray-800 p-5 sm:p-6">
            <h3 className="mb-4 text-xl font-bold">Masa Değiştir</h3>
            <div className="mb-4">
              <label className="mb-2 block text-sm font-medium">Yeni Masa</label>
              <select
                value={newMasa}
                onChange={(e) => setNewMasa(e.target.value)}
                className="w-full rounded-lg border border-white/20 bg-white/10 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="">Masa Seçin</option>
                {allTables.map((table) => (
                  <option key={table.masa} value={table.masa}>
                    Masa {table.masa}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleMasaDegistir}
                disabled={loading || !newMasa.trim()}
                className="flex-1 rounded-lg bg-primary-600 px-4 py-2 transition-colors hover:bg-primary-700 disabled:opacity-50"
              >
                Değiştir
              </button>
              <button
                onClick={() => {
                  setShowMasaModal(false);
                  setNewMasa('');
                }}
                disabled={loading}
                className="rounded-lg bg-white/10 px-4 py-2 transition-colors hover:bg-white/20 disabled:opacity-50"
              >
                İptal
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Adisyon Detay Modal */}
      {showAdisyonDetay && selectedAdisyonDetay && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 overflow-y-auto">
          <div className="my-8 w-full max-w-4xl rounded-lg bg-gray-800 p-5 sm:p-6">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-xl font-bold">Adisyon Detayları - #{selectedAdisyonDetay.adisyon.id}</h3>
              <button
                onClick={() => {
                  setShowAdisyonDetay(false);
                  setSelectedAdisyonDetay(null);
                }}
                className="text-white/70 hover:text-white transition-colors"
              >
                ✕
              </button>
            </div>

            {/* Adisyon Bilgileri */}
            <div className="mb-6 grid grid-cols-2 gap-4 rounded-lg bg-white/5 p-4">
              <div>
                <p className="text-sm text-white/60">Masa</p>
                <p className="font-semibold">Masa {selectedAdisyonDetay.adisyon.masa}</p>
              </div>
              <div>
                <p className="text-sm text-white/60">Durum</p>
                <p className="font-semibold">
                  <span className={`rounded px-2 py-1 text-xs ${
                    selectedAdisyonDetay.adisyon.durum === 'acik'
                      ? 'bg-green-500/20 text-green-300'
                      : 'bg-gray-500/20 text-gray-300'
                  }`}>
                    {selectedAdisyonDetay.adisyon.durum === 'acik' ? 'Açık' : 'Kapalı'}
                  </span>
                </p>
              </div>
              <div>
                <p className="text-sm text-white/60">Açılış Zamanı</p>
                <p className="font-semibold">
                  {selectedAdisyonDetay.adisyon.acilis_zamani
                    ? new Date(selectedAdisyonDetay.adisyon.acilis_zamani).toLocaleString('tr-TR')
                    : '-'}
                </p>
              </div>
              <div>
                <p className="text-sm text-white/60">Kapanış Zamanı</p>
                <p className="font-semibold">
                  {selectedAdisyonDetay.adisyon.kapanis_zamani
                    ? new Date(selectedAdisyonDetay.adisyon.kapanis_zamani).toLocaleString('tr-TR')
                    : '-'}
                </p>
              </div>
              <div>
                <p className="text-sm text-white/60">Toplam Tutar</p>
                <p className="font-semibold">{selectedAdisyonDetay.adisyon.toplam_tutar.toFixed(2)} ₺</p>
              </div>
              <div>
                <p className="text-sm text-white/60">Ödeme Toplamı</p>
                <p className="font-semibold text-green-300">{selectedAdisyonDetay.adisyon.odeme_toplam.toFixed(2)} ₺</p>
              </div>
              <div>
                <p className="text-sm text-white/60">Bakiye</p>
                <p className="font-semibold text-primary-300">{selectedAdisyonDetay.adisyon.bakiye.toFixed(2)} ₺</p>
              </div>
              <div>
                <p className="text-sm text-white/60">İskonto</p>
                <p className="font-semibold">
                  {selectedAdisyonDetay.adisyon.iskonto_orani > 0
                    ? `${selectedAdisyonDetay.adisyon.iskonto_orani.toFixed(1)}% (${selectedAdisyonDetay.adisyon.iskonto_tutari.toFixed(2)} ₺)`
                    : '-'}
                </p>
              </div>
            </div>

            {/* Siparişler */}
            <div className="mb-6">
              <h4 className="mb-3 text-lg font-semibold">Siparişler</h4>
              {selectedAdisyonDetay.siparisler.length === 0 ? (
                <p className="text-center text-white/50 py-4">Sipariş yok</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-white/10">
                        <th className="px-3 py-2 text-left text-xs font-semibold text-white/70">Ürün</th>
                        <th className="px-3 py-2 text-right text-xs font-semibold text-white/70">Miktar</th>
                        <th className="px-3 py-2 text-right text-xs font-semibold text-white/70">Birim Fiyat</th>
                        <th className="px-3 py-2 text-right text-xs font-semibold text-white/70">Tutar</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold text-white/70">Kaynak</th>
                        <th className="px-3 py-2 text-center text-xs font-semibold text-white/70">Durum</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedAdisyonDetay.siparisler.map((siparis: any) => (
                        <tr key={siparis.id} className="border-b border-white/5">
                          <td className="px-3 py-2">
                            {siparis.urun_adi}
                            {siparis.notlar && <p className="text-xs text-white/50 mt-1">{siparis.notlar}</p>}
                          </td>
                          <td className="px-3 py-2 text-right">{siparis.miktar}</td>
                          <td className="px-3 py-2 text-right">{siparis.birim_fiyat.toFixed(2)} ₺</td>
                          <td className="px-3 py-2 text-right font-semibold">{siparis.tutar.toFixed(2)} ₺</td>
                          <td className="px-3 py-2">
                            <span className="inline-flex items-center gap-2 text-xs text-white/70">
                              {siparis.source_type === 'personel' ? (
                                <>
                                  <span className="inline-flex h-2 w-2 rounded-full bg-emerald-400" />
                                  {siparis.source_label ?? 'Personel'}
                                </>
                              ) : (
                                <>
                                  <span className="inline-flex h-2 w-2 rounded-full bg-sky-400" />
                                  {siparis.source_label ?? 'AI Asistan'}
                                </>
                              )}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-center">
                            <span className={`rounded px-2 py-1 text-xs ${
                              siparis.durum === 'odendi'
                                ? 'bg-green-500/20 text-green-300'
                                : siparis.durum === 'hazir'
                                ? 'bg-blue-500/20 text-blue-300'
                                : siparis.durum === 'hazirlaniyor'
                                ? 'bg-yellow-500/20 text-yellow-300'
                                : 'bg-gray-500/20 text-gray-300'
                            }`}>
                              {siparis.durum}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Ödemeler */}
            <div className="mb-4">
              <h4 className="mb-3 text-lg font-semibold">Ödemeler</h4>
              {selectedAdisyonDetay.odemeler.length === 0 ? (
                <p className="text-center text-white/50 py-4">Ödeme yok</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-white/10">
                        <th className="px-3 py-2 text-left text-xs font-semibold text-white/70">Tarih</th>
                        <th className="px-3 py-2 text-left text-xs font-semibold text-white/70">Yöntem</th>
                        <th className="px-3 py-2 text-right text-xs font-semibold text-white/70">Tutar</th>
                        <th className="px-3 py-2 text-right text-xs font-semibold text-white/70">Tip</th>
                        <th className="px-3 py-2 text-center text-xs font-semibold text-white/70">Durum</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedAdisyonDetay.odemeler.map((odeme: any) => (
                        <tr key={odeme.id} className="border-b border-white/5">
                          <td className="px-3 py-2 text-sm">
                            {odeme.created_at
                              ? new Date(odeme.created_at).toLocaleString('tr-TR')
                              : '-'}
                          </td>
                          <td className="px-3 py-2">
                            <span className="rounded bg-white/10 px-2 py-1 text-xs capitalize">
                              {odeme.yontem}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-right font-semibold text-green-300">
                            {odeme.tutar.toFixed(2)} ₺
                          </td>
                          <td className="px-3 py-2 text-right text-sm">
                            {odeme.tip > 0 ? `${odeme.tip.toFixed(2)} ₺` : '-'}
                          </td>
                          <td className="px-3 py-2 text-center">
                            <span className={`rounded px-2 py-1 text-xs ${
                              odeme.iptal
                                ? 'bg-red-500/20 text-red-300'
                                : 'bg-green-500/20 text-green-300'
                            }`}>
                              {odeme.iptal ? 'İptal' : 'Geçerli'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="flex justify-end">
              <button
                onClick={() => {
                  setShowAdisyonDetay(false);
                  setSelectedAdisyonDetay(null);
                }}
                className="rounded-lg bg-white/10 px-6 py-2 transition-colors hover:bg-white/20"
              >
                Kapat
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
