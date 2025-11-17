import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';

// API URL'ini normalize et (protokol eksikse veya yanlışsa düzelt)
const normalizeApiUrl = (url: string | undefined): string => {
  if (!url) {
    return 'http://localhost:8000';
  }
  
  // Başındaki/sonundaki boşlukları temizle
  url = url.trim();
  
  // Protokol yoksa veya yanlışsa düzelt
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    // Eğer 'ttps://' gibi bir hata varsa düzelt
    if (url.startsWith('ttps://')) {
      url = 'https://' + url.substring(7);
    } else {
      // Protokol yoksa https ekle (production için)
      url = 'https://' + url;
    }
  }
  
  // Sonundaki / işaretini kaldır
  url = url.replace(/\/$/, '');
  
  return url;
};

const API_BASE_URL = normalizeApiUrl(import.meta.env?.VITE_API_URL as string);

// Axios instance oluştur
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - her istekte token ve şube ID ekle
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('neso.accessToken') || sessionStorage.getItem('neso.token');
    const subeId = Number(localStorage.getItem('neso.subeId') || sessionStorage.getItem('neso.subeId') || '1');
    
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    if (subeId) {
      config.headers['X-Sube-Id'] = String(subeId);
    }

    if (config.data instanceof FormData) {
      config.headers['Content-Type'] = 'multipart/form-data';
    }
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Refresh token akışı için flag (sonsuz döngüyü önlemek için)
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: any) => void;
  reject: (error?: any) => void;
}> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

