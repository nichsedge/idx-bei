import React, { useEffect, useState } from 'react';
import { 
  Radar, 
  Eye, 
  RotateCw, 
  ArrowRight, 
  Loader2, 
  Users,
  Bell,
  Send,
  CheckCircle2,
  AlertOctagon,
  Radio
} from 'lucide-react';
import type { StealthAnomaly, StealthAccumulationResponse, BandarAnomalyAlertItem } from '../types';
import { fetchStealthAccumulation, fetchBandarAnomalies, testBandarTelegramAlert } from '../services/api';

interface BandarmologyTabProps {
  onSelectStock: (ticker: string) => void;
}

export const BandarmologyTab: React.FC<BandarmologyTabProps> = ({ onSelectStock }) => {
  const [activeSubView, setActiveSubView] = useState<'radar' | 'anomalies'>('radar');
  const [data, setData] = useState<StealthAccumulationResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [, setError] = useState<string | null>(null);
  const [filterSignal, setFilterSignal] = useState<string>('ALL');
  const [filterPhase, setFilterPhase] = useState<string>('ALL');
  const [lookbackDays, setLookbackDays] = useState<number>(5);

  // Anomaly Notifier state
  const [anomalies, setAnomalies] = useState<BandarAnomalyAlertItem[]>([]);
  const [loadingAnomalies, setLoadingAnomalies] = useState<boolean>(false);
  const [sigmaThreshold, setSigmaThreshold] = useState<number>(3.0);
  const [filterAnomalyType, setFilterAnomalyType] = useState<string>('ALL');
  const [testingTelegram, setTestingTelegram] = useState<boolean>(false);
  const [telegramStatus, setTelegramStatus] = useState<{ ok: boolean; msg: string } | null>(null);

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

  const loadAnomalies = async (threshold = sigmaThreshold) => {
    setLoadingAnomalies(true);
    try {
      const res = await fetchBandarAnomalies(threshold);
      setAnomalies(res);
    } catch (err: any) {
      console.warn('Could not load 3σ anomalies:', err);
    } finally {
      setLoadingAnomalies(false);
    }
  };

  const handleTestTelegram = async () => {
    setTestingTelegram(true);
    setTelegramStatus(null);
    try {
      const res = await testBandarTelegramAlert();
      if (res.ok) {
        setTelegramStatus({ ok: true, msg: `Alert successfully sent to chat ${res.chat_id || ''}!` });
      } else {
        setTelegramStatus({
          ok: false,
          msg: res.error || 'Failed: Ensure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set in env.',
        });
      }
    } catch (err: any) {
      setTelegramStatus({
        ok: false,
        msg: err.message || 'Failed to ping Telegram webhook.',
      });
    } finally {
      setTestingTelegram(false);
    }
  };

  useEffect(() => {
    loadData(lookbackDays);
  }, [lookbackDays]);

  useEffect(() => {
    if (activeSubView === 'anomalies') {
      loadAnomalies(sigmaThreshold);
    }
  }, [activeSubView, sigmaThreshold]);

  const radarAnomalies: StealthAnomaly[] = data?.anomalies || [];
  const phaseACount = radarAnomalies.filter((a) => a.WyckoffPhase?.startsWith('Phase A')).length;
  const phaseBCount = radarAnomalies.filter((a) => a.WyckoffPhase?.startsWith('Phase B')).length;
  const phaseCCount = radarAnomalies.filter((a) => a.WyckoffPhase?.startsWith('Phase C')).length;
  const phaseDCount = radarAnomalies.filter((a) => a.WyckoffPhase?.startsWith('Phase D')).length;

  const filteredRadarAnomalies = radarAnomalies.filter((a) => {
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

  // 3σ Anomaly counts
  const filteredAnomalies = anomalies.filter((a) => {
    if (filterAnomalyType === 'ALL') return true;
    return a.anomaly_type === filterAnomalyType;
  });

  const countAbsorption = anomalies.filter((a) => a.anomaly_type === 'INSTITUTIONAL_ABSORPTION').length;
  const countMarkup = anomalies.filter((a) => a.anomaly_type === 'INSTITUTIONAL_MARKUP').length;
  const countTrap = anomalies.filter((a) => a.anomaly_type === 'RETAIL_TRAP_DISTRIBUTION').length;
  const countDump = anomalies.filter((a) => a.anomaly_type === 'INSTITUTIONAL_DUMP').length;

  return (
    <div className="bandarmology-tab" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Banner & Sub-View Switcher */}
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
            <Radar size={28} style={{ color: activeSubView === 'anomalies' ? '#f43f5e' : '#38bdf8' }} />
            <h2 style={{ margin: 0, fontSize: '1.35rem', fontWeight: 700 }}>
              {activeSubView === 'anomalies' ? 'Bandar / Institutional Flow 3σ Notifier' : 'Bandarmology & Institutional Radar'}
            </h2>
          </div>
          <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            {activeSubView === 'anomalies'
              ? 'Real-time statistical outlier engine flagging sudden institutional absorption (>3σ) with private Telegram alerts.'
              : 'Unmask quiet institutional accumulation, retail liquidity traps, and broker dominance shifts across IDX.'}
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {/* Sub-view switcher */}
          <div style={{
            display: 'flex',
            background: 'rgba(0, 0, 0, 0.3)',
            padding: '4px',
            borderRadius: '10px',
            border: '1px solid rgba(255, 255, 255, 0.08)',
          }}>
            <button
              onClick={() => setActiveSubView('radar')}
              style={{
                padding: '0.45rem 0.9rem',
                borderRadius: '8px',
                border: 'none',
                background: activeSubView === 'radar' ? '#38bdf8' : 'transparent',
                color: activeSubView === 'radar' ? '#0f172a' : 'var(--text-secondary)',
                fontWeight: 700,
                fontSize: '0.8rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                transition: 'all 0.2s ease',
              }}
            >
              <Eye size={14} />
              <span>Wyckoff Radar</span>
            </button>
            <button
              onClick={() => setActiveSubView('anomalies')}
              style={{
                padding: '0.45rem 0.9rem',
                borderRadius: '8px',
                border: 'none',
                background: activeSubView === 'anomalies' ? '#f43f5e' : 'transparent',
                color: activeSubView === 'anomalies' ? '#ffffff' : 'var(--text-secondary)',
                fontWeight: 700,
                fontSize: '0.8rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                transition: 'all 0.2s ease',
              }}
            >
              <Bell size={14} />
              <span>🚨 3σ Anomaly Notifier</span>
            </button>
          </div>

          <button
            onClick={() => (activeSubView === 'anomalies' ? loadAnomalies() : loadData())}
            disabled={loading || loadingAnomalies}
            className="filter-btn"
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.55rem 1rem', cursor: 'pointer', fontSize: '0.8rem' }}
          >
            <RotateCw size={14} className={loading || loadingAnomalies ? 'spinning' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* VIEW 1: 3σ ANOMALY NOTIFIER */}
      {activeSubView === 'anomalies' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Daemon Status & Telegram Banner */}
          <div style={{
            background: 'linear-gradient(135deg, rgba(244, 63, 94, 0.1) 0%, rgba(15, 23, 42, 0.7) 100%)',
            border: '1px solid rgba(244, 63, 94, 0.25)',
            borderRadius: '16px',
            padding: '1.25rem 1.5rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '1rem',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <div style={{
                width: '42px',
                height: '42px',
                borderRadius: '10px',
                background: 'rgba(244, 63, 94, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#f43f5e',
              }}>
                <Radio size={22} className="pulse" />
              </div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '1rem', fontWeight: 700, color: '#ffffff' }}>
                    Background Daemon & Telegram Telemetry
                  </span>
                  <span style={{
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    padding: '2px 8px',
                    borderRadius: '999px',
                    background: 'rgba(16, 185, 129, 0.2)',
                    color: '#34d399',
                    border: '1px solid rgba(16, 185, 129, 0.3)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}>
                    <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#34d399' }} />
                    DAEMON READY (idx notify --daemon)
                  </span>
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                  Alerts fire when an institutional volume absorption or flow anomaly crosses <strong style={{ color: '#f43f5e' }}>{sigmaThreshold}σ</strong> (Z &ge; {sigmaThreshold.toFixed(1)}).
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <button
                onClick={handleTestTelegram}
                disabled={testingTelegram}
                style={{
                  background: 'rgba(56, 189, 248, 0.15)',
                  border: '1px solid rgba(56, 189, 248, 0.35)',
                  color: '#38bdf8',
                  padding: '0.5rem 1rem',
                  borderRadius: '8px',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                {testingTelegram ? <Loader2 size={14} className="spinning" /> : <Send size={14} />}
                <span>Test Telegram Webhook</span>
              </button>

              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Cutoff:</span>
                {[2.0, 3.0, 4.0].map((th) => (
                  <button
                    key={th}
                    onClick={() => setSigmaThreshold(th)}
                    style={{
                      padding: '0.35rem 0.65rem',
                      borderRadius: '6px',
                      border: sigmaThreshold === th ? '1px solid #f43f5e' : '1px solid rgba(255, 255, 255, 0.1)',
                      background: sigmaThreshold === th ? 'rgba(244, 63, 94, 0.25)' : 'rgba(255, 255, 255, 0.03)',
                      color: sigmaThreshold === th ? '#ffffff' : 'var(--text-secondary)',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                  >
                    {th.toFixed(1)}σ
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Telegram Status feedback */}
          {telegramStatus && (
            <div style={{
              padding: '0.75rem 1rem',
              borderRadius: '10px',
              background: telegramStatus.ok ? 'rgba(16, 185, 129, 0.15)' : 'rgba(244, 63, 94, 0.15)',
              border: `1px solid ${telegramStatus.ok ? '#10b981' : '#f43f5e'}`,
              color: telegramStatus.ok ? '#34d399' : '#fb7185',
              fontSize: '0.8rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}>
              {telegramStatus.ok ? <CheckCircle2 size={16} /> : <AlertOctagon size={16} />}
              <span>{telegramStatus.msg}</span>
            </div>
          )}

          {/* Anomaly Category KPI Cards */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '1rem',
          }}>
            {[
              {
                id: 'INSTITUTIONAL_ABSORPTION',
                label: 'Whale Absorption',
                count: countAbsorption,
                desc: 'Flat price, volume >3σ, smart buying',
                color: '#10b981',
                badge: '🐋 ABSORPTION',
              },
              {
                id: 'INSTITUTIONAL_MARKUP',
                label: 'Bullish Markup',
                count: countMarkup,
                desc: 'Aggressive buy aggression, breakout',
                color: '#38bdf8',
                badge: '🚀 MARKUP',
              },
              {
                id: 'RETAIL_TRAP_DISTRIBUTION',
                label: 'Retail Trap Warning',
                count: countTrap,
                desc: 'Price up, smart money exit orders',
                color: '#f59e0b',
                badge: '🪤 RETAIL TRAP',
              },
              {
                id: 'INSTITUTIONAL_DUMP',
                label: 'Massive Dump',
                count: countDump,
                desc: 'Severe foreign flow liquidation',
                color: '#f43f5e',
                badge: '📉 DUMP',
              },
            ].map((card) => {
              const active = filterAnomalyType === card.id;
              return (
                <div
                  key={card.id}
                  onClick={() => setFilterAnomalyType(active ? 'ALL' : card.id)}
                  style={{
                    background: active ? `${card.color}15` : 'rgba(15, 23, 42, 0.55)',
                    border: `1px solid ${active ? card.color : 'rgba(255, 255, 255, 0.08)'}`,
                    borderRadius: '14px',
                    padding: '1.1rem',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.8rem', fontWeight: 700, color: card.color }}>{card.label}</span>
                    <span style={{
                      fontSize: '1.1rem',
                      fontWeight: 800,
                      color: '#ffffff',
                    }}>
                      {card.count}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    {card.desc}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Filter Pills */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Filter Pattern:</span>
            {['ALL', 'INSTITUTIONAL_ABSORPTION', 'INSTITUTIONAL_MARKUP', 'RETAIL_TRAP_DISTRIBUTION', 'INSTITUTIONAL_DUMP'].map((type) => (
              <button
                key={type}
                onClick={() => setFilterAnomalyType(type)}
                style={{
                  padding: '0.35rem 0.75rem',
                  borderRadius: '20px',
                  border: filterAnomalyType === type ? '1px solid #38bdf8' : '1px solid rgba(255, 255, 255, 0.1)',
                  background: filterAnomalyType === type ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.03)',
                  color: filterAnomalyType === type ? '#ffffff' : 'var(--text-secondary)',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                {type === 'ALL' ? `ALL ANOMALIES (${anomalies.length})` : type.replace(/_/g, ' ')}
              </button>
            ))}
          </div>

          {/* Anomalies List / Cards */}
          {loadingAnomalies ? (
            <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
              <Loader2 size={32} className="spinning" style={{ margin: '0 auto 0.75rem' }} />
              <p>Evaluating multi-session Z-scores and institutional absorption vectors...</p>
            </div>
          ) : filteredAnomalies.length === 0 ? (
            <div style={{
              padding: '3rem',
              textAlign: 'center',
              background: 'rgba(15, 23, 42, 0.4)',
              borderRadius: '16px',
              border: '1px solid rgba(255, 255, 255, 0.06)',
            }}>
              <CheckCircle2 size={32} style={{ color: '#10b981', margin: '0 auto 0.5rem', opacity: 0.8 }} />
              <h4 style={{ margin: '0 0 0.5rem', fontSize: '1rem' }}>No Anomalies for Selected Filter</h4>
              <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                No stocks currently exceed the {sigmaThreshold}σ anomaly threshold for this pattern. Try lowering the threshold to 2.0σ.
              </p>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '1rem' }}>
              {filteredAnomalies.map((a) => {
                const isAbs = a.anomaly_type === 'INSTITUTIONAL_ABSORPTION';
                const isMarkup = a.anomaly_type === 'INSTITUTIONAL_MARKUP';
                const isTrap = a.anomaly_type === 'RETAIL_TRAP_DISTRIBUTION';
                const color = isAbs ? '#10b981' : isMarkup ? '#38bdf8' : isTrap ? '#f59e0b' : '#f43f5e';

                return (
                  <div
                    key={a.ticker}
                    style={{
                      background: 'rgba(15, 23, 42, 0.65)',
                      border: `1px solid ${color}40`,
                      borderRadius: '14px',
                      padding: '1.25rem',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.85rem',
                      transition: 'all 0.2s ease',
                    }}
                  >
                    {/* Header */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ fontSize: '1.2rem', fontWeight: 800, color: '#ffffff' }}>{a.ticker}</span>
                          <span style={{
                            fontSize: '0.7rem',
                            fontWeight: 800,
                            padding: '2px 8px',
                            borderRadius: '6px',
                            background: `${color}25`,
                            color: color,
                            border: `1px solid ${color}50`,
                          }}>
                            {isAbs ? '🐋 WHALE ABSORPTION' : isMarkup ? '🚀 MARKUP' : isTrap ? '🪤 RETAIL TRAP' : '📉 DUMP'}
                          </span>
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                          {a.company_name}
                        </div>
                      </div>

                      <div style={{ textAlign: 'right' }}>
                        <div style={{
                          fontSize: '0.9rem',
                          fontWeight: 800,
                          color: '#f43f5e',
                          background: 'rgba(244, 63, 94, 0.15)',
                          padding: '2px 8px',
                          borderRadius: '6px',
                          border: '1px solid rgba(244, 63, 94, 0.3)',
                        }}>
                          +{a.z_composite.toFixed(1)}σ
                        </div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                          Z-Score Spike
                        </div>
                      </div>
                    </div>

                    {/* Price & Flow Metrics Grid */}
                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(3, 1fr)',
                      gap: '0.5rem',
                      background: 'rgba(255, 255, 255, 0.02)',
                      padding: '0.75rem',
                      borderRadius: '10px',
                      fontSize: '0.75rem',
                    }}>
                      <div>
                        <span style={{ color: 'var(--text-secondary)' }}>Price</span>
                        <div style={{ fontWeight: 700, marginTop: '2px' }}>
                          Rp {a.price.toLocaleString()}
                          <span style={{
                            marginLeft: '4px',
                            color: a.price_change_pct >= 0 ? '#34d399' : '#f87171',
                            fontSize: '0.7rem',
                          }}>
                            ({a.price_change_pct >= 0 ? '+' : ''}{a.price_change_pct.toFixed(1)}%)
                          </span>
                        </div>
                      </div>

                      <div>
                        <span style={{ color: 'var(--text-secondary)' }}>Turnover</span>
                        <div style={{ fontWeight: 700, marginTop: '2px' }}>
                          Rp {a.turnover_rp_b.toFixed(1)}B
                        </div>
                      </div>

                      <div>
                        <span style={{ color: 'var(--text-secondary)' }}>Foreign Buy</span>
                        <div style={{ fontWeight: 700, marginTop: '2px', color: a.foreign_buy_ratio_pct >= 50 ? '#34d399' : '#f87171' }}>
                          {a.foreign_buy_ratio_pct.toFixed(1)}%
                        </div>
                      </div>

                      <div>
                        <span style={{ color: 'var(--text-secondary)' }}>Net Foreign Flow</span>
                        <div style={{ fontWeight: 700, marginTop: '2px', color: a.net_foreign_flow_rp_b >= 0 ? '#34d399' : '#f87171' }}>
                          {a.net_foreign_flow_rp_b >= 0 ? '+' : ''}Rp {a.net_foreign_flow_rp_b.toFixed(1)}B
                        </div>
                      </div>

                      <div>
                        <span style={{ color: 'var(--text-secondary)' }}>Volume Z</span>
                        <div style={{ fontWeight: 700, marginTop: '2px', color: '#38bdf8' }}>
                          +{a.z_vol.toFixed(1)}σ
                        </div>
                      </div>

                      <div>
                        <span style={{ color: 'var(--text-secondary)' }}>Smart Delta</span>
                        <div style={{ fontWeight: 700, marginTop: '2px' }}>
                          {a.smart_money_delta.toFixed(1)}x
                        </div>
                      </div>
                    </div>

                    {/* Wyckoff Phase */}
                    <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                      <span style={{ color: 'var(--text-secondary)' }}>Wyckoff Phase: </span>
                      <strong style={{ color: '#e2e8f0' }}>{a.wyckoff_phase}</strong>
                    </div>

                    {/* Actionable Playbook */}
                    <div style={{
                      background: `${color}10`,
                      borderLeft: `3px solid ${color}`,
                      padding: '0.65rem 0.85rem',
                      borderRadius: '0 8px 8px 0',
                      fontSize: '0.75rem',
                      lineHeight: 1.45,
                      color: '#e2e8f0',
                    }}>
                      {a.playbook}
                    </div>

                    {/* Chart action */}
                    <button
                      onClick={() => onSelectStock(a.ticker)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '6px',
                        padding: '0.45rem',
                        borderRadius: '8px',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        background: 'rgba(255, 255, 255, 0.04)',
                        color: 'var(--text-primary)',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      <span>Inspect {a.ticker} Depth & Candlesticks</span>
                      <ArrowRight size={12} />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* VIEW 2: ORIGINAL STEALTH WYCKOFF RADAR */}
      {activeSubView === 'radar' && (
        <>
          {/* KPI Cards */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '1rem',
          }}>
            <div className="stat-card" style={{
              background: 'rgba(15, 23, 42, 0.55)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '16px',
              padding: '1.25rem',
            }}>
              <span className="stat-label" style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Market Smart Delta</span>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', marginTop: '0.25rem' }}>
                <span className="stat-value" style={{ fontSize: '1.8rem', fontWeight: 800, color: '#38bdf8' }}>
                  {data?.smart_money_delta ? `${data.smart_money_delta.toFixed(1)}x` : '—'}
                </span>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Smart vs Retail Vol</span>
              </div>
            </div>

            <div className="stat-card" style={{
              background: 'rgba(15, 23, 42, 0.55)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '16px',
              padding: '1.25rem',
            }}>
              <span className="stat-label" style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Stealth Candidates</span>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', marginTop: '0.25rem' }}>
                <span className="stat-value" style={{ fontSize: '1.8rem', fontWeight: 800, color: '#10b981' }}>
                  {radarAnomalies.filter((a) => a.Signal === 'STEALTH_ACCUMULATION').length}
                </span>
                <span style={{ fontSize: '0.8rem', color: '#10b981' }}>Quiet Absorption</span>
              </div>
            </div>

            <div className="stat-card" style={{
              background: 'rgba(15, 23, 42, 0.55)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '16px',
              padding: '1.25rem',
            }}>
              <span className="stat-label" style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Retail Traps Detected</span>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', marginTop: '0.25rem' }}>
                <span className="stat-value" style={{ fontSize: '1.8rem', fontWeight: 800, color: '#f59e0b' }}>
                  {radarAnomalies.filter((a) => a.Signal === 'RETAIL_TRAP').length}
                </span>
                <span style={{ fontSize: '0.8rem', color: '#f59e0b' }}>Caution High</span>
              </div>
            </div>

            <div className="stat-card" style={{
              background: 'rgba(15, 23, 42, 0.55)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '16px',
              padding: '1.25rem',
            }}>
              <span className="stat-label" style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Lookback Window</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.4rem' }}>
                {[3, 5, 10, 20].map((d) => (
                  <button
                    key={d}
                    onClick={() => setLookbackDays(d)}
                    style={{
                      padding: '0.25rem 0.6rem',
                      borderRadius: '6px',
                      border: lookbackDays === d ? '1px solid #38bdf8' : '1px solid rgba(255, 255, 255, 0.1)',
                      background: lookbackDays === d ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                      color: lookbackDays === d ? '#ffffff' : 'var(--text-secondary)',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    {d}d
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Wyckoff Phase Lifecycle Pipeline */}
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

          {/* Main Table & Rules Panel */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 340px',
            gap: '1.5rem',
            alignItems: 'start',
          }}>
            {/* Left: Table */}
            <div style={{
              background: 'rgba(15, 23, 42, 0.55)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '16px',
              padding: '1.25rem',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700 }}>
                  Active Institutional Flow Candidates ({filteredRadarAnomalies.length})
                </h3>

                {/* Filter buttons */}
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  {['ALL', 'STEALTH_ACCUMULATION', 'MARKUP_CONFIRMATION', 'RETAIL_TRAP', 'DISTRIBUTION'].map((sig) => (
                    <button
                      key={sig}
                      onClick={() => setFilterSignal(sig)}
                      style={{
                        padding: '0.3rem 0.65rem',
                        borderRadius: '6px',
                        border: filterSignal === sig ? '1px solid #38bdf8' : '1px solid rgba(255, 255, 255, 0.1)',
                        background: filterSignal === sig ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.04)',
                        color: filterSignal === sig ? '#ffffff' : 'var(--text-secondary)',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      {sig.replace(/_/g, ' ')}
                    </button>
                  ))}
                </div>
              </div>

              {loading ? (
                <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  <Loader2 size={32} className="spinning" style={{ margin: '0 auto 0.5rem' }} />
                  <p>Processing broker summaries & foreign flow metrics...</p>
                </div>
              ) : filteredRadarAnomalies.length === 0 ? (
                <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  <Users size={32} style={{ margin: '0 auto 0.5rem', opacity: 0.5 }} />
                  <p>No stocks currently match the selected Bandarmology filters.</p>
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', color: 'var(--text-secondary)', textAlign: 'left' }}>
                        <th style={{ padding: '0.75rem 0.5rem' }}>Ticker</th>
                        <th style={{ padding: '0.75rem 0.5rem' }}>Signal</th>
                        <th style={{ padding: '0.75rem 0.5rem' }}>Wyckoff Phase</th>
                        <th style={{ padding: '0.75rem 0.5rem' }}>Net Foreign Flow</th>
                        <th style={{ padding: '0.75rem 0.5rem' }}>Price Δ ({lookbackDays}d)</th>
                        <th style={{ padding: '0.75rem 0.5rem' }}>Conviction</th>
                        <th style={{ padding: '0.75rem 0.5rem', textAlign: 'right' }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredRadarAnomalies.map((item) => {
                        const isStealth = item.Signal === 'STEALTH_ACCUMULATION';
                        const isTrap = item.Signal === 'RETAIL_TRAP';
                        const isMarkup = item.Signal === 'MARKUP_CONFIRMATION';
                        const badgeColor = isStealth ? '#10b981' : isTrap ? '#f87171' : isMarkup ? '#38bdf8' : '#eab308';

                        return (
                          <tr
                            key={item.StockCode}
                            style={{
                              borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                              transition: 'background 0.2s ease',
                            }}
                          >
                            <td style={{ padding: '0.75rem 0.5rem', fontWeight: 700 }}>
                              {item.StockCode}
                            </td>
                            <td style={{ padding: '0.75rem 0.5rem' }}>
                              <span style={{
                                padding: '0.2rem 0.5rem',
                                borderRadius: '4px',
                                fontSize: '0.75rem',
                                fontWeight: 700,
                                background: `${badgeColor}15`,
                                color: badgeColor,
                                border: `1px solid ${badgeColor}30`,
                              }}>
                                {item.Signal.replace(/_/g, ' ')}
                              </span>
                            </td>
                            <td style={{ padding: '0.75rem 0.5rem', color: '#94a3b8' }}>
                              {item.WyckoffPhase || 'Phase B'}
                            </td>
                            <td style={{ padding: '0.75rem 0.5rem', fontWeight: 600, color: (item.CumNetForeignFlowRpB || 0) >= 0 ? '#34d399' : '#f87171' }}>
                              {(item.CumNetForeignFlowRpB || 0) >= 0 ? '+' : ''}Rp {(item.CumNetForeignFlowRpB || 0).toFixed(1)}B
                            </td>
                            <td style={{ padding: '0.75rem 0.5rem', color: (item.CumPriceChangePct || 0) >= 0 ? '#34d399' : '#f87171' }}>
                              {(item.CumPriceChangePct || 0) >= 0 ? '+' : ''}{(item.CumPriceChangePct || 0).toFixed(1)}%
                            </td>
                            <td style={{ padding: '0.75rem 0.5rem' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <div style={{
                                  width: '45px',
                                  height: '6px',
                                  borderRadius: '3px',
                                  background: 'rgba(255, 255, 255, 0.1)',
                                  overflow: 'hidden',
                                }}>
                                  <div style={{
                                    width: `${item.AccumulationScore || 50}%`,
                                    height: '100%',
                                    background: badgeColor,
                                  }} />
                                </div>
                                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                  {item.AccumulationScore || 50}
                                </span>
                              </div>
                            </td>
                            <td style={{ padding: '0.75rem 0.5rem', textAlign: 'right' }}>
                              <button
                                onClick={() => onSelectStock(item.StockCode)}
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '4px',
                                  padding: '0.35rem 0.75rem',
                                  borderRadius: '6px',
                                  border: '1px solid rgba(255, 255, 255, 0.1)',
                                  background: 'rgba(255, 255, 255, 0.05)',
                                  color: 'var(--text-primary)',
                                  fontSize: '0.75rem',
                                  cursor: 'pointer',
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
        </>
      )}
    </div>
  );
};
