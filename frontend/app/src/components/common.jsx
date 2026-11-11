import { Card, Tag } from 'antd';
import { colors } from '../theme';

const nf = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const nf0 = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 });

export const fmtH = (v, { sign = false } = {}) => {
  if (v == null || Number.isNaN(v)) return '—';
  const s = nf.format(Math.abs(v) < 0.05 ? 0 : v);
  return sign && v > 0.05 ? `+${s}` : s;
};
export const fmtN = (v) => (v == null ? '—' : nf0.format(v));
export const fmtPct = (v) => (v == null ? '—' : `${v > 0 ? '+' : ''}${Math.round(v * 100)}%`);

export function PageHead({ title, sub, extra }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {sub && <div className="sub">{sub}</div>}
      </div>
      {extra && <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>{extra}</div>}
    </div>
  );
}

export function StatusTag({ status }) {
  const s = colors.status[status] ?? colors.status.not_started;
  return (
    <Tag bordered={false} style={{ background: s.bg, color: s.fg, fontWeight: 500, marginInlineEnd: 0 }}>
      {s.label}
    </Tag>
  );
}

export function Kpi({ label, value, unit, hint, tone, highlight = false }) {
  const color = tone === 'fact' ? colors.factText : tone === 'plan' ? colors.planText : colors.text;
  return (
    <Card size="small" style={{ height: '100%', ...(highlight ? { background: colors.factSoft, borderColor: '#F1D3B4' } : null) }}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value" style={{ color }}>
        {value}
        {unit && <span style={{ fontSize: 15, fontWeight: 400, color: colors.muted }}> {unit}</span>}
      </div>
      {hint && <div className="kpi-hint">{hint}</div>}
    </Card>
  );
}

export function Deviation({ value, unit = 'ч' }) {
  if (value == null) return <span className="muted">—</span>;
  const over = value > 0.05;
  return (
    <span className="num" style={{ color: over ? colors.factText : colors.muted, fontWeight: over ? 600 : 400 }}>
      {fmtH(value, { sign: true })} {unit}
    </span>
  );
}

export function LegendDot({ color, children }) {
  return (
    <span style={{ marginRight: 16, fontSize: 14, whiteSpace: 'nowrap' }}>
      <span className="legend-dot" style={{ background: color }} />
      {children}
    </span>
  );
}