// Response interceptor - 401 hatası durumunda refresh token akışı
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // 401 hatası ve henüz retry edilmemişse
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // Refresh zaten devam ediyor, kuyruğa ekle
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then(token => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return apiClient(originalRequest);
          })
          .catch(err => {
            return Promise.reject(err);
          });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = localStorage.getItem('neso.refreshToken');
      
      if (!refreshToken) {
        // Refresh token yok, logout yap
        isRefreshing = false;
        processQueue(new Error('No refresh token'), null);
        localStorage.removeItem('neso.accessToken');
        localStorage.removeItem('neso.refreshToken');
        sessionStorage.removeItem('neso.token');
        window.location.href = '/login';
        return Promise.reject(error);
      }

      try {
        // Refresh token ile yeni access token al
        const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });

        const { access_token, refresh_token: newRefreshToken } = response.data;

        // Yeni token'ları kaydet
        localStorage.setItem('neso.accessToken', access_token);
        if (newRefreshToken) {
          localStorage.setItem('neso.refreshToken', newRefreshToken);
        }
        sessionStorage.setItem('neso.token', access_token);

        // Store'u güncelle
        const { useAuthStore } = await import('../store/authStore');
        useAuthStore.getState().setTokens(access_token, newRefreshToken);

        // Orijinal isteği yeni token ile tekrar dene
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        
        // Kuyruktaki istekleri işle
        processQueue(null, access_token);
        isRefreshing = false;

        return apiClient(originalRequest);
      } catch (refreshError) {
        // Refresh başarısız, logout yap
        isRefreshing = false;
        processQueue(refreshError, null);
        localStorage.removeItem('neso.accessToken');
        localStorage.removeItem('neso.refreshToken');
        sessionStorage.removeItem('neso.token');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

// Analytics API
export const analyticsApi = {
  saatlikYogunluk: async (period: 'gunluk' | 'haftalik' | 'aylik' = 'gunluk', tarih?: string) => {
    const params = new URLSearchParams({ period });
    if (tarih) params.append('tarih', tarih);
    return apiClient.get(`/analytics/saatlik-yogunluk?${params.toString()}`);
  },
  
  enCokTercihEdilenUrunler: async (limit: number = 10, period: 'gunluk' | 'haftalik' | 'aylik' | 'tumu' = 'tumu', tarih?: string) => {
    const params = new URLSearchParams({ 
      limit: String(limit),
      period 
    });
    if (tarih) params.append('tarih', tarih);
    return apiClient.get(`/analytics/en-cok-tercih-edilen-urunler?${params.toString()}`);
  },
  
  ozet: async (options?: { period?: 'gunluk' | 'haftalik' | 'aylik'; start?: string; end?: string; tarih?: string }) => {
    const params = new URLSearchParams();
    if (options?.period) params.append('period', options.period);
    if (options?.tarih) params.append('tarih', options.tarih);
    if (options?.start) params.append('start', options.start);
    if (options?.end) params.append('end', options.end);
    if (!options?.period && !options?.start) {
      params.append('period', 'gunluk');
    }
    return apiClient.get(`/analytics/ozet?${params.toString()}`);
  },
};

// Admin API
export const adminApi = {
  ozet: async (options?: { gun?: string; start?: string; end?: string }) => {
    const searchParams = new URLSearchParams();
    if (options?.gun) searchParams.append('gun', options.gun);
    if (options?.start) searchParams.append('start', options.start);
    if (options?.end) searchParams.append('end', options.end);
    const queryString = searchParams.toString();
    return apiClient.get(`/admin/ozet${queryString ? `?${queryString}` : ''}`);
  },
  
  trend: async (options?: { gunSay?: number; start?: string; end?: string }) => {
    const searchParams = new URLSearchParams();
    if (options?.start && options?.end) {
      searchParams.append('start', options.start);
      searchParams.append('end', options.end);
    } else if (options?.gunSay) {
      searchParams.append('gun_say', String(options.gunSay));
    }
    const queryString = searchParams.toString();
    return apiClient.get(`/admin/trend${queryString ? `?${queryString}` : ''}`);
  },
  
  topUrunler: async (options?: { gunSay?: number; limit?: number; metrik?: 'adet' | 'ciro'; start?: string; end?: string }) => {
    const searchParams = new URLSearchParams();
    if (options?.start && options?.end) {
      searchParams.append('start', options.start);
      searchParams.append('end', options.end);
    } else if (options?.gunSay) {
      searchParams.append('gun_say', String(options.gunSay));
    }
    if (options?.limit) {
      searchParams.append('limit', String(options.limit));
    }
    if (options?.metrik) {
      searchParams.append('metrik', options.metrik);
    }
    const queryString = searchParams.toString();
    return apiClient.get(`/admin/top-urunler${queryString ? `?${queryString}` : ''}`);
  },
  
  personelAnaliz: async (gunSay: number = 30, limit: number = 20) => {
    return apiClient.get(`/admin/personel-analiz?gun_say=${gunSay}&limit=${limit}`);
  },
};

// SuperAdmin API
export const superadminApi = {
  // Tenants
  tenantsList: async () => {
    return apiClient.get('/superadmin/tenants');
  },
  
  tenantDetail: async (id: number) => {
    return apiClient.get(`/superadmin/tenants/${id}`);
  },
  
  tenantCreate: async (data: { ad: string; vergi_no?: string; telefon?: string; aktif?: boolean }) => {
    return apiClient.post('/superadmin/tenants', data);
  },
  
  tenantUpdate: async (id: number, data: { ad: string; vergi_no?: string; telefon?: string; aktif?: boolean }) => {
    return apiClient.patch(`/superadmin/tenants/${id}`, data);
  },
  
  tenantDelete: async (id: number) => {
    return apiClient.delete(`/superadmin/tenants/${id}`);
  },
  
  // Users
  usersList: async (options?: { includePassive?: boolean }) => {
    const params = options?.includePassive ? { include_passive: true } : undefined;
    return apiClient.get('/superadmin/users', { params });
  },
  
  userUpsert: async (data: { username: string; role: string; aktif: boolean; password?: string }) => {
    return apiClient.post('/superadmin/users/upsert', data);
  },
  
  getUserPermissions: async (username: string) => {
    return apiClient.get(`/superadmin/users/${username}/permissions`);
  },
  
  updateUserPermissions: async (username: string, permissions: Record<string, boolean>) => {
    return apiClient.put(`/superadmin/users/${username}/permissions`, {
      username,
      permissions,
    });
  },
  
  getAvailablePermissions: async () => {
    return apiClient.get('/superadmin/permissions/available');
  },
  
  getRoleDefaultPermissions: async (role: string) => {
    return apiClient.get(`/superadmin/permissions/role-defaults/${role}`);
  },
  
  // Quick Setup
  quickSetup: async (data: {
    isletme_ad: string;
    isletme_vergi_no?: string;
    isletme_telefon?: string;
    sube_ad?: string;
    admin_username: string;
    admin_password: string;
    plan_type?: string;
    ayllik_fiyat?: number;
    domain?: string;
    app_name?: string;
    logo_url?: string;
    primary_color?: string;
  }) => {
    return apiClient.post('/superadmin/quick-setup', data);
  },
  
  // Dashboard Stats
  dashboardStats: async () => {
    return apiClient.get('/superadmin/dashboard/stats');
  },
};

// Subscription API
export const subscriptionApi = {
  list: async (params?: { isletme_id?: number; status?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.isletme_id) searchParams.append('isletme_id', String(params.isletme_id));
    if (params?.status) searchParams.append('status', params.status);
    return apiClient.get(`/subscription/list?${searchParams.toString()}`);
  },
  
  get: async (isletme_id: number) => {
    return apiClient.get(`/subscription/${isletme_id}`);
  },
  
  create: async (data: {
    isletme_id: number;
    plan_type: string;
    status?: string;
    max_subeler?: number;
    max_kullanicilar?: number;
    max_menu_items?: number;
    ayllik_fiyat?: number;
    trial_baslangic?: string;
    trial_bitis?: string;
    baslangic_tarihi?: string;
    bitis_tarihi?: string;
    otomatik_yenileme?: boolean;
  }) => {
    return apiClient.post('/subscription/create', data);
  },
  
  update: async (isletme_id: number, data: any) => {
    return apiClient.patch(`/subscription/${isletme_id}`, data);
  },
  
  updateStatus: async (isletme_id: number, status: string, bitis_tarihi?: string) => {
    return apiClient.patch(`/subscription/${isletme_id}/status`, { status, bitis_tarihi });
  },
  
  getLimits: async (isletme_id: number) => {
    return apiClient.get(`/subscription/${isletme_id}/limits`);
  },
};

// Payment API
export const paymentApi = {
  list: async (params?: { isletme_id?: number; subscription_id?: number; durum?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.isletme_id) searchParams.append('isletme_id', String(params.isletme_id));
    if (params?.subscription_id) searchParams.append('subscription_id', String(params.subscription_id));
    if (params?.durum) searchParams.append('durum', params.durum);
    return apiClient.get(`/payment/list?${searchParams.toString()}`);
  },
  
  get: async (payment_id: number) => {
    return apiClient.get(`/payment/${payment_id}`);
  },
  
  create: async (data: {
    isletme_id: number;
    subscription_id?: number;
    tutar: number;
    odeme_turu?: string;
    durum?: string;
    fatura_no?: string;
    aciklama?: string;
    odeme_tarihi?: string;
  }) => {
    return apiClient.post('/payment/create', data);
  },
  
  updateStatus: async (payment_id: number, durum: string, odeme_tarihi?: string) => {
    return apiClient.patch(`/payment/${payment_id}/status`, { durum, odeme_tarihi });
  },
  
  getSummary: async (isletme_id: number) => {
    return apiClient.get(`/payment/isletme/${isletme_id}/summary`);
  },
};

// Customization API
export const customizationApi = {
  get: async (isletme_id: number) => {
    return apiClient.get(`/customization/isletme/${isletme_id}`);
  },
  
  create: async (data: {
    isletme_id: number;
    domain?: string;
    app_name?: string;
    logo_url?: string;
    primary_color?: string;
    secondary_color?: string;
    footer_text?: string;
    email?: string;
    telefon?: string;
    adres?: string;
    meta_settings?: Record<string, any>;
  }) => {
    return apiClient.post('/customization/create', data);
  },
  
  update: async (isletme_id: number, data: any) => {
    return apiClient.patch(`/customization/isletme/${isletme_id}`, data);
  },
  
  getByDomain: async (domain: string) => {
    return publicApiClient.get(`/customization/domain/${domain}`);
  },
};

export default apiClient;

// API fonksiyonları
export const authApi = {
  login: async (username: string, password: string) => {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);
    
    const response = await axios.post(`${API_BASE_URL}/auth/token`, formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    return response.data;
  },
  
  refreshToken: async (refreshToken: string) => {
    const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
      refresh_token: refreshToken,
    });
    return response.data;
  },
  
  me: async () => {
    const response = await apiClient.get('/auth/me');
    return response;
  },
};

