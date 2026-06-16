// components/FormStrip.tsx — Últimas N fechas W/D/L

interface Props {
  results: string; // ej: "WWDLW"
}

const LABELS: Record<string, string> = {
  W: 'V',
  D: 'E',
  L: 'D',
};

export function FormStrip({ results }: Props) {
  if (!results) return <span style={{ color: 'var(--color-text-dim)', fontSize: '0.75rem' }}>Sin datos</span>;

  return (
    <div className="form-strip">
      {results.split('').map((char, i) => (
        <div
          key={i}
          className={`form-chip ${char}`}
          data-tooltip={char === 'W' ? 'Victoria' : char === 'D' ? 'Empate' : 'Derrota'}
        >
          {LABELS[char] ?? char}
        </div>
      ))}
    </div>
  );
}
