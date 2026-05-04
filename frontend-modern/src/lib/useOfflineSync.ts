import { useState, useEffect } from 'react';
import { offlineManager } from './offlineManager';
import { kasaApi, siparisApi } from './api';

export function useOfflineSync() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [syncing, setSyncing] = useState(false);
  const [queueCount, setQueueCount] = useState(0);

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      syncOfflineQueue();
    };
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Initial check
    setQueueCount(offlineManager.getQueue().length);
    if (navigator.onLine && offlineManager.getQueue().length > 0) {
      syncOfflineQueue();
    }

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const syncOfflineQueue = async () => {
    if (syncing) return;
    setSyncing(true);

    const queue = offlineManager.getQueue();
    setQueueCount(queue.length);

    if (queue.length === 0) {
      setSyncing(false);
      return;
    }

    let successCount = 0;

    for (const action of queue) {
      try {
        if (action.type === 'PAYMENT') {
          await kasaApi.odemeEkle(action.payload);
        } else if (action.type === 'CLOSE_ACCOUNT') {
          await kasaApi.hesapKapat(action.payload.masa);
        } else if (action.type === 'CHANGE_TABLE') {
          await kasaApi.itemMasaDegistir(action.payload);
        } else if (action.type === 'IKRAM') {
          await kasaApi.itemIkram(action.payload);
        } else if (action.type === 'NEW_ORDER') {
          await siparisApi.add(action.payload);
        }
        offlineManager.removeAction(action.id);
        successCount++;
      } catch (err) {
        console.error(`Sync error for action ${action.id}:`, err);
        // Break early to prevent out-of-order sync issues
        break;
      }
    }

    setQueueCount(offlineManager.getQueue().length);
    setSyncing(false);

    if (successCount > 0) {
      // Reload page data to reflect synced state
      window.dispatchEvent(new Event('offline-sync-complete'));
    }
  };

  return { isOnline, syncing, queueCount };
}
