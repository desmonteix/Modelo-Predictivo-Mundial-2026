// pages/Dashboard.tsx — Panel principal con próximos partidos y equipos
import { useQuery } from '@tanstack/react-query';
import { TrendingUp, Trophy, Activity } from 'lucide-react';
import { obtenerPartidos, obtenerEquipos, healthCheck, obtenerStats } from '../lib/api';
import { FormStrip } from '../components/FormStrip';
import { format } from 'date-fns';
import { es } from 'date-fns/locale';

const FASES_COLORES: Record<string, string> = {
  'Final': '#fbbf24',
  'Semifinal': '#a78bfa',
  'Cuartos De Final': '#3b82f6',
  'Octavos De Final': '#10b981',
  'Fase De Grupos': '#64748b',
};

function formatFecha(dateStr: string) {
  try {
    return format(new Date(dateStr), "d MMM, HH:mm", { locale: es });
  } catch {
    return dateStr;
  }
}

export function Dashboard() {
  const { data: partidos = [], isLoading: loadingPartidos } = useQuery({
    queryKey: ['partidos-proximos'],
    queryFn: () => obtenerPartidos(false, 10, 1),
    retry: 1,
  });

  const { data: partidos_completados = [] } = useQuery({
    queryKey: ['partidos-completados'],
    queryFn: () => obtenerPartidos(true, 6, 1),
    retry: 1,
  });

  const { data: equipos = [], isLoading: loadingEquipos } = useQuery({
    queryKey: ['equipos'],
    queryFn: obtenerEquipos,
    retry: 1,
  });

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: healthCheck,
    retry: 1,
    staleTime: 30000,
  });

  const topEquipos = equipos.slice(0, 8);

  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: obtenerStats,
    retry: 1,
  });

  const totalPartidos = stats?.total_matches || partidos.length + partidos_completados.length;
  const totalEquipos = stats?.total_teams || equipos.length;
  const totalProximos = stats?.matches_upcoming || partidos.length;
  const totalCompletados = stats?.matches_completed || partidos_completados.length;

  return (
    <div>
      {/* Hero */}
      <div className="hero-section" style={{ marginBottom: '2rem' }}>
        <div style={{ position: 'relative', zIndex: 1 }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            background: 'rgba(59,130,246,0.15)',
            border: '1px solid rgba(59,130,246,0.25)',
            borderRadius: 20,
            padding: '0.25rem 0.875rem',
            fontSize: '0.75rem',
            color: 'var(--color-primary)',
            fontWeight: 600,
            marginBottom: '1rem',
          }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981', display: 'inline-block', animation: 'pulse-glow 2s infinite' }} />
            Sistema Activo — Mundial FIFA 2026
          </div>
          <h1 style={{ marginBottom: '0.5rem' }}>
            Predictor Fútbol 🏆
          </h1>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '1rem', maxWidth: 500 }}>
            Predicciones calibradas con modelos Dixon-Coles y XGBoost.
            Ponderación temporal inteligente con decay exponencial.
          </p>

          {health && (
            <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem', flexWrap: 'wrap' }}>
              {health.modelos_cargados?.map((m: string) => (
                <div key={m} style={{
                  fontSize: '0.75rem',
                  padding: '0.3rem 0.75rem',
                  background: 'rgba(16,185,129,0.1)',
                  border: '1px solid rgba(16,185,129,0.2)',
                  borderRadius: 20,
                  color: '#10b981',
                  fontWeight: 600,
                }}>
                  ✓ {m}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="stats-grid" style={{ marginBottom: '2rem' }}>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(59,130,246,0.15)' }}>🏟️</div>
          <div className="stat-value" style={{ color: 'var(--color-primary)' }}>
            {totalPartidos}
          </div>
          <div className="stat-label">Partidos cargados</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(16,185,129,0.15)' }}>👥</div>
          <div className="stat-value" style={{ color: '#10b981' }}>{totalEquipos}</div>
          <div className="stat-label">Equipos registrados</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(245,158,11,0.15)' }}>⏰</div>
          <div className="stat-value" style={{ color: '#f59e0b' }}>{totalProximos}</div>
          <div className="stat-label">Próximos partidos</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(167,139,250,0.15)' }}>✅</div>
          <div className="stat-value" style={{ color: '#a78bfa' }}>{totalCompletados}</div>
          <div className="stat-label">Partidos completados</div>
        </div>
      </div>

      <div className="grid-2" style={{ gap: '1.5rem', marginBottom: '1.5rem' }}>
        {/* Próximos partidos */}
        <div>
          <div className="section-header">
            <h2 className="section-title">
              <Activity size={18} color="var(--color-primary)" />
              Próximos Partidos
            </h2>
          </div>

          {loadingPartidos ? (
            <div className="loading-container">
              <div className="spinner" />
              <span>Cargando partidos...</span>
            </div>
          ) : partidos.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">📅</div>
              <h3>Sin partidos próximos</h3>
              <p>Ingesta los datos del Mundial para ver los fixtures aquí.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {partidos.slice(0, 6).map(partido => (
                <PartidoCard key={partido.match_id} partido={partido} />
              ))}
            </div>
          )}
        </div>

        {/* Ranking ELO */}
        <div>
          <div className="section-header">
            <h2 className="section-title">
              <TrendingUp size={18} color="var(--color-secondary)" />
              Ranking ELO
            </h2>
          </div>

          {loadingEquipos ? (
            <div className="loading-container">
              <div className="spinner" />
              <span>Cargando equipos...</span>
            </div>
          ) : topEquipos.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">🏆</div>
              <h3>Sin datos de equipos</h3>
              <p>El ranking ELO aparecerá aquí después de ingestar datos.</p>
            </div>
          ) : (
            <div className="card" style={{ padding: '0' }}>
              {topEquipos.map((equipo, i) => (
                <div key={equipo.team_id} style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '0.875rem 1.25rem',
                  borderBottom: i < topEquipos.length - 1 ? '1px solid var(--color-border)' : 'none',
                  gap: '1rem',
                  transition: 'background 0.2s ease',
                }}>
                  {/* Posición */}
                  <div style={{
                    width: 28,
                    height: 28,
                    borderRadius: '50%',
                    background: i < 3 ? 'var(--gradient-gold)' : 'rgba(255,255,255,0.06)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.75rem',
                    fontWeight: 800,
                    color: i < 3 ? '#fff' : 'var(--color-text-muted)',
                    flexShrink: 0,
                  }}>
                    {i + 1}
                  </div>

                  {/* Info equipo */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: '0.15rem' }}>
                      {equipo.name}
                    </div>
                    {equipo.last5_results && (
                      <FormStrip results={equipo.last5_results} />
                    )}
                  </div>

                  {/* ELO */}
                  <div style={{ textAlign: 'right', flexShrink: 0 }}>
                    <div style={{ fontWeight: 800, color: 'var(--color-primary)' }}>
                      {equipo.elo_rating.toFixed(0)}
                    </div>
                    <div style={{ fontSize: '0.65rem', color: 'var(--color-text-muted)' }}>ELO</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Resultados recientes */}
      {partidos_completados.length > 0 && (
        <div>
          <div className="section-header">
            <h2 className="section-title">
              <Trophy size={18} color="var(--color-gold)" />
              Resultados Recientes
            </h2>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
            {partidos_completados.map(partido => (
              <ResultadoCard key={partido.match_id} partido={partido} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function PartidoCard({ partido }: { partido: any }) {
  const stageColor = FASES_COLORES[partido.match_stage] || '#64748b';

  return (
    <div className="card" style={{ padding: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
        {partido.match_stage && (
          <span style={{
            fontSize: '0.65rem',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            color: stageColor,
            background: `${stageColor}15`,
            padding: '0.2rem 0.5rem',
            borderRadius: 20,
            border: `1px solid ${stageColor}30`,
          }}>
            {partido.match_stage}
          </span>
        )}
        <span style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>
          {formatFecha(partido.date)}
        </span>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontWeight: 700, fontSize: '0.9rem' }}>{partido.home_team}</span>
        <span style={{ color: 'var(--color-text-dim)', fontSize: '0.75rem', fontWeight: 600 }}>VS</span>
        <span style={{ fontWeight: 700, fontSize: '0.9rem', textAlign: 'right' }}>{partido.away_team}</span>
      </div>

      {partido.has_prediction && (
        <div style={{
          marginTop: '0.5rem',
          fontSize: '0.7rem',
          color: 'var(--color-secondary)',
          display: 'flex',
          alignItems: 'center',
          gap: '0.25rem',
        }}>
          <span>✓</span> Predicción disponible
        </div>
      )}
    </div>
  );
}

function ResultadoCard({ partido }: { partido: any }) {
  const resultColor = partido.result === 'H' ? '#3b82f6' : partido.result === 'D' ? '#94a3b8' : '#f59e0b';

  return (
    <div className="card" style={{ padding: '1rem' }}>
      {partido.match_stage && (
        <div style={{ fontSize: '0.65rem', color: 'var(--color-text-dim)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          {partido.match_stage}
        </div>
      )}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontWeight: 600, fontSize: '0.85rem', flex: 1 }}>{partido.home_team}</span>
        <div style={{
          background: `${resultColor}15`,
          border: `1px solid ${resultColor}30`,
          borderRadius: 8,
          padding: '0.3rem 0.75rem',
          fontWeight: 900,
          fontSize: '1.1rem',
          color: 'var(--color-text)',
          margin: '0 0.5rem',
        }}>
          {partido.home_goals ?? '?'} – {partido.away_goals ?? '?'}
        </div>
        <span style={{ fontWeight: 600, fontSize: '0.85rem', flex: 1, textAlign: 'right' }}>{partido.away_team}</span>
      </div>
    </div>
  );
}
