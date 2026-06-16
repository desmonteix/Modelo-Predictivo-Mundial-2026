// components/GoalDistChart.tsx — Distribución de probabilidad de goles
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import type { Distribucion } from '../lib/api';

interface Props {
  distribution: Distribucion;
  team: string;
  expectedValue: number;
  color?: string;
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div style={{
        background: 'var(--color-bg-card)',
        border: '1px solid var(--color-border)',
        borderRadius: '8px',
        padding: '8px 12px',
        fontSize: '0.8rem',
      }}>
        <p style={{ color: 'var(--color-text-muted)' }}>{label} gol{label !== '1' ? 'es' : ''}</p>
        <p style={{ color: 'var(--color-text)', fontWeight: 700 }}>
          {(payload[0].value * 100).toFixed(1)}%
        </p>
      </div>
    );
  }
  return null;
};

export function GoalDistChart({ distribution, team, expectedValue, color = '#3b82f6' }: Props) {
  const data = [
    { label: '0', value: distribution['0'] },
    { label: '1', value: distribution['1'] },
    { label: '2', value: distribution['2'] },
    { label: '3+', value: distribution['3+'] },
  ];

  const maxVal = Math.max(...data.map(d => d.value));

  return (
    <div style={{ padding: '0.5rem 0' }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '0.5rem',
      }}>
        <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', fontWeight: 500 }}>
          {team}
        </span>
        <span style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--color-text)' }}>
          {expectedValue.toFixed(1)} <span style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', fontWeight: 400 }}>esperados</span>
        </span>
      </div>

      <ResponsiveContainer width="100%" height={90}>
        <BarChart data={data} margin={{ top: 4, right: 0, left: -20, bottom: 0 }}>
          <XAxis
            dataKey="label"
            tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis hide />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {data.map((entry, index) => (
              <Cell
                key={index}
                fill={entry.value === maxVal ? color : `${color}55`}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
