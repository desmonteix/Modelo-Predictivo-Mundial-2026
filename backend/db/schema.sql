-- =============================================================
-- PREDICTOR FÚTBOL — Schema PostgreSQL v1.0
-- Módulo 2: Arquitectura de base de datos
-- =============================================================

-- Extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- búsqueda de texto

-- =============================================================
-- TABLA: leagues — Ligas y competiciones
-- =============================================================
CREATE TABLE IF NOT EXISTS leagues (
    league_id       SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    country         VARCHAR(100),
    competition_type VARCHAR(50) DEFAULT 'league',  -- league, cup, international
    tier            INTEGER DEFAULT 1,
    external_id     VARCHAR(50),  -- ID en football-data.org
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_leagues_external_id ON leagues(external_id);

-- =============================================================
-- TABLA: teams — Equipos
-- =============================================================
CREATE TABLE IF NOT EXISTS teams (
    team_id         SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    short_name      VARCHAR(50),
    country         VARCHAR(100),
    stadium         VARCHAR(100),
    stadium_capacity INTEGER,
    external_id     VARCHAR(50) UNIQUE,  -- ID en fuente externa
    aliases         TEXT[],       -- nombres alternativos para normalización
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_teams_name ON teams USING gin(name gin_trgm_ops);
CREATE INDEX idx_teams_external_id ON teams(external_id);

-- =============================================================
-- TABLA: referees — Árbitros
-- =============================================================
CREATE TABLE IF NOT EXISTS referees (
    referee_id          SERIAL PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,
    country             VARCHAR(100),
    avg_fouls_per_match FLOAT DEFAULT 0.0,
    avg_yellows         FLOAT DEFAULT 0.0,
    avg_reds            FLOAT DEFAULT 0.0,
    strictness_score    FLOAT DEFAULT 5.0 CHECK (strictness_score >= 0 AND strictness_score <= 10),
    matches_officiated  INTEGER DEFAULT 0,
    external_id         VARCHAR(50),
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================
-- TABLA: matches — Partidos
-- =============================================================
CREATE TABLE IF NOT EXISTS matches (
    match_id            SERIAL PRIMARY KEY,
    external_id         VARCHAR(50) UNIQUE,  -- ID en fuente externa
    date                TIMESTAMP WITH TIME ZONE NOT NULL,
    season              VARCHAR(20) NOT NULL,  -- ej: "2022-23", "2026"
    league_id           INTEGER REFERENCES leagues(league_id),
    home_team_id        INTEGER REFERENCES teams(team_id),
    away_team_id        INTEGER REFERENCES teams(team_id),
    
    -- Resultado
    home_goals          INTEGER,
    away_goals          INTEGER,
    home_goals_ht       INTEGER,   -- half time
    away_goals_ht       INTEGER,
    result              CHAR(1) CHECK (result IN ('H', 'D', 'A')),  -- Home/Draw/Away
    
    -- Estadísticas en crudo
    home_corners        INTEGER,
    away_corners        INTEGER,
    home_fouls          INTEGER,
    away_fouls          INTEGER,
    home_yellow_cards   INTEGER,
    away_yellow_cards   INTEGER,
    home_red_cards      INTEGER,
    away_red_cards      INTEGER,
    home_shots          INTEGER,
    away_shots          INTEGER,
    home_shots_on_target INTEGER,
    away_shots_on_target INTEGER,
    
    -- Contexto
    stadium             VARCHAR(100),
    attendance          INTEGER,
    referee_id          INTEGER REFERENCES referees(referee_id),
    weather_conditions  JSONB,   -- {"condition": "rain", "temp_c": 12, "wind_kmh": 20}
    match_stage         VARCHAR(50),  -- "Group Stage", "Round of 16", "Final", etc.
    match_importance    FLOAT DEFAULT 0.5 CHECK (match_importance >= 0 AND match_importance <= 1),
    is_neutral_venue    BOOLEAN DEFAULT FALSE,
    
    -- Pipeline
    importance_weight   FLOAT DEFAULT 1.0,  -- asignado por el pipeline temporal
    data_source         VARCHAR(50),
    data_quality_score  FLOAT DEFAULT 1.0,
    is_completed        BOOLEAN DEFAULT FALSE,
    
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_matches_date ON matches(date);
CREATE INDEX idx_matches_league_season ON matches(league_id, season);
CREATE INDEX idx_matches_home_team ON matches(home_team_id, date);
CREATE INDEX idx_matches_away_team ON matches(away_team_id, date);
CREATE INDEX idx_matches_teams ON matches(home_team_id, away_team_id, date);

-- =============================================================
-- TABLA: team_stats_per_match — Estadísticas avanzadas por partido
-- =============================================================
CREATE TABLE IF NOT EXISTS team_stats_per_match (
    id              SERIAL PRIMARY KEY,
    match_id        INTEGER REFERENCES matches(match_id) ON DELETE CASCADE,
    team_id         INTEGER REFERENCES teams(team_id),
    is_home         BOOLEAN NOT NULL,
    
    -- xG y métricas ofensivas
    xg              FLOAT,   -- Expected Goals
    xga             FLOAT,   -- xG Against (concedido)
    shots           INTEGER,
    shots_on_target INTEGER,
    
    -- Dominio
    possession      FLOAT,   -- porcentaje 0-100
    passes_completed INTEGER,
    pass_accuracy   FLOAT,
    
    -- Pressing
    pressing_intensity  FLOAT,  -- PPDA (Passes Allowed Per Defensive Action) — menor = más presión
    
    -- Disciplina (desde perspectiva de este equipo)
    yellow_cards    INTEGER DEFAULT 0,
    red_cards       INTEGER DEFAULT 0,
    offsides        INTEGER DEFAULT 0,
    fouls_committed INTEGER DEFAULT 0,
    fouls_received  INTEGER DEFAULT 0,
    
    -- Corners
    corners_for     INTEGER DEFAULT 0,
    corners_against INTEGER DEFAULT 0,
    
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(match_id, team_id)
);

CREATE INDEX idx_team_stats_match ON team_stats_per_match(match_id);
CREATE INDEX idx_team_stats_team ON team_stats_per_match(team_id);

-- =============================================================
-- TABLA: player_stats_per_match — Estadísticas individuales (Jugadores)
-- =============================================================
CREATE TABLE IF NOT EXISTS player_stats_per_match (
    id              SERIAL PRIMARY KEY,
    match_id        INTEGER REFERENCES matches(match_id) ON DELETE CASCADE,
    team_id         INTEGER REFERENCES teams(team_id),
    player_id       INTEGER, -- ID externo del jugador en API-Football
    player_name     VARCHAR(100),
    position        VARCHAR(10),
    rating          FLOAT,
    minutes_played  INTEGER,
    goals           INTEGER DEFAULT 0,
    assists         INTEGER DEFAULT 0,
    shots           INTEGER DEFAULT 0,
    passes_accuracy FLOAT,
    tackles         INTEGER DEFAULT 0,
    interceptions   INTEGER DEFAULT 0,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(match_id, player_id)
);

CREATE INDEX idx_player_stats_match ON player_stats_per_match(match_id);
CREATE INDEX idx_player_stats_player ON player_stats_per_match(player_id);

-- =============================================================
-- TABLA: team_form — Forma reciente de cada equipo
-- =============================================================
CREATE TABLE IF NOT EXISTS team_form (
    id                      SERIAL PRIMARY KEY,
    team_id                 INTEGER REFERENCES teams(team_id),
    as_of_date              DATE NOT NULL,
    league_id               INTEGER REFERENCES leagues(league_id),
    season                  VARCHAR(20),
    
    -- Últimos 5 partidos
    last5_results           CHAR(5),  -- ej: "WWDLW" (W=win, D=draw, L=loss)
    last5_points            INTEGER,  -- puntos de los últimos 5 (máx 15)
    last5_goals_scored      FLOAT,
    last5_goals_conceded    FLOAT,
    last5_xg                FLOAT,
    last5_xga               FLOAT,
    last5_corners           FLOAT,
    last5_clean_sheets      INTEGER,
    
    -- Racha
    streak_type             CHAR(1) CHECK (streak_type IN ('W', 'D', 'L', 'U')),  -- U=unbeaten
    streak_length           INTEGER DEFAULT 0,
    
    -- ELO en este momento
    elo_rating              FLOAT DEFAULT 1500.0,
    
    -- Contexto local/visitante
    home_win_rate           FLOAT,
    away_win_rate           FLOAT,
    home_goals_scored_avg   FLOAT,
    away_goals_scored_avg   FLOAT,
    
    created_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(team_id, as_of_date, league_id)
);

CREATE INDEX idx_team_form_team_date ON team_form(team_id, as_of_date DESC);

-- =============================================================
-- TABLA: head_to_head — Historial directo entre equipos
-- =============================================================
CREATE TABLE IF NOT EXISTS head_to_head (
    id              SERIAL PRIMARY KEY,
    team_a_id       INTEGER REFERENCES teams(team_id),
    team_b_id       INTEGER REFERENCES teams(team_id),
    league_id       INTEGER REFERENCES leagues(league_id),  -- NULL = todos
    
    matches_played  INTEGER DEFAULT 0,
    team_a_wins     INTEGER DEFAULT 0,
    draws           INTEGER DEFAULT 0,
    team_b_wins     INTEGER DEFAULT 0,
    
    -- Promedios ponderados temporalmente
    avg_total_goals     FLOAT,
    avg_corners         FLOAT,
    avg_fouls           FLOAT,
    team_a_win_rate_home FLOAT,   -- win rate de A cuando juega local
    team_b_win_rate_home FLOAT,
    
    -- Última actualización
    last_match_date DATE,
    as_of_date      DATE NOT NULL,
    
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(team_a_id, team_b_id, as_of_date)
);

CREATE INDEX idx_h2h_teams ON head_to_head(team_a_id, team_b_id);

-- =============================================================
-- TABLA: players_availability — Disponibilidad de jugadores
-- =============================================================
CREATE TABLE IF NOT EXISTS players_availability (
    id                      SERIAL PRIMARY KEY,
    team_id                 INTEGER REFERENCES teams(team_id),
    match_id                INTEGER REFERENCES matches(match_id),
    key_players_out         JSONB DEFAULT '[]',   -- [{"name": "Messi", "impact": 0.8, "reason": "injury"}]
    injury_impact_score     FLOAT DEFAULT 0.0 CHECK (injury_impact_score >= 0 AND injury_impact_score <= 1),
    suspensions             JSONB DEFAULT '[]',
    confirmed               BOOLEAN DEFAULT FALSE,  -- si la info está confirmada
    notes                   TEXT,
    created_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(team_id, match_id)
);

-- =============================================================
-- TABLA: temporal_weights — Pesos por temporada/liga
-- =============================================================
CREATE TABLE IF NOT EXISTS temporal_weights (
    id              SERIAL PRIMARY KEY,
    season          VARCHAR(20) NOT NULL,
    league_id       INTEGER REFERENCES leagues(league_id),
    weight_factor   FLOAT NOT NULL CHECK (weight_factor >= 0 AND weight_factor <= 1),
    is_current      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(season, league_id)
);

-- =============================================================
-- TABLA: predictions — Predicciones generadas
-- =============================================================
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id       SERIAL PRIMARY KEY,
    match_id            INTEGER REFERENCES matches(match_id),
    
    -- Metadata
    generated_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    model_version       VARCHAR(50),
    data_quality_score  FLOAT,
    
    -- Predicciones de goles
    goals_home_value    FLOAT,
    goals_home_most_likely INTEGER,
    goals_home_distribution JSONB,   -- {"0": 0.18, "1": 0.32, ...}
    goals_home_confidence FLOAT,
    
    goals_away_value    FLOAT,
    goals_away_most_likely INTEGER,
    goals_away_distribution JSONB,
    goals_away_confidence FLOAT,
    
    -- Goles totales
    total_goals_value   FLOAT,
    over_2_5_prob       FLOAT,
    under_2_5_prob      FLOAT,
    total_goals_confidence FLOAT,
    
    -- Resultado 1X2
    home_win_prob       FLOAT,
    draw_prob           FLOAT,
    away_win_prob       FLOAT,
    predicted_result    CHAR(1),
    result_confidence   FLOAT,
    
    -- Corners
    corners_total       FLOAT,
    corners_home        FLOAT,
    corners_away        FLOAT,
    corners_over_9_5    FLOAT,
    corners_over_11_5   FLOAT,
    corners_confidence  FLOAT,
    
    -- Faltas
    fouls_total         FLOAT,
    fouls_home          FLOAT,
    fouls_away          FLOAT,
    fouls_over_20_5     FLOAT,
    referee_impact      VARCHAR(20),
    fouls_confidence    FLOAT,
    
    -- Factores y advertencias
    key_factors         JSONB DEFAULT '[]',
    warnings            JSONB DEFAULT '[]',
    full_output         JSONB,  -- output completo del Módulo 5
    
    -- Resultado real (para backtesting)
    actual_result       CHAR(1),
    actual_home_goals   INTEGER,
    actual_away_goals   INTEGER,
    was_correct_result  BOOLEAN,
    brier_score         FLOAT,
    
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_predictions_match ON predictions(match_id);
CREATE INDEX idx_predictions_generated ON predictions(generated_at DESC);

-- =============================================================
-- TABLA: elo_history — Histórico de ratings ELO
-- =============================================================
CREATE TABLE IF NOT EXISTS elo_history (
    id          SERIAL PRIMARY KEY,
    team_id     INTEGER REFERENCES teams(team_id),
    match_id    INTEGER REFERENCES matches(match_id),
    date        DATE NOT NULL,
    elo_before  FLOAT NOT NULL,
    elo_after   FLOAT NOT NULL,
    elo_change  FLOAT,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_elo_team_date ON elo_history(team_id, date DESC);

-- =============================================================
-- TABLA: coach_changes — Cambios de entrenador (breakpoints)
-- =============================================================
CREATE TABLE IF NOT EXISTS coach_changes (
    id              SERIAL PRIMARY KEY,
    team_id         INTEGER REFERENCES teams(team_id),
    change_date     DATE NOT NULL,
    old_coach       VARCHAR(100),
    new_coach       VARCHAR(100),
    reset_applied   BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_coach_changes_team ON coach_changes(team_id, change_date DESC);

-- =============================================================
-- DATOS INICIALES — Ligas
-- =============================================================
INSERT INTO leagues (name, country, competition_type, tier, external_id) VALUES
    ('FIFA World Cup', 'International', 'international', 1, '2000'),
    ('UEFA Champions League', 'Europe', 'cup', 1, '2001'),
    ('Premier League', 'England', 'league', 1, 'PL'),
    ('La Liga', 'Spain', 'league', 1, 'PD'),
    ('Bundesliga', 'Germany', 'league', 1, 'BL1'),
    ('Serie A', 'Italy', 'league', 1, 'SA'),
    ('Ligue 1', 'France', 'league', 1, 'FL1'),
    ('Copa America', 'South America', 'international', 1, '2152')
ON CONFLICT DO NOTHING;

-- =============================================================
-- Vista útil: próximos partidos con equipos
-- =============================================================
CREATE OR REPLACE VIEW upcoming_matches AS
SELECT 
    m.match_id,
    m.date,
    m.season,
    l.name as league_name,
    ht.name as home_team,
    at.name as away_team,
    m.match_stage,
    m.match_importance,
    m.is_completed
FROM matches m
JOIN leagues l ON m.league_id = l.league_id
JOIN teams ht ON m.home_team_id = ht.team_id
JOIN teams at ON m.away_team_id = at.team_id
WHERE m.date >= NOW()
ORDER BY m.date;

-- Vista: predicciones con resultado
CREATE OR REPLACE VIEW prediction_accuracy AS
SELECT 
    p.prediction_id,
    m.date,
    l.name as league,
    ht.name as home_team,
    at.name as away_team,
    p.predicted_result,
    p.actual_result,
    p.was_correct_result,
    p.home_win_prob,
    p.draw_prob,
    p.away_win_prob,
    p.brier_score,
    p.result_confidence
FROM predictions p
JOIN matches m ON p.match_id = m.match_id
JOIN leagues l ON m.league_id = l.league_id
JOIN teams ht ON m.home_team_id = ht.team_id
JOIN teams at ON m.away_team_id = at.team_id
WHERE p.actual_result IS NOT NULL;
