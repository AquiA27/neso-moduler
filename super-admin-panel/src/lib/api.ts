import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';

const API_BASE_URL = (import.meta.env?.VITE_API_URL as string) || 'http://localhost:8000';

const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('neso.accessToken') || sessionStorage.getItem('neso.token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

let isRefreshing = false;
let failedQueue: Array<{ resolve: (value?: any) => void; reject: (error?: any) => void }> = [];

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

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(token => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return apiClient(originalRequest);
        }).catch(err => Promise.reject(err));
      }
      originalRequest._retry = true;
      isRefreshing = true;
      const refreshToken = localStorage.getItem('neso.refreshToken');
      if (!refreshToken) {
        isRefreshing = false;
        processQueue(new Error('No refresh token'), null);
        localStorage.removeItem('neso.accessToken');
        localStorage.removeItem('neso.refreshToken');
        sessionStorage.removeItem('neso.token');
        window.location.href = '/login';
        return Promise.reject(error);
      }
      try {
        const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });
        const { access_token, refresh_token: newRefreshToken } = response.data;
        localStorage.setItem('neso.accessToken', access_token);
        if (newRefreshToken) {
          localStorage.setItem('neso.refreshToken', newRefreshToken);
        }
        sessionStorage.setItem('neso.token', access_token);
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        processQueue(null, access_token);
        isRefreshing = false;
        return apiClient(originalRequest);
      } catch (refreshError) {
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
    return apiClient.get('/auth/me');
  },
};

export const superadminApi = {
  tenantsList: async () => apiClient.get('/superadmin/tenants'),
  tenantCreate: async (data: { ad: string; vergi_no?: string; telefon?: string; aktif?: boolean }) =>
    apiClient.post('/superadmin/tenants', data),
  tenantUpdate: async (id: number, data: { ad: string; vergi_no?: string; telefon?: string; aktif?: boolean }) =>
    apiClient.patch(`/superadmin/tenants/${id}`, data),
  tenantDelete: async (id: number) => apiClient.delete(`/superadmin/tenants/${id}`),
  usersList: async () => apiClient.get('/superadmin/users'),
  userUpsert: async (data: { username: string; role: string; aktif: boolean; password?: string }) =>
    apiClient.post('/superadmin/users/upsert', data),
  quickSetup: async (data: any) => apiClient.post('/superadmin/quick-setup', data),
  dashboardStats: async () => apiClient.get('/superadmin/dashboard/stats'),
};

export const subscriptionApi = {
  list: async (params?: { isletme_id?: number; status?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.isletme_id) searchParams.append('isletme_id', String(params.isletme_id));
    if (params?.status) searchParams.append('status', params.status);
    return apiClient.get(`/subscription/list?${searchParams.toString()}`);
  },
  get: async (isletme_id: number) => apiClient.get(`/subscription/${isletme_id}`),
  create: async (data: any) => apiClient.post('/subscription/create', data),
  update: async (isletme_id: number, data: any) => apiClient.patch(`/subscription/${isletme_id}`, data),
  updateStatus: async (isletme_id: number, status: string, bitis_tarihi?: string) =>
    apiClient.patch(`/subscription/${isletme_id}/status`, { status, bitis_tarihi }),
  getLimits: async (isletme_id: number) => apiClient.get(`/subscription/${isletme_id}/limits`),
};

export const paymentApi = {
  list: async (params?: { isletme_id?: number; subscription_id?: number; durum?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.isletme_id) searchParams.append('isletme_id', String(params.isletme_id));
    if (params?.subscription_id) searchParams.append('subscription_id', String(params.subscription_id));
    if (params?.durum) searchParams.append('durum', params.durum);
    return apiClient.get(`/payment/list?${searchParams.toString()}`);
  },
  get: async (payment_id: number) => apiClient.get(`/payment/${payment_id}`),
  create: async (data: any) => apiClient.post('/payment/create', data),
  updateStatus: async (payment_id: number, durum: string, odeme_tarihi?: string) =>
    apiClient.patch(`/payment/${payment_id}/status`, { durum, odeme_tarihi }),
  getSummary: async (isletme_id: number) => apiClient.get(`/payment/isletme/${isletme_id}/summary`),
};

export const customizationApi = {
  get: async (isletme_id: number) => apiClient.get(`/customization/isletme/${isletme_id}`),
  create: async (data: any) => apiClient.post('/customization/create', data),
  update: async (isletme_id: number, data: any) => apiClient.patch(`/customization/isletme/${isletme_id}`, data),
};

export default apiClient;


