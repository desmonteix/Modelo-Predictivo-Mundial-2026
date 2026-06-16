// pages/EquiposPage.tsx — Lista de equipos con ELO y forma reciente
import { useQuery } from '@tanstack/react-query';
import { TrendingUp } from 'lucide-react';
import { obtenerEquipos } from '../lib/api';
import { FormStrip } from '../components/FormStrip';

export function EquiposPage() {
  const { data: equipos = [], isLoading } = useQuery({
    queryKey: ['equipos'],
    queryFn: obtenerEquipos,
    retry: 1,
  });

  if (isLoading) {
    return (
      <div className="loading-container">
        <div className="spinner" />
        <span>Cargando equipos...</span>
      </div>
    );
  }

  return (
    <div>
      <div className="section-header">
        <div>
          <h1 style={{ fontSize: '1.75rem', marginBottom: '0.25rem' }}>
            👥 Equipos del Mundial
          </h1>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
            Rankings ELO y forma reciente de todos los equipos registrados
          </p>
        </div>
      </div>

      {equipos.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">👥</div>
          <h3>Sin equipos registrados</h3>
          <p>Ejecuta el script de ingestión de datos para cargar los equipos del Mundial.</p>
          <div style={{
            marginTop: '1rem',
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid var(--color-border)',
            borderRadius: 8,
            padding: '0.875rem 1.25rem',
            fontSize: '0.8rem',
            color: 'var(--color-text-muted)',
            textAlign: 'left',
            fontFamily: 'monospace',
          }}>
            python backend/data/ingest_world_cup.py --api-key TU_KEY --seasons 2022 2026
          </div>
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{
                background: 'rgba(255,255,255,0.03)',
                borderBottom: '1px solid var(--color-border)',
              }}>
                {['#', 'Equipo', 'País', 'ELO', 'Forma', 'Racha'].map(h => (
                  <th key={h} style={{
                    padding: '0.875rem 1.25rem',
                    textAlign: 'left',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    color: 'var(--color-text-muted)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {equipos.map((equipo, i) => (
                <tr
                  key={equipo.team_id}
                  style={{
                    borderBottom: '1px solid var(--color-border)',
                    transition: 'background 0.15s ease',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.02)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                >
                  <td style={{ padding: '0.875rem 1.25rem', width: 50 }}>
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
                    }}>
                      {i + 1}
                    </div>
                  </td>
                  <td style={{ padding: '0.875rem 1.25rem' }}>
                    <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{equipo.name}</div>
                    {equipo.short_name && (
                      <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>{equipo.short_name}</div>
                    )}
                  </td>
                  <td style={{ padding: '0.875rem 1.25rem', color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
                    {equipo.country ?? '—'}
                  </td>
                  <td style={{ padding: '0.875rem 1.25rem' }}>
                    <div style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.3rem',
                      fontWeight: 800,
                      fontSize: '1rem',
                      color: 'var(--color-primary)',
                    }}>
                      <TrendingUp size={12} />
                      {equipo.elo_rating.toFixed(0)}
                    </div>
                  </td>
                  <td style={{ padding: '0.875rem 1.25rem' }}>
                    <FormStrip results={equipo.last5_results ?? ''} />
                  </td>
                  <td style={{ padding: '0.875rem 1.25rem' }}>
                    {equipo.streak_type && (
                      <span className={`form-chip ${equipo.streak_type}`} style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: 6, height: 'auto', width: 'auto' }}>
                        {equipo.streak_type} ×{equipo.streak_length}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
