"""
Router de Equipos — GET /api/v1/teams
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from db.connection import get_db

router = APIRouter()


@router.get("/teams", summary="Listar equipos")
async def listar_equipos(
    liga_id: int = None,
    db: AsyncSession = Depends(get_db),
):
    """Lista todos los equipos registrados."""
    params = {}
    where = ""
    if liga_id:
        where = "WHERE m.league_id = :liga_id"
        params["liga_id"] = liga_id

    result = await db.execute(
        text(f"""
            SELECT DISTINCT
                t.team_id, t.name, t.short_name, t.country,
                COALESCE(tf.elo_rating, 1500) as elo_rating,
                tf.last5_results, tf.streak_type, tf.streak_length
            FROM teams t
            LEFT JOIN team_form tf ON tf.team_id = t.team_id
                AND tf.as_of_date = (
                    SELECT MAX(as_of_date) FROM team_form WHERE team_id = t.team_id
                )
            ORDER BY elo_rating DESC
        """),
        params,
    )
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]


@router.get("/teams/{team_id}", summary="Detalle de equipo")
async def detalle_equipo(
    team_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Retorna estadísticas detalladas de un equipo."""
    result = await db.execute(
        text("""
            SELECT
                t.team_id, t.name, t.short_name, t.country, t.stadium,
                COALESCE(tf.elo_rating, 1500) as elo_rating,
                tf.last5_results, tf.last5_goals_scored,
                tf.last5_goals_conceded, tf.home_win_rate, tf.away_win_rate,
                tf.streak_type, tf.streak_length, tf.last5_clean_sheets
            FROM teams t
            LEFT JOIN team_form tf ON tf.team_id = t.team_id
                AND tf.as_of_date = (
                    SELECT MAX(as_of_date) FROM team_form WHERE team_id = t.team_id
                )
            WHERE t.team_id = :id
        """),
        {"id": team_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    return dict(row._mapping)


@router.get("/teams/{team_id}/h2h/{rival_id}", summary="Head-to-head entre equipos")
async def head_to_head(
    team_id: int,
    rival_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Historial directo entre dos equipos."""
    result = await db.execute(
        text("""
            SELECT
                m.match_id, m.date, m.season, m.match_stage,
                ht.name as home_team, at.name as away_team,
                m.home_goals, m.away_goals, m.result
            FROM matches m
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            WHERE (
                (m.home_team_id = :team_id AND m.away_team_id = :rival_id)
                OR
                (m.home_team_id = :rival_id AND m.away_team_id = :team_id)
            )
            AND m.is_completed = TRUE
            ORDER BY m.date DESC
            LIMIT 15
        """),
        {"team_id": team_id, "rival_id": rival_id},
    )
    rows = result.fetchall()
    partidos = [dict(row._mapping) for row in rows]

    # Calcular estadísticas H2H
    equipo_wins = sum(
        1 for p in partidos
        if (p["result"] == "H" and p["home_team"] != "unknown")
    )

    return {
        "team_id": team_id,
        "rival_id": rival_id,
        "partidos": partidos,
        "total_partidos": len(partidos),
    }
