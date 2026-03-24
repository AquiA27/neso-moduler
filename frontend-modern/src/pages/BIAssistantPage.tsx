import { useState, useRef, useEffect } from 'react';
import { biAssistantApi } from '../lib/api';
import { Send } from 'lucide-react';
import { useAuthStore } from '../store/authStore';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, AreaChart, Area
} from 'recharts';

interface Message {
  type: 'user' | 'assistant';
  text: string;
  chartData?: any;
  timestamp: Date;
}

const COLORS = ['#eab308', '#3b82f6', '#10b981', '#ef4444', '#8b5cf6', '#f97316'];

export default function BIAssistantPage() {
  const [messages, setMessages] = useState<Message[]>([]);
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

  useEffect(() => {
    const fetchMorningBrief = async () => {
      setLoading(true);
      try {
        const response = await biAssistantApi.morningBrief(subeId);
        let rawResponse = response.data.reply || 'Günaydın! Size nasıl yardımcı olabilirim?';
        const { pureText, chartData } = extractChartFromJson(rawResponse);

        setMessages([{
          type: 'assistant',
          text: pureText,
          chartData: chartData,
          timestamp: new Date(),
        }]);
      } catch (err) {
        setMessages([{
          type: 'assistant',
          text: 'Merhaba! Ben Neso İşletme BI Asistanınız. Günlük verileriniz hakkında ne öğrenmek istersiniz?\n\n💡 Örneğin: "Son 15 günün cirosunu göster" derseniz size grafik çizebilirim!',
          timestamp: new Date(),
        }]);
      } finally {
        setLoading(false);
      }
    };

    fetchMorningBrief();
  }, [subeId]);

  const extractChartFromJson = (text: string): { pureText: string, chartData: any } => {
    const jsonRegex = /```json\n([\s\S]*?)\n```/g;
    let pureText = text;
    let chartData = null;

    const match = jsonRegex.exec(text);
    if (match && match[1]) {
      try {
        chartData = JSON.parse(match[1]);
        pureText = text.replace(match[0], '').trim();
      } catch (e) {
        console.error("Failed to parse chart JSON from LLM response", e);
      }
    }

    // Some models might skip the "json" tag
    if (!chartData) {
      const anyRegex = /```\n([\s\S]*?)\n```/g;
      const matchAny = anyRegex.exec(text);
      if (matchAny && matchAny[1] && matchAny[1].includes('"chartType"')) {
        try {
          chartData = JSON.parse(matchAny[1]);
          pureText = text.replace(matchAny[0], '').trim();
        } catch (e) { }
      }
    }

    return { pureText, chartData };
  };

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

      let rawResponse = response.data.reply || 'Anlayamadım, tekrar deneyebilir misiniz?';
      const { pureText, chartData } = extractChartFromJson(rawResponse);

      const assistantMessage: Message = {
        type: 'assistant',
        text: pureText,
        chartData: chartData,
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

  const renderChart = (chartConfig: any) => {
    if (!chartConfig || !chartConfig.data || chartConfig.data.length === 0) return null;

    const type = chartConfig.chartType || 'bar';
    const fillCol = chartConfig.color || '#eab308';
    const dataKey = chartConfig.dataKey || 'value';

    let ChartComponent: any = BarChart;
    if (type === 'line') ChartComponent = LineChart;
    if (type === 'pie') ChartComponent = PieChart;
    if (type === 'area') ChartComponent = AreaChart;

    return (
      <div className="w-full h-64 mt-4 bg-slate-900/50 p-4 rounded-xl border border-white/5">
        {chartConfig.title && (
          <h4 className="text-sm font-semibold text-center mb-4 text-slate-300">{chartConfig.title}</h4>
        )}
        <ResponsiveContainer width="100%" height="100%">
          {type === 'pie' ? (
            <PieChart>
              <Pie
                data={chartConfig.data}
                dataKey={dataKey}
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={80}
                label
              >
                {chartConfig.data.map((_: any, index: number) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f8fafc' }}
                itemStyle={{ color: '#f8fafc' }}
              />
              <Legend />
            </PieChart>
          ) : (
            <ChartComponent data={chartConfig.data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
              <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} tickLine={false} />
              <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', color: '#f8fafc', borderRadius: '8px' }}
                itemStyle={{ color: '#eab308', fontWeight: 'bold' }}
                cursor={{ fill: '#334155', opacity: 0.4 }}
              />
              {type === 'bar' && <Bar dataKey={dataKey} fill={fillCol} radius={[4, 4, 0, 0]} />}
              {type === 'line' && <Line type="monotone" dataKey={dataKey} stroke={fillCol} strokeWidth={3} dot={{ r: 4, strokeWidth: 2 }} activeDot={{ r: 6 }} />}
              {type === 'area' && <Area type="monotone" dataKey={dataKey} stroke={fillCol} fill={fillCol} fillOpacity={0.3} />}
            </ChartComponent>
          )}
        </ResponsiveContainer>
      </div>
    );
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
                className={`max-w-[85%] rounded-lg p-4 ${msg.type === 'user'
                  ? 'bg-neso-gold text-neso-dark shadow-md'
                  : 'bg-gradient-to-br from-neso-dark to-slate-900 text-neso-light shadow-md border border-neso-gold/20'
                  }`}
              >
                <div className="whitespace-pre-wrap leading-relaxed">{msg.text}</div>
                {msg.chartData && renderChart(msg.chartData)}
                <div className={`text-xs mt-2 ${msg.type === 'user' ? 'opacity-70' : 'text-slate-500'}`}>
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
              <div className="bg-gradient-to-br from-neso-dark to-slate-900 rounded-lg p-4 border border-neso-gold/20 flex gap-3 items-center">
                <div className="w-6 h-6 border-2 border-neso-gold border-t-transparent rounded-full animate-spin"></div>
                <span className="text-slate-400 text-sm">Analiz ediliyor...</span>
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
            placeholder="İşletme verilerinizle, cironuzla veya karlılığınızla ilgili bir soru sorun..."
            disabled={loading}
            rows={2}
            className="flex-1 px-4 py-3 bg-gradient-to-br from-slate-800 to-slate-900 border border-neso-gold/30 rounded-xl focus:outline-none focus:ring-2 focus:ring-neso-gold resize-none disabled:opacity-50 text-white placeholder-neso-gray shadow-inner"
          />
          <button
            onClick={handleQuery}
            disabled={loading || !inputText.trim()}
            className="px-6 py-2 bg-gradient-to-r from-neso-gold to-neso-lightgold hover:from-neso-gold/90 hover:to-neso-lightgold/90 rounded-xl transition-all shadow-lg shadow-neso-gold/30 font-semibold text-neso-dark disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <Send className="w-5 h-5" />
            Gönder
          </button>
        </div>
      </div>
    </div>
  );
}

