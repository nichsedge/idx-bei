import React, { useEffect, useMemo, useState } from 'react';
import { TrendingUp, Loader2, AlertTriangle, Info, ArrowUpDown } from 'lucide-react';
import type { MomentumBoard, MomentumRow } from '../types';
import { fetchMomentumBoard } from '../services/api';

interface MomentumTabProps {
  onSelectStock: (ticker: string) => void;
}

const panel: React.CSSProperties = {
  background: 'rgba(15, 23, 42, 0.65)',
  backdropFilter: 'blur(16px)',
  border: '1px solid rgba(255, 255, 255, 0.08)',
  borderRadius: '16px',
  padding: '1.25rem',
};

type SortKey = 'score' | 'r1M' | 'r3M' | 'r6M' | 'r12M' | 'xs3M' | 'from_high' | 'value_20_60' | 'avg_value_20d' | 'ref';

const pct = (x: number | null | undefined, digits = 0) =>
  x == null ? '—' : `${x >= 0 ? '+' : ''}${(x * 100).toFixed(digits)}%`;
const tone = (x: number | null | undefined) =>
  x == null ? 'var(--text-secondary)' : x > 0.005 ? '#34d399' : x < -0.005 ? '#f87171' : 'var(--text-secondary)';
const scoreColor = (s: number) => (s >= 75 ? '#34d399' : s >= 50 ? '#facc15' : s >= 25 ? '#fb923c' : '#f87171');

