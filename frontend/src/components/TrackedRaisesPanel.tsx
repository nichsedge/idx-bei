import React, { useEffect, useState } from 'react';
import { ClipboardList, ExternalLink } from 'lucide-react';
import type { RaiseStage, RaiseStatus, TrackedRaise } from '../types';
import { fetchRightsPipeline } from '../services/api';
import { fmtInt, fmtPrice, fmtShares } from '../lib/capital';

interface TrackedRaisesPanelProps {
  panelStyle: React.CSSProperties;
  onSelectStock: (ticker: string) => void;
}

const STAGE_LABEL: Record<RaiseStage, string> = {
  plan: 'Plan',
  egm: 'EGM',
  registration: 'Registration',
  effective: 'Effective',
  trading: 'Rights trading',
  listed: 'Listed',
};

const STATUS_COLOR: Record<RaiseStatus, string> = {
  watch: '#f59e0b',
  active: '#38bdf8',
  completed: '#34d399',
  cancelled: '#94a3b8',
};

const DATE_LABEL: Record<string, string> = {
  effective: 'Effective',
  cum: 'Cum',
  ex: 'Ex',
  recording: 'Recording',
  trading_start: 'Trading from',
  trading_end: 'Trading to',
  listing_start: 'Listing from',
};

function termsText(r: TrackedRaise): string {
  const t = r.terms ?? {};
  if (t.ratio_old && t.ratio_new) {
    return `${fmtInt(t.ratio_old)} : ${fmtInt(t.ratio_new)}` + (t.exercise_price ? ` @ ${fmtPrice(t.exercise_price)}` : '');
  }
  if (t.authorised_after && t.shares_before) {
    return `Authorised to ${fmtShares(t.authorised_after)} (${(t.authorised_after / t.shares_before).toFixed(1)}× issued)`;
  }
  return 'Terms not announced';
}

export const TrackedRaisesPanel: React.FC<TrackedRaisesPanelProps> = ({ panelStyle, onSelectStock }) => {
  const [items, setItems] = useState<TrackedRaise[]>([]);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    fetchRightsPipeline()
      .then((res) => {
        setItems(res.rights);
        setUpdatedAt(res.updated_at);
      })
      .catch(() => setItems([]));
  }, []);

  return (
    <div style={{ ...panelStyle, padding: 0, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', padding: '1rem 1.25rem 0.5rem' }}>
        <ClipboardList size={18} style={{ color: '#a78bfa' }} />
        <h3 style={{ margin: 0, fontSize: '1rem' }}>Tracked raises</h3>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
          planned, ongoing and recent rights issues / placements from <code>data/rights.json</code>
        </span>
        <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>updated {updatedAt ?? '—'}</span>
      </div>
      <div className="table-container" style={{ marginTop: 0 }}>
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Status</th>
              <th>Stage</th>
              <th>Terms</th>
              <th style={{ textAlign: 'right' }}>TERP</th>
              <th>Latest event</th>
              <th style={{ textAlign: 'right' }}>Review</th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => {
              const last = [...r.events].sort((a, b) => b.event_date.localeCompare(a.event_date))[0];
              const isOpen = open === r.id;
              return (
                <React.Fragment key={r.id}>
                  <tr onClick={() => setOpen(isOpen ? null : r.id)} style={{ cursor: 'pointer', background: isOpen ? 'rgba(167, 139, 250, 0.12)' : undefined }}>
                    <td>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectStock(r.ticker);
                        }}
                        className="ticker-badge"
                        style={{ cursor: 'pointer', border: 'none' }}
                        title="Open in Stock Terminal"
                      >
                        {r.ticker}
                      </button>
                    </td>
                    <td>
                      <span style={{ fontSize: '0.7rem', fontWeight: 700, color: STATUS_COLOR[r.status], textTransform: 'uppercase' }}>{r.status}</span>
                    </td>
                    <td style={{ fontSize: '0.8rem' }}>{STAGE_LABEL[r.stage] ?? r.stage}</td>
                    <td style={{ fontSize: '0.8rem' }}>{termsText(r)}</td>
                    <td className="numeric" style={{ textAlign: 'right' }}>{r.terp ? fmtPrice(Math.round(r.terp * 100) / 100) : '—'}</td>
                    <td style={{ fontSize: '0.8rem', maxWidth: '420px' }}>
                      <span className="numeric" style={{ color: 'var(--text-secondary)' }}>{r.last_event_date}</span> {last?.title ?? ''}
                    </td>
                    <td className="numeric" style={{ textAlign: 'right', color: r.pending_review ? '#f59e0b' : 'var(--text-secondary)' }}>
                      {r.pending_review ? `${r.pending_review} pending` : '—'}
                    </td>
                  </tr>
                  {isOpen && (
                    <tr>
                      <td colSpan={7} style={{ background: 'rgba(15, 23, 42, 0.5)', fontSize: '0.8rem', lineHeight: 1.5 }}>
                        {r.name && <div style={{ fontWeight: 700 }}>{r.name}{r.linked_deal ? <span style={{ fontWeight: 400, color: 'var(--text-secondary)' }}> · part of deal {r.linked_deal}</span> : null}</div>}
                        {r.notes && <p style={{ margin: '0.35rem 0', color: 'var(--text-secondary)' }}>{r.notes}</p>}
                        {r.terms?.in_kind && <div>In kind: {r.terms.in_kind}</div>}
                        {r.key_dates && (
                          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', margin: '0.35rem 0' }}>
                            {Object.entries(r.key_dates).map(([k, v]) => (
                              <span key={k}>
                                <span style={{ color: 'var(--text-secondary)' }}>{DATE_LABEL[k] ?? k}</span> <span className="numeric">{v}</span>
                              </span>
                            ))}
                          </div>
                        )}
                        <ul style={{ margin: '0.35rem 0 0', paddingLeft: '1.1rem' }}>
                          {[...r.events]
                            .sort((a, b) => a.event_date.localeCompare(b.event_date))
                            .map((e, i) => (
                              <li key={i}>
                                <span className="numeric">{e.event_date}</span> <span style={{ color: '#a78bfa' }}>[{STAGE_LABEL[e.stage] ?? e.stage}]</span> {e.title}
                                {e.source_url && (
                                  <a href={e.source_url} target="_blank" rel="noreferrer" style={{ marginLeft: 6 }} title="Source">
                                    <ExternalLink size={12} />
                                  </a>
                                )}
                                {e.review_status === 'pending' && <span style={{ marginLeft: 6, color: '#f59e0b' }}>pending review</span>}
                              </li>
                            ))}
                        </ul>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
            {items.length === 0 && (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-secondary)' }}>No tracked raises. Add entries to data/rights.json.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
