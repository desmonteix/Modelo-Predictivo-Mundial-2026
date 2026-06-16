"""
Router de Partidos — GET /api/v1/matches
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from db.connection import get_db

router = APIRouter()


@router.get("/matches", summary="Listar partidos")
async def listar_partidos(
    completados: bool = False,
    liga_id: int = None,
    limite: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Lista próximos o completados partidos del Mundial."""
    filtros = ["m.is_completed = :completados"]
    params = {"completados": completados, "limite": limite}

    if liga_id:
        filtros.append("m.league_id = :liga_id")
        params["liga_id"] = liga_id

    if not completados:
        filtros.append("m.date > NOW()")
        order = "ASC"
    else:
        order = "DESC"

    where = " AND ".join(filtros)

    result = await db.execute(
        text(f"""
            SELECT
                m.match_id, m.date, m.season, m.match_stage,
                l.name as league,
                ht.name as home_team, ht.team_id as home_team_id,
                at.name as away_team, at.team_id as away_team_id,
                m.home_goals, m.away_goals, m.result,
                m.match_importance, m.is_completed,
                CASE WHEN p.prediction_id IS NOT NULL THEN TRUE ELSE FALSE END as has_prediction
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            LEFT JOIN predictions p ON p.match_id = m.match_id
            WHERE {where}
            ORDER BY m.date {order}
            LIMIT :limite
        """),
        params,
    )
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]


@router.get("/matches/{match_id}", summary="Detalle de un partido")
async def detalle_partido(
    match_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Devuelve el detalle completo de un partido incluyendo estadísticas."""
    result = await db.execute(
        text("""
            SELECT
                m.*,
                l.name as league_name,
                ht.name as home_team_name,
                at.name as away_team_name,
                r.name as referee_name, r.strictness_score
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            JOIN teams ht ON m.home_team_id = ht.team_id
            JOIN teams at ON m.away_team_id = at.team_id
            LEFT JOIN referees r ON m.referee_id = r.referee_id
            WHERE m.match_id = :id
        """),
        {"id": match_id},
    )
    row = result.fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return dict(row._mapping)
