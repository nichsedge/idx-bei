import React, { useEffect, useMemo, useState } from 'react';
import { Layers, Calculator, AlertTriangle, ArrowRight, Loader2, Info } from 'lucide-react';
import type { CapitalRaise, CapitalRaiseType, CorporateActionItem, RightsIssuesResponse } from '../types';
import { fetchCorporateActions, fetchRightsIssues, fetchStockData } from '../services/api';
import {
  fmtInt,
  fmtPct,
  fmtRp,
  fmtShares,
  holderScenarios,
} from '../lib/capital';
import { TrackedRaisesPanel } from './TrackedRaisesPanel';

interface RightsIssueTabProps {
  onSelectStock: (ticker: string) => void;
}

const panel: React.CSSProperties = {
  background: 'rgba(15, 23, 42, 0.65)',
  backdropFilter: 'blur(16px)',
  border: '1px solid rgba(255, 255, 255, 0.08)',
  borderRadius: '16px',
  padding: '1.25rem',
};

const TYPE_LABEL: Record<CapitalRaiseType, string> = {
  rights_issue: 'Rights issue',
  private_placement: 'Private placement',
};

const ACTION_LABEL: Record<string, string> = {
  hmetd: 'Rights issue (HMETD)',
  tanpaHmetd: 'Private placement',
  PrivatePlacement: 'Private placement',
  waran: 'Warrant exercise',
  stockSplit: 'Stock split',
  reverseStock: 'Reverse split',
  sahamBonus: 'Bonus shares',
  dividenSaham: 'Stock dividend',
  gabungUsaha: 'Merger',
  kurangModal: 'Capital reduction',
  konversiSaham: 'Conversion',
  partialDelisting: 'Partial delisting',
  ipo: 'IPO',
  companyListing: 'Company listing',
  BuybackSaham: 'Buyback',
};

const PERIODS: { id: string; label: string; years: number | null }[] = [
  { id: '1y', label: 'Last 12 months', years: 1 },
  { id: '3y', label: 'Last 3 years', years: 3 },
  { id: '5y', label: 'Last 5 years', years: 5 },
  { id: 'all', label: 'All history', years: null },
];

const flagColor = (flag: string) =>
  flag === 'LARGE' ? '#ef4444' : flag === 'SERIAL' ? '#f59e0b' : '#a78bfa';

