// components/ConfidenceBadge.tsx
interface Props {
  level: 'alto' | 'medio' | 'bajo';
  score?: number;
}

export function ConfidenceBadge({ level, score }: Props) {
  const dot = level === 'alto' ? '●' : level === 'medio' ? '◐' : '○';
  return (
    <span className={`confidence-badge ${level}`}>
      {dot} {level.charAt(0).toUpperCase() + level.slice(1)}
      {score !== undefined && ` ${(score * 100).toFixed(0)}%`}
    </span>
  );
}
