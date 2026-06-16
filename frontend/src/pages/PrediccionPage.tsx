// pages/PrediccionPage.tsx — Página principal de predicción de partidos
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { AlertTriangle, Zap, Trophy, TrendingUp } from 'lucide-react';
import { predecirPartido } from '../lib/api';
import type { Prediccion } from '../lib/api';
import { ConfidenceBadge } from '../components/ConfidenceBadge';
import { ProbabilityBar } from '../components/ProbabilityBar';
import { GoalDistChart } from '../components/GoalDistChart';

// Equipos del Mundial 2026
const EQUIPOS_MUNDIAL = [
  'Argentina', 'Brasil', 'Francia', 'España', 'Alemania',
  'Inglaterra', 'Portugal', 'Países Bajos', 'Uruguay', 'Colombia',
  'México', 'Estados Unidos', 'Marruecos', 'Japón', 'Corea del Sur',
  'Senegal', 'Ghana', 'Camerún', 'Ecuador', 'Peru',
  'Chile', 'Bolivia', 'Venezuela', 'Paraguay',
];

const FASES = [
  'Fase de Grupos', 'Octavos de Final', 'Cuartos de Final',
  'Semifinal', 'Tercer Lugar', 'Final',
];

export function PrediccionPage() {
  const [homeTeam, setHomeTeam] = useState('');
  const [awayTeam, setAwayTeam] = useState('');
  const [matchStage, setMatchStage] = useState('Fase de Grupos');
  const [prediccion, setPrediccion] = useState<Prediccion | null>(null);

  const mutation = useMutation({
    mutationFn: () => predecirPartido(homeTeam, awayTeam, 'FIFA World Cup', matchStage, true),
    onSuccess: (data) => setPrediccion(data),
  });

  const canPredict = homeTeam.trim() && awayTeam.trim() && homeTeam !== awayTeam;

  return (
    <div>
      {/* Header */}
      <div className="section-header">
        <div>
          <h1 style={{ fontSize: '1.75rem', marginBottom: '0.25rem' }}>
            🔮 Predictor de Partidos
          </h1>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
            Análisis estadístico con modelos Dixon-Coles y XGBoost
          </p>
        </div>
      </div>

      {/* Formulario de predicción */}
      <div className="card" style={{ marginBottom: '2rem' }}>
        <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Zap size={18} color="var(--color-primary)" /> Configurar partido
        </h3>

        <div className="grid-3" style={{ gap: '1rem', marginBottom: '1.5rem' }}>
          {/* Equipo local */}
          <div className="input-group">
            <label className="input-label">⚽ Equipo Local</label>
            <input
              id="home-team-input"
              className="input"
              list="equipos-local"
              placeholder="Ej: Argentina"
              value={homeTeam}
              onChange={e => setHomeTeam(e.target.value)}
            />
            <datalist id="equipos-local">
              {EQUIPOS_MUNDIAL.map(e => <option key={e} value={e} />)}
            </datalist>
          </div>

          {/* Equipo visitante */}
          <div className="input-group">
            <label className="input-label">✈️ Equipo Visitante</label>
            <input
              id="away-team-input"
              className="input"
              list="equipos-visitante"
              placeholder="Ej: Francia"
              value={awayTeam}
              onChange={e => setAwayTeam(e.target.value)}
            />
            <datalist id="equipos-visitante">
              {EQUIPOS_MUNDIAL.map(e => <option key={e} value={e} />)}
            </datalist>
          </div>

          {/* Fase */}
          <div className="input-group">
            <label className="input-label">🏆 Fase del Torneo</label>
            <select
              id="match-stage-select"
              className="input"
              value={matchStage}
              onChange={e => setMatchStage(e.target.value)}
            >
              {FASES.map(f => <option key={f} value={f}>{f}</option>)}
            </select>
          </div>
        </div>

        <button
          id="predict-btn"
          className="btn btn-primary"
          disabled={!canPredict || mutation.isPending}
          onClick={() => mutation.mutate()}
          style={{ width: '100%', justifyContent: 'center', padding: '0.875rem' }}
        >
          {mutation.isPending ? (
            <>
              <div className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
              Analizando partido...
            </>
          ) : (
            <>
              <Zap size={16} />
              Generar Predicción
            </>
          )}
        </button>

        {mutation.isError && (
          <div className="warning-banner" style={{ marginTop: '1rem' }}>
            <AlertTriangle size={16} className="warning-icon" />
            <span className="warning-text">
              Error al generar predicción. Verifica que el servidor esté corriendo.
            </span>
          </div>
        )}
      </div>

      {/* Resultado de predicción */}
      {prediccion && <PrediccionResultado prediccion={prediccion} />}
    </div>
  );
}

