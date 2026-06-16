// App.tsx — Aplicación principal con sidebar y routing
import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LayoutDashboard, Zap, Users, Trophy } from 'lucide-react';
import { Dashboard } from './pages/Dashboard';
import { PrediccionPage } from './pages/PrediccionPage';
import { EquiposPage } from './pages/EquiposPage';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000,
      gcTime: 5 * 60 * 1000,
    },
  },
});

type Page = 'dashboard' | 'prediccion' | 'equipos';

const NAV_ITEMS = [
  { id: 'dashboard' as Page, label: 'Dashboard', icon: LayoutDashboard },
  { id: 'prediccion' as Page, label: 'Predicciones', icon: Zap },
  { id: 'equipos' as Page, label: 'Equipos', icon: Users },
];

function AppLayout() {
  const [activePage, setActivePage] = useState<Page>('dashboard');

  const renderPage = () => {
    switch (activePage) {
      case 'dashboard': return <Dashboard />;
      case 'prediccion': return <PrediccionPage />;
      case 'equipos': return <EquiposPage />;
      default: return <Dashboard />;
    }
  };

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        {/* Logo */}
        <div className="sidebar-logo">
          <div className="logo-icon">⚽</div>
          <div>
            <div className="logo-text">Predictor Fútbol</div>
            <div className="logo-subtitle">Mundial FIFA · ML Analytics</div>
          </div>
        </div>

        {/* Navegación */}
        <nav className="sidebar-nav">
          <div className="nav-section-label">Menú Principal</div>
          {NAV_ITEMS.map(item => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                id={`nav-${item.id}`}
                className={`nav-item ${activePage === item.id ? 'active' : ''}`}
                onClick={() => setActivePage(item.id)}
              >
                <Icon className="nav-icon" size={17} />
                {item.label}
              </button>
            );
          })}

          {/* Info Mundial */}
          <div className="nav-section-label" style={{ marginTop: '1rem' }}>Competición</div>
          <div style={{
            margin: '0.5rem 0.75rem',
            background: 'rgba(251,191,36,0.08)',
            border: '1px solid rgba(251,191,36,0.2)',
            borderRadius: 12,
            padding: '0.875rem',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
              <Trophy size={14} color="#fbbf24" />
              <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#fbbf24' }}>
                Mundial FIFA 2026
              </span>
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', lineHeight: 1.5 }}>
              USA · México · Canadá<br />
              48 equipos · 104 partidos
            </div>
          </div>
        </nav>

        {/* Footer del sidebar */}
        <div style={{
          padding: '1rem 1.5rem',
          borderTop: '1px solid var(--color-border)',
          fontSize: '0.7rem',
          color: 'var(--color-text-dim)',
        }}>
          <div>Predictor Fútbol v1.0</div>
          <div>Dixon-Coles · XGBoost · ELO</div>
        </div>
      </aside>

      {/* Contenido principal */}
      <main className="main-content">
        {renderPage()}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppLayout />
    </QueryClientProvider>
  );
}
