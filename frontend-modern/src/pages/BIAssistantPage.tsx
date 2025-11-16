import { useState, useRef, useEffect } from 'react';
import { biAssistantApi } from '../lib/api';
import { Send } from 'lucide-react';
import { useAuthStore } from '../store/authStore';

interface Message {
  type: 'user' | 'assistant';
  text: string;
  timestamp: Date;
}

export default function BIAssistantPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      type: 'assistant',
      text: 'Merhaba! Ben Neso Fıstık Kafe İşletme Asistanınız. Bugün size nasıl yardımcı olabilirim?',
      timestamp: new Date(),
    },
  ]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const subeId = useAuthStore((state) => state.subeId);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleQuery = async () => {
    if (!inputText.trim()) return;

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
      const response = await biAssistantApi.query({
        text: currentInput,
        sube_id: subeId,
      });

      let assistantText = response.data.reply || 'Anlayamadım, tekrar deneyebilir misiniz?';

      const assistantMessage: Message = {
        type: 'assistant',
        text: assistantText,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: any) {
      console.error('BI query error:', err);
      const errorMessage: Message = {
        type: 'assistant',
        text: `Hata: ${err.response?.data?.detail || err.message || 'Bir sorun oluştu'}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleQuery();
    }
  };

  return (
    <div className="space-y-6">
      <h2 className="text-4xl font-bold gradient-text">📊 İşletme Zekası Asistanı</h2>

      <div className="card h-[600px] flex flex-col">
        <div className="flex-1 overflow-y-auto p-4 space-y-4 mb-4 custom-scrollbar">
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.type === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-lg p-4 ${
                  msg.type === 'user'
                    ? 'bg-neso-gold text-neso-dark shadow-md'
                    : 'bg-gradient-to-br from-neso-dark to-slate-900 text-neso-light shadow-md border border-neso-gold/20'
                }`}
              >
                <div className="whitespace-pre-wrap">{msg.text}</div>
                <div className="text-xs mt-2 opacity-70">
                  {msg.timestamp.toLocaleTimeString('tr-TR', {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </div>
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-gradient-to-br from-neso-dark to-slate-900 rounded-lg p-4 border border-neso-gold/20">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-neso-lightgold rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-neso-lightgold rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  <div className="w-2 h-2 bg-neso-lightgold rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                </div>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Input */}
        <div className="flex gap-2 p-4 border-t border-white/10">
          <textarea
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="İşletme verilerinizle ilgili bir soru sorun..."
            disabled={loading}
            rows={2}
            className="flex-1 px-4 py-2 bg-gradient-to-br from-slate-800 to-slate-900 border border-neso-gold/30 rounded-xl focus:outline-none focus:ring-2 focus:ring-neso-gold resize-none disabled:opacity-50 text-white placeholder-neso-gray"
          />
          <button
            onClick={handleQuery}
            disabled={loading || !inputText.trim()}
            className="px-6 py-2 bg-gradient-to-r from-neso-gold to-neso-lightgold hover:from-neso-gold/90 hover:to-neso-lightgold/90 rounded-xl transition-all shadow-lg shadow-neso-gold/30 font-semibold text-neso-dark disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <Send className="w-4 h-4" />
            Gönder
          </button>
        </div>
      </div>
    </div>
  );
}

