import { useState, useRef, useEffect } from 'react';
import { biAssistantApi } from '../lib/api';
import apiClient from '../lib/api';
import { 
  Send, Sparkles, Brain, TrendingUp, ShoppingBag, Target, Info, RefreshCw, Zap, MessageSquare 
} from 'lucide-react';
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
  const [activeTab, setActiveTab] = useState<'chat' | 'analytics'>('chat');
  
  // Chat State
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const subeId = useAuthStore((state) => state.subeId);

  // Analytics State
  const [analiticsLoading, setAnaliticsLoading] = useState(false);
  const [forecast, setForecast] = useState<any[]>([]);
  const [affinity, setAffinity] = useState<any[]>([]);
  const [optimization, setOptimization] = useState<any[]>([]);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (activeTab === 'chat') scrollToBottom();
  }, [messages, activeTab]);

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

    if (subeId) fetchMorningBrief();
  }, [subeId]);

  const fetchPredictiveData = async () => {
    setAnaliticsLoading(true);
    try {
      const [forecastRes, affinityRes, optimRes] = await Promise.all([
        apiClient.get('/analytics/predictive/demand-forecast'),
        apiClient.get('/analytics/predictive/product-affinity'),
        apiClient.get('/analytics/predictive/menu-optimization')
      ]);
      setForecast(forecastRes.data);
      setAffinity(affinityRes.data);
      setOptimization(optimRes.data);
    } catch (error) {
      console.error('Veriler yüklenirken hata oluştu:', error);
    } finally {
      setAnaliticsLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'analytics' && forecast.length === 0) {
      fetchPredictiveData();
    }
  }, [activeTab]);

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
      {/* Header with Tabs */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between border-b border-white/10 pb-4">
        <h2 className="text-4xl font-bold gradient-text">📊 İşletme Zekası</h2>
        
        <div className="flex bg-slate-900/80 p-1 rounded-2xl border border-white/5">
          <button
            onClick={() => setActiveTab('chat')}
            className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-bold transition-all ${
              activeTab === 'chat' 
                ? 'bg-neso-gold text-neso-dark shadow-lg shadow-neso-gold/20' 
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <MessageSquare size={18} />
            AI Asistan
          </button>
          <button
            onClick={() => setActiveTab('analytics')}
            className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-bold transition-all ${
              activeTab === 'analytics' 
                ? 'bg-neso-gold text-neso-dark shadow-lg shadow-neso-gold/20' 
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Sparkles size={18} />
            Akıllı Analitik
          </button>
        </div>
      </div>

      {activeTab === 'chat' ? (
        <div className="card h-[650px] flex flex-col animate-in slide-in-from-bottom-4 duration-500">
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

          <div className="flex gap-2 p-4 border-t border-white/10">
            <textarea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="İşletme verilerinizle ilgili bir soru sorun..."
              disabled={loading}
              rows={2}
              className="flex-1 px-4 py-3 bg-gradient-to-br from-slate-800 to-slate-900 border border-neso-gold/30 rounded-xl focus:outline-none focus:ring-2 focus:ring-neso-gold resize-none disabled:opacity-50 text-white placeholder-neso-gray shadow-inner"
            />
            <button
              onClick={handleQuery}
              disabled={loading || !inputText.trim()}
              className="px-6 py-2 bg-gradient-to-r from-neso-gold to-neso-lightgold rounded-xl transition-all shadow-lg font-semibold text-neso-dark disabled:opacity-50 flex items-center gap-2"
            >
              <Send className="w-5 h-5" />
              Gönder
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-8 animate-in fade-in duration-700">
          {analiticsLoading ? (
            <div className="flex flex-col h-[60vh] items-center justify-center gap-4">
              <RefreshCw className="h-10 w-10 animate-spin text-neso-gold" />
              <p className="text-slate-400 font-medium animate-pulse">Yapay Zeka Analiz Yapıyor...</p>
            </div>
          ) : (
            <>
              {/* Demand & Affinity Grid */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Forecast */}
                <div className="glass-card p-8 rounded-[2.5rem] relative overflow-hidden group">
                  <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:opacity-20 transition-opacity">
                    <TrendingUp size={80} />
                  </div>
                  <h3 className="text-xl font-bold text-white mb-6 flex items-center gap-3">
                    <Zap className="text-amber-400" size={20} />
                    7 Günlük Satış Tahmini
                  </h3>
                  <div className="space-y-6">
                    {forecast.slice(0, 5).map((item, idx) => (
                      <div key={idx} className="p-5 rounded-3xl bg-white/[0.03] border border-white/5">
                        <div className="flex items-center justify-between mb-4">
                          <span className="font-bold text-white tracking-tight">{item.urun}</span>
                          <div className={`px-3 py-1 rounded-full text-[10px] font-black uppercase
                            ${item.stock_status === 'yeterli' ? 'bg-emerald-500/10 text-emerald-400' : 
                              item.stock_status === 'riskli' ? 'bg-amber-500/10 text-amber-400' : 
                              item.stock_status === 'yetersiz' ? 'bg-rose-500/10 text-rose-400' : 
                              'bg-slate-500/10 text-slate-400'}
                          `}>
                            Stok: {item.stock_status}
                          </div>
                        </div>
                        <div className="h-20 w-full">
                          <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={item.forecast}>
                              <Line type="monotone" dataKey="predicted_sales" stroke="#eab308" strokeWidth={2} dot={false} />
                            </LineChart>
                          </ResponsiveContainer>
                        </div>
                        <div className="mt-2 text-right">
                          <span className="text-[10px] text-slate-500 font-bold uppercase">Tahmin:</span>
                          <span className="ml-2 text-lg font-black text-white">{item.total_predicted_7d} Adet</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Affinity */}
                <div className="glass-card p-8 rounded-[2.5rem] relative overflow-hidden group">
                  <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:opacity-20 transition-opacity">
                    <ShoppingBag size={80} />
                  </div>
                  <h3 className="text-xl font-bold text-white mb-6 flex items-center gap-3">
                    <Sparkles className="text-purple-400" size={20} />
                    Akıllı Sepet Birliktelikleri
                  </h3>
                  <div className="space-y-4">
                    {affinity.map((pair, idx) => (
                      <div key={idx} className="p-6 rounded-3xl bg-white/[0.03] border border-white/5 relative overflow-hidden">
                         <div className="absolute right-0 top-0 h-full w-1 bg-neso-gold/40" style={{ height: `${pair.correlation_score * 100}%` }} />
                         <div className="flex items-center justify-between">
                            <div className="flex flex-col">
                              <span className="text-sm font-bold text-white">{pair.product_a}</span>
                              <span className="text-[10px] text-slate-500 font-bold">ve</span>
                              <span className="text-sm font-bold text-white">{pair.product_b}</span>
                            </div>
                            <div className="text-right text-2xl font-black text-neso-gold">
                              %{Math.round(pair.correlation_score * 100)}
                            </div>
                         </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Optimization */}
              <div className="glass-card p-10 rounded-[3rem]">
                <h3 className="text-2xl font-black text-white mb-8 flex items-center gap-3">
                  <Target className="text-rose-500" />
                  MENÜ OPTİMİZASYONU
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                   {optimization.map((item, idx) => (
                      <div key={idx} className="p-6 rounded-[2rem] bg-white/[0.02] border border-white/5 flex flex-col h-full">
                         <div className="flex justify-between items-start mb-4">
                            <span className="font-black text-white uppercase">{item.urun}</span>
                            <span className={`px-3 py-1 rounded-xl text-[9px] font-black
                              ${item.tip === 'hero' ? 'bg-emerald-500/20 text-emerald-400' : 
                                item.tip === 'sleeping' ? 'bg-blue-500/20 text-blue-400' : 
                                item.tip === 'underperformer' ? 'bg-rose-500/20 text-rose-400' : 
                                'bg-slate-500/20 text-slate-400'}
                            `}>{item.tip.toUpperCase()}</span>
                         </div>
                         <p className="text-sm text-slate-400 mb-6 flex-1 italic">"{item.oneri}"</p>
                         <div className="flex justify-between text-[11px] font-bold text-slate-500 border-t border-white/5 pt-4">
                            <span>MARJ: %{item.metrikler.kar_marji}</span>
                            <span>ADET: {item.metrikler.adet}</span>
                         </div>
                      </div>
                   ))}
                </div>
              </div>

              {/* Info */}
              <div className="p-6 rounded-[2rem] bg-neso-gold/5 border border-neso-gold/10 flex items-center gap-4">
                <Info size={20} className="text-neso-gold" />
                <p className="text-sm text-slate-400">Bu veriler son 60 günlük hareketlerinizden AI tarafından üretilmiştir.</p>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
