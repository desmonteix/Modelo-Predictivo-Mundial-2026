// components/ProbabilityBar.tsx — Barra 1X2

interface Props {
  homeProb: number;
  drawProb: number;
  awayProb: number;
  homeTeam: string;
  awayTeam: string;
}

export function ProbabilityBar({ homeProb, drawProb, awayProb, homeTeam, awayTeam }: Props) {
  return (
    <div className="prob-bar-container">
      <div className="prob-bar-labels">
        <span>{homeTeam}</span>
        <span>Empate</span>
        <span>{awayTeam}</span>
      </div>
      <div className="prob-bar">
        <div className="prob-bar-home" style={{ width: `${homeProb * 100}%` }} />
        <div className="prob-bar-draw" style={{ width: `${drawProb * 100}%` }} />
        <div className="prob-bar-away" style={{ width: `${awayProb * 100}%` }} />
      </div>
      <div className="prob-values">
        <span className="prob-home">{(homeProb * 100).toFixed(0)}%</span>
        <span className="prob-draw">{(drawProb * 100).toFixed(0)}%</span>
        <span className="prob-away">{(awayProb * 100).toFixed(0)}%</span>
      </div>
    </div>
  );
}
