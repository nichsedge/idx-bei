import React, { useEffect, useRef, useState } from 'react';
import { 
  PlayCircle, 
  ShieldAlert, 
  Loader2,
  Download
} from 'lucide-react';
import { 
  createChart, 
  LineSeries, 
  type IChartApi, 
  type ISeriesApi, 
  type LineData, 
  type Time 
} from 'lightweight-charts';
import type { BacktestParams, BacktestResponse } from '../types';
import { runBacktest } from '../services/api';

interface BacktesterTabProps {
  onSelectStock: (ticker: string) => void;
}

export const BacktesterTab: React.FC<BacktesterTabProps> = ({ onSelectStock }) => {
  const [strategy, setStrategy] = useState<BacktestParams['strategy']>('foreign_flow');
  const [holdingDays, setHoldingDays] = useState<number>(20);
  const [topN, setTopN] = useState<number>(10);
  const [stopLoss, setStopLoss] = useState<number>(7);
  const [takeProfit, setTakeProfit] = useState<number>(15);
  const [positionSizing, setPositionSizing] = useState<'equal_weight' | 'volatility_parity'>('equal_weight');

  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BacktestResponse | null>(null);

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<IChartApi | null>(null);
  const lineSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  const handleRun = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await runBacktest({
        strategy,
        holding_days: holdingDays,
        top_n: topN,
        min_turnover_rp: 1_000_000_000,
        stop_loss_pct: stopLoss > 0 ? stopLoss : undefined,
        take_profit_pct: takeProfit > 0 ? takeProfit : undefined,
        position_sizing: positionSizing,
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message || 'Backtest execution failed');
    } finally {
      setLoading(false);
    }
  };

  const exportTradesCSV = () => {
    if (!result?.trades || result.trades.length === 0) return;
    const headers = ['Ticker', 'Entry Date', 'Exit Date', 'Entry Price', 'Exit Price', 'Return (%)', 'Weight', 'Weighted Return'];
    const rows = result.trades.map((t) => [
      t.StockCode,
      t.EntryDate,
      t.ExitDate,
      t.EntryPrice,
      t.ExitPrice,
      t.ReturnPct,
      t.Weight ?? '',
      t.WeightedReturn ?? '',
    ]);
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `backtest_${strategy}_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  useEffect(() => {
    handleRun();
  }, []);

  // Render or update equity curve chart
  useEffect(() => {
    const container = chartContainerRef.current;
    if (!container || !result || !result.equity_curve || result.equity_curve.length === 0) return;

    container.innerHTML = '';

    const chart = createChart(container, {
      width: container.clientWidth,
      height: 360,
      layout: {
        background: { color: '#070a13' },
        textColor: '#9ca3af',
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.05)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.05)' },
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: 'rgba(255, 255, 255, 0.1)' },
      timeScale: { borderColor: 'rgba(255, 255, 255, 0.1)' },
    });
    chartInstanceRef.current = chart;

    const lineSeries = chart.addSeries(LineSeries, {
      color: '#10b981',
      lineWidth: 2,
      priceFormat: {
        type: 'custom',
        formatter: (p: number) => p.toFixed(2),
      },
    });
    lineSeriesRef.current = lineSeries;

    const formattedPoints: LineData<Time>[] = result.equity_curve.map((p) => ({
      time: p.time as Time,
      value: p.value,
    }));

    lineSeries.setData(formattedPoints);
    chart.timeScale().fitContent();

    const handleResize = () => {
      if (container && chart) {
        chart.applyOptions({ width: container.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [result]);

  const metrics = result?.metrics;

  return (
    <div className="backtester-tab" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Banner & Control Deck */}
      <div style={{
        background: 'rgba(15, 23, 42, 0.65)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '16px',
        padding: '1.5rem',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
              <PlayCircle size={28} style={{ color: '#10b981' }} />
              <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 700 }}>Quantitative Strategy Simulator</h2>
            </div>
            <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
              Simulate historical execution across 145,000+ daily bars with stop loss, profit targets, and benchmark alpha calculation.
            </p>
          </div>

          <button
            onClick={handleRun}
            disabled={loading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.75rem 1.5rem',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
              color: '#ffffff',
              fontWeight: 700,
              fontSize: '0.9rem',
              border: 'none',
              cursor: 'pointer',
              boxShadow: '0 4px 14px rgba(16, 185, 129, 0.3)',
            }}
          >
            {loading ? <Loader2 size={18} className="spinning" /> : <PlayCircle size={18} />}
            <span>{loading ? 'Simulating...' : 'Run Simulation'}</span>
          </button>
        </div>

        {/* Parameter Inputs */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '1rem',
          paddingTop: '1rem',
          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
        }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
              Strategy Alpha Engine
            </label>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value as any)}
              className="filter-select"
              style={{ width: '100%', padding: '0.5rem', borderRadius: '8px' }}
            >
              <option value="foreign_flow">Foreign Flow Accumulation</option>
              <option value="stealth_accumulation">Wyckoff Stealth Accumulation (Smart Money)</option>
              <option value="bandarmology">Bandarmology Momentum</option>
              <option value="composite_alpha">Composite Multi-Factor Alpha</option>
              <option value="sharia_value">Sharia Value Screen</option>
              <option value="dividend_arbitrage">Dividend Arbitrage (3-Way)</option>
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
              Holding Period (Sessions)
            </label>
            <input
              type="number"
              value={holdingDays}
              onChange={(e) => setHoldingDays(Number(e.target.value))}
              min={5}
              max={120}
              className="filter-input"
              style={{ width: '100%', padding: '0.5rem', borderRadius: '8px' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
              Top-N Basket Size
            </label>
            <input
              type="number"
              value={topN}
              onChange={(e) => setTopN(Number(e.target.value))}
              min={1}
              max={30}
              className="filter-input"
              style={{ width: '100%', padding: '0.5rem', borderRadius: '8px' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
              Stop Loss (%)
            </label>
            <input
              type="number"
              value={stopLoss}
              onChange={(e) => setStopLoss(Number(e.target.value))}
              min={0}
              max={30}
              className="filter-input"
              style={{ width: '100%', padding: '0.5rem', borderRadius: '8px' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
              Take Profit (%)
            </label>
            <input
              type="number"
              value={takeProfit}
              onChange={(e) => setTakeProfit(Number(e.target.value))}
              min={0}
              max={100}
              className="filter-input"
              style={{ width: '100%', padding: '0.5rem', borderRadius: '8px' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>
              Position Sizing Mode
            </label>
            <select
              value={positionSizing}
              onChange={(e) => setPositionSizing(e.target.value as any)}
              className="filter-select"
              style={{ width: '100%', padding: '0.5rem', borderRadius: '8px' }}
            >
              <option value="equal_weight">Equal Weight (1/N)</option>
              <option value="volatility_parity">Volatility Parity (Inverse Vol)</option>
            </select>
          </div>
        </div>
      </div>

      {error && (
        <div className="error-banner" style={{ padding: '1.25rem' }}>
          <ShieldAlert size={24} />
          <div>
            <h4 style={{ margin: 0 }}>Simulator Error</h4>
            <p style={{ margin: 0, fontSize: '0.85rem' }}>{error}</p>
          </div>
        </div>
      )}

      {/* KPI Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: '1rem',
      }}>
        <div className="stat-card" style={{ background: 'rgba(15, 23, 42, 0.55)', padding: '1.25rem', borderRadius: '14px' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Total Strategy Return</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, marginTop: '0.35rem', color: (metrics?.total_return_pct ?? 0) >= 0 ? '#10b981' : '#ef4444' }}>
            {metrics?.total_return_pct !== undefined ? `${metrics.total_return_pct > 0 ? '+' : ''}${metrics.total_return_pct}%` : '—'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
            Cumulative portfolio return
          </div>
        </div>

        <div className="stat-card" style={{ background: 'rgba(15, 23, 42, 0.55)', padding: '1.25rem', borderRadius: '14px' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Sharpe Ratio</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, marginTop: '0.35rem', color: '#38bdf8' }}>
            {metrics?.sharpe_ratio !== undefined ? metrics.sharpe_ratio : '—'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
            Risk-adjusted excess return
          </div>
        </div>

        <div className="stat-card" style={{ background: 'rgba(15, 23, 42, 0.55)', padding: '1.25rem', borderRadius: '14px' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Max Drawdown</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, marginTop: '0.35rem', color: '#ef4444' }}>
            {metrics?.max_drawdown_pct !== undefined ? `-${Math.abs(metrics.max_drawdown_pct)}%` : '—'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
            Peak-to-trough decline
          </div>
        </div>

        <div className="stat-card" style={{ background: 'rgba(15, 23, 42, 0.55)', padding: '1.25rem', borderRadius: '14px' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Win Rate</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, marginTop: '0.35rem', color: '#facc15' }}>
            {metrics?.win_rate_pct !== undefined ? `${metrics.win_rate_pct}%` : '—'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
            Winning trades percentage
          </div>
        </div>

        <div className="stat-card" style={{ background: 'rgba(15, 23, 42, 0.55)', padding: '1.25rem', borderRadius: '14px' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Benchmark Alpha</div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, marginTop: '0.35rem', color: (metrics?.alpha_pct ?? 0) >= 0 ? '#10b981' : '#ef4444' }}>
            {metrics?.alpha_pct !== undefined ? `${metrics.alpha_pct > 0 ? '+' : ''}${metrics.alpha_pct}%` : '—'}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
            Outperformance vs IHSG
          </div>
        </div>
      </div>

      {/* 3-Way Dividend Arbitrage Comparison Matrix */}
      {strategy === 'dividend_arbitrage' && (metrics?.strategy_a_naive_hold || metrics?.strategy_b_precum_exit || metrics?.strategy_c_postex_rebuy) && (
        <div style={{
          background: 'rgba(15, 23, 42, 0.65)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(234, 179, 8, 0.25)',
          borderRadius: '16px',
          padding: '1.5rem',
        }}>
          <div style={{ marginBottom: '1.25rem' }}>
            <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 700, color: '#facc15' }}>
              3-Way Dividend Capture Arbitrage Comparison ({metrics?.total_events || 0} Dividend Events)
            </h3>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Empirical historical simulation: Hold through Ex-Date vs Pre-Cum Capital Gain Exit vs Post-Ex Rebuy
            </span>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '1rem',
          }}>
            {/* Strategy A */}
            <div style={{
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '12px',
              padding: '1.25rem',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 700, fontSize: '0.9rem', color: '#f8fafc' }}>Strategy A: Naive Hold</span>
                <span style={{ fontSize: '0.7rem', padding: '2px 6px', borderRadius: '4px', background: 'rgba(255,255,255,0.08)', color: 'var(--text-secondary)' }}>Collects Div</span>
              </div>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '0.35rem 0 0.75rem' }}>
                Hold through Ex-Date, pay 10% dividend tax, suffer Ex-Date drop.
              </p>
              <div style={{ fontSize: '1.5rem', fontWeight: 800, color: (metrics.strategy_a_naive_hold?.total_return_pct ?? 0) >= 0 ? '#10b981' : '#ef4444' }}>
                {metrics.strategy_a_naive_hold?.total_return_pct !== undefined ? `${metrics.strategy_a_naive_hold.total_return_pct > 0 ? '+' : ''}${metrics.strategy_a_naive_hold.total_return_pct}%` : '—'}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginTop: '0.5rem', color: 'var(--text-secondary)' }}>
                <span>Win Rate: {metrics.strategy_a_naive_hold?.win_rate_pct ?? '—'}%</span>
                <span>Max DD: -{Math.abs(metrics.strategy_a_naive_hold?.max_drawdown_pct ?? 0)}%</span>
              </div>
            </div>

            {/* Strategy B */}
            <div style={{
              background: 'rgba(56, 189, 248, 0.04)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              borderRadius: '12px',
              padding: '1.25rem',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 700, fontSize: '0.9rem', color: '#38bdf8' }}>Strategy B: Pre-Cum Exit</span>
                <span style={{ fontSize: '0.7rem', padding: '2px 6px', borderRadius: '4px', background: 'rgba(56, 189, 248, 0.2)', color: '#38bdf8' }}>Capital Gain</span>
              </div>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '0.35rem 0 0.75rem' }}>
                Sell on Cum Date close, avoid Ex-Date drop & dividend tax.
              </p>
              <div style={{ fontSize: '1.5rem', fontWeight: 800, color: (metrics.strategy_b_precum_exit?.total_return_pct ?? 0) >= 0 ? '#10b981' : '#ef4444' }}>
                {metrics.strategy_b_precum_exit?.total_return_pct !== undefined ? `${metrics.strategy_b_precum_exit.total_return_pct > 0 ? '+' : ''}${metrics.strategy_b_precum_exit.total_return_pct}%` : '—'}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginTop: '0.5rem', color: 'var(--text-secondary)' }}>
                <span>Win Rate: {metrics.strategy_b_precum_exit?.win_rate_pct ?? '—'}%</span>
                <span>Max DD: -{Math.abs(metrics.strategy_b_precum_exit?.max_drawdown_pct ?? 0)}%</span>
              </div>
            </div>

            {/* Strategy C */}
            <div style={{
              background: 'rgba(16, 185, 129, 0.04)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              borderRadius: '12px',
              padding: '1.25rem',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 700, fontSize: '0.9rem', color: '#34d399' }}>Strategy C: Post-Ex Rebuy</span>
                <span style={{ fontSize: '0.7rem', padding: '2px 6px', borderRadius: '4px', background: 'rgba(16, 185, 129, 0.2)', color: '#34d399' }}>Dip Rebuy</span>
              </div>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '0.35rem 0 0.75rem' }}>
                Enter 2 days after Ex-Date after panic settles, hold 10 sessions.
              </p>
              <div style={{ fontSize: '1.5rem', fontWeight: 800, color: (metrics.strategy_c_postex_rebuy?.total_return_pct ?? 0) >= 0 ? '#10b981' : '#ef4444' }}>
                {metrics.strategy_c_postex_rebuy?.total_return_pct !== undefined ? `${metrics.strategy_c_postex_rebuy.total_return_pct > 0 ? '+' : ''}${metrics.strategy_c_postex_rebuy.total_return_pct}%` : '—'}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginTop: '0.5rem', color: 'var(--text-secondary)' }}>
                <span>Win Rate: {metrics.strategy_c_postex_rebuy?.win_rate_pct ?? '—'}%</span>
                <span>Max DD: -{Math.abs(metrics.strategy_c_postex_rebuy?.max_drawdown_pct ?? 0)}%</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Equity Curve & Trades */}
      <div style={{
        background: 'rgba(15, 23, 42, 0.55)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '16px',
        padding: '1.5rem',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700 }}>Portfolio Equity Curve (Base 100)</h3>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Compounded portfolio growth over time
            </span>
          </div>
        </div>

        <div
          ref={chartContainerRef}
          style={{ width: '100%', height: '360px', position: 'relative', borderRadius: '8px', overflow: 'hidden' }}
        />
      </div>

      {/* Simulated Trades Table */}
      {result && result.trades && result.trades.length > 0 && (
        <div style={{
          background: 'rgba(15, 23, 42, 0.55)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '16px',
          padding: '1.5rem',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700 }}>
                Simulated Trades Log ({result.trades.length})
              </h3>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                Showing up to 50 recent executions
              </span>
            </div>
            <button
              onClick={exportTradesCSV}
              className="filter-btn"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.45rem 0.9rem',
                fontSize: '0.8rem',
                cursor: 'pointer',
                background: 'rgba(56, 189, 248, 0.1)',
                border: '1px solid rgba(56, 189, 248, 0.3)',
                color: '#38bdf8',
                borderRadius: '8px',
                fontWeight: 600,
              }}
            >
              <Download size={15} />
              <span>Export Trades CSV</span>
            </button>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', color: 'var(--text-secondary)', textAlign: 'left' }}>
                  <th style={{ padding: '0.75rem 0.5rem' }}>Ticker</th>
                  <th style={{ padding: '0.75rem 0.5rem' }}>Entry Date</th>
                  <th style={{ padding: '0.75rem 0.5rem' }}>Exit Date</th>
                  <th style={{ padding: '0.75rem 0.5rem' }}>Entry Price</th>
                  <th style={{ padding: '0.75rem 0.5rem' }}>Exit Price</th>
                  <th style={{ padding: '0.75rem 0.5rem' }}>Weight</th>
                  <th style={{ padding: '0.75rem 0.5rem', textAlign: 'right' }}>Return (%)</th>
                </tr>
              </thead>
              <tbody>
                {result.trades.slice(0, 50).map((t, idx) => (
                  <tr
                    key={`${t.StockCode}-${t.EntryDate}-${idx}`}
                    onClick={() => onSelectStock(t.StockCode)}
                    style={{
                      borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                      cursor: 'pointer',
                    }}
                    className="table-row-hover"
                  >
                    <td style={{ padding: '0.75rem 0.5rem', fontWeight: 700, color: '#38bdf8' }}>{t.StockCode}</td>
                    <td style={{ padding: '0.75rem 0.5rem', color: 'var(--text-secondary)' }}>{t.EntryDate}</td>
                    <td style={{ padding: '0.75rem 0.5rem', color: 'var(--text-secondary)' }}>{t.ExitDate}</td>
                    <td style={{ padding: '0.75rem 0.5rem' }}>Rp {t.EntryPrice.toLocaleString()}</td>
                    <td style={{ padding: '0.75rem 0.5rem' }}>Rp {t.ExitPrice.toLocaleString()}</td>
                    <td style={{ padding: '0.75rem 0.5rem', color: 'var(--text-secondary)' }}>
                      {t.Weight !== undefined ? `${(t.Weight * 100).toFixed(1)}%` : '—'}
                    </td>
                    <td style={{ padding: '0.75rem 0.5rem', textAlign: 'right', fontWeight: 700, color: t.ReturnPct >= 0 ? '#10b981' : '#ef4444' }}>
                      {t.ReturnPct >= 0 ? `+${t.ReturnPct}%` : `${t.ReturnPct}%`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
