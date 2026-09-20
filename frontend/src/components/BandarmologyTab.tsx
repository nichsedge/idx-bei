import React, { useEffect, useState } from 'react';
import { 
  Radar, 
  TrendingUp, 
  AlertTriangle, 
  ShieldAlert, 
  Eye, 
  RotateCw, 
  Activity, 
  ArrowRight, 
  Loader2, 
  Users 
} from 'lucide-react';
import type { StealthAnomaly, StealthAccumulationResponse } from '../types';
import { fetchStealthAccumulation } from '../services/api';

interface BandarmologyTabProps {
  onSelectStock: (ticker: string) => void;
}

export const BandarmologyTab: React.FC<BandarmologyTabProps> = ({ onSelectStock }) => {
  const [data, setData] = useState<StealthAccumulationResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [filterSignal, setFilterSignal] = useState<string>('ALL');
  const [filterPhase, setFilterPhase] = useState<string>('ALL');
  const [lookbackDays, setLookbackDays] = useState<number>(5);

  const loadData = async (lookback = lookbackDays) => {
    setLoading(true);
    setError(null);
    try {
      const stealthRes = await fetchStealthAccumulation(lookback);
      setData(stealthRes);
    } catch (err: any) {
      setError(err.message || 'Failed to load bandarmology intelligence');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData(lookbackDays);
  }, [lookbackDays]);

  const anomalies: StealthAnomaly[] = data?.anomalies || [];
  const phaseACount = anomalies.filter((a) => a.WyckoffPhase?.startsWith('Phase A')).length;
  const phaseBCount = anomalies.filter((a) => a.WyckoffPhase?.startsWith('Phase B')).length;
  const phaseCCount = anomalies.filter((a) => a.WyckoffPhase?.startsWith('Phase C')).length;
  const phaseDCount = anomalies.filter((a) => a.WyckoffPhase?.startsWith('Phase D')).length;

  const filteredAnomalies = anomalies.filter((a) => {
    if (filterSignal !== 'ALL' && a.Signal !== filterSignal) return false;
    if (filterPhase !== 'ALL') {
      if (filterPhase === 'Phase A' && !a.WyckoffPhase?.startsWith('Phase A')) return false;
      if (filterPhase === 'Phase B' && !a.WyckoffPhase?.startsWith('Phase B')) return false;
      if (filterPhase === 'Phase C' && !a.WyckoffPhase?.startsWith('Phase C')) return false;
      if (filterPhase === 'Phase D' && !a.WyckoffPhase?.startsWith('Phase D')) return false;
    }
    return true;
  });

  const summaryObj = typeof data?.summary === 'object' && data.summary !== null ? data.summary : null;
  const summaryText =
    typeof data?.summary === 'string'
      ? data.summary
      : summaryObj
      ? `On session ${summaryObj.on_date}, Smart Money Turnover reached Rp ${summaryObj.smart_money_turnover_rp_b?.toLocaleString()}B vs Retail Rp ${summaryObj.retail_turnover_rp_b?.toLocaleString()}B. Detected ${summaryObj.anomalies_detected} stocks exhibiting significant accumulation divergence.`
      : (data ? 'No abnormal institutional accumulation detected for this trading session.' : 'Analyzing market-wide broker transactions...');

  return (
    <div className="bandarmology-tab" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Banner & Refresh */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: 'rgba(15, 23, 42, 0.65)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '16px',
        padding: '1.5rem',
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
            <Radar size={28} style={{ color: '#38bdf8' }} />
            <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 700 }}>Bandarmology & Institutional Radar</h2>
          </div>
          <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Unmask quiet institutional accumulation, retail liquidity traps, and broker dominance shifts across the Indonesia Stock Exchange.
          </p>
        </div>
        <button
          onClick={() => loadData()}
          disabled={loading}
          className="filter-btn"
          style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.6rem 1.2rem', cursor: 'pointer' }}
        >
          <RotateCw size={16} className={loading ? 'spinning' : ''} />
          <span>Refresh Radar</span>
        </button>
      </div>

      {/* KPI Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
        gap: '1rem',
      }}>
        <div className="stat-card" style={{
          background: 'rgba(15, 23, 42, 0.55)',
          border: '1px solid rgba(56, 189, 248, 0.2)',
          borderRadius: '14px',
          padding: '1.25rem',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            <span>Smart Money Delta</span>
            <Activity size={18} style={{ color: '#38bdf8' }} />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, marginTop: '0.5rem', color: (data?.smart_money_delta ?? 0) >= 1.0 ? '#10b981' : '#ef4444' }}>
            {data?.smart_money_delta !== undefined ? `${data.smart_money_delta}x` : '—'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
            Institutional vs Retail broker turnover ratio
          </div>
        </div>

        <div className="stat-card" style={{
          background: 'rgba(15, 23, 42, 0.55)',
          border: '1px solid rgba(16, 185, 129, 0.2)',
          borderRadius: '14px',
          padding: '1.25rem',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            <span>Market Regime</span>
            <TrendingUp size={18} style={{ color: '#10b981' }} />
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 800, marginTop: '0.5rem', color: '#10b981' }}>
            {data?.signal || 'NEUTRAL'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
            Dominant order flow pressure
          </div>
        </div>

        <div className="stat-card" style={{
          background: 'rgba(15, 23, 42, 0.55)',
          border: '1px solid rgba(245, 158, 11, 0.2)',
          borderRadius: '14px',
          padding: '1.25rem',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            <span>Detected Anomalies</span>
            <AlertTriangle size={18} style={{ color: '#f59e0b' }} />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, marginTop: '0.5rem', color: '#f59e0b' }}>
            {anomalies.length} Stocks
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
            Stocks exhibiting accumulation divergence
          </div>
        </div>

        <div className="stat-card" style={{
          background: 'rgba(15, 23, 42, 0.55)',
          border: '1px solid rgba(168, 85, 247, 0.2)',
          borderRadius: '14px',
          padding: '1.25rem',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            <span>Institutional Flow</span>
            <Users size={18} style={{ color: '#c084fc' }} />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, marginTop: '0.5rem', color: '#c084fc' }}>
            {summaryObj ? `Rp ${(summaryObj.smart_money_turnover_rp_b / 1000).toFixed(1)}T` : 'Active'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
            Smart money session turnover
          </div>
        </div>
      </div>

      {loading && !data && (
        <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-secondary)' }}>
          <Loader2 size={36} className="spinning" style={{ margin: '0 auto 1rem', color: '#38bdf8' }} />
          <p>Scanning broker summaries & detecting stealth flow...</p>
        </div>
      )}

      {error && (
        <div className="error-banner" style={{ padding: '1.5rem' }}>
          <ShieldAlert size={28} />
          <div>
            <h4 style={{ margin: 0 }}>Radar Alert</h4>
            <p style={{ margin: 0, fontSize: '0.9rem' }}>{error}</p>
          </div>
        </div>
      )}

      {/* Wyckoff Accumulation Lifecycle Pipeline */}
      {data && (
        <div style={{
          background: 'rgba(15, 23, 42, 0.55)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '16px',
          padding: '1.25rem',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700 }}>Wyckoff Phase Lifecycle Pipeline</h3>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                Stage distribution of institutional campaign across monitored stocks
              </span>
            </div>
            {filterPhase !== 'ALL' && (
              <button
                onClick={() => setFilterPhase('ALL')}
                style={{
                  padding: '0.3rem 0.6rem',
                  fontSize: '0.75rem',
                  borderRadius: '6px',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  background: 'rgba(255, 255, 255, 0.05)',
                  color: 'var(--text-secondary)',
                  cursor: 'pointer',
                }}
              >
                Clear Phase Filter
              </button>
            )}
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '0.75rem',
          }}>
            {[
              { id: 'Phase A', label: 'Phase A: Stopping Action', desc: 'Selling Climax & Automatic Rally', count: phaseACount, color: '#f59e0b' },
              { id: 'Phase B', label: 'Phase B: Absorption', desc: 'Secondary Testing & Range Bound', count: phaseBCount, color: '#38bdf8' },
              { id: 'Phase C', label: 'Phase C: Spring / Shakeout', desc: 'Liquidity Sweep & False Breakdown', count: phaseCCount, color: '#10b981' },
              { id: 'Phase D', label: 'Phase D: Markup (SOS)', desc: 'Sign of Strength & Trend Breakout', count: phaseDCount, color: '#a855f7' },
            ].map((p) => {
              const active = filterPhase === p.id;
              return (
                <div
                  key={p.id}
                  onClick={() => setFilterPhase(active ? 'ALL' : p.id)}
                  style={{
                    background: active ? `rgba(56, 189, 248, 0.15)` : 'rgba(255, 255, 255, 0.03)',
                    border: `1px solid ${active ? p.color : 'rgba(255, 255, 255, 0.06)'}`,
                    borderRadius: '12px',
                    padding: '1rem',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                    <span style={{ fontSize: '0.8rem', fontWeight: 700, color: p.color }}>{p.label}</span>
                    <span style={{
                      fontSize: '0.85rem',
                      fontWeight: 800,
                      background: 'rgba(255, 255, 255, 0.08)',
                      padding: '0.15rem 0.45rem',
                      borderRadius: '6px',
                      color: '#ffffff',
                    }}>
                      {p.count}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                    {p.desc}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Main Content Grid */}
      {data && (
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1.5rem' }}>
          {/* Anomalies Table */}
          <div style={{
            background: 'rgba(15, 23, 42, 0.55)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '16px',
            padding: '1.5rem',
            overflow: 'hidden',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700 }}>Stealth Flow & Wyckoff Anomalies ({filteredAnomalies.length})</h3>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  Institutional absorption vs retail liquidity traps over {lookbackDays}-session window
                </span>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', background: 'rgba(255, 255, 255, 0.04)', borderRadius: '8px', padding: '2px', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
                  {[1, 3, 5, 10].map((days) => (
                    <button
                      key={days}
                      onClick={() => setLookbackDays(days)}
                      style={{
                        padding: '0.25rem 0.5rem',
                        borderRadius: '6px',
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        border: 'none',
                        background: lookbackDays === days ? '#38bdf8' : 'transparent',
                        color: lookbackDays === days ? '#0f172a' : 'var(--text-secondary)',
                        cursor: 'pointer',
                      }}
                    >
                      {days}D
                    </button>
                  ))}
                </div>
                {['ALL', 'STEALTH_ACCUMULATION', 'MARKUP_CONFIRMATION', 'RETAIL_TRAP', 'DISTRIBUTION'].map((sig) => (
                  <button
                    key={sig}
                    onClick={() => setFilterSignal(sig)}
                    style={{
                      padding: '0.35rem 0.65rem',
                      borderRadius: '8px',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                      background: filterSignal === sig ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.04)',
                      color: filterSignal === sig ? '#38bdf8' : 'var(--text-secondary)',
                      cursor: 'pointer',
                    }}
                  >
                    {sig.replace('_', ' ')}
                  </button>
                ))}
              </div>
            </div>

            {filteredAnomalies.length === 0 ? (
              <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                <Eye size={32} style={{ margin: '0 auto 0.5rem', opacity: 0.5 }} />
                <p>No anomalies detected under the current filter.</p>
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', color: 'var(--text-secondary)', textAlign: 'left' }}>
                      <th style={{ padding: '0.75rem 0.5rem' }}>Ticker</th>
                      <th style={{ padding: '0.75rem 0.5rem' }}>Signal & Phase</th>
                      <th style={{ padding: '0.75rem 0.5rem' }}>Conviction</th>
                      <th style={{ padding: '0.75rem 0.5rem' }}>Price (1D / {lookbackDays}D)</th>
                      <th style={{ padding: '0.75rem 0.5rem' }}>Net Flow (1D / {lookbackDays}D)</th>
                      <th style={{ padding: '0.75rem 0.5rem' }}>Flow Ratio</th>
                      <th style={{ padding: '0.75rem 0.5rem' }}>Priority</th>
                      <th style={{ padding: '0.75rem 0.5rem', textAlign: 'right' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredAnomalies.map((a, idx) => {
                      const isStealth = a.Signal === 'STEALTH_ACCUMULATION';
                      const isMarkup = a.Signal === 'MARKUP_CONFIRMATION';
                      const isTrap = a.Signal === 'RETAIL_TRAP';
                      const isDist = a.Signal === 'DISTRIBUTION';

                      let badgeBg = 'rgba(255, 255, 255, 0.05)';
                      let badgeColor = 'var(--text-secondary)';
                      let badgeBorder = 'rgba(255, 255, 255, 0.1)';

                      if (isStealth) {
                        badgeBg = 'rgba(16, 185, 129, 0.15)';
                        badgeColor = '#34d399';
                        badgeBorder = 'rgba(16, 185, 129, 0.3)';
                      } else if (isMarkup) {
                        badgeBg = 'rgba(56, 189, 248, 0.15)';
                        badgeColor = '#38bdf8';
                        badgeBorder = 'rgba(56, 189, 248, 0.3)';
                      } else if (isTrap || isDist) {
                        badgeBg = 'rgba(239, 68, 68, 0.15)';
                        badgeColor = '#f87171';
                        badgeBorder = 'rgba(239, 68, 68, 0.3)';
                      }

                      const score = a.AccumulationScore ?? 50;
                      const scoreColor = score >= 75 ? '#34d399' : (score <= 30 ? '#f87171' : '#facc15');

                      return (
                        <tr
                          key={`${a.StockCode}-${idx}`}
                          style={{
                            borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                            transition: 'background 0.15s ease',
                            cursor: 'pointer',
                          }}
                          className="table-row-hover"
                          onClick={() => onSelectStock(a.StockCode)}
                        >
                          <td style={{ padding: '0.85rem 0.5rem' }}>
                            <span style={{ fontWeight: 700, color: '#f8fafc', fontSize: '0.95rem' }}>{a.StockCode}</span>
                          </td>
                          <td style={{ padding: '0.85rem 0.5rem' }}>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                              <span
                                style={{
                                  padding: '0.2rem 0.5rem',
                                  borderRadius: '6px',
                                  fontSize: '0.7rem',
                                  fontWeight: 700,
                                  background: badgeBg,
                                  color: badgeColor,
                                  border: `1px solid ${badgeBorder}`,
                                  width: 'fit-content',
                                }}
                              >
                                {a.Signal.replace('_', ' ')}
                              </span>
                              {a.WyckoffPhase && (
                                <span style={{ fontSize: '0.65rem', color: 'var(--text-secondary)', marginLeft: '2px' }}>
                                  {a.WyckoffPhase.replace('_', ' ')}
                                </span>
                              )}
                            </div>
                          </td>
                          <td style={{ padding: '0.85rem 0.5rem' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span style={{ fontWeight: 700, color: scoreColor, fontSize: '0.85rem' }}>{score}</span>
                              <div style={{ width: '40px', height: '4px', background: 'rgba(255, 255, 255, 0.1)', borderRadius: '2px', overflow: 'hidden' }}>
                                <div style={{ width: `${score}%`, height: '100%', background: scoreColor }} />
                              </div>
                            </div>
                          </td>
                          <td style={{ padding: '0.85rem 0.5rem', fontWeight: 600 }}>
                            <div style={{ display: 'flex', flexDirection: 'column' }}>
                              <span style={{ color: a.PriceChangePct >= 0 ? '#10b981' : '#ef4444' }}>
                                {a.PriceChangePct >= 0 ? `+${a.PriceChangePct.toFixed(2)}%` : `${a.PriceChangePct.toFixed(2)}%`}
                              </span>
                              {a.CumPriceChangePct !== undefined && (
                                <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                                  {lookbackDays}D: {a.CumPriceChangePct >= 0 ? `+${a.CumPriceChangePct.toFixed(1)}%` : `${a.CumPriceChangePct.toFixed(1)}%`}
                                </span>
                              )}
                            </div>
                          </td>
                          <td style={{ padding: '0.85rem 0.5rem', fontWeight: 600 }}>
                            <div style={{ display: 'flex', flexDirection: 'column' }}>
                              <span style={{ color: (a.NetForeignFlowRpB ?? 0) >= 0 ? '#10b981' : '#ef4444' }}>
                                {a.NetForeignFlowRpB !== undefined
                                  ? `${a.NetForeignFlowRpB >= 0 ? '+' : ''}Rp ${a.NetForeignFlowRpB.toFixed(1)}B`
                                  : '—'}
                              </span>
                              {a.CumNetForeignFlowRpB !== undefined && (
                                <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                                  {lookbackDays}D: {a.CumNetForeignFlowRpB >= 0 ? '+' : ''}Rp {a.CumNetForeignFlowRpB.toFixed(1)}B
                                </span>
                              )}
                            </div>
                          </td>
                          <td style={{ padding: '0.85rem 0.5rem', color: 'var(--text-secondary)' }}>
                            {a.FlowRatioPct !== undefined ? `${a.FlowRatioPct >= 0 ? '+' : ''}${a.FlowRatioPct}%` : '—'}
                          </td>
                          <td style={{ padding: '0.85rem 0.5rem' }}>
                            <span style={{
                              padding: '0.15rem 0.45rem',
                              borderRadius: '4px',
                              fontSize: '0.7rem',
                              fontWeight: 700,
                              background: a.Priority === 'HIGH' ? 'rgba(234, 179, 8, 0.15)' : 'rgba(255, 255, 255, 0.05)',
                              color: a.Priority === 'HIGH' ? '#facc15' : 'var(--text-secondary)',
                            }}>
                              {a.Priority || 'MEDIUM'}
                            </span>
                          </td>
                          <td style={{ padding: '0.85rem 0.5rem', textAlign: 'right' }}>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onSelectStock(a.StockCode);
                              }}
                              style={{
                                background: 'rgba(56, 189, 248, 0.15)',
                                border: '1px solid rgba(56, 189, 248, 0.3)',
                                color: '#38bdf8',
                                padding: '0.35rem 0.6rem',
                                borderRadius: '6px',
                                cursor: 'pointer',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                fontSize: '0.75rem',
                                fontWeight: 600,
                              }}
                            >
                              <span>Chart</span>
                              <ArrowRight size={12} />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Right Column: Bandarmology Principles & Summary */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{
              background: 'rgba(15, 23, 42, 0.55)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '16px',
              padding: '1.5rem',
            }}>
              <h3 style={{ margin: '0 0 1rem', fontSize: '1.05rem', fontWeight: 700 }}>Bandarmology Rules</h3>
              <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                <li>
                  <strong style={{ color: '#34d399' }}>Stealth Accumulation:</strong> High institutional net buying (Foreign Flow ratio &gt; 15%) while price remains flat (&le; 1.0%). Smart money is quietly absorbing supply without spiking prices.
                </li>
                <li>
                  <strong style={{ color: '#f87171' }}>Retail Trap:</strong> Price gain (&gt; 1.0%) accompanied by heavy institutional net distribution (Foreign Flow ratio &lt; -15%). Retail buyers are bidding into smart money exit orders.
                </li>
                <li>
                  <strong style={{ color: '#38bdf8' }}>Smart Money Delta:</strong> Ratio of institutional broker turnover (AK, BK, ZP, RX, CC) to retail broker turnover (YP, PD, XC, NI).
                </li>
              </ul>
            </div>

            {/* Quick Actions Card */}
            <div style={{
              background: 'rgba(15, 23, 42, 0.55)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(56, 189, 248, 0.2)',
              borderRadius: '16px',
              padding: '1.5rem',
            }}>
              <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.95rem', fontWeight: 700, color: '#38bdf8' }}>
                Market Session Verdict
              </h4>
              <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                {summaryText}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
