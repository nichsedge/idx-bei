import React, { useEffect, useMemo, useState } from 'react';
import { Handshake, ExternalLink, ArrowRight, Loader2, Info, Calculator, ShieldAlert } from 'lucide-react';
import type { CorporateActionItem, Deal, DealsResponse, DealStage, DealStatus, DealType } from '../types';
import { fetchCorporateActions, fetchDeals, fetchStockData } from '../services/api';
import { STAGE_LABELS, STAGE_ORDER, fmtInt, fmtPct, fmtPrice, fmtRp, fmtShares, tenderReturn } from '../lib/capital';

interface DealsTabProps {
  onSelectStock: (ticker: string) => void;
  onOpenRights: () => void;
}

const panel: React.CSSProperties = {
  background: 'rgba(15, 23, 42, 0.65)',
  backdropFilter: 'blur(16px)',
  border: '1px solid rgba(255, 255, 255, 0.08)',
  borderRadius: '16px',
  padding: '1.25rem',
};

const TYPE_LABEL: Record<DealType, string> = {
  acquisition: 'Acquisition',
  backdoor_candidate: 'Backdoor candidate',
  tender_offer: 'Tender offer',
  merger: 'Merger',
  going_private: 'Going private',
};

const STATUS_COLOR: Record<DealStatus, string> = {
  active: '#38bdf8',
  completed: '#10b981',
  cancelled: '#ef4444',
  lapsed: '#9ca3af',
};

const SOURCE_COLOR = { official: '#10b981', news: '#38bdf8', rumour: '#f59e0b' } as const;

const scoreColor = (score: number) => (score >= 60 ? '#ef4444' : score >= 35 ? '#f59e0b' : '#10b981');

// Corporate actions that matter for a deal's later stages (plan §2.1 stage 6).
const RELATED_ACTIONS: Record<string, string> = {
  hmetd: 'Rights issue',
  tanpaHmetd: 'Private placement',
  PrivatePlacement: 'Private placement',
  gabungUsaha: 'Merger',
  partialDelisting: 'Partial delisting',
  reverseStock: 'Reverse split',
};

