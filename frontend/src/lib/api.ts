// lib/api.ts — Cliente Axios para la API
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

// ── Tipos ────────────────────────────────────────────────

export interface Distribucion {
  '0': number;
  '1': number;
  '2': number;
  '3+': number;
}

export interface PrediccionGoles {
  value: number;
  most_likely: number;
  distribution: Distribucion;
  confidence: number;
  confidence_label: 'alto' | 'medio' | 'bajo';
}

export interface PrediccionGolesTotal {
  value: number;
  over_2_5_prob: number;
  under_2_5_prob: number;
  most_likely_range: string;
  confidence: number;
  confidence_label: 'alto' | 'medio' | 'bajo';
}

export interface PrediccionResultado {
  home_win_prob: number;
  draw_prob: number;
  away_win_prob: number;
  predicted_result: 'H' | 'D' | 'A';
  confidence: number;
  confidence_label: 'alto' | 'medio' | 'bajo';
}

export interface PrediccionGanador {
  predicted: string;
  probability: number;
  confidence_label: 'alto' | 'medio' | 'bajo';
  va_a_penales_prob?: number;
}

export interface PrediccionCorners {
  value: number;
  home_corners: number;
  away_corners: number;
  over_9_5_prob: number;
  over_11_5_prob: number;
  confidence: number;
  confidence_label: 'alto' | 'medio' | 'bajo';
}

export interface PrediccionFaltas {
  value: number;
  home_fouls: number;
  away_fouls: number;
  over_20_5_prob: number;
  referee_impact: string;
  confidence: number;
  confidence_label: 'alto' | 'medio' | 'bajo';
}

export interface PrediccionExactScore {
  home: number;
  away: number;
  prob: number;
}

export interface Prediccion {
  match: {
    home_team: string;
    away_team: string;
    league: string;
    date: string;
    match_stage?: string;
    data_quality_score: number;
  };
  predictions: {
    goals_home: PrediccionGoles;
    goals_away: PrediccionGoles;
    total_goals: PrediccionGolesTotal;
    result_1X2: PrediccionResultado;
    winner: PrediccionGanador;
    corners: PrediccionCorners;
    fouls: PrediccionFaltas;
    exact_scores?: PrediccionExactScore[];
  };
  key_factors: string[];
  warnings: string[];
  generated_at: string;
  model_version: string;
}

export interface Partido {
  match_id: number;
  date: string;
  season: string;
  match_stage?: string;
  league: string;
  home_team: string;
  home_team_id: number;
  away_team: string;
  away_team_id: number;
  home_goals?: number;
  away_goals?: number;
  result?: string;
  match_importance: number;
  is_completed: boolean;
  has_prediction: boolean;
}

export interface Equipo {
  team_id: number;
  name: string;
  short_name?: string;
  country?: string;
  elo_rating: number;
  last5_results?: string;
  streak_type?: string;
  streak_length?: number;
}

// ── Funciones de API ─────────────────────────────────────

export const predecirPartido = async (
  homeTeam: string,
  awayTeam: string,
  league = 'FIFA World Cup',
  matchStage?: string,
  isNeutral = false
): Promise<Prediccion> => {
  const { data } = await api.post('/predict', {
    home_team_name: homeTeam,
    away_team_name: awayTeam,
    league_name: league,
    match_stage: matchStage,
    is_neutral: isNeutral,
  });
  return data;
};

export const obtenerPartidos = async (completados = false, limite = 20, liga_id?: number): Promise<Partido[]> => {
  const { data } = await api.get('/matches', { params: { completados, limite, liga_id } });
  return data;
};

export const obtenerEquipos = async (): Promise<Equipo[]> => {
  const { data } = await api.get('/teams');
  return data;
};

export const obtenerEquipo = async (teamId: number) => {
  const { data } = await api.get(`/teams/${teamId}`);
  return data;
};

export const obtenerPredicciones = async (limite = 20) => {
  const { data } = await api.get('/predictions', { params: { limite } });
  return data;
};

export const healthCheck = async () => {
  const { data } = await api.get('/health');
  return data;
};

export const obtenerStats = async () => {
  const { data } = await api.get('/stats');
  return data;
};
