import { useEffect, useRef, useState, useCallback } from 'react';

interface UseWebSocketOptions {
  url: string;
  topics?: string[];
  onMessage?: (data: any) => void;
  onError?: (error: Event) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  auth?: boolean; // If true, uses /ws/connect/auth with token
}

interface WebSocketState {
  connected: boolean;
  connecting: boolean;
  lastMessage: any;
  error: Event | null;
}

export function useWebSocket(options: UseWebSocketOptions) {
  const {
    url,
    topics = [],
    onMessage,
    onError,
    onConnect,
    onDisconnect,
    reconnectInterval = 3000,
    maxReconnectAttempts = 10,
    auth = false,
  } = options;

  const [state, setState] = useState<WebSocketState>({
    connected: false,
    connecting: false,
    lastMessage: null,
    error: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const shouldReconnectRef = useRef(true);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    setState(prev => ({ ...prev, connecting: true, error: null }));

    try {
      let finalUrl = url;
      
      // If auth is enabled, add token to URL
      if (auth) {
        const token = localStorage.getItem('neso.accessToken') || sessionStorage.getItem('neso.token');
        if (token) {
          const separator = finalUrl.includes('?') ? '&' : '?';
          finalUrl = `${finalUrl}${separator}token=${encodeURIComponent(token)}`;
        } else {
          console.warn('No token available for authenticated WebSocket connection');
          return;
        }
      }
      
      // Add topics to URL if provided
      if (topics.length > 0) {
        const separator = finalUrl.includes('?') ? '&' : '?';
        finalUrl = `${finalUrl}${separator}topics=${topics.join(',')}`;
      }
      
      const ws = new WebSocket(finalUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket connected');
        setState(prev => ({ ...prev, connected: true, connecting: false }));
        reconnectAttemptsRef.current = 0;
        
        // Subscribe to topics
        if (topics.length > 0) {
          ws.send(JSON.stringify({ type: 'subscribe', topics }));
        }
        
        onConnect?.();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setState(prev => ({ ...prev, lastMessage: data }));
          onMessage?.(data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setState(prev => ({ ...prev, error }));
        onError?.(error);
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setState(prev => ({ ...prev, connected: false, connecting: false }));
        wsRef.current = null;
        onDisconnect?.();

        // Auto-reconnect
        if (shouldReconnectRef.current && reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current++;
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log(`Reconnecting... (${reconnectAttemptsRef.current}/${maxReconnectAttempts})`);
            connect();
          }, reconnectInterval);
        }
      };
    } catch (error) {
      console.error('WebSocket connection failed:', error);
      setState(prev => ({ ...prev, connecting: false, error: error as Event }));
    }
  }, [url, topics, auth, onMessage, onError, onConnect, onDisconnect, reconnectInterval, maxReconnectAttempts]);

  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false;
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
      return true;
    }
    console.warn('WebSocket is not connected');
    return false;
  }, []);

  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [url]); // Only reconnect if URL changes

  return {
    ...state,
    connect,
    disconnect,
    sendMessage,
    reconnect: () => {
      reconnectAttemptsRef.current = 0;
      shouldReconnectRef.current = true;
      connect();
    },
  };
}