export const menuApi = {
  list: async (params?: { sadece_aktif?: boolean; limit?: number; varyasyonlar_dahil?: boolean }) => {
    const searchParams = new URLSearchParams();
    if (params?.sadece_aktif) searchParams.append('sadece_aktif', 'true');
    if (params?.limit) searchParams.append('limit', String(params.limit));
    if (params?.varyasyonlar_dahil) searchParams.append('varyasyonlar_dahil', 'true');
    return apiClient.get(`/menu/liste?${searchParams.toString()}`);
  },
  
  add: async (data: { ad: string; fiyat: number; kategori: string; aktif?: boolean; aciklama?: string }) => {
    return apiClient.post('/menu/ekle', data);
  },
  
  update: async (id: number, data: Partial<{ ad: string; fiyat: number; kategori: string; aktif: boolean; aciklama: string }>) => {
    return apiClient.patch(`/menu/guncelle`, { id, ...data });
  },
  
  uploadImage: async (id: number, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post(`/menu/${id}/gorsel`, formData);
  },
  
  deleteImage: async (id: number) => {
    return apiClient.delete(`/menu/${id}/gorsel`);
  },
  
  delete: async (id: number) => {
    return apiClient.delete(`/menu/sil?id=${id}`);
  },
};

export const siparisApi = {
  add: async (data: { masa: string; sepet: Array<{ urun: string; adet: number; fiyat: number }>; tutar: number }) => {
    return apiClient.post('/siparis/ekle', data);
  },
  
  list: async (limit?: number) => {
    return apiClient.get(`/siparis/liste${limit ? `?limit=${limit}` : ''}`);
  },
  
  updateStatus: async (id: number, yeni_durum: string) => {
    return apiClient.patch(`/siparis/${id}/durum?yeni_durum=${encodeURIComponent(yeni_durum)}`);
  },
};

