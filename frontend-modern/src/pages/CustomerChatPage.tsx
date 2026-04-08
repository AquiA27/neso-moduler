import { useState, useRef, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Send, ArrowLeft, Mic, Volume2 } from 'lucide-react';
import { assistantApi, normalizeApiUrl } from '../lib/api';

interface Message {
  type: 'user' | 'assistant';
  text: string;
  timestamp: Date;
  suggestions?: string[];
  audioBase64?: string;
}

export default function CustomerChatPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [masa, setMasa] = useState(searchParams.get('masa') || '');
  const [masaLoading, setMasaLoading] = useState(false);
  void masaLoading; // used to track QR loading state
  const [subeId, setSubeId] = useState<number>(parseInt(searchParams.get('sube_id') || '1', 10));
  const qrCode = searchParams.get('qr');
  
  const [messages, setMessages] = useState<Message[]>([
    {
      type: 'assistant',
      text: 'Merhaba! Ben Neso, sipariş asistanınız! 👋\n\nMenümüzden dilediğinizi seçebilirsiniz. Az sonra günün favorilerini paylaşacağım.',
      timestamp: new Date(),
    },
  ]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [detectedLanguage, setDetectedLanguage] = useState<string>('tr');
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const synthRef = useRef<SpeechSynthesis | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);
  const audioTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    const loadRecommendedItems = async () => {
      try {
        const API_BASE_URL = normalizeApiUrl(import.meta.env.VITE_API_URL as string);
        const response = await fetch(`${API_BASE_URL}/public/menu?sube_id=${subeId}`);
        if (!response.ok) {
          throw new Error(`Menü yüklenemedi (${response.status})`);
        }
        const data = await response.json();
        if (Array.isArray(data) && data.length > 0) {
          const topItems = data.slice(0, 3);
          const formatter = new Intl.NumberFormat('tr-TR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          });
          const recommendations = topItems.map(
            (item: { ad: string; fiyat?: number }) =>
              `${item.ad}${item.fiyat ? ` (${formatter.format(item.fiyat)} ₺)` : ''}`
          );
          const exampleParts = topItems.slice(0, 2).map((item: { ad: string }) => item.ad);
          const sampleText =
            exampleParts.length === 2
              ? `Örneğin: "2 ${exampleParts[0]} ve 1 ${exampleParts[1]}"`
              : exampleParts.length === 1
                ? `Örneğin: "2 ${exampleParts[0]}"`
                : 'Siparişinizi ürün adı ve adetini söyleyerek oluşturabilirsiniz.';
          const introMessage = `Merhaba! Ben Neso, sipariş asistanınız! 👋\n\nBugün deneyebileceğiniz favorilerimiz:\n${recommendations
            .map((item) => `• ${item}`)
            .join('\n')}\n\nSipariş vermek için ürün adı ve adetini söylemeniz yeterli. ${sampleText}`;
          setMessages((prev) => {
            const updated = [...prev];
            const suggestionPhrases = topItems.map(
              (item: { ad: string }) => `${item.ad} 1 adet`
            );
            if (updated.length > 0 && updated[0].type === 'assistant') {
              updated[0] = {
                ...updated[0],
                text: introMessage,
                suggestions: suggestionPhrases,
              };
            } else {
              updated.unshift({
                type: 'assistant',
                text: introMessage,
                suggestions: suggestionPhrases,
                timestamp: new Date(),
              });
            }
            return updated;
          });
        }
      } catch (error) {
        console.warn('Menü önerileri yüklenemedi:', error);
      }
    };

    loadRecommendedItems();
  }, [subeId]);

  useEffect(() => {
    // Load conversation ID from sessionStorage
    const savedId = sessionStorage.getItem('neso-conversation-id');
    if (savedId) {
      setConversationId(savedId);
    }
    
    // Speech synthesis initialization
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      synthRef.current = window.speechSynthesis;
    }
    
    return () => {
      stopSpeaking();
    };
  }, []);
  
  // QR kod ile masa bilgisi yükle
  useEffect(() => {
    const loadMasaFromQR = async () => {
      if (qrCode && !masa) {
        try {
          setMasaLoading(true);
          const API_BASE_URL = normalizeApiUrl(import.meta.env.VITE_API_URL as string);
          const encodedQRCode = encodeURIComponent(qrCode);
          console.log('[QR] Loading masa info for QR code:', qrCode.substring(0, 20) + '...');
          const response = await fetch(`${API_BASE_URL}/public/masa/${encodedQRCode}`);
          if (response.ok) {
            const data = await response.json();
            console.log('[QR] Masa bilgisi yüklendi:', data);
            setMasa(data.masa_adi);
            if (data.sube_id) {
              setSubeId(parseInt(data.sube_id, 10));
              console.log('[QR] sube_id güncellendi:', data.sube_id);
            }
          } else {
            const errorData = await response.json().catch(() => ({ detail: 'Masa bulunamadı' }));
            console.error('[QR] Masa API error:', response.status, errorData);
            // Fallback: QR lookup failed, allow chat without masa
            setMasa('');
          }
        } catch (err) {
          console.error('QR kod masa bilgisi yüklenemedi:', err);
          // Fallback: allow chat without masa info
          setMasa('');
        } finally {
          setMasaLoading(false);
        }
      }
    };
    
    loadMasaFromQR();
  }, [qrCode]); // masa dependency'yi kaldır

  const handleSend = async () => {
    if (!inputText.trim() || loading) return;

    const userMessage: Message = {
      type: 'user',
      text: inputText,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const currentInput = inputText;
    setInputText('');
    setLoading(true);

    try {
      console.log('[SEND] Sipariş gönderiliyor - masa:', masa, 'text:', currentInput);
      const response = await assistantApi.chat({
        text: currentInput,
        masa: masa || undefined,
        sube_id: subeId,
        conversation_id: conversationId || undefined,
      });

      if (response.data.conversation_id) {
        setConversationId(response.data.conversation_id);
        sessionStorage.setItem('neso-conversation-id', response.data.conversation_id);
      }

      // Dil algılama sonucunu sakla
      if (response.data.detected_language) {
        setDetectedLanguage(response.data.detected_language);
      }

      // Önerileri ve diğer verileri mesaja ekle
      const fallbackText = 'Şu an seni tam anlayamadım ama menümüzden öneriler sunabilirim.';
      const replyText = response.data.message || response.data.reply || fallbackText;
      const suggestionList = response.data.suggestions 
        || (response.data.recommendations?.map((rec: { product_name?: string }) => rec.product_name).filter(Boolean) as string[])
        || [];

      const assistantMessage: Message = {
        type: 'assistant',
        text: replyText,
        suggestions: suggestionList,
        audioBase64: response.data.audio_base64 || undefined,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
      playAssistantSpeech(assistantMessage).catch(err => {
        console.warn('Failed to play assistant speech:', err);
      });
      
    } catch (err: any) {
      console.error('Chat error:', err);
      const errorMessage: Message = {
        type: 'assistant',
        text: `Üzgünüm, bir hata oluştu. Lütfen tekrar deneyin. ${err.response?.data?.detail || ''}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    setInputText(suggestion);
    // We need to use a little timeout to allow the state to update before sending
    setTimeout(() => handleSend(), 0);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleBack = () => {
    navigate(-1);
  };

  // Voice recording using MediaRecorder
  const startListening = async () => {
    if (isListening) return;

    stopSpeaking();

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (event) => {
        audioChunksRef.current.push(event.data);
      };

      mediaRecorderRef.current.onstop = async () => {
        setLoading(true);
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        const formData = new FormData();
        formData.append('file', audioBlob, 'voice.webm');
        if (masa) formData.append('masa', masa);
        if (subeId) formData.append('sube_id', String(subeId));
        if (conversationId) formData.append('conversation_id', conversationId);

        try {
          const response = await assistantApi.voiceCommand(formData);
          
          // Add user message (from transcribed text)
          const userMessage: Message = {
            type: 'user',
            text: response.data.text, // Assuming the backend returns the transcribed text
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, userMessage]);

          // Handle assistant response
          if (response.data.conversation_id) {
            setConversationId(response.data.conversation_id);
            sessionStorage.setItem('neso-conversation-id', response.data.conversation_id);
          }
          if (response.data.detected_language) {
            setDetectedLanguage(response.data.detected_language);
          }

          const fallbackText = 'Şu an seni tam anlayamadım ama menümüzden öneriler sunabilirim.';
          const replyText = response.data.message || response.data.reply || fallbackText;
          const suggestionList = response.data.suggestions 
            || (response.data.recommendations?.map((rec: { product_name?: string }) => rec.product_name).filter(Boolean) as string[])
            || [];

          const assistantMessage: Message = {
            type: 'assistant',
            text: replyText,
            suggestions: suggestionList,
            audioBase64: response.data.audio_base64 || undefined,
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, assistantMessage]);
        playAssistantSpeech(assistantMessage).catch(err => {
          console.warn('Failed to play assistant speech:', err);
        });

        } catch (err: any) {
          console.error('Voice command error:', err);
          const errorMessage: Message = {
            type: 'assistant',
            text: `Sesli komut işlenirken bir hata oluştu: ${err.response?.data?.detail || ''}`,
            timestamp: new Date(),
          };
          setMessages((prev) => [...prev, errorMessage]);
        } finally {
          setLoading(false);
        }
      };

      mediaRecorderRef.current.start();
      setIsListening(true);
    } catch (error) {
      console.error('Error accessing microphone:', error);
      alert('Mikrofona erişilemiyor. Lütfen tarayıcı ayarlarınızı kontrol edin.');
    }
  };

  const stopListening = () => {
    if (mediaRecorderRef.current && isListening) {
      mediaRecorderRef.current.stop();
      setIsListening(false);
      // The rest of the logic is in the onstop event handler
    }
  };

  // Sesli okuma (TTS)
  const cleanupAudioPlayback = () => {
    if (audioTimeoutRef.current) {
      clearTimeout(audioTimeoutRef.current);
      audioTimeoutRef.current = null;
    }
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = '';
      audioRef.current = null;
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
  };

  const playAudioBase64 = (base64: string, onFailure?: () => void): boolean => {
    // Base64 string kontrolü
    if (!base64 || typeof base64 !== 'string' || base64.trim().length === 0) {
      console.warn('Invalid or empty audio base64 string');
      if (onFailure) {
        onFailure();
      }
      return false;
    }

    let failureHandled = false;
    const handleFailure = (err?: unknown) => {
      if (failureHandled) {
        return;
      }
      failureHandled = true;
      console.error('Assistant audio playback failed', err);
      setIsSpeaking(false);
      cleanupAudioPlayback();
      if (onFailure) {
        onFailure();
      }
    };

    try {
      // Base64 string'i temizle (data:audio/wav;base64, prefix'i kaldır)
      let cleanBase64 = base64.trim();
      if (cleanBase64.includes(',')) {
        cleanBase64 = cleanBase64.split(',')[1];
      }

      const binary = atob(cleanBase64);
      const buffer = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i += 1) {
        buffer[i] = binary.charCodeAt(i);
      }
      
      // Buffer boyutu kontrolü
      if (buffer.length === 0) {
        console.warn('Decoded audio buffer is empty');
        if (onFailure) {
          onFailure();
        }
        return false;
      }

      const blob = new Blob([buffer], { type: 'audio/mp3' });
      const url = URL.createObjectURL(blob);

      if (synthRef.current) {
        synthRef.current.cancel();
      }
      cleanupAudioPlayback();

      const audio = new Audio();
      audioUrlRef.current = url;
      audioRef.current = audio;

      // Event handler'ları src set etmeden önce ayarla
      audio.onplay = () => setIsSpeaking(true);
      audio.onended = () => {
        setIsSpeaking(false);
        cleanupAudioPlayback();
      };
      audio.onerror = (event: Event | string) => {
        if (typeof event === 'string') {
          handleFailure(new Error(`Audio playback error: ${event}`));
          return;
        }
        const audioElement = event.target as HTMLAudioElement;
        const error = audioElement?.error;
        if (error) {
          handleFailure(new Error(`Audio playback error: code ${error.code} - ${error.message || 'Unknown error'}`));
        } else {
          handleFailure(event);
        }
      };

      // Zaman aşımı kontrolü
      audioTimeoutRef.current = setTimeout(() => {
        if (!audio.readyState || audio.readyState < 2) {
          console.warn('Audio loading timeout');
          handleFailure(new Error('Audio loading timeout'));
        }
      }, 10000);  // 10 saniye timeout

      // Yüklenmeyi bekle, sonra çal
      audio.oncanplaythrough = () => {
        if (audioTimeoutRef.current) {
          clearTimeout(audioTimeoutRef.current);
          audioTimeoutRef.current = null;
        }
        const playPromise = audio.play();
        if (playPromise && typeof playPromise.then === 'function') {
          playPromise.catch((err) => {
            // Kullanıcı etkileşimi gerektiren hatalar için fallback'e geç
            if (err.name === 'NotAllowedError' || err.name === 'NotSupportedError') {
              console.warn('Audio autoplay blocked, falling back to TTS');
            }
            handleFailure(err);
          });
        }
      };

      // src'yi set et ve yükle
      audio.src = url;
      audio.load();  // Audio'yu yükle

      return true;
    } catch (error) {
      console.error('Failed to decode assistant audio', error);
      cleanupAudioPlayback();
      if (synthRef.current) {
        synthRef.current.cancel();
      }
      setIsSpeaking(false);
      if (onFailure) {
        onFailure();
      }
      return false;
    }
  };

  // speakTextFallback removed - backend TTS should always provide audio_base64
  // Fallback caused double audio playback (backend + browser TTS)

  const playAssistantSpeech = async (message: Message) => {
    // audioBase64 varsa ve geçerliyse önce onu dene
    if (message.audioBase64 && message.audioBase64.trim().length > 0) {
      const played = playAudioBase64(message.audioBase64, () => {
        console.warn('Backend TTS audio playback failed');
      });
      if (played) {
        return;
      }
    }
  };

  const stopSpeaking = () => {
    cleanupAudioPlayback();
    if (synthRef.current) {
      synthRef.current.cancel();
    }
    setIsSpeaking(false);
  };

  return (
  return (
    <div className="min-h-screen bg-[#050c0a] text-white font-outfit relative overflow-hidden flex flex-col">
      {/* Background Decorative Elements */}
      <div className="fixed top-0 right-0 w-[500px] h-[500px] bg-emerald-500/5 blur-[120px] rounded-full -translate-y-1/2 translate-x-1/2 pointer-events-none" />
      <div className="fixed bottom-0 left-0 w-[400px] h-[400px] bg-emerald-600/5 blur-[100px] rounded-full translate-y-1/2 -translate-x-1/2 pointer-events-none" />

      {/* Header */}
      <div className="relative z-10 border-b border-white/5 bg-white/[0.02] backdrop-blur-xl">
        <div className="max-w-4xl mx-auto px-6 py-6 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <button
              onClick={handleBack}
              className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center hover:bg-white/10 transition-all group"
            >
              <ArrowLeft className="h-5 w-5 text-white/50 group-hover:text-white transition-colors" />
            </button>
            <div>
              <h1 className="text-xl font-black text-white tracking-tight">NESO<span className="text-emerald-500">.</span> ASİSTAN</h1>
              <div className="flex items-center gap-3">
                 {masa && (
                    <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-bold text-[10px] uppercase">
                      MASA: {masa}
                    </div>
                  )}
                 <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                 <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Çevrimiçi</span>
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
             <button
                onClick={isSpeaking ? stopSpeaking : undefined}
                className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all ${isSpeaking ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/20' : 'bg-white/5 text-slate-500'}`}
             >
                <Volume2 className={`w-5 h-5 ${isSpeaking ? 'animate-pulse' : ''}`} />
             </button>
          </div>
        </div>
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-8 relative">
        <div className="max-w-4xl mx-auto space-y-8">
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex items-end gap-3 ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {msg.type === 'assistant' && (
                <div className="w-8 h-8 rounded-full bg-emerald-500 flex items-center justify-center shrink-0 shadow-lg shadow-emerald-500/20 text-[10px] font-black">N</div>
              )}
              <div
                className={`max-w-[85%] relative ${
                  msg.type === 'user'
                    ? 'bg-emerald-600 text-white rounded-3xl rounded-br-none px-6 py-4 shadow-xl shadow-emerald-900/20 shadow-inner border border-emerald-400/20'
                    : 'glass-panel text-slate-200 rounded-3xl rounded-bl-none px-6 py-4 border border-white/5'
                }`}
              >
                <div className="whitespace-pre-wrap text-[15px] leading-relaxed font-medium">
                  {msg.text}
                </div>
                
                {msg.type === 'assistant' && msg.suggestions && msg.suggestions.length > 0 && (
                  <div className="mt-6 flex flex-wrap gap-2">
                    {msg.suggestions.map((suggestion, i) => (
                      <button
                        key={i}
                        onClick={() => handleSuggestionClick(suggestion)}
                        className="px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-full text-xs font-bold text-emerald-400 transition-all hover:scale-105"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                )}
                
                <div className={`text-[10px] font-bold mt-3 uppercase tracking-widest opacity-30 ${msg.type === 'user' ? 'text-right' : 'text-left'}`}>
                  {msg.timestamp.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
            </div>
          ))}
          
          {loading && (
            <div className="flex justify-start items-center gap-3">
               <div className="w-8 h-8 rounded-full bg-slate-800 animate-pulse shrink-0" />
               <div className="glass-panel px-6 py-4 rounded-3xl rounded-bl-none border border-white/5">
                  <div className="flex gap-2">
                    <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                    <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                    <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                  </div>
               </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="relative z-10 p-6 bg-white/[0.02] backdrop-blur-2xl border-t border-white/5">
        <div className="max-w-4xl mx-auto flex flex-col gap-4">
          {isListening && (
            <div className="flex items-center gap-3 px-4 py-2 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs font-bold uppercase tracking-widest animate-pulse">
              <div className="w-2 h-2 rounded-full bg-rose-500 animate-ping" />
              Sizi Dinliyorum...
            </div>
          )}
          
          <div className="flex items-center gap-3">
            <div className="flex-1 relative group">
              <textarea
                ref={inputRef}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Neso'yla konuşun..."
                className="w-full bg-white/[0.03] border border-white/10 rounded-[1.5rem] px-6 py-4 pr-14 text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500/50 focus:bg-white/[0.05] transition-all resize-none min-h-[60px] max-h-[150px]"
                rows={1}
                disabled={loading || isListening}
              />
              <button
                onClick={isListening ? stopListening : startListening}
                disabled={loading}
                className={`absolute right-3 bottom- side-y-1/2 -translate-y-1/2 md:translate-y-0 md:static p-3 rounded-2xl transition-all ${
                  isListening
                    ? 'bg-rose-500 text-white shadow-lg shadow-rose-500/20 scale-110'
                    : 'text-slate-500 hover:text-white hover:bg-white/5'
                }`}
                aria-label="Sesli Komut"
              >
                <div className="relative">
                  {isListening && <div className="absolute inset-0 bg-white rounded-full animate-ping opacity-20" />}
                  <Mic className={`w-6 h-6 ${isListening ? 'animate-pulse' : ''}`} />
                </div>
              </button>
            </div>

            <button
              onClick={handleSend}
              disabled={!inputText.trim() || loading || isListening}
              className="glow-button w-14 h-14 rounded-[1.5rem] flex items-center justify-center shrink-0 disabled:opacity-50 disabled:grayscale transition-all hover:scale-105 active:scale-90"
            >
              <Send className="w-6 h-6 text-white" />
            </button>
          </div>
          
          <div className="flex justify-center md:hidden">
             <div className="w-12 h-1 bg-white/10 rounded-full" />
          </div>
        </div>
      </div>
    </div>
  );
}
