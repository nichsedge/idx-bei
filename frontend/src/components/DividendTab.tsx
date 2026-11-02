import React, { useEffect, useState } from 'react';
import { 
  Coins, 
  RotateCw, 
  ArrowRight, 
  Loader2,
  ShieldCheck,
  TrendingUp,
  Clock,
  Sparkles,
  Calculator,
  Scale
} from 'lucide-react';
import type { 
  DividendOpportunity, 
  DividendAnalysis, 
  SovereignRunwayResponse, 
  CashCowProfile 
} from '../types';
import { 
  fetchDividendScreen, 
  fetchDividendAnalysis, 
  fetchSovereignRunwaySimulation, 
  fetchCashCows
} from '../services/api';

interface DividendTabProps {
  onSelectStock: (ticker: string) => void;
}

export const DividendTab: React.FC<DividendTabProps> = ({ onSelectStock }) => {
  const [activeSubTab, setActiveSubTab] = useState<'screener' | 'simulator'>('screener');

  // Screener state
  const [opportunities, setOpportunities] = useState<DividendOpportunity[]>([]);
  const [selectedTicker, setSelectedTicker] = useState<string>('BBCA');
  const [analysis, setAnalysis] = useState<DividendAnalysis | null>(null);
  const [minYield] = useState<number>(3.0);
  const [trapTier, setTrapTier] = useState<string>('ALL');
  const [loadingList, setLoadingList] = useState<boolean>(true);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);
  const [, setError] = useState<string | null>(null);

  // Simulator state
  const [startingCapital, setStartingCapital] = useState<number>(1_000_000_000);
  const [monthlyExpense, setMonthlyExpense] = useState<number>(15_000_000);
  const [projectionYears, setProjectionYears] = useState<number>(20);
  const [inflationPct, setInflationPct] = useState<number>(4.0);
  const [cashCows, setCashCows] = useState<CashCowProfile[]>([]);
  const [selectedCows, setSelectedCows] = useState<string[]>(['BBCA', 'BBRI', 'BMRI', 'ASII', 'ADRO']);
  const [simResult, setSimResult] = useState<SovereignRunwayResponse | null>(null);
  const [loadingSim, setLoadingSim] = useState<boolean>(false);
  const [activeRegimeTab, setActiveRegimeTab] = useState<'uu_cipta_kerja_0pct' | 'standard_tax_drag_10pct' | 'foreign_tax_drag_20pct'>('uu_cipta_kerja_0pct');

  const loadScreen = async () => {
    setLoadingList(true);
    try {
      const data = await fetchDividendScreen(minYield);
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

  const loadSimulator = async () => {
    setLoadingSim(true);
    try {
      const cows = await fetchCashCows();
      setCashCows(cows);

      // Build equal weights among selected cash cows
      const weights: Record<string, number> = {};
      const activeList = selectedCows.length > 0 ? selectedCows : ['BBCA', 'BBRI', 'BMRI', 'ASII', 'ADRO'];
      activeList.forEach((t) => {
        weights[t] = 1.0 / activeList.length;
      });

      const res = await fetchSovereignRunwaySimulation({
        starting_capital: startingCapital,
        monthly_living_expense: monthlyExpense,
        expense_inflation_pct: inflationPct,
        projection_years: projectionYears,
        portfolio_weights: weights,
      });
      setSimResult(res);
    } catch (err: any) {
      console.warn('Simulation failed:', err);
    } finally {
      setLoadingSim(false);
    }
  };

  const toggleCashCow = (ticker: string) => {
    setSelectedCows((prev) => {
      if (prev.includes(ticker)) {
        if (prev.length <= 1) return prev; // Keep at least one
        return prev.filter((t) => t !== ticker);
      }
      return [...prev, ticker];
    });
  };

  useEffect(() => {
    loadScreen();
  }, [minYield]);

  useEffect(() => {
    if (selectedTicker) {
      loadDetail(selectedTicker);
    }
  }, [selectedTicker]);

  useEffect(() => {
    if (activeSubTab === 'simulator') {
      loadSimulator();
    }
  }, [activeSubTab, startingCapital, monthlyExpense, projectionYears, inflationPct, selectedCows]);

  const filteredOpportunities = opportunities.filter((op) => {
    const score = op.TrapScore ?? 50;
    if (trapTier === 'SAFE') return score <= 35;
    if (trapTier === 'MODERATE') return score > 35 && score <= 60;
    if (trapTier === 'HIGH_TRAP') return score > 60;
    return true;
  });

  return (
    <div className="dividend-tab" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Banner & Tab Navigation */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: 'rgba(15, 23, 42, 0.65)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '16px',
        padding: '1.25rem 1.5rem',
        flexWrap: 'wrap',
        gap: '1rem',
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
            <Coins size={28} style={{ color: activeSubTab === 'simulator' ? '#10b981' : '#eab308' }} />
            <h2 style={{ margin: 0, fontSize: '1.35rem', fontWeight: 700 }}>
              {activeSubTab === 'simulator' ? 'Indonesian Sovereign Runway & Tax Drag Simulator' : 'Dividend Decision & Ex-Date Trap Radar'}
            </h2>
          </div>
          <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            {activeSubTab === 'simulator'
              ? 'Model sovereign runway & tax drag exemptions under UU Cipta Kerja (PMK-18/PMK.03/2021) for IDX cash cows.'
              : 'Quantitative Buy / Hold / Sell decision engine assessing yield, 5-dimension trap risk, and cum-date runups.'}
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {/* Sub-tab pills */}
          <div style={{
            display: 'flex',
            background: 'rgba(0, 0, 0, 0.3)',
            padding: '4px',
            borderRadius: '10px',
            border: '1px solid rgba(255, 255, 255, 0.08)',
          }}>
            <button
              onClick={() => setActiveSubTab('screener')}
              style={{
                padding: '0.45rem 0.9rem',
                borderRadius: '8px',
                border: 'none',
                background: activeSubTab === 'screener' ? '#eab308' : 'transparent',
                color: activeSubTab === 'screener' ? '#0f172a' : 'var(--text-secondary)',
                fontWeight: 700,
                fontSize: '0.8rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                transition: 'all 0.2s ease',
              }}
            >
              <Coins size={14} />
              <span>Trap & Cum Screener</span>
            </button>
            <button
              onClick={() => setActiveSubTab('simulator')}
              style={{
                padding: '0.45rem 0.9rem',
                borderRadius: '8px',
                border: 'none',
                background: activeSubTab === 'simulator' ? '#10b981' : 'transparent',
                color: activeSubTab === 'simulator' ? '#0f172a' : 'var(--text-secondary)',
                fontWeight: 700,
                fontSize: '0.8rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                transition: 'all 0.2s ease',
              }}
            >
              <Calculator size={14} />
              <span>🇮🇩 Sovereign Runway & Tax Drag</span>
            </button>
          </div>

          <button
            onClick={() => (activeSubTab === 'simulator' ? loadSimulator() : loadScreen())}
            disabled={loadingList || loadingSim}
            className="filter-btn"
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.55rem 1rem', cursor: 'pointer', fontSize: '0.8rem' }}
          >
            <RotateCw size={14} className={loadingList || loadingSim ? 'spinning' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* VIEW 1: SOVEREIGN RUNWAY & TAX DRAG SIMULATOR */}
      {activeSubTab === 'simulator' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Executive Metrics Overview */}
          {simResult && (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: '1rem',
            }}>
              {/* Card 1: Final Wealth with UU Cipta Kerja Exemption */}
              <div style={{
                background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(15, 23, 42, 0.7) 100%)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                borderRadius: '16px',
                padding: '1.25rem',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.8rem', color: '#34d399', fontWeight: 600 }}>UU Cipta Kerja Portfolio (0% Tax)</span>
                  <ShieldCheck size={18} style={{ color: '#10b981' }} />
                </div>
                <div style={{ fontSize: '1.75rem', fontWeight: 800, marginTop: '0.35rem', color: '#ffffff' }}>
                  Rp {(simResult.regimes.uu_cipta_kerja_0pct.final_portfolio_value_idr / 1e9).toFixed(2)}B
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  Annual Net Dividend: <strong style={{ color: '#34d399' }}>Rp {(simResult.regimes.uu_cipta_kerja_0pct.final_annual_net_dividend_idr / 1e6).toFixed(0)}M/yr</strong> ({simResult.regimes.uu_cipta_kerja_0pct.final_coverage_ratio.toFixed(1)}x expenses)
                </div>
              </div>

              {/* Card 2: Cumulative Tax Saved */}
              <div style={{
                background: 'rgba(15, 23, 42, 0.55)',
                border: '1px solid rgba(56, 189, 248, 0.25)',
                borderRadius: '16px',
                padding: '1.25rem',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.8rem', color: '#38bdf8', fontWeight: 600 }}>Direct Tax Saved (PMK-18 Exemption)</span>
                  <Coins size={18} style={{ color: '#38bdf8' }} />
                </div>
                <div style={{ fontSize: '1.75rem', fontWeight: 800, marginTop: '0.35rem', color: '#38bdf8' }}>
                  Rp {(simResult.comparison.total_tax_saved_via_uu_cipta_kerja_idr / 1e6).toFixed(0)}M
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  Wealth Gap vs 10% drag: <strong style={{ color: '#ffffff' }}>+Rp {(simResult.comparison.tax_drag_wealth_gap_idr / 1e9).toFixed(2)}B</strong>
                </div>
              </div>

              {/* Card 3: Sovereign Runway Freedom Year */}
              <div style={{
                background: 'rgba(15, 23, 42, 0.55)',
                border: '1px solid rgba(234, 179, 8, 0.25)',
                borderRadius: '16px',
                padding: '1.25rem',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.8rem', color: '#facc15', fontWeight: 600 }}>Sovereign Freedom Milestone</span>
                  <Clock size={18} style={{ color: '#eab308' }} />
                </div>
                <div style={{ fontSize: '1.75rem', fontWeight: 800, marginTop: '0.35rem', color: '#facc15' }}>
                  {simResult.comparison.time_to_freedom_uu_cipta_kerja_years
                    ? `Year ${simResult.comparison.time_to_freedom_uu_cipta_kerja_years}`
                    : 'Year 20+'}
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  {simResult.comparison.years_saved_by_reinvestment
                    ? `Reached ${simResult.comparison.years_saved_by_reinvestment} year(s) earlier than 10% tax drag!`
                    : '100% Perpetual Dividend Coverage'}
                </div>
              </div>

              {/* Card 4: Portfolio Weighted Yield & Growth */}
              <div style={{
                background: 'rgba(15, 23, 42, 0.55)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '16px',
                padding: '1.25rem',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 600 }}>Basket Yield & CAGR</span>
                  <TrendingUp size={18} style={{ color: '#a855f7' }} />
                </div>
                <div style={{ fontSize: '1.75rem', fontWeight: 800, marginTop: '0.35rem', color: '#ffffff' }}>
                  {simResult.parameters.weighted_initial_yield_pct.toFixed(2)}%
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  Avg Dividend CAGR: <strong style={{ color: '#a855f7' }}>+{simResult.parameters.weighted_dividend_cagr_pct.toFixed(1)}% / yr</strong>
                </div>
              </div>
            </div>
          )}

          {/* Interactive Runway Controls & Basket Builder */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1.1fr 1fr',
            gap: '1.25rem',
          }}>
            {/* Left: Financial Inputs */}
            <div style={{
              background: 'rgba(15, 23, 42, 0.55)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '16px',
              padding: '1.5rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '1.25rem',
            }}>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Calculator size={18} style={{ color: '#10b981' }} />
                <span>Runway Parameters</span>
              </h3>

              {/* Starting Capital */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '0.4rem' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Initial Portfolio Capital</span>
                  <strong style={{ color: '#ffffff' }}>Rp {(startingCapital / 1e6).toLocaleString()} Million</strong>
                </div>
                <input
                  type="range"
                  min={250_000_000}
                  max={10_000_000_000}
                  step={250_000_000}
                  value={startingCapital}
                  onChange={(e) => setStartingCapital(Number(e.target.value))}
                  style={{ width: '100%', accentColor: '#10b981', cursor: 'pointer' }}
                />
                <div style={{ display: 'flex', gap: '6px', marginTop: '6px' }}>
                  {[500_000_000, 1_000_000_000, 2_500_000_000, 5_000_000_000].map((val) => (
                    <button
                      key={val}
                      onClick={() => setStartingCapital(val)}
                      style={{
                        padding: '2px 8px',
                        fontSize: '0.7rem',
                        borderRadius: '4px',
                        border: startingCapital === val ? '1px solid #10b981' : '1px solid rgba(255, 255, 255, 0.1)',
                        background: startingCapital === val ? 'rgba(16, 185, 129, 0.2)' : 'rgba(255, 255, 255, 0.03)',
                        color: startingCapital === val ? '#34d399' : 'var(--text-secondary)',
                        cursor: 'pointer',
                      }}
                    >
                      Rp {val / 1e9}B
                    </button>
                  ))}
                </div>
              </div>

              {/* Monthly Expense */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '0.4rem' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Target Monthly Living Expense</span>
                  <strong style={{ color: '#ffffff' }}>Rp {(monthlyExpense / 1e6).toLocaleString()} Million / mo</strong>
                </div>
                <input
                  type="range"
                  min={5_000_000}
                  max={50_000_000}
                  step={2_500_000}
                  value={monthlyExpense}
                  onChange={(e) => setMonthlyExpense(Number(e.target.value))}
                  style={{ width: '100%', accentColor: '#38bdf8', cursor: 'pointer' }}
                />
                <div style={{ display: 'flex', gap: '6px', marginTop: '6px' }}>
                  {[10_000_000, 15_000_000, 25_000_000, 40_000_000].map((val) => (
                    <button
                      key={val}
                      onClick={() => setMonthlyExpense(val)}
                      style={{
                        padding: '2px 8px',
                        fontSize: '0.7rem',
                        borderRadius: '4px',
                        border: monthlyExpense === val ? '1px solid #38bdf8' : '1px solid rgba(255, 255, 255, 0.1)',
                        background: monthlyExpense === val ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.03)',
                        color: monthlyExpense === val ? '#38bdf8' : 'var(--text-secondary)',
                        cursor: 'pointer',
                      }}
                    >
                      Rp {val / 1e6}M
                    </button>
                  ))}
                </div>
              </div>

              {/* Horizon & Inflation */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Horizon (Years)</span>
                  <div style={{ display: 'flex', gap: '6px', marginTop: '4px' }}>
                    {[10, 15, 20, 25].map((yr) => (
                      <button
                        key={yr}
                        onClick={() => setProjectionYears(yr)}
                        style={{
                          flex: 1,
                          padding: '0.4rem',
                          borderRadius: '6px',
                          border: projectionYears === yr ? '1px solid #eab308' : '1px solid rgba(255, 255, 255, 0.1)',
                          background: projectionYears === yr ? 'rgba(234, 179, 8, 0.2)' : 'rgba(255, 255, 255, 0.03)',
                          color: projectionYears === yr ? '#facc15' : 'var(--text-secondary)',
                          fontSize: '0.75rem',
                          fontWeight: 700,
                          cursor: 'pointer',
                        }}
                      >
                        {yr}y
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Expense Inflation (CPI)</span>
                  <div style={{ display: 'flex', gap: '6px', marginTop: '4px' }}>
                    {[3.0, 4.0, 5.0].map((inf) => (
                      <button
                        key={inf}
                        onClick={() => setInflationPct(inf)}
                        style={{
                          flex: 1,
                          padding: '0.4rem',
                          borderRadius: '6px',
                          border: inflationPct === inf ? '1px solid #a855f7' : '1px solid rgba(255, 255, 255, 0.1)',
                          background: inflationPct === inf ? 'rgba(168, 85, 247, 0.2)' : 'rgba(255, 255, 255, 0.03)',
                          color: inflationPct === inf ? '#d8b4fe' : 'var(--text-secondary)',
                          fontSize: '0.75rem',
                          fontWeight: 700,
                          cursor: 'pointer',
                        }}
                      >
                        {inf.toFixed(1)}%
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Right: Curated Cash Cow Basket */}
            <div style={{
              background: 'rgba(15, 23, 42, 0.55)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '16px',
              padding: '1.5rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Sparkles size={18} style={{ color: '#eab308' }} />
                  <span>Curated IDX Cash Cows ({selectedCows.length} Selected)</span>
                </h3>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Equal Weight Basket</span>
              </div>

              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                gap: '0.5rem',
                maxHeight: '260px',
                overflowY: 'auto',
                paddingRight: '4px',
              }}>
                {(cashCows.length > 0 ? cashCows : [
                  { ticker: 'BBCA', name: 'Bank Central Asia', dividend_yield_pct: 3.4, dividend_cagr_pct: 11.5, sovereign_tier: 'CORE' },
                  { ticker: 'BBRI', name: 'Bank Rakyat Indonesia', dividend_yield_pct: 6.8, dividend_cagr_pct: 8.0, sovereign_tier: 'HIGH_YIELD' },
                  { ticker: 'BMRI', name: 'Bank Mandiri', dividend_yield_pct: 5.6, dividend_cagr_pct: 9.2, sovereign_tier: 'CORE' },
                  { ticker: 'ASII', name: 'Astra International', dividend_yield_pct: 7.4, dividend_cagr_pct: 6.0, sovereign_tier: 'VALUE' },
                  { ticker: 'ADRO', name: 'Adaro Energy', dividend_yield_pct: 12.5, dividend_cagr_pct: 4.0, sovereign_tier: 'SUPER_YIELD' },
                  { ticker: 'TLKM', name: 'Telkom Indonesia', dividend_yield_pct: 5.8, dividend_cagr_pct: 4.5, sovereign_tier: 'DEFENSIVE' },
                  { ticker: 'PTBA', name: 'Bukit Asam', dividend_yield_pct: 14.2, dividend_cagr_pct: 3.0, sovereign_tier: 'SUPER_YIELD' },
                  { ticker: 'ICBP', name: 'Indofood CBP', dividend_yield_pct: 3.6, dividend_cagr_pct: 8.5, sovereign_tier: 'DEFENSIVE' },
                  { ticker: 'BBNI', name: 'Bank Negara Indonesia', dividend_yield_pct: 5.2, dividend_cagr_pct: 9.0, sovereign_tier: 'CORE' },
                ]).map((cow: any) => {
                  const isChecked = selectedCows.includes(cow.ticker);
                  return (
                    <div
                      key={cow.ticker}
                      onClick={() => toggleCashCow(cow.ticker)}
                      style={{
                        padding: '0.65rem',
                        borderRadius: '10px',
                        border: isChecked ? '1px solid #10b981' : '1px solid rgba(255, 255, 255, 0.08)',
                        background: isChecked ? 'rgba(16, 185, 129, 0.12)' : 'rgba(255, 255, 255, 0.02)',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontWeight: 800, fontSize: '0.9rem', color: isChecked ? '#34d399' : '#ffffff' }}>
                          {cow.ticker}
                        </span>
                        <span style={{ fontSize: '0.75rem', color: '#10b981', fontWeight: 700 }}>
                          {cow.dividend_yield_pct ? `${cow.dividend_yield_pct.toFixed(1)}%` : '—'}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {cow.name}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Statutory Tax Rules & e-Reporting Schedule (PMK-18/PMK.03/2021) */}
          {simResult?.statutory_calendar && (
            <div style={{
              background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.08) 0%, rgba(15, 23, 42, 0.6) 100%)',
              border: '1px solid rgba(56, 189, 248, 0.25)',
              borderRadius: '16px',
              padding: '1.25rem 1.5rem',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '0.5rem' }}>
                <Scale size={20} style={{ color: '#38bdf8' }} />
                <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: '#ffffff' }}>
                  Statutory 3-Year Reinvestment Schedule (PMK No. 18/PMK.03/2021)
                </h4>
              </div>
              <p style={{ margin: '0 0 1rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                Indonesian individual taxpayers (WPOP) enjoy <strong>0% PPh Final (Tax Free)</strong> on domestic dividends under UU Cipta Kerja by fulfilling these statutory deadlines:
              </p>

              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: '0.75rem',
              }}>
                <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '0.85rem', borderRadius: '10px' }}>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Reinvestment Deadline</span>
                  <div style={{ fontSize: '1.05rem', fontWeight: 800, color: '#38bdf8', marginTop: '2px' }}>
                    {simResult.statutory_calendar.reinvestment_deadline}
                  </div>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                    Paling lambat akhir bulan ke-3 tahun pajak berikutnya
                  </span>
                </div>

                <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '0.85rem', borderRadius: '10px' }}>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Holding Release Date</span>
                  <div style={{ fontSize: '1.05rem', fontWeight: 800, color: '#10b981', marginTop: '2px' }}>
                    {simResult.statutory_calendar.holding_release_date}
                  </div>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                    Wajib diinvestasikan minimal 3 tahun pajak berturut-turut
                  </span>
                </div>

                <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '0.85rem', borderRadius: '10px' }}>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Annual Reporting Platform</span>
                  <div style={{ fontSize: '1.05rem', fontWeight: 800, color: '#facc15', marginTop: '2px' }}>
                    e-Reporting DJP Online
                  </div>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                    Laporan Realisasi Investasi tahunan bersamaan SPT
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Multi-Regime Compounding Schedule Table */}
          {simResult && (
            <div style={{
              background: 'rgba(15, 23, 42, 0.55)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '16px',
              padding: '1.25rem',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                <div>
                  <h4 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700 }}>
                    Year-by-Year Sovereign Runway Compounding Projection
                  </h4>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                    Simulating cashflow coverage against living expenses indexed to {inflationPct}% annual CPI inflation
                  </span>
                </div>

                {/* Regime Selector Tabs */}
                <div style={{ display: 'flex', gap: '6px' }}>
                  {[
                    { id: 'uu_cipta_kerja_0pct', label: 'UU Cipta Kerja (0% Tax)', color: '#10b981' },
                    { id: 'standard_tax_drag_10pct', label: 'Standard Drag (10% Tax)', color: '#f59e0b' },
                    { id: 'foreign_tax_drag_20pct', label: 'Foreign (20% Withholding)', color: '#f43f5e' },
                  ].map((r) => (
                    <button
                      key={r.id}
                      onClick={() => setActiveRegimeTab(r.id as any)}
                      style={{
                        padding: '0.35rem 0.75rem',
                        borderRadius: '6px',
                        border: activeRegimeTab === r.id ? `1px solid ${r.color}` : '1px solid rgba(255, 255, 255, 0.1)',
                        background: activeRegimeTab === r.id ? `${r.color}20` : 'rgba(255, 255, 255, 0.03)',
                        color: activeRegimeTab === r.id ? '#ffffff' : 'var(--text-secondary)',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      {r.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Table */}
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', color: 'var(--text-secondary)', textAlign: 'left' }}>
                      <th style={{ padding: '0.65rem 0.5rem' }}>Year</th>
                      <th style={{ padding: '0.65rem 0.5rem' }}>Calendar</th>
                      <th style={{ padding: '0.65rem 0.5rem' }}>Portfolio Capital</th>
                      <th style={{ padding: '0.65rem 0.5rem' }}>Gross Dividend</th>
                      <th style={{ padding: '0.65rem 0.5rem' }}>Tax Deducted</th>
                      <th style={{ padding: '0.65rem 0.5rem' }}>Net Dividend</th>
                      <th style={{ padding: '0.65rem 0.5rem' }}>Living Expense</th>
                      <th style={{ padding: '0.65rem 0.5rem' }}>Runway Coverage</th>
                      <th style={{ padding: '0.65rem 0.5rem', textAlign: 'right' }}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {simResult.regimes[activeRegimeTab].schedule.map((row) => (
                      <tr
                        key={row.simulation_year}
                        style={{
                          borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                          background: row.sovereign_independent ? 'rgba(16, 185, 129, 0.05)' : 'transparent',
                        }}
                      >
                        <td style={{ padding: '0.65rem 0.5rem', fontWeight: 700 }}>Year {row.simulation_year}</td>
                        <td style={{ padding: '0.65rem 0.5rem', color: '#94a3b8' }}>{row.calendar_year}</td>
                        <td style={{ padding: '0.65rem 0.5rem', fontWeight: 600 }}>Rp {(row.portfolio_value_end_idr / 1e9).toFixed(2)}B</td>
                        <td style={{ padding: '0.65rem 0.5rem' }}>Rp {(row.gross_dividend_idr / 1e6).toFixed(0)}M</td>
                        <td style={{ padding: '0.65rem 0.5rem', color: row.tax_paid_idr > 0 ? '#f87171' : '#34d399' }}>
                          {row.tax_paid_idr > 0 ? `-Rp ${(row.tax_paid_idr / 1e6).toFixed(0)}M` : 'Rp 0 (0% Exemption)'}
                        </td>
                        <td style={{ padding: '0.65rem 0.5rem', fontWeight: 700, color: '#38bdf8' }}>
                          Rp {(row.net_dividend_idr / 1e6).toFixed(0)}M
                        </td>
                        <td style={{ padding: '0.65rem 0.5rem', color: 'var(--text-secondary)' }}>
                          Rp {(row.annual_living_expense_idr / 1e6).toFixed(0)}M
                        </td>
                        <td style={{ padding: '0.65rem 0.5rem' }}>
                          <span style={{
                            padding: '2px 6px',
                            borderRadius: '4px',
                            fontWeight: 700,
                            background: row.sovereign_independent ? 'rgba(16, 185, 129, 0.2)' : 'rgba(234, 179, 8, 0.15)',
                            color: row.sovereign_independent ? '#34d399' : '#facc15',
                          }}>
                            {(row.coverage_ratio * 100).toFixed(0)}%
                          </span>
                        </td>
                        <td style={{ padding: '0.65rem 0.5rem', textAlign: 'right' }}>
                          {row.sovereign_independent ? (
                            <span style={{ color: '#10b981', fontWeight: 700 }}>Sovereign Freedom</span>
                          ) : (
                            <span style={{ color: 'var(--text-secondary)' }}>{row.runway_months.toFixed(0)} mos runway</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* VIEW 2: ORIGINAL DIVIDEND TRAP SCREENER */}
      {activeSubTab === 'screener' && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 380px',
          gap: '1.5rem',
          alignItems: 'start',
        }}>
          {/* Left Column: Filterable Screener Table */}
          <div style={{
            background: 'rgba(15, 23, 42, 0.55)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '16px',
            padding: '1.25rem',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700 }}>Upcoming Dividend Opportunities</h3>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  Screened by Net Dividend Yield & Ex-Date Trap Risk
                </span>
              </div>

              {/* Filters */}
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Risk Filter:</span>
                {['ALL', 'SAFE', 'MODERATE', 'HIGH_TRAP'].map((tier) => (
                  <button
                    key={tier}
                    onClick={() => setTrapTier(tier)}
                    style={{
                      padding: '0.25rem 0.55rem',
                      borderRadius: '6px',
                      border: trapTier === tier ? '1px solid #eab308' : '1px solid rgba(255, 255, 255, 0.1)',
                      background: trapTier === tier ? 'rgba(234, 179, 8, 0.2)' : 'rgba(255, 255, 255, 0.04)',
                      color: trapTier === tier ? '#facc15' : 'var(--text-secondary)',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    {tier.replace('_', ' ')}
                  </button>
                ))}
              </div>
            </div>

            {loadingList ? (
              <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                <Loader2 size={32} className="spinning" style={{ margin: '0 auto 0.5rem' }} />
                <p>Loading corporate dividend declarations & yield calculations...</p>
              </div>
            ) : filteredOpportunities.length === 0 ? (
              <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                <Coins size={32} style={{ margin: '0 auto 0.5rem', opacity: 0.5 }} />
                <p>No dividend declarations matching min-yield {minYield}%. Try lowering filter.</p>
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', color: 'var(--text-secondary)', textAlign: 'left' }}>
                      <th style={{ padding: '0.75rem 0.5rem' }}>Ticker</th>
                      <th style={{ padding: '0.75rem 0.5rem' }}>Yield</th>
                      <th style={{ padding: '0.75rem 0.5rem' }}>DPS (IDR)</th>
                      <th style={{ padding: '0.75rem 0.5rem' }}>Trap Risk</th>
                      <th style={{ padding: '0.75rem 0.5rem' }}>Cum Date</th>
                      <th style={{ padding: '0.75rem 0.5rem' }}>Recommendation</th>
                      <th style={{ padding: '0.75rem 0.5rem', textAlign: 'right' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredOpportunities.map((op) => {
                      const isSelected = op.StockCode === selectedTicker;
                      const score = op.TrapScore ?? 50;
                      const riskColor = score <= 35 ? '#10b981' : score <= 60 ? '#f59e0b' : '#f87171';
                      const rec = op.Recommendation || 'HOLD';
                      const recColor = rec.includes('BUY') ? '#10b981' : rec.includes('SELL') ? '#f87171' : '#eab308';

                      return (
                        <tr
                          key={op.StockCode}
                          onClick={() => loadDetail(op.StockCode)}
                          style={{
                            borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                            background: isSelected ? 'rgba(234, 179, 8, 0.08)' : 'transparent',
                            cursor: 'pointer',
                            transition: 'background 0.2s ease',
                          }}
                        >
                          <td style={{ padding: '0.75rem 0.5rem', fontWeight: 700 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span>{op.StockCode}</span>
                              {isSelected && <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#eab308' }} />}
                            </div>
                          </td>
                          <td style={{ padding: '0.75rem 0.5rem', fontWeight: 700, color: '#38bdf8' }}>
                            {op.DividendYield ? `${op.DividendYield.toFixed(1)}%` : '—'}
                          </td>
                          <td style={{ padding: '0.75rem 0.5rem' }}>
                            Rp {op.DPS?.toLocaleString() || '—'}
                          </td>
                          <td style={{ padding: '0.75rem 0.5rem' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <div style={{
                                width: '40px',
                                height: '6px',
                                borderRadius: '3px',
                                background: 'rgba(255, 255, 255, 0.1)',
                                overflow: 'hidden',
                              }}>
                                <div style={{
                                  width: `${Math.min(100, score)}%`,
                                  height: '100%',
                                  background: riskColor,
                                }} />
                              </div>
                              <span style={{ fontSize: '0.75rem', color: riskColor, fontWeight: 700 }}>
                                {score}
                              </span>
                            </div>
                          </td>
                          <td style={{ padding: '0.75rem 0.5rem', color: '#94a3b8' }}>
                            {op.CumDate || '—'}
                          </td>
                          <td style={{ padding: '0.75rem 0.5rem' }}>
                            <span style={{
                              padding: '0.2rem 0.45rem',
                              borderRadius: '4px',
                              fontSize: '0.7rem',
                              fontWeight: 700,
                              background: `${recColor}15`,
                              color: recColor,
                              border: `1px solid ${recColor}30`,
                            }}>
                              {rec}
                            </span>
                          </td>
                          <td style={{ padding: '0.75rem 0.5rem', textAlign: 'right' }}>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onSelectStock(op.StockCode);
                              }}
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                padding: '0.3rem 0.6rem',
                                borderRadius: '6px',
                                border: '1px solid rgba(255, 255, 255, 0.1)',
                                background: 'rgba(255, 255, 255, 0.05)',
                                color: 'var(--text-primary)',
                                fontSize: '0.75rem',
                                cursor: 'pointer',
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

          {/* Right Column: Deep Trap Analysis Card */}
          <div style={{
            background: 'rgba(15, 23, 42, 0.55)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '16px',
            padding: '1.5rem',
            position: 'sticky',
            top: '1rem',
          }}>
            {loadingDetail ? (
              <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                <Loader2 size={32} className="spinning" style={{ margin: '0 auto 0.5rem' }} />
                <p>Analyzing forensic dividend risk for {selectedTicker}...</p>
              </div>
            ) : analysis ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.3rem', fontWeight: 800 }}>{analysis.ticker}</h3>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      Dividend Decision Profile
                    </span>
                  </div>
                  <div style={{
                    padding: '0.35rem 0.75rem',
                    borderRadius: '8px',
                    fontWeight: 800,
                    fontSize: '0.85rem',
                    background: analysis.recommendation?.includes('BUY') ? 'rgba(16, 185, 129, 0.2)' : analysis.recommendation?.includes('SELL') ? 'rgba(239, 68, 68, 0.2)' : 'rgba(234, 179, 8, 0.2)',
                    color: analysis.recommendation?.includes('BUY') ? '#10b981' : analysis.recommendation?.includes('SELL') ? '#ef4444' : '#eab308',
                    border: `1px solid ${analysis.recommendation?.includes('BUY') ? 'rgba(16, 185, 129, 0.4)' : analysis.recommendation?.includes('SELL') ? 'rgba(239, 68, 68, 0.4)' : 'rgba(234, 179, 8, 0.4)'}`,
                  }}>
                    {analysis.recommendation || 'HOLD'}
                  </div>
                </div>

                {/* Score breakdown */}
                <div style={{
                  background: 'rgba(255, 255, 255, 0.02)',
                  padding: '1rem',
                  borderRadius: '12px',
                  border: '1px solid rgba(255, 255, 255, 0.05)',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.85rem' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Dividend Trap Risk Score</span>
                    <strong style={{ color: (analysis.trap_score ?? 50) > 60 ? '#ef4444' : '#10b981' }}>
                      {analysis.trap_score ?? 50}/100 ({analysis.trap_level || 'MODERATE'})
                    </strong>
                  </div>
                  <div style={{
                    width: '100%',
                    height: '8px',
                    borderRadius: '4px',
                    background: 'rgba(255, 255, 255, 0.1)',
                    overflow: 'hidden',
                  }}>
                    <div style={{
                      width: `${analysis.trap_score ?? 50}%`,
                      height: '100%',
                      background: (analysis.trap_score ?? 50) > 60 ? '#ef4444' : (analysis.trap_score ?? 50) > 35 ? '#f59e0b' : '#10b981',
                    }} />
                  </div>
                </div>

                {/* Tactical playbook */}
                <div style={{
                  background: 'rgba(255, 255, 255, 0.02)',
                  padding: '1rem',
                  borderRadius: '12px',
                  border: '1px solid rgba(255, 255, 255, 0.05)',
                }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#38bdf8' }}>Tactical Execution Playbook</span>
                  <p style={{ margin: '0.5rem 0 0', fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                    {analysis.playbook?.best_strategy
                      ? `Recommended Strategy: ${analysis.playbook.best_strategy}. Historical returns indicate superior risk-adjusted alpha by exiting prior to Ex-Date markdown.`
                      : 'Accumulate selectively. Sustainable payout with institutional liquidity support.'}
                  </p>
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
      )}
    </div>
  );
};