export const DealsTab: React.FC<DealsTabProps> = ({ onSelectStock, onOpenRights }) => {
  const [dealsFile, setDealsFile] = useState<DealsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [stageFilter, setStageFilter] = useState<'all' | DealStage>('all');
  const [typeFilter, setTypeFilter] = useState<'all' | DealType>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | DealStatus>('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    fetchDeals()
      .then(setDealsFile)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  // Already sorted by last event date (newest first) by the API.
  const deals = useMemo(() => dealsFile?.deals ?? [], [dealsFile]);

  const filtered = useMemo(() => {
    const q = search.trim().toUpperCase();
    return deals.filter(
      (d) =>
        (stageFilter === 'all' || d.current_stage === stageFilter) &&
        (typeFilter === 'all' || d.deal_type === typeFilter) &&
        (statusFilter === 'all' || d.status === statusFilter) &&
        (!q || d.target_ticker.includes(q) || (d.acquirer ?? '').toUpperCase().includes(q)),
    );
  }, [deals, search, stageFilter, typeFilter, statusFilter]);

  const selected = filtered.find((d) => d.id === selectedId) ?? filtered[0] ?? null;

  const kpis = useMemo(
    () => ({
      active: deals.filter((d) => d.status === 'active').length,
      tenders: deals.filter((d) => d.status === 'active' && d.current_stage === 'tender_offer').length,
      likelyBackdoor: deals.filter((d) => d.backdoor.score >= 60).length,
      pendingReview: deals.reduce((n, d) => n + d.pending_review, 0),
    }),
    [deals],
  );

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-secondary)' }}>
        <Loader2 size={32} className="spinning" style={{ color: '#38bdf8' }} />
        <p>Loading deals...</p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Banner */}
      <div style={{ ...panel, padding: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
          <Handshake size={28} style={{ color: '#38bdf8' }} />
          <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 700 }}>Acquisition & Backdoor Listing Tracker</h2>
        </div>
        <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          Takeovers, changes of control, tender offers and backdoor-listing patterns on IDX, with a timeline and source for every event.
        </p>
      </div>

      {/* KPI tiles */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '0.75rem' }}>
        {[
          { label: 'Active deals', value: kpis.active, color: '#38bdf8' },
          { label: 'Open tender offers', value: kpis.tenders, color: '#a78bfa' },
          { label: 'Likely backdoor (≥ 60)', value: kpis.likelyBackdoor, color: '#ef4444' },
          { label: 'Events awaiting review', value: kpis.pendingReview, color: '#f59e0b' },
        ].map((k) => (
          <div key={k.label} style={{ ...panel, padding: '1rem' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{k.label}</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, color: k.color, fontVariantNumeric: 'tabular-nums' }}>{fmtInt(k.value)}</div>
          </div>
        ))}
      </div>

      {deals.length === 0 ? (
        <div style={{ ...panel, color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          <p style={{ marginTop: 0 }}>
            {error ? `Could not load deals (${error}).` : 'No deals yet.'} The tracker reads <code>data/deals.json</code>, which the deal pipeline (plan §5) will write. Until then you can add deals to that file by hand.
          </p>
        </div>
      ) : (
        <>
          {/* Filters */}
          <div style={{ ...panel, display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap', padding: '0.9rem 1.25rem' }}>
            <input className="form-control" style={{ maxWidth: '220px', paddingLeft: '1rem' }} placeholder="Ticker or acquirer…" value={search} onChange={(e) => setSearch(e.target.value)} />
            <select className="form-control" style={{ maxWidth: '180px' }} value={stageFilter} onChange={(e) => setStageFilter(e.target.value as typeof stageFilter)}>
              <option value="all">All stages</option>
              {STAGE_ORDER.map((s) => <option key={s} value={s}>{STAGE_LABELS[s]}</option>)}
            </select>
            <select className="form-control" style={{ maxWidth: '200px' }} value={typeFilter} onChange={(e) => setTypeFilter(e.target.value as typeof typeFilter)}>
              <option value="all">All types</option>
              {(Object.keys(TYPE_LABEL) as DealType[]).map((t) => <option key={t} value={t}>{TYPE_LABEL[t]}</option>)}
            </select>
            <select className="form-control" style={{ maxWidth: '160px' }} value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}>
              <option value="all">All statuses</option>
              {(Object.keys(STATUS_COLOR) as DealStatus[]).map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <span style={{ marginLeft: 'auto', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              {fmtInt(filtered.length)} deals · data updated {dealsFile?.updated_at ?? '—'}
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 0.9fr) minmax(0, 1.6fr)', gap: '1.25rem', alignItems: 'start' }}>
            {/* Feed */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', maxHeight: '760px', overflowY: 'auto' }}>
              {filtered.map((d) => {
                const bd = d.backdoor;
                const isSel = selected?.id === d.id;
                return (
                  <button
                    key={d.id}
                    onClick={() => setSelectedId(d.id)}
                    style={{
                      ...panel,
                      padding: '0.9rem 1rem',
                      textAlign: 'left',
                      cursor: 'pointer',
                      color: 'inherit',
                      border: isSel ? '1px solid rgba(56, 189, 248, 0.5)' : panel.border,
                      background: isSel ? 'rgba(56, 189, 248, 0.08)' : panel.background,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span className="ticker-badge">{d.target_ticker}</span>
                      <span style={{ fontSize: '0.7rem', fontWeight: 700, color: STATUS_COLOR[d.status], textTransform: 'uppercase' }}>{d.status}</span>
                    </div>
                    <div style={{ fontSize: '0.85rem', margin: '0.4rem 0 0.3rem', color: '#e2e8f0' }}>{d.acquirer ?? 'Unknown acquirer'}</div>
                    <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.72rem', color: 'var(--text-secondary)', flexWrap: 'wrap' }}>
                      <span>{TYPE_LABEL[d.deal_type]}</span>·<span>{STAGE_LABELS[d.current_stage]}</span>·<span>{d.last_event_date}</span>
                      <span style={{ marginLeft: 'auto', fontWeight: 700, color: scoreColor(bd.score) }}>BD {bd.score}</span>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Deal page */}
            {selected && <DealDetail deal={selected} onSelectStock={onSelectStock} onOpenRights={onOpenRights} />}
          </div>
        </>
      )}

      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
        <Info size={14} style={{ flexShrink: 0, marginTop: '2px' }} />
        <span>
          Only official disclosures confirm a deal; news and rumours are shown as such. The backdoor score is a pattern match on public information, not an accusation.
          Events marked "pending" have not been reviewed by a person yet.
        </span>
      </div>
    </div>
  );
};

const DealDetail: React.FC<{
  deal: Deal;
  onSelectStock: (ticker: string) => void;
  onOpenRights: () => void;
}> = ({ deal, onSelectStock, onOpenRights }) => {
  const bd = deal.backdoor;
  const premium = deal.tender_premium_pct;
  const [tickerActions, setTickerActions] = useState<CorporateActionItem[]>([]);
  const controlEvent = deal.events.find((e) => e.stake_pct != null);
  const tenderEvent = deal.events.find((e) => e.tender_price != null);
  const stageIdx = STAGE_ORDER.indexOf(deal.current_stage);
  const events = [...deal.events].sort((a, b) => a.event_date.localeCompare(b.event_date) || STAGE_ORDER.indexOf(a.stage) - STAGE_ORDER.indexOf(b.stage));

  useEffect(() => {
    setTickerActions([]);
    fetchCorporateActions(deal.target_ticker)
      .then(setTickerActions)
      .catch(() => setTickerActions([]));
  }, [deal.target_ticker]);

  const related = useMemo(() => {
    const since = deal.first_signal_at ?? deal.announced_at ?? '';
    return tickerActions
      .filter((a) => RELATED_ACTIONS[a.category] && a.listing_date >= since)
      .map((a) => ({ date: a.listing_date, label: RELATED_ACTIONS[a.category], shares: a.shares }))
      .sort((a, b) => a.date.localeCompare(b.date));
  }, [tickerActions, deal.first_signal_at, deal.announced_at]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <div style={panel}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="ticker-badge" style={{ fontSize: '1.05rem' }}>{deal.target_ticker}</span>
              <span style={{ fontWeight: 700 }}>{deal.target_name}</span>
            </div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.3rem' }}>
              {TYPE_LABEL[deal.deal_type]} · announced {deal.announced_at ?? '—'}
              {deal.completed_at && <> · completed {deal.completed_at}</>}
            </div>
          </div>
          <button className="filter-btn" onClick={() => onSelectStock(deal.target_ticker)} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.4rem 0.75rem', cursor: 'pointer' }}>
            Terminal <ArrowRight size={14} />
          </button>
        </div>

        {/* Stage progress */}
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${STAGE_ORDER.length}, 1fr)`, gap: '0.25rem', margin: '1rem 0 0.25rem' }}>
          {STAGE_ORDER.map((s, i) => (
            <div key={s} title={STAGE_LABELS[s]}>
              <div style={{ height: '6px', borderRadius: '3px', background: i <= stageIdx ? (i === stageIdx ? '#38bdf8' : 'rgba(56,189,248,0.45)') : 'rgba(255,255,255,0.08)' }} />
              <div style={{ fontSize: '0.6rem', color: i === stageIdx ? '#38bdf8' : 'var(--text-secondary)', marginTop: '0.25rem', textAlign: 'center' }}>{STAGE_LABELS[s]}</div>
            </div>
          ))}
        </div>

        {/* Key numbers */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '0.5rem', marginTop: '1rem' }}>
          {[
            { l: 'Stake acquired', v: controlEvent?.stake_pct != null ? fmtPct(controlEvent.stake_pct, 2) : '—' },
            { l: 'Shares acquired', v: controlEvent?.shares ? fmtShares(controlEvent.shares) : '—' },
            { l: 'Acquisition price', v: controlEvent?.price ? fmtPrice(controlEvent.price) : '—' },
            { l: 'Tender price', v: tenderEvent?.tender_price ? fmtPrice(tenderEvent.tender_price) : '—' },
            { l: 'TO premium vs pre-ann.', v: premium != null ? fmtPct(premium) : '—' },
            { l: 'TO vs acquisition price', v: tenderEvent?.tender_price && controlEvent?.price ? fmtPct((tenderEvent.tender_price / controlEvent.price - 1) * 100) : '—' },
          ].map((x) => (
            <div key={x.l} style={{ background: 'rgba(255,255,255,0.03)', borderRadius: '8px', padding: '0.55rem' }}>
              <div style={{ color: 'var(--text-secondary)', fontSize: '0.68rem' }}>{x.l}</div>
              <div className="numeric" style={{ fontWeight: 700 }}>{x.v}</div>
            </div>
          ))}
        </div>

        {/* Parties */}
        <div style={{ display: 'grid', gridTemplateColumns: 'max-content 1fr', gap: '0.3rem 1rem', fontSize: '0.82rem', marginTop: '1rem' }}>
          <span style={{ color: 'var(--text-secondary)' }}>Acquirer</span>
          <span>{deal.acquirer ?? '—'}{deal.acquirer_group && <span style={{ color: 'var(--text-secondary)' }}> ({deal.acquirer_group})</span>}</span>
          <span style={{ color: 'var(--text-secondary)' }}>Sellers</span>
          <span>{deal.sellers?.join(', ') || '—'}</span>
          <span style={{ color: 'var(--text-secondary)' }}>Advisors</span>
          <span>{deal.advisors?.join(', ') || '—'}</span>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.25rem', alignItems: 'start' }}>
        {/* Backdoor score */}
        <div style={panel}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.6rem' }}>
            <ShieldAlert size={18} style={{ color: scoreColor(bd.score) }} />
            <h3 style={{ margin: 0, fontSize: '1rem' }}>Backdoor listing score</h3>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
            <span style={{ fontSize: '2rem', fontWeight: 800, color: scoreColor(bd.score) }}>{bd.score}</span>
            <span style={{ color: 'var(--text-secondary)' }}>/ 100 · {bd.label}</span>
          </div>
          <div className="progress-bar-container" style={{ height: '6px', background: 'rgba(255,255,255,0.08)', borderRadius: '3px', margin: '0.5rem 0 0.75rem' }}>
            <div style={{ width: `${bd.score}%`, height: '100%', borderRadius: '3px', background: scoreColor(bd.score) }} />
          </div>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            {bd.signals.map((s) => (
              <li key={s.key} style={{ display: 'flex', justifyContent: 'space-between', color: s.fired ? '#f8fafc' : 'var(--text-secondary)', opacity: s.fired ? 1 : 0.55 }}>
                <span>{s.fired ? '●' : '○'} {s.label}</span>
                <span className="numeric">{s.fired ? '+' + s.weight : s.weight}</span>
              </li>
            ))}
          </ul>
        </div>

        {tenderEvent?.tender_price ? <TenderCalculator ticker={deal.target_ticker} offerPrice={tenderEvent.tender_price} /> : null}
      </div>

      {/* Timeline */}
      <div style={panel}>
        <h3 style={{ margin: '0 0 0.75rem', fontSize: '1rem' }}>Timeline</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {events.map((e, i) => (
            <div key={i} style={{ display: 'grid', gridTemplateColumns: '92px 1fr', gap: '0.75rem', borderLeft: `2px solid ${SOURCE_COLOR[e.source_type]}`, paddingLeft: '0.75rem' }}>
              <div>
                <div className="numeric" style={{ fontSize: '0.8rem' }}>{e.event_date}</div>
                <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>{STAGE_LABELS[e.stage]}</div>
              </div>
              <div>
                <div style={{ fontSize: '0.88rem' }}>{e.title}</div>
                <div style={{ display: 'flex', gap: '0.6rem', fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '0.2rem', flexWrap: 'wrap' }}>
                  <span style={{ color: SOURCE_COLOR[e.source_type], fontWeight: 700, textTransform: 'uppercase' }}>{e.source_type}</span>
                  {e.review_status === 'pending' && <span style={{ color: '#f59e0b' }}>pending review</span>}
                  {e.confidence != null && <span>confidence {fmtPct(e.confidence * 100, 0)}</span>}
                  {e.notes && <span>{e.notes}</span>}
                  {e.source_url && (
                    <a href={e.source_url} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', display: 'inline-flex', alignItems: 'center', gap: '0.2rem' }}>
                      source <ExternalLink size={11} />
                    </a>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {related.length > 0 && (
          <>
            <h4 style={{ margin: '1.25rem 0 0.5rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Related corporate actions (IDX listings)</h4>
            {related.map((r, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', padding: '0.2rem 0' }}>
                <span><span className="numeric" style={{ color: 'var(--text-secondary)' }}>{r.date}</span> · {r.label}</span>
                <span className="numeric">{fmtShares(r.shares)} shares</span>
              </div>
            ))}
            <button className="filter-btn" onClick={onOpenRights} style={{ marginTop: '0.5rem', padding: '0.3rem 0.6rem', fontSize: '0.75rem', cursor: 'pointer' }}>
              Open Rights Issue Tracker
            </button>
          </>
        )}
      </div>
    </div>
  );
};

// ---------- Tender offer calculator (plan §3.5) ----------

const TenderCalculator: React.FC<{ ticker: string; offerPrice: number }> = ({ ticker, offerPrice }) => {
  const [marketPrice, setMarketPrice] = useState<number>(NaN);
  const [offer, setOffer] = useState(offerPrice);
  const [buyFee, setBuyFee] = useState(0.15);
  const [days, setDays] = useState(30);
  const [note, setNote] = useState('');

  useEffect(() => {
    setOffer(offerPrice);
    setMarketPrice(NaN);
    setNote('Loading last close…');
    fetchStockData(ticker)
      .then((res) => {
        const close = Number(res?.latest?.close ?? res?.records?.[res.records.length - 1]?.close);
        if (close > 0) {
          setMarketPrice(close);
          setNote('Last close ' + fmtRp(close));
        } else {
          setNote('No price data; enter the market price.');
        }
      })
      .catch(() => setNote('No price data; enter the market price.'));
  }, [ticker, offerPrice]);

  const r = tenderReturn({ marketPrice, offerPrice: offer, buyFeePct: buyFee, daysToPayment: days });

  const input = (label: string, value: number, set: (v: number) => void, step = 1) => (
    <label style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
      {label}
      <input
        type="number"
        className="form-control"
        style={{ padding: '0.5rem 0.75rem' }}
        value={Number.isNaN(value) ? '' : value}
        step={step}
        min={0}
        onChange={(e) => set(e.target.value === '' ? NaN : Number(e.target.value))}
      />
    </label>
  );

  return (
    <div style={panel}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
        <Calculator size={18} style={{ color: '#a78bfa' }} />
        <h3 style={{ margin: 0, fontSize: '1rem' }}>Tender offer calculator</h3>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem' }}>
        {input('Market price (Rp)', marketPrice, setMarketPrice)}
        {input('Offer price (Rp)', offer, setOffer)}
        {input('Buy fee %', buyFee, setBuyFee, 0.01)}
        {input('Days until payment', days, setDays)}
      </div>
      <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '0.4rem' }}>{note}</div>
      {r ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem', marginTop: '0.75rem' }}>
          {[
            { l: 'Gross spread', v: fmtPct(r.grossSpreadPct, 2) },
            { l: 'Net return', v: fmtPct(r.netReturnPct, 2) },
            { l: 'Annualised', v: r.annualisedPct != null ? fmtPct(r.annualisedPct, 1) : '—' },
          ].map((x) => (
            <div key={x.l} style={{ background: 'rgba(255,255,255,0.03)', borderRadius: '8px', padding: '0.5rem' }}>
              <div style={{ color: 'var(--text-secondary)', fontSize: '0.68rem' }}>{x.l}</div>
              <div className="numeric" style={{ fontWeight: 700, color: r.netReturnPct >= 0 ? '#6ee7b7' : '#fca5a5' }}>{x.v}</div>
            </div>
          ))}
        </div>
      ) : (
        <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.75rem' }}>Enter market and offer prices.</p>
      )}
      <p style={{ margin: '0.6rem 0 0', fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
        Assumes you buy at market and tender every share. If the market price is above the offer, uptake is usually low. Check the offer period before acting.
      </p>
    </div>
  );
};
