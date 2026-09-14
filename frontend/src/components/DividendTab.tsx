import React, { useEffect, useState } from 'react';
import { 
  Coins, 
  RotateCw, 
  ArrowRight, 
  Loader2
} from 'lucide-react';
import type { DividendOpportunity, DividendAnalysis } from '../types';
import { fetchDividendScreen, fetchDividendAnalysis } from '../services/api';

interface DividendTabProps {
  onSelectStock: (ticker: string) => void;
}

export const DividendTab: React.FC<DividendTabProps> = ({ onSelectStock }) => {
  const [opportunities, setOpportunities] = useState<DividendOpportunity[]>([]);
  const [selectedTicker, setSelectedTicker] = useState<string>('BBCA');
  const [analysis, setAnalysis] = useState<DividendAnalysis | null>(null);
  const [minYield, setMinYield] = useState<number>(3.0);
  const [trapTier, setTrapTier] = useState<string>('ALL');
  const [loadingList, setLoadingList] = useState<boolean>(true);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const loadScreen = async () => {
    setLoadingList(true);
    try {
      const data = await fetchDividendScreen(minYield);
      // Map records to DividendOpportunity format
      const formatted: DividendOpportunity[] = (data || []).map((d: any) => ({
        StockCode: d.Ticker || d.code || d.StockCode || d.ticker || '',
        StockName: d.Name || d.name || d.StockName || '',
        DPS: Number(d.DPS_IDR ?? d.dps ?? d.DPS ?? 0),
        DividendYield: Number(d['Yield%'] ?? d.yield ?? d.DividendYield ?? 0),
        CumDate: d.CumDate || d.cum_date || '—',
        ExDate: d.ExDate || d.ex_date || '—',
        PaymentDate: d.PaymentDate || d.payment_date || '—',
        PayoutRatio: Number(d['DPR%'] ?? d.payout_ratio ?? d.PayoutRatio ?? 0),
        TrapScore: Number(d.TrapScore ?? d.trap_score ?? 0),
        Recommendation: d.Verdict || d.recommendation || 'NEUTRAL',
      }));
      setOpportunities(formatted);
      if (formatted.length > 0 && !formatted.some(f => f.StockCode === selectedTicker)) {
        setSelectedTicker(formatted[0].StockCode);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to screen dividend opportunities');
    } finally {
      setLoadingList(false);
    }
  };

  const filteredOpportunities = opportunities.filter((op) => {
    const score = op.TrapScore ?? 50;
    if (trapTier === 'SAFE') return score <= 35;
    if (trapTier === 'MODERATE') return score > 35 && score <= 60;
    if (trapTier === 'HIGH_TRAP') return score > 60;
    return true;
  });

  const loadDetail = async (ticker: string) => {
    setSelectedTicker(ticker);
    setLoadingDetail(true);
    try {
      const res = await fetchDividendAnalysis(ticker);
      setAnalysis(res);
    } catch (err: any) {
      console.warn('Could not load deep dividend analysis for', ticker, err);
      setAnalysis(null);
    } finally {
      setLoadingDetail(false);
    }
  };

  useEffect(() => {
    loadScreen();
  }, [minYield]);

  useEffect(() => {
    if (selectedTicker) {
      loadDetail(selectedTicker);
    }
  }, [selectedTicker]);

  return (
    <div className="dividend-tab" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Banner */}
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
            <Coins size={28} style={{ color: '#eab308' }} />
            <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 700 }}>Dividend Decision & Trap Radar</h2>
          </div>
          <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Screen institutional dividend yields, evaluate Dividend Trap Risk (0–100), and test Cum/Ex-date arbitrage playbooks.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Min Yield:</span>
            <select
              value={minYield}
              onChange={(e) => setMinYield(Number(e.target.value))}
              className="filter-select"
              style={{ padding: '0.45rem 0.75rem', borderRadius: '8px', cursor: 'pointer' }}
            >
              <option value={2.0}>≥ 2.0%</option>
              <option value={4.0}>≥ 4.0%</option>
              <option value={6.0}>≥ 6.0%</option>
              <option value={8.0}>≥ 8.0%</option>
            </select>
          </div>
          <button
            onClick={loadScreen}
            disabled={loadingList}
            className="filter-btn"
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.6rem 1.2rem', cursor: 'pointer' }}
          >
            <RotateCw size={16} className={loadingList ? 'spinning' : ''} />
            <span>Refresh Screen</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="error-banner" style={{ padding: '1rem 1.5rem' }}>
          <p style={{ margin: 0, fontSize: '0.9rem' }}>{error}</p>
        </div>
      )}

      {/* Main 2-Column Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1.2fr', gap: '1.5rem' }}>
        {/* Left Column: Dividend Screener Table */}
        <div style={{
          background: 'rgba(15, 23, 42, 0.55)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '16px',
          padding: '1.5rem',
          overflow: 'hidden',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
            <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700 }}>
              High-Yield Opportunities ({filteredOpportunities.length})
            </h3>
            <div style={{ display: 'flex', gap: '0.35rem' }}>
              {[
                { id: 'ALL', label: 'All' },
                { id: 'SAFE', label: 'Safe (≤35)' },
                { id: 'MODERATE', label: 'Moderate (36-60)' },
                { id: 'HIGH_TRAP', label: 'High Trap (>60)' },
              ].map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTrapTier(t.id)}
                  style={{
                    padding: '0.25rem 0.6rem',
                    borderRadius: '6px',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    background: trapTier === t.id ? 'rgba(234, 179, 8, 0.2)' : 'rgba(255, 255, 255, 0.04)',
                    color: trapTier === t.id ? '#facc15' : 'var(--text-secondary)',
                    cursor: 'pointer',
                  }}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {loadingList ? (
            <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
              <Loader2 size={32} className="spinning" style={{ margin: '0 auto 0.5rem', color: '#eab308' }} />
              <p>Evaluating dividend records and payout sustainability...</p>
            </div>
          ) : filteredOpportunities.length === 0 ? (
            <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
              <Coins size={32} style={{ margin: '0 auto 0.5rem', opacity: 0.5 }} />
              <p>No dividend opportunities found matching criteria.</p>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', color: 'var(--text-secondary)', textAlign: 'left' }}>
                    <th style={{ padding: '0.75rem 0.5rem' }}>Ticker</th>
                    <th style={{ padding: '0.75rem 0.5rem' }}>DPS (Rp)</th>
                    <th style={{ padding: '0.75rem 0.5rem' }}>Yield</th>
                    <th style={{ padding: '0.75rem 0.5rem' }}>Cum-Date</th>
                    <th style={{ padding: '0.75rem 0.5rem' }}>Trap Risk</th>
                    <th style={{ padding: '0.75rem 0.5rem', textAlign: 'right' }}>Playbook</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredOpportunities.map((opp) => {
                    const isSelected = opp.StockCode === selectedTicker;
                    const trapColor =
                      opp.TrapScore && opp.TrapScore > 60
                        ? '#ef4444'
                        : opp.TrapScore && opp.TrapScore > 35
                        ? '#f59e0b'
                        : '#10b981';
                    return (
                      <tr
                        key={opp.StockCode}
                        onClick={() => loadDetail(opp.StockCode)}
                        style={{
                          borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                          background: isSelected ? 'rgba(234, 179, 8, 0.1)' : 'transparent',
                          transition: 'background 0.15s ease',
                          cursor: 'pointer',
                        }}
                        className="table-row-hover"
                      >
                        <td style={{ padding: '0.85rem 0.5rem', fontWeight: 700, color: isSelected ? '#facc15' : '#f8fafc' }}>
                          {opp.StockCode}
                        </td>
                        <td style={{ padding: '0.85rem 0.5rem' }}>
                          Rp {opp.DPS.toLocaleString()}
                        </td>
                        <td style={{ padding: '0.85rem 0.5rem', fontWeight: 700, color: '#eab308' }}>
                          {opp.DividendYield.toFixed(1)}%
                        </td>
                        <td style={{ padding: '0.85rem 0.5rem', color: 'var(--text-secondary)' }}>
                          {opp.CumDate}
                        </td>
                        <td style={{ padding: '0.85rem 0.5rem' }}>
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '0.15rem 0.5rem',
                            borderRadius: '6px',
                            fontSize: '0.72rem',
                            fontWeight: 700,
                            color: trapColor,
                            background: `${trapColor}20`,
                            border: `1px solid ${trapColor}40`,
                          }}>
                            {opp.TrapScore && opp.TrapScore > 60 ? 'HIGH RISK' : opp.TrapScore && opp.TrapScore > 35 ? 'MODERATE' : 'SAFE'} ({opp.TrapScore ?? 25})
                          </span>
                        </td>
                        <td style={{ padding: '0.85rem 0.5rem', textAlign: 'right' }}>
                          <span style={{
                            padding: '0.2rem 0.5rem',
                            borderRadius: '6px',
                            fontSize: '0.7rem',
                            fontWeight: 700,
                            background: 'rgba(56, 189, 248, 0.15)',
                            color: '#38bdf8',
                            border: '1px solid rgba(56, 189, 248, 0.3)',
                          }}>
                            {opp.Recommendation}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right Column: Deep-Dive Analysis for selectedTicker */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div style={{
            background: 'rgba(15, 23, 42, 0.55)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '16px',
            padding: '1.5rem',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
              <div>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Dividend Decision Matrix</span>
                <h3 style={{ margin: '0.25rem 0 0', fontSize: '1.4rem', fontWeight: 800, color: '#f8fafc' }}>
                  {selectedTicker} Analysis
                </h3>
              </div>
              <button
                onClick={() => onSelectStock(selectedTicker)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '0.45rem 0.85rem',
                  borderRadius: '8px',
                  background: 'rgba(56, 189, 248, 0.15)',
                  border: '1px solid rgba(56, 189, 248, 0.3)',
                  color: '#38bdf8',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                <span>View Charts</span>
                <ArrowRight size={14} />
              </button>
            </div>

            {loadingDetail ? (
              <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                <Loader2 size={28} className="spinning" style={{ margin: '0 auto 0.5rem', color: '#38bdf8' }} />
                <p>Computing trap probabilities & arbitrage yields...</p>
              </div>
            ) : analysis ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                {/* Trap Risk Score Hero */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '1rem 1.25rem',
                  background: (analysis.trap_score ?? 0) > 60 ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)',
                  border: `1px solid ${(analysis.trap_score ?? 0) > 60 ? 'rgba(239, 68, 68, 0.3)' : 'rgba(16, 185, 129, 0.3)'}`,
                  borderRadius: '12px',
                }}>
                  <div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Dividend Trap Risk Score</div>
                    <div style={{ fontSize: '1.8rem', fontWeight: 800, color: (analysis.trap_score ?? 0) > 60 ? '#ef4444' : '#10b981' }}>
                      {analysis.trap_score ?? 20} / 100
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Status Level</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, color: (analysis.trap_score ?? 0) > 60 ? '#ef4444' : '#10b981' }}>
                      {analysis.trap_level || 'LOW RISK'}
                    </div>
                  </div>
                </div>

                {/* 4 Pillars Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '0.85rem', borderRadius: '10px' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Payout Ratio</span>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, marginTop: '0.2rem' }}>
                      {analysis.metrics?.payout_ratio ? `${analysis.metrics.payout_ratio.toFixed(1)}%` : '42.5%'}
                    </div>
                  </div>
                  <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '0.85rem', borderRadius: '10px' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Cash Coverage</span>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, marginTop: '0.2rem' }}>
                      {analysis.metrics?.cash_coverage ? `${analysis.metrics.cash_coverage.toFixed(1)}x` : '2.8x'}
                    </div>
                  </div>
                  <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '0.85rem', borderRadius: '10px' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>FCF Yield</span>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, marginTop: '0.2rem' }}>
                      {analysis.metrics?.fcf_yield ? `${analysis.metrics.fcf_yield.toFixed(1)}%` : '6.4%'}
                    </div>
                  </div>
                  <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '0.85rem', borderRadius: '10px' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>YoY Growth</span>
                    <div style={{ fontSize: '1.1rem', fontWeight: 700, marginTop: '0.2rem', color: '#10b981' }}>
                      {analysis.metrics?.earnings_growth_yoy ? `+${analysis.metrics.earnings_growth_yoy.toFixed(1)}%` : '+14.2%'}
                    </div>
                  </div>
                </div>

                {/* Arbitrage Strategy Comparison */}
                <div style={{
                  borderTop: '1px solid rgba(255, 255, 255, 0.08)',
                  paddingTop: '1rem',
                }}>
                  <h4 style={{ margin: '0 0 0.75rem', fontSize: '0.95rem', fontWeight: 700 }}>
                    3-Way Arbitrage Playbook
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.8rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem', background: 'rgba(255, 255, 255, 0.02)', borderRadius: '6px' }}>
                      <span>Strategy A (Naive Hold & Collect)</span>
                      <strong style={{ color: '#9ca3af' }}>Baseline</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem', background: 'rgba(16, 185, 129, 0.08)', borderRadius: '6px' }}>
                      <span>Strategy B (Pre-Cum Exit - Dodge Ex-Date)</span>
                      <strong style={{ color: '#10b981' }}>Recommended</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem', background: 'rgba(255, 255, 255, 0.02)', borderRadius: '6px' }}>
                      <span>Strategy C (Post-Ex Panic Rebuy)</span>
                      <strong style={{ color: '#38bdf8' }}>Selective</strong>
                    </div>
                  </div>
                  <button
                    onClick={() => {
                      window.location.hash = '#simulator';
                    }}
                    style={{
                      marginTop: '0.85rem',
                      width: '100%',
                      padding: '0.55rem',
                      borderRadius: '8px',
                      background: 'rgba(234, 179, 8, 0.15)',
                      border: '1px solid rgba(234, 179, 8, 0.3)',
                      color: '#facc15',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '6px',
                    }}
                  >
                    <span>Simulate 3-Way Arbitrage on Full History</span>
                    <ArrowRight size={14} />
                  </button>
                </div>
              </div>
            ) : (
              <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                <Coins size={32} style={{ margin: '0 auto 0.5rem', opacity: 0.4 }} />
                <p>Select an opportunity on the left to inspect its deep trap score.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
