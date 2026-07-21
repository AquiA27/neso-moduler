import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RotateCw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

// Beklenmeyen render hatalarında beyaz ekran yerine markalı kurtarma ekranı gösterir
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Yakalanmamış arayüz hatası:', error, info.componentStack);
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="flex h-screen flex-col items-center justify-center gap-8 p-6 text-center animate-in fade-in duration-500">
        <div className="relative">
          <div className="p-6 rounded-3xl bg-rose-500/10 border border-rose-500/20 text-rose-400">
            <AlertTriangle size={40} />
          </div>
          <div className="absolute inset-0 rounded-3xl bg-rose-500/10 blur-2xl -z-10" />
        </div>
        <div className="space-y-2 max-w-md">
          <h2 className="text-2xl font-bold text-white tracking-tight">Beklenmeyen bir hata oluştu</h2>
          <p className="text-slate-400 font-medium">
            Ekip otomatik olarak bilgilendirildi. Sayfayı yenileyerek kaldığınız yerden devam edebilirsiniz.
          </p>
        </div>
        <button onClick={() => window.location.reload()} className="glow-button">
          <RotateCw size={18} />
          Sayfayı Yenile
        </button>
      </div>
    );
  }
}
