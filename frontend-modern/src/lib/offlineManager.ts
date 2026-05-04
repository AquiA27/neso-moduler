export interface OfflineAction {
  id: string;
  type: 'PAYMENT' | 'CLOSE_ACCOUNT' | 'CHANGE_TABLE' | 'IKRAM';
  payload: any;
  timestamp: number;
}

const OFFLINE_QUEUE_KEY = 'neso_offline_queue';
const CACHE_KEY_PREFIX = 'neso_cache_';

export const offlineManager = {
  isOnline: () => navigator.onLine,

  // Cache data
  saveToCache: (key: string, data: any) => {
    try {
      localStorage.setItem(CACHE_KEY_PREFIX + key, JSON.stringify(data));
    } catch (e) {
      console.error('Cache save error', e);
    }
  },

  getFromCache: (key: string) => {
    try {
      const data = localStorage.getItem(CACHE_KEY_PREFIX + key);
      return data ? JSON.parse(data) : null;
    } catch (e) {
      console.error('Cache read error', e);
      return null;
    }
  },

  // Offline Actions Queue
  getQueue: (): OfflineAction[] => {
    try {
      const data = localStorage.getItem(OFFLINE_QUEUE_KEY);
      return data ? JSON.parse(data) : [];
    } catch (e) {
      return [];
    }
  },

  addAction: (type: OfflineAction['type'], payload: any) => {
    const queue = offlineManager.getQueue();
    queue.push({
      id: Math.random().toString(36).substr(2, 9),
      type,
      payload,
      timestamp: Date.now()
    });
    localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(queue));
  },

  removeAction: (id: string) => {
    const queue = offlineManager.getQueue();
    const newQueue = queue.filter(a => a.id !== id);
    localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(newQueue));
  },

  clearQueue: () => {
    localStorage.removeItem(OFFLINE_QUEUE_KEY);
  }
};