function median(values: number[]): number {
  if (values.length === 0) return 0;
  const s = [...values].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

export const RightsIssueTab: React.FC<RightsIssueTabProps> = ({ onSelectStock }) => {
  const [data, setData] = useState<RightsIssuesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tickerHistory, setTickerHistory] = useState<CorporateActionItem[]>([]);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<'all' | CapitalRaiseType>('all');
  const [period, setPeriod] = useState('3y');
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [selected, setSelected] = useState<CapitalRaise | null>(null);

  useEffect(() => {
    fetchRightsIssues()
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const raises = data?.raises ?? [];
  const flagLabels = data?.flag_labels ?? {};

  const filtered = useMemo(() => {
    const years = PERIODS.find((p) => p.id === period)?.years ?? null;
    const cutoff = years ? new Date(Date.now() - years * 365.25 * 86400000).toISOString().slice(0, 10) : '';
    const q = search.trim().toUpperCase();
    return raises.filter(
      (r) =>
        (typeFilter === 'all' || r.type === typeFilter) &&
        (!cutoff || r.listing_date >= cutoff) &&
        (!q || r.ticker.includes(q)) &&
        (!flaggedOnly || r.flags.length > 0),
    );
  }, [raises, search, typeFilter, period, flaggedOnly]);

  useEffect(() => {
    if (!selected && filtered.length > 0) setSelected(filtered[0]);
  }, [filtered, selected]);

  const kpis = useMemo(() => {
    const cutoff = new Date(Date.now() - 365.25 * 86400000).toISOString().slice(0, 10);
    const lastYear = raises.filter((r) => r.listing_date >= cutoff);
    const rights = lastYear.filter((r) => r.type === 'rights_issue');
    return {
      rights12m: rights.length,
      placements12m: lastYear.length - rights.length,
      medianDilution: median(rights.map((r) => r.dilution_pct)),
      large12m: lastYear.filter((r) => r.flags.includes('LARGE')).length,
      serialTickers: new Set(lastYear.filter((r) => r.flags.includes('SERIAL')).map((r) => r.ticker)).size,
      latest: raises[0]?.listing_date ?? '—',
    };
  }, [raises]);

  const selectedTicker = selected?.ticker;
  useEffect(() => {
    setTickerHistory([]);
    if (!selectedTicker) return;
    fetchCorporateActions(selectedTicker)
      .then(setTickerHistory)
      .catch(() => setTickerHistory([]));
  }, [selectedTicker]);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-secondary)' }}>
        <Loader2 size={32} className="spinning" style={{ color: '#38bdf8' }} />
        <p>Loading corporate actions...</p>
      </div>
    );
  }

  if (error || raises.length === 0) {
    return (
      <div className="error-banner">
        <AlertTriangle size={40} />
        <h2>No rights issue data</h2>
        <p>{error ?? 'The API found no corporate actions.'} The tracker reads <code>data/corporateActions.json</code>. Generate it with:</p>
        <code>uv run idx corporate</code>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Banner */}
      <div style={{ ...panel, padding: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
            <Layers size={28} style={{ color: '#a78bfa' }} />
            <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 700 }}>Rights Issue Tracker</h2>
          </div>
          <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Rights issues (PMHMETD) and private placements (PMTHMETD) listed on IDX: size, dilution, serial issuers, and a holder calculator.
          </p>
        </div>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
          Latest listing in data: <strong style={{ color: '#e2e8f0' }}>{kpis.latest}</strong>
        </span>
      </div>

      <TrackedRaisesPanel panelStyle={panel} onSelectStock={onSelectStock} />

      {/* KPI tiles */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '0.75rem' }}>
        {[
          { label: 'Rights issues, 12m', value: fmtInt(kpis.rights12m), color: '#a78bfa' },
          { label: 'Private placements, 12m', value: fmtInt(kpis.placements12m), color: '#38bdf8' },
          { label: 'Median listed dilution, 12m', value: fmtPct(kpis.medianDilution), color: '#f8fafc' },
          { label: 'Large issues (≥ 1×), 12m', value: fmtInt(kpis.large12m), color: '#ef4444' },
          { label: 'Serial issuers, 12m', value: fmtInt(kpis.serialTickers), color: '#f59e0b' },
        ].map((k) => (
          <div key={k.label} style={{ ...panel, padding: '1rem' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{k.label}</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, color: k.color, fontVariantNumeric: 'tabular-nums' }}>{k.value}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div style={{ ...panel, display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap', padding: '0.9rem 1.25rem' }}>
        <input
          className="form-control"
          style={{ maxWidth: '180px', paddingLeft: '1rem' }}
          placeholder="Ticker…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select className="form-control" style={{ maxWidth: '200px' }} value={typeFilter} onChange={(e) => setTypeFilter(e.target.value as typeof typeFilter)}>
          <option value="all">All types</option>
          <option value="rights_issue">Rights issues</option>
          <option value="private_placement">Private placements</option>
        </select>
        <select className="form-control" style={{ maxWidth: '180px' }} value={period} onChange={(e) => setPeriod(e.target.value)}>
          {PERIODS.map((p) => (
            <option key={p.id} value={p.id}>{p.label}</option>
          ))}
        </select>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', color: 'var(--text-secondary)', cursor: 'pointer' }}>
          <input type="checkbox" checked={flaggedOnly} onChange={(e) => setFlaggedOnly(e.target.checked)} />
          Flagged only
        </label>
        <span style={{ marginLeft: 'auto', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{fmtInt(filtered.length)} results</span>
      </div>

      {/* Table + detail */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.5fr) minmax(320px, 1fr)', gap: '1.25rem', alignItems: 'start' }}>
        <div style={{ ...panel, padding: 0, overflow: 'hidden' }}>
          <div className="table-container" style={{ marginTop: 0, maxHeight: '640px', overflowY: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Listed</th>
                  <th>Ticker</th>
                  <th>Type</th>
                  <th style={{ textAlign: 'right' }}>New shares</th>
                  <th style={{ textAlign: 'right' }}>vs existing</th>
                  <th style={{ textAlign: 'right' }}>Dilution</th>
                  <th>Flags</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => (
                  <tr
                    key={r.type + r.id}
                    onClick={() => setSelected(r)}
                    style={{ cursor: 'pointer', background: selected?.id === r.id && selected.type === r.type ? 'rgba(167, 139, 250, 0.12)' : undefined }}
                  >
                    <td className="numeric">{r.listing_date}</td>
                    <td><span className="ticker-badge">{r.ticker}</span></td>
                    <td style={{ fontSize: '0.8rem' }}>{TYPE_LABEL[r.type]}</td>
                    <td className="numeric" style={{ textAlign: 'right' }}>{fmtShares(r.new_shares)}</td>
                    <td className="numeric" style={{ textAlign: 'right' }}>{fmtPct(r.size_vs_old_pct)}</td>
                    <td className="numeric" style={{ textAlign: 'right' }}>{fmtPct(r.dilution_pct)}</td>
                    <td>
                      <div style={{ display: 'flex', gap: '0.25rem', flexWrap: 'wrap' }}>
                        {r.flags.map((f) => (
                          <span key={f} title={flagLabels[f]} style={{ fontSize: '0.65rem', fontWeight: 700, padding: '0.1rem 0.4rem', borderRadius: '6px', color: flagColor(f), border: `1px solid ${flagColor(f)}55` }}>
                            {f.replace(/_/g, ' ')}
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={7} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>No matching capital raises.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {selected && (
            <div style={panel}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <div>
                  <span className="ticker-badge" style={{ fontSize: '1rem' }}>{selected.ticker}</span>
                  <span style={{ marginLeft: '0.5rem', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{TYPE_LABEL[selected.type]} · listed {selected.listing_date}</span>
                </div>
                <button className="filter-btn" onClick={() => onSelectStock(selected.ticker)} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.4rem 0.75rem', cursor: 'pointer' }}>
                  Terminal <ArrowRight size={14} />
                </button>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem 1rem', fontSize: '0.85rem', marginBottom: '0.75rem' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Shares before</span><span className="numeric">{fmtInt(selected.shares_before)}</span>
                <span style={{ color: 'var(--text-secondary)' }}>New shares</span><span className="numeric">{fmtInt(selected.new_shares)}</span>
                <span style={{ color: 'var(--text-secondary)' }}>Shares after</span><span className="numeric">{fmtInt(selected.shares_after)}</span>
                <span style={{ color: 'var(--text-secondary)' }}>Listed new per old</span><span className="numeric">≈ {(selected.size_vs_old_pct / 100).toFixed(3)}</span>
                <span style={{ color: 'var(--text-secondary)' }}>Dilution if not taken up</span><span className="numeric">{fmtPct(selected.dilution_pct)}</span>
                <span style={{ color: 'var(--text-secondary)' }}>Raises in 36m</span><span className="numeric">{selected.raises_in_36m}</span>
                {selected.tranches > 1 && (
                  <>
                    <span style={{ color: 'var(--text-secondary)' }}>Listed in batches</span>
                    <span className="numeric">{selected.tranches}, last {selected.last_listing_date}</span>
                  </>
                )}
              </div>
              {selected.flags.length > 0 && (
                <ul style={{ margin: '0 0 0.75rem 1rem', fontSize: '0.8rem', color: '#fca5a5' }}>
                  {selected.flags.map((f) => <li key={f}>{flagLabels[f]}</li>)}
                </ul>
              )}
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '0.4rem' }}>Corporate action history</div>
              <div style={{ maxHeight: '220px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                {tickerHistory.map((h, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', borderLeft: `2px solid ${h.category === 'hmetd' || h.category === 'tanpaHmetd' ? '#a78bfa' : 'rgba(255,255,255,0.15)'}`, paddingLeft: '0.5rem' }}>
                    <span><span className="numeric" style={{ color: 'var(--text-secondary)' }}>{h.listing_date}</span> · {ACTION_LABEL[h.category] ?? h.category}</span>
                    <span className="numeric">{fmtShares(h.shares)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <RightsCalculator ticker={selected?.ticker} />
        </div>
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
        <Info size={14} style={{ flexShrink: 0, marginTop: '2px' }} />
        <span>
          Source: IDX corporate action listings (date the new shares were listed). A listing record can cover only one batch of exercised
          shares and the IDX feed misses some issues, so sizes and dilution can be understated. Exercise price, schedule (cum/ex, trading, exercise deadline), standby buyer
          and use of proceeds come from prospectus extraction (plan §3.10), which is not built yet. Flags describe patterns, not wrongdoing. The calculator is not investment advice.
        </span>
      </div>
    </div>
  );
};

// ---------- Holder calculator (plan §3.10 d) ----------

const numInput: React.CSSProperties = { padding: '0.5rem 0.75rem' };

const RightsCalculator: React.FC<{ ticker?: string }> = ({ ticker }) => {
  const [lots, setLots] = useState(100);
  const [avgCost, setAvgCost] = useState(500);
  const [ratioOld, setRatioOld] = useState(1);
  const [ratioNew, setRatioNew] = useState(1);
  const [exercisePrice, setExercisePrice] = useState(200);
  const [cumPrice, setCumPrice] = useState(500);
  const [rightsPrice, setRightsPrice] = useState<number | ''>('');
  const [buyFee, setBuyFee] = useState(0.15);
  const [sellFee, setSellFee] = useState(0.25);
  const [priceNote, setPriceNote] = useState('');

  const useLastClose = async () => {
    if (!ticker) return;
    setPriceNote('Loading…');
    try {
      const res = await fetchStockData(ticker);
      const close = Number(res?.latest?.close ?? res?.records?.[res.records.length - 1]?.close);
      if (close > 0) {
        setCumPrice(close);
        setPriceNote(`${ticker} last close ${fmtRp(close)}`);
      } else {
        setPriceNote('No price data');
      }
    } catch {
      setPriceNote('No price data for ' + ticker);
    }
  };

  const result = useMemo(() => {
    const base = { ratioOld, ratioNew, exercisePrice, cumPrice };
    const terp = (ratioOld * cumPrice + ratioNew * exercisePrice) / (ratioOld + ratioNew);
    const theoRight = Math.max(0, terp - exercisePrice);
    return holderScenarios({
      ...base,
      sharesHeld: lots * 100,
      avgCost,
      rightsPrice: rightsPrice === '' ? theoRight : rightsPrice,
      buyFeePct: buyFee,
      sellFeePct: sellFee,
    });
  }, [lots, avgCost, ratioOld, ratioNew, exercisePrice, cumPrice, rightsPrice, buyFee, sellFee]);

  const field = (label: string, value: number | '', set: (v: number) => void, step = 1, placeholder?: string) => (
    <label style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
      {label}
      <input
        type="number"
        className="form-control"
        style={numInput}
        value={Number.isNaN(value) ? '' : value}
        step={step}
        min={0}
        placeholder={placeholder}
        onChange={(e) => set(e.target.value === '' ? NaN : Number(e.target.value))}
      />
    </label>
  );

  return (
    <div style={panel}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
        <Calculator size={18} style={{ color: '#38bdf8' }} />
        <h3 style={{ margin: 0, fontSize: '1rem' }}>Holder calculator</h3>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.6rem' }}>
        {field('Lots held (1 lot = 100)', lots, setLots)}
        {field('Average cost (Rp)', avgCost, setAvgCost)}
        {field('Ratio: every N old shares…', ratioOld, setRatioOld)}
        {field('…get M rights', ratioNew, setRatioNew)}
        {field('Exercise price (Rp)', exercisePrice, setExercisePrice)}
        {field('Cum price (Rp)', cumPrice, setCumPrice)}
        <label style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
          Rights market price (Rp)
          <input
            type="number"
            className="form-control"
            style={numInput}
            value={rightsPrice}
            min={0}
            placeholder="theoretical"
            onChange={(e) => setRightsPrice(e.target.value === '' ? '' : Number(e.target.value))}
          />
        </label>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.4rem' }}>
          {field('Buy fee %', buyFee, setBuyFee, 0.01)}
          {field('Sell fee %', sellFee, setSellFee, 0.01)}
        </div>
      </div>
      {ticker && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.6rem', fontSize: '0.75rem' }}>
          <button className="filter-btn" onClick={useLastClose} style={{ padding: '0.3rem 0.6rem', cursor: 'pointer', fontSize: '0.75rem' }}>
            Use {ticker} last close
          </button>
          <span style={{ color: 'var(--text-secondary)' }}>{priceNote}</span>
        </div>
      )}

      {!result ? (
        <p style={{ marginTop: '1rem', fontSize: '0.85rem', color: '#fca5a5' }}>Enter a positive ratio, cum price and shares held.</p>
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem', margin: '1rem 0', fontSize: '0.8rem' }}>
            {[
              { l: 'TERP', v: fmtRp(result.metrics.terp) },
              { l: 'Theoretical right', v: fmtRp(result.metrics.rightValue) },
              { l: 'Rights you get', v: fmtInt(result.rights) },
              { l: 'Discount to cum', v: fmtPct(result.metrics.discountToCum) },
              { l: 'Discount to TERP', v: fmtPct(result.metrics.discountToTerp) },
              { l: 'Dilution if ignored', v: fmtPct(result.metrics.dilutionPct) },
            ].map((x) => (
              <div key={x.l} style={{ background: 'rgba(255,255,255,0.03)', borderRadius: '8px', padding: '0.5rem' }}>
                <div style={{ color: 'var(--text-secondary)', fontSize: '0.68rem' }}>{x.l}</div>
                <div className="numeric" style={{ fontWeight: 700 }}>{x.v}</div>
              </div>
            ))}
          </div>

          <div className="table-container" style={{ marginTop: 0 }}>
            <table style={{ fontSize: '0.78rem' }}>
              <thead>
                <tr>
                  <th>Choice</th>
                  <th style={{ textAlign: 'right' }}>Cash</th>
                  <th style={{ textAlign: 'right' }}>Value after</th>
                  <th style={{ textAlign: 'right' }}>Avg cost</th>
                  <th style={{ textAlign: 'right' }}>Stake kept</th>
                </tr>
              </thead>
              <tbody>
                {result.scenarios.map((s) => (
                  <tr key={s.key} title={s.note}>
                    <td>
                      {s.label}
                      {s.key === 'cash_neutral' && (
                        <div style={{ fontSize: '0.68rem', color: 'var(--text-secondary)' }}>
                          exercise {fmtInt(s.exercised)}, sell {fmtInt(s.sold)}
                        </div>
                      )}
                    </td>
                    <td className="numeric" style={{ textAlign: 'right', color: s.cashFlow < 0 ? '#fca5a5' : s.cashFlow > 0 ? '#6ee7b7' : undefined }}>{fmtRp(s.cashFlow)}</td>
                    <td className="numeric" style={{ textAlign: 'right' }}>{fmtRp(s.valueAfter)}</td>
                    <td className="numeric" style={{ textAlign: 'right' }}>{fmtRp(s.avgCostAfter)}</td>
                    <td className="numeric" style={{ textAlign: 'right' }}>{fmtPct(s.ownershipKeptPct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p style={{ margin: '0.6rem 0 0', fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
            Value after = shares × TERP + cash. "Do nothing" loses the rights' value when the exercise period ends. Fractional rights are rounded down.
          </p>
        </>
      )}
    </div>
  );
};