function PrediccionResultado({ prediccion }: { prediccion: Prediccion }) {
  const { match, predictions, key_factors, warnings } = prediccion;
  const { goals_home, goals_away, total_goals, result_1X2, corners, fouls, winner, exact_scores } = predictions;

  return (
    <div className="animate-fadeInUp">
      {/* Match header */}
      <div className="card" style={{
        marginBottom: '1.5rem',
        background: 'linear-gradient(135deg, rgba(59,130,246,0.08) 0%, rgba(16,185,129,0.05) 100%)',
        borderColor: 'rgba(59,130,246,0.2)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
          {match.match_stage && (
            <div style={{ marginBottom: '0.5rem' }}>
              <span className="match-stage-badge">🏆 {match.match_stage}</span>
            </div>
          )}
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '2rem', marginBottom: '1rem' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '2.5rem', marginBottom: '0.25rem' }}>🏳️</div>
              <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>{match.home_team}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Local</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '1.5rem', fontWeight: 900, color: 'var(--color-text-dim)' }}>VS</div>
              <div style={{
                fontSize: '0.8rem',
                color: 'var(--color-primary)',
                fontWeight: 700,
                background: 'rgba(59,130,246,0.1)',
                borderRadius: 6,
                padding: '2px 8px',
                marginTop: '0.25rem',
              }}>
                Campo Neutral
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '2.5rem', marginBottom: '0.25rem' }}>🏳️</div>
              <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>{match.away_team}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Visitante</div>
            </div>
          </div>

          {/* Barra 1X2 */}
          <div style={{ maxWidth: '500px', margin: '0 auto' }}>
            <ProbabilityBar
              homeProb={result_1X2.home_win_prob}
              drawProb={result_1X2.draw_prob}
              awayProb={result_1X2.away_win_prob}
              homeTeam={match.home_team}
              awayTeam={match.away_team}
            />
          </div>

          {/* Ganador predicho */}
          <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.75rem' }}>
            <Trophy size={16} color="var(--color-gold)" />
            <span style={{ fontWeight: 700, color: 'var(--color-gold)' }}>
              Ganador esperado: {winner.predicted}
            </span>
            <span style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
              ({(winner.probability * 100).toFixed(0)}%)
            </span>
            <ConfidenceBadge level={winner.confidence_label} />
          </div>
        </div>

        {/* Data quality */}
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          gap: '1rem',
          fontSize: '0.75rem',
          color: 'var(--color-text-muted)',
          borderTop: '1px solid var(--color-border)',
          paddingTop: '1rem',
        }}>
          <span>Calidad de datos: {(match.data_quality_score * 100).toFixed(0)}%</span>
          <span>•</span>
          <span>Modelo v{prediccion.model_version}</span>
          <span>•</span>
          <span>{match.league}</span>
        </div>
      </div>

      {/* Grid de predicciones */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '1.5rem' }}>

        {/* Goles */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              ⚽ Goles
            </h3>
            <ConfidenceBadge level={goals_home.confidence_label} score={goals_home.confidence} />
          </div>

          <GoalDistChart
            distribution={goals_home.distribution}
            team={match.home_team}
            expectedValue={goals_home.value}
            color="#3b82f6"
          />
          <div style={{ height: '1px', background: 'var(--color-border)', margin: '0.75rem 0' }} />
          <GoalDistChart
            distribution={goals_away.distribution}
            team={match.away_team}
            expectedValue={goals_away.value}
            color="#f59e0b"
          />

          <div style={{
            marginTop: '1rem',
            background: 'rgba(255,255,255,0.03)',
            borderRadius: 8,
            padding: '0.75rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginBottom: '0.2rem' }}>Total esperado</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 800 }}>{total_goals.value.toFixed(1)}</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginBottom: '0.2rem' }}>Over 2.5</div>
              <div style={{ fontSize: '1rem', fontWeight: 700, color: total_goals.over_2_5_prob > 0.5 ? '#10b981' : '#f59e0b' }}>
                {(total_goals.over_2_5_prob * 100).toFixed(0)}%
              </div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginBottom: '0.2rem' }}>Rango probable</div>
              <div style={{ fontSize: '1rem', fontWeight: 700 }}>{total_goals.most_likely_range}</div>
            </div>
          </div>
        </div>

        {/* Resultado 1X2 */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <h3 style={{ fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              🎯 Resultado 1X2
            </h3>
            <ConfidenceBadge level={result_1X2.confidence_label} score={result_1X2.confidence} />
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.25rem' }}>
            {[
              { label: '1', name: match.home_team.split(' ').slice(-1)[0], prob: result_1X2.home_win_prob, color: '#3b82f6', selected: result_1X2.predicted_result === 'H' },
              { label: 'X', name: 'Empate', prob: result_1X2.draw_prob, color: '#94a3b8', selected: result_1X2.predicted_result === 'D' },
              { label: '2', name: match.away_team.split(' ').slice(-1)[0], prob: result_1X2.away_win_prob, color: '#f59e0b', selected: result_1X2.predicted_result === 'A' },
            ].map(item => (
              <div
                key={item.label}
                style={{
                  flex: 1,
                  textAlign: 'center',
                  padding: '1rem 0.5rem',
                  borderRadius: 12,
                  background: item.selected ? `${item.color}20` : 'rgba(255,255,255,0.03)',
                  border: `1px solid ${item.selected ? item.color + '40' : 'var(--color-border)'}`,
                  transition: 'all 0.3s ease',
                }}
              >
                <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', marginBottom: '0.25rem' }}>{item.name}</div>
                <div style={{ fontSize: '2rem', fontWeight: 900, color: item.selected ? item.color : 'var(--color-text)', lineHeight: 1 }}>
                  {(item.prob * 100).toFixed(0)}%
                </div>
                <div style={{
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  color: item.color,
                  background: `${item.color}20`,
                  borderRadius: 4,
                  padding: '2px 6px',
                  display: 'inline-block',
                  marginTop: '0.4rem',
                }}>
                  {item.label}
                </div>
                {item.selected && <div style={{ fontSize: '0.65rem', color: item.color, marginTop: '0.25rem' }}>✓ Predicho</div>}
              </div>
            ))}
          </div>
        </div>

        {/* Marcadores Exactos */}
        {exact_scores && exact_scores.length > 0 && (
          <div className="card" style={{ gridColumn: '1 / -1' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 style={{ fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                📋 Resultados Más Probables
              </h3>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '1rem' }}>
              {exact_scores.map((score, index) => {
                const isTop = index === 0;
                return (
                  <div key={`${score.home}-${score.away}`} style={{
                    background: isTop ? 'rgba(16,185,129,0.1)' : 'rgba(255,255,255,0.03)',
                    border: `1px solid ${isTop ? 'rgba(16,185,129,0.3)' : 'var(--color-border)'}`,
                    borderRadius: 12,
                    padding: '1rem',
                    textAlign: 'center',
                    transition: 'transform 0.2s ease',
                  }}>
                    <div style={{ fontSize: '1.5rem', fontWeight: 900, letterSpacing: '2px', marginBottom: '0.25rem' }}>
                      {score.home} - {score.away}
                    </div>
                    <div style={{
                      fontSize: '1.1rem', 
                      fontWeight: 700, 
                      color: isTop ? '#10b981' : 'var(--color-text)',
                    }}>
                      {(score.prob * 100).toFixed(1)}%
                    </div>
                    {isTop && (
                      <div style={{ fontSize: '0.65rem', color: '#10b981', marginTop: '0.5rem', fontWeight: 700, textTransform: 'uppercase' }}>
                        Favorito
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Corners */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              📐 Corners
            </h3>
            <ConfidenceBadge level={corners.confidence_label} score={corners.confidence} />
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-around', marginBottom: '1rem' }}>
            <MetricCircle value={corners.value.toFixed(1)} label="Total" color="var(--color-primary)" />
            <MetricCircle value={corners.home_corners.toFixed(1)} label={match.home_team.split(' ')[0]} color="#60a5fa" />
            <MetricCircle value={corners.away_corners.toFixed(1)} label={match.away_team.split(' ')[0]} color="#a78bfa" />
          </div>

          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <OverUnderChip label="Over 9.5" prob={corners.over_9_5_prob} />
            <OverUnderChip label="Over 11.5" prob={corners.over_11_5_prob} />
          </div>
        </div>

        {/* Faltas */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              🟨 Faltas
            </h3>
            <ConfidenceBadge level={fouls.confidence_label} score={fouls.confidence} />
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-around', marginBottom: '1rem' }}>
            <MetricCircle value={fouls.value.toFixed(1)} label="Total" color="var(--color-warning)" />
            <MetricCircle value={fouls.home_fouls.toFixed(1)} label={match.home_team.split(' ')[0]} color="#fbbf24" />
            <MetricCircle value={fouls.away_fouls.toFixed(1)} label={match.away_team.split(' ')[0]} color="#f87171" />
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <OverUnderChip label="Over 20.5" prob={fouls.over_20_5_prob} />
            <div style={{
              fontSize: '0.75rem',
              padding: '0.35rem 0.75rem',
              borderRadius: 20,
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid var(--color-border)',
              color: 'var(--color-text-muted)',
            }}>
              🧑‍⚖️ Impacto árbitro: <strong style={{ color: 'var(--color-text)' }}>{fouls.referee_impact}</strong>
            </div>
          </div>
        </div>
      </div>

      {/* Key factors */}
      {key_factors.length > 0 && (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <h3 style={{ fontSize: '1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <TrendingUp size={16} color="var(--color-secondary)" />
            Factores clave
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {key_factors.map((factor, i) => (
              <div key={i} style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.75rem',
                padding: '0.65rem 0.875rem',
                background: 'rgba(16,185,129,0.06)',
                borderRadius: 8,
                border: '1px solid rgba(16,185,129,0.15)',
              }}>
                <span style={{ color: 'var(--color-secondary)', flexShrink: 0, marginTop: '1px' }}>✓</span>
                <span style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>{factor}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Warnings */}
      {warnings.length > 0 && (
        <div>
          {warnings.map((warning, i) => (
            <div key={i} className="warning-banner">
              <AlertTriangle size={14} className="warning-icon" />
              <span className="warning-text">{warning}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MetricCircle({ value, label, color }: { value: string; label: string; color: string }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{
        width: 60,
        height: 60,
        borderRadius: '50%',
        border: `2px solid ${color}40`,
        background: `${color}10`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontWeight: 800,
        fontSize: '1.1rem',
        color,
        margin: '0 auto 0.4rem',
      }}>
        {value}
      </div>
      <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>{label}</div>
    </div>
  );
}

function OverUnderChip({ label, prob }: { label: string; prob: number }) {
  const isHigh = prob >= 0.55;
  const color = isHigh ? '#10b981' : '#f59e0b';
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '0.4rem',
      padding: '0.35rem 0.75rem',
      borderRadius: 20,
      background: `${color}10`,
      border: `1px solid ${color}30`,
      fontSize: '0.75rem',
      fontWeight: 600,
    }}>
      <span style={{ color: 'var(--color-text-muted)' }}>{label}</span>
      <span style={{ color, fontWeight: 800 }}>{(prob * 100).toFixed(0)}%</span>
    </div>
  );
}