export const mutfakApi = {
  kuyruk: async (params?: { limit?: number; durum?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.append('limit', String(params.limit));
    if (params?.durum) searchParams.append('durum', params.durum);
    return apiClient.get(`/mutfak/kuyruk?${searchParams.toString()}`);
  },
  
  updateStatus: async (id: number, yeni_durum: string) => {
    return apiClient.patch(`/mutfak/durum/${id}?yeni_durum=${encodeURIComponent(yeni_durum)}`);
  },
};

export const kasaApi = {
  hesapOzet: async (masa: string) => {
    return apiClient.get(`/kasa/hesap/ozet?masa=${encodeURIComponent(masa)}`);
  },

  gunlukOzet: async () => {
    return apiClient.get('/kasa/ozet/gunluk');
  },
  
  hesapDetay: async (masa: string) => {
    return apiClient.get(`/kasa/hesap/detay?masa=${encodeURIComponent(masa)}`);
  },
  
  masalar: async (params?: { limit?: number; tumu?: boolean }) => {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.append('limit', String(params.limit));
    if (params?.tumu) searchParams.append('tumu', 'true');
    const queryString = searchParams.toString();
    return apiClient.get(`/kasa/masalar${queryString ? `?${queryString}` : ''}`);
  },
  
  siparisler: async (limit?: number) => {
    return apiClient.get(`/kasa/siparisler${limit ? `?limit=${limit}` : ''}`);
  },
  
  odemeEkle: async (data: { masa: string; tutar: number; yontem: string; iskonto_orani?: number }) => {
    return apiClient.post('/kasa/odeme/ekle', data);
  },
  itemMasaDegistir: async (data: { siparis_id: number; item_index: number; yeni_masa: string }) => {
    return apiClient.post('/kasa/siparis/item/masa-degistir', data);
  },
  itemIkram: async (data: { siparis_id: number; item_index: number }) => {
    return apiClient.post('/kasa/siparis/item/ikram', data);
  },
  
  hesapKapat: async (masa: string) => {
    return apiClient.post(`/kasa/hesap/kapat?masa=${encodeURIComponent(masa)}`);
  },
};

// Adisyon API
export const adisyonApi = {
  olustur: async (masa: string) => {
    return apiClient.post('/adisyon/olustur', { masa });
  },
  
  acik: async (limit?: number, durum?: string) => {
    const params = new URLSearchParams();
    if (limit) params.append('limit', String(limit));
    if (durum) params.append('durum', durum);
    const queryString = params.toString();
    return apiClient.get(`/adisyon/acik${queryString ? `?${queryString}` : ''}`);
  },
  
  masaAdisyon: async (masa: string) => {
    return apiClient.get(`/adisyon/masa/${encodeURIComponent(masa)}`);
  },
  
  detay: async (adisyonId: number) => {
    return apiClient.get(`/adisyon/${adisyonId}`);
  },
  
  kapat: async (adisyonId: number) => {
    return apiClient.post(`/adisyon/${adisyonId}/kapat`);
  },
  
  iskonto: async (adisyonId: number, iskonto_orani: number) => {
    return apiClient.patch(`/adisyon/${adisyonId}/iskonto?iskonto_orani=${iskonto_orani}`);
  },

  detayli: async (adisyonId: number) => {
    return apiClient.get(`/adisyon/${adisyonId}/detayli`);
  },
};

export const stokApi = {
  list: async (params?: { limit?: number }) => {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.append('limit', String(params.limit));
    return apiClient.get(`/stok/liste?${searchParams.toString()}`);
  },
  
  add: async (data: { ad: string; kategori: string; birim: string; mevcut: number; min: number; alis_fiyat: number }) => {
    return apiClient.post('/stok/ekle', data);
  },
  
  update: async (originalAd: string, data: Partial<{ ad?: string; yeni_ad?: string; kategori: string; birim: string; mevcut: number; min: number; alis_fiyat: number }>) => {
    return apiClient.patch(`/stok/guncelle`, { ad: originalAd, ...data });
  },
  
  delete: async (ad: string) => {
    return apiClient.delete(`/stok/sil?ad=${encodeURIComponent(ad)}`);
  },
  
  alerts: async () => {
    return apiClient.get('/stok/uyarilar');
  },
};

export const receteApi = {
  list: async (params?: { limit?: number; urun?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.append('limit', String(params.limit));
    if (params?.urun) searchParams.append('urun', params.urun);
    return apiClient.get(`/recete/liste?${searchParams.toString()}`);
  },
  
  add: async (data: { urun: string; stok: string; miktar: number; birim: string }) => {
    return apiClient.post('/recete/ekle', data);
  },
  
  delete: async (id: number) => {
    return apiClient.delete(`/recete/sil/${id}`);
  },
};

// Public API client - no authentication required
const publicApiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Public API client interceptor - sadece sube_id ekle, token ekleme
publicApiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const subeId = Number(sessionStorage.getItem('neso.subeId') || localStorage.getItem('neso.subeId') || '1');
    if (subeId) {
      config.headers['X-Sube-Id'] = String(subeId);
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export const assistantApi = {
  parse: async (text: string) => {
    return apiClient.post('/assistant/parse', { text });
  },
  
  createOrder: async (masa: string, text: string) => {
    return apiClient.post('/assistant/siparis', { masa, text });
  },
  
  chat: async (data: { text: string; masa?: string; sube_id?: number; conversation_id?: string }) => {
    return apiClient.post('/assistant/chat', data);
  },

  voiceCommand: async (formData: FormData) => {
    // This is a public endpoint, no auth needed
    return publicApiClient.post('/assistant/voice-command', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },

  getSettings: async () => {
    return apiClient.get('/assistant/settings');
  },

  updateSettings: async (data: { tts_voice_id?: string; tts_speech_rate?: number; tts_provider?: string }) => {
    return apiClient.put('/assistant/settings', data);
  },
};

// Public menu API for customers
export const publicMenuApi = {
  list: async (subeId?: number) => {
    const searchParams = new URLSearchParams();
    const finalSubeId = subeId || Number(sessionStorage.getItem('neso.subeId') || localStorage.getItem('neso.subeId') || '1');
    searchParams.append('sube_id', String(finalSubeId));
    // /public/menu endpoint'ini kullan - authentication gerekmez, zaten sadece aktif ürünleri döndürür
    return publicApiClient.get(`/public/menu?${searchParams.toString()}`);
  },
};

// BI Assistant API
export const biAssistantApi = {
  query: async (data: { text: string; sube_id?: number }) => {
    return apiClient.post('/bi-assistant/query', data);
  },
};

// Giderler API
export const giderlerApi = {
  list: async (params?: { baslangic_tarih?: string; bitis_tarih?: string; kategori?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.baslangic_tarih) searchParams.append('baslangic_tarih', params.baslangic_tarih);
    if (params?.bitis_tarih) searchParams.append('bitis_tarih', params.bitis_tarih);
    if (params?.kategori) searchParams.append('kategori', params.kategori);
    return apiClient.get(`/giderler/liste?${searchParams.toString()}`);
  },
  
  add: async (data: { kategori: string; aciklama?: string; tutar: number; tarih: string; fatura_no?: string }) => {
    return apiClient.post('/giderler/ekle', data);
  },
  
  update: async (data: { id: number; kategori?: string; aciklama?: string; tutar?: number; tarih?: string; fatura_no?: string }) => {
    return apiClient.patch('/giderler/guncelle', data);
  },
  
  delete: async (id: number) => {
    return apiClient.delete(`/giderler/sil/${id}`);
  },
  
  kategoriler: async () => {
    return apiClient.get('/giderler/kategoriler');
  },
};

// Masalar API
export const masalarApi = {
  list: async () => {
    return apiClient.get('/masalar/liste');
  },
  
  add: async (data: { masa_adi: string; kapasite?: number; pozisyon_x?: number; pozisyon_y?: number }) => {
    return apiClient.post('/masalar/ekle', data);
  },
  
  update: async (data: { id: number; masa_adi?: string; durum?: string; kapasite?: number; pozisyon_x?: number; pozisyon_y?: number }) => {
    return apiClient.patch('/masalar/guncelle', data);
  },
  
  delete: async (id: number) => {
    return apiClient.delete(`/masalar/sil/${id}`);
  },
};

export const menuVaryasyonlarApi = {
  list: async (menuId?: number) => {
    const params = menuId ? `?menu_id=${menuId}` : '';
    return apiClient.get(`/menu-varyasyonlar/liste${params}`);
  },
  
  add: async (data: { menu_id: number; ad: string; ek_fiyat?: number; sira?: number; aktif?: boolean }) => {
    return apiClient.post('/menu-varyasyonlar/ekle', data);
  },
  
  update: async (data: { id: number; ad?: string; ek_fiyat?: number; sira?: number; aktif?: boolean }) => {
    return apiClient.patch('/menu-varyasyonlar/guncelle', data);
  },
  
  delete: async (varyasyonId: number) => {
    return apiClient.delete(`/menu-varyasyonlar/sil/${varyasyonId}`);
  },
};