export const MomentumTab: React.FC<MomentumTabProps> = ({ onSelectStock }) => {
  const [board, setBoard] = useState<MomentumBoard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [groupKey, setGroupKey] = useState('deals');
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortDesc, setSortDesc] = useState(true);
  const [query, setQuery] = useState('');

  useEffect(() => {
    fetchMomentumBoard(30)
      .then((b) => {
        setBoard(b);
        if (b.groups.length && !b.groups.some((g) => g.key === 'deals' && g.rows.length)) setGroupKey(b.groups[0].key);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const group = board?.groups.find((g) => g.key === groupKey) ?? board?.groups[0];
  const refLabel = groupKey === 'deals' ? 'Deal BD' : 'Screen';

  const rows = useMemo(() => {
    const q = query.trim().toUpperCase();
    const val = (r: MomentumRow): number => {
      const v = sortKey === 'ref' ? (r.deal_score ?? r.screen_score) : r[sortKey];
      return v == null ? Number.NEGATIVE_INFINITY : v;
    };
    return (group?.rows ?? [])
      .filter((r) => !q || r.code.includes(q) || (r.context ?? '').toUpperCase().includes(q))
      .sort((a, b) => (sortDesc ? val(b) - val(a) : val(a) - val(b)));
  }, [group, sortKey, sortDesc, query]);

  const sortBy = (key: SortKey) => {
    if (key === sortKey) setSortDesc(!sortDesc);
    else {
      setSortKey(key);
      setSortDesc(true);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-secondary)' }}>
        <Loader2 size={32} className="spinning" style={{ color: '#38bdf8' }} />
        <p>Ranking price momentum…</p>
      </div>
    );
  }
  if (error || !board || board.error || !board.market) {
    return (
      <div className="error-banner">
        <AlertTriangle size={40} />
        <h2>No momentum data</h2>
        <p>{error ?? board?.error ?? 'Price data is missing.'}</p>
        <code>uv run idx backfill --start 20251001 --end 20261023 --type stock</code>
      </div>
    );
  }

  const mkt = board.market;
  const th = (label: string, key?: SortKey, align: 'left' | 'right' = 'right') => (
    <th
      onClick={key ? () => sortBy(key) : undefined}
      style={{ textAlign: align, cursor: key ? 'pointer' : 'default', whiteSpace: 'nowrap', color: key === sortKey ? '#38bdf8' : undefined }}
      title={key ? 'Sort' : undefined}
    >
      {label}
      {key && <ArrowUpDown size={11} style={{ marginLeft: 3, opacity: key === sortKey ? 1 : 0.35 }} />}
    </th>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <div style={{ ...panel, padding: '1.5rem', display: 'flex', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
            <TrendingUp size={28} style={{ color: '#34d399' }} />
            <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 700 }}>Momentum Rank Board</h2>
          </div>
          <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Deal and screen candidates ranked by price momentum against all {mkt.universe} IDX stocks.
          </p>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, auto)', gap: '0.25rem 1.25rem', fontSize: '0.8rem', alignItems: 'baseline' }}>
          <span style={{ color: 'var(--text-secondary)' }}>As of</span>
          <span className="numeric" style={{ gridColumn: 'span 3' }}>{mkt.as_of} ({mkt.trading_days} trading days since {mkt.first_date})</span>
          {(['1M', '3M', '6M', '12M'] as const).map((k) => (
            <React.Fragment key={k}>
              <span style={{ color: 'var(--text-secondary)' }}>IHSG {k}</span>
              <span className="numeric" style={{ color: tone(mkt.ihsg[k]) }}>{pct(mkt.ihsg[k], 1)}</span>
            </React.Fragment>
          ))}
        </div>
      </div>

      <div style={{ ...panel, display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap', padding: '0.9rem 1.25rem' }}>
        {board.groups.map((g) => (
          <button
            key={g.key}
            onClick={() => setGroupKey(g.key)}
            className="filter-btn"
            style={{
              padding: '0.45rem 0.9rem',
              cursor: 'pointer',
              borderRadius: '10px',
              border: g.key === group?.key ? '1px solid rgba(52, 211, 153, 0.5)' : '1px solid rgba(255,255,255,0.1)',
              background: g.key === group?.key ? 'rgba(52, 211, 153, 0.12)' : 'transparent',
              color: g.key === group?.key ? '#34d399' : '#cbd5e1',
              fontWeight: 600,
            }}
          >
            {g.title} ({g.rows.length})
          </button>
        ))}
        <input
          className="form-control"
          style={{ maxWidth: '220px', paddingLeft: '1rem', marginLeft: 'auto' }}
          placeholder="Ticker or signal…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <div style={{ ...panel, padding: 0, overflow: 'hidden' }}>
        <div className="table-container" style={{ marginTop: 0, maxHeight: '720px', overflowY: 'auto' }}>
          <table style={{ fontSize: '0.82rem' }}>
            <thead>
              <tr>
                {th('#', undefined, 'left')}
                {th('Ticker', undefined, 'left')}
                {th('Score', 'score')}
                {th('Mkt rank')}
                {th('Close')}
                {th('1M', 'r1M')}
                {th('3M', 'r3M')}
                {th('6M', 'r6M')}
                {th('12M', 'r12M')}
                {th('vs IHSG 3M', 'xs3M')}
                {th('From high', 'from_high')}
                {th('MA20/50')}
                {th('Value 20/60d', 'value_20_60')}
                {th('Avg value (Rp bn)', 'avg_value_20d')}
                {th(refLabel, 'ref')}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={r.code}>
                  <td className="numeric">{i + 1}</td>
                  <td>
                    <button
                      onClick={() => onSelectStock(r.code)}
                      className="ticker-badge"
                      style={{ cursor: 'pointer', border: 'none' }}
                      title="Open in Stock Terminal"
                    >
                      {r.code}
                    </button>
                    {r.last_adjustment && (
                      <span
                        title={`Prices before the ex-date ${r.last_adjustment.date} are adjusted by ${r.last_adjustment.factor} (split, reverse split or rights issue, from IDX's reference price).`}
                        style={{ marginLeft: 6, color: 'var(--text-secondary)', fontSize: '0.7rem', fontWeight: 700 }}
                      >
                        ADJ
                      </span>
                    )}
                    {r.adj_warning && (
                      <span
                        title="A one-day move beyond 35% (IDX auto-rejection limit) that the corporate-action adjustment does not explain. Returns may be distorted."
                        style={{ marginLeft: 6, color: '#fb923c', fontSize: '0.7rem', fontWeight: 700 }}
                      >
                        ADJ?
                      </span>
                    )}
                    {!r.no_price && !r.avg_value_20d && (
                      <span
                        title="No trading value in the last 20 days (suspended or illiquid); returns may be stale."
                        style={{ marginLeft: 6, color: '#f87171', fontSize: '0.7rem', fontWeight: 700 }}
                      >
                        NO TRADES 20D
                      </span>
                    )}
                    {(r.context || r.last_signal) && (
                      <div
                        title={r.context}
                        style={{
                          fontSize: '0.68rem',
                          color: 'var(--text-secondary)',
                          marginTop: 3,
                          maxWidth: 230,
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {r.context}
                        {r.last_signal && ` · last ${r.last_signal}`}
                      </div>
                    )}
                  </td>
                  {r.no_price ? (
                    <td colSpan={12} style={{ color: 'var(--text-secondary)' }}>No recent price (suspended or not trading)</td>
                  ) : (
                    <>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 6 }}>
                          <div style={{ width: 46, height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.08)' }}>
                            <div style={{ width: `${r.score}%`, height: '100%', borderRadius: 3, background: scoreColor(r.score ?? 0) }} />
                          </div>
                          <span className="numeric" style={{ fontWeight: 700, color: scoreColor(r.score ?? 0) }}>{r.score?.toFixed(0)}</span>
                        </div>
                      </td>
                      <td className="numeric" style={{ textAlign: 'right', color: 'var(--text-secondary)' }}>
                        {r.market_rank}/{mkt.universe}
                      </td>
                      <td className="numeric" style={{ textAlign: 'right' }}>{r.close?.toLocaleString('id-ID')}</td>
                      {(['r1M', 'r3M', 'r6M', 'r12M', 'xs3M', 'from_high'] as const).map((k) => (
                        <td key={k} className="numeric" style={{ textAlign: 'right', color: tone(r[k]) }}>{pct(r[k])}</td>
                      ))}
                      <td style={{ textAlign: 'right' }} title="Close above 20-day / 50-day average">
                        <span style={{ color: r.above_ma20 ? '#34d399' : '#f87171' }}>{r.above_ma20 ? '▲' : '▼'}</span>
                        <span style={{ color: r.above_ma50 ? '#34d399' : '#f87171', marginLeft: 2 }}>{r.above_ma50 ? '▲' : '▼'}</span>
                      </td>
                      <td className="numeric" style={{ textAlign: 'right', color: (r.value_20_60 ?? 0) >= 1.5 ? '#38bdf8' : undefined }}>
                        {r.value_20_60 == null ? '—' : `${r.value_20_60.toFixed(1)}×`}
                      </td>
                      <td className="numeric" style={{ textAlign: 'right' }}>{((r.avg_value_20d ?? 0) / 1e9).toFixed(1)}</td>
                    </>
                  )}
                  <td className="numeric" style={{ textAlign: 'right' }}>{r.deal_score ?? r.screen_score ?? '—'}</td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={15} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>No tickers in this group.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
        <Info size={14} style={{ flexShrink: 0, marginTop: '2px' }} />
        <span>
          Score = percentile among all IDX stocks: 20% 1M + 40% 3M + 40% 6M return. Closes are adjusted for splits and rights issues using IDX's
          ex-date reference price (ADJ shows the latest ex-date); ADJ? marks a one-day move beyond 35% that the adjustment does not explain. Value 20/60d above 1.5× means rising trading interest. Screen candidates come from the latest
          `idx screen` run{board.screen_period ? ` (${board.screen_period})` : ''}. Momentum describes past prices, not a forecast or advice.
        </span>
      </div>
    </div>
  );
};
