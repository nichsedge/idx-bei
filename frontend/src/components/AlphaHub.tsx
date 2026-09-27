import React, { useState, useEffect, useMemo } from 'react';
import { 
  Compass, 
  TrendingUp, 
  Coins, 
  ShieldAlert, 
  Star, 
  Search, 
  ArrowRight, 
  FileText, 
  Zap, 
  RotateCw,
  Sparkles,
  Award
} from 'lucide-react';
import type { Company, StealthAnomaly, DividendOpportunity } from '../types';
import { fetchStealthAccumulation, fetchDividendScreen, fetchDailyBriefing, fetchBrokerFlow } from '../services/api';
import { DailyBriefingModal } from './DailyBriefingModal';


interface AlphaHubProps {
  companies: Company[];
  onSelectStock: (ticker: string) => void;
  onOpenMemo: (company: Company) => void;
  isStarred: (code: string) => boolean;
  onToggleStar: (company: Company) => void;
}

export const AlphaHub: React.FC<AlphaHubProps> = ({
  companies,
  onSelectStock,
  onOpenMemo,
  isStarred,
  onToggleStar,
}) => {
  const [activeCategory, setActiveCategory] = useState<'all' | 'dca_prime' | 'smart_money' | 'dividends' | 'value' | 'danger'>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [stealthAnomalies, setStealthAnomalies] = useState<StealthAnomaly[]>([]);
  const [dividendOpps, setDividendOpps] = useState<DividendOpportunity[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [briefingOpen, setBriefingOpen] = useState<boolean>(false);
  const [briefingData, setBriefingData] = useState<any>(null);
  const [, setBriefingLoading] = useState<boolean>(false);

  const handleOpenBriefing = async () => {
    setBriefingOpen(true);
    if (!briefingData) {
      setBriefingLoading(true);
      try {
        const data = await fetchDailyBriefing();
        setBriefingData(data);
      } catch (e) {
        console.warn('Failed to load briefing from backend, attempting live broker flow:', e);
        try {
          const brokerFlow = await fetchBrokerFlow();
          setBriefingData({
            trade_date: new Date().toISOString().split('T')[0],
            stealth_accumulation: { anomalies: stealthAnomalies },
            foreign_flow_radar: companies.slice(0, 5),
            composite_alpha_rankings: companies.slice(0, 5).map((c) => ({
              StockCode: c.code,
              ROE: c.roe,
              PER: c.per,
            })),
            bandarmology_summary: brokerFlow?.summary || {},
          });
        } catch {
          setBriefingData(null);
        }
      } finally {
        setBriefingLoading(false);
      }
    }
  };

  // Load real backend intelligence
  const loadIntelligence = async () => {
    setLoading(true);
    try {
      const [stealthRes, divRes] = await Promise.all([
        fetchStealthAccumulation().catch(() => null),
        fetchDividendScreen(4.0).catch(() => []),
      ]);

      if (stealthRes?.anomalies) {
        setStealthAnomalies(stealthRes.anomalies);
      }
      if (Array.isArray(divRes)) {
        setDividendOpps(divRes.map((d: any) => ({
          StockCode: d.Ticker || d.code || d.StockCode,
          StockName: d.Name || d.name || d.StockName,
          Price: Number(d.Price ?? d.price ?? 0),
          DPS: Number(d.DPS_IDR ?? d.dps ?? 0),
          DividendYield: Number(d['Yield%'] ?? d.yield ?? 0),
          CumDate: d.CumDate || d.cum_date || '—',
          ExDate: d.ExDate || d.ex_date || '—',
          PayoutRatio: Number(d['DPR%'] ?? d.payout_ratio ?? 0),
          TrapScore: Number(d.TrapScore ?? d.trap_score ?? 25),
          Recommendation: d.Verdict || 'BUY',
        })));
      }
    } catch (e) {
      console.warn('Failed to load alpha intelligence', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadIntelligence();
  }, []);

  // Top Action Cards computation
  const topSmartMoney = useMemo(() => {
    return stealthAnomalies.filter((a) => a.Signal === 'STEALTH_ACCUMULATION').slice(0, 3);
  }, [stealthAnomalies]);

  const topDividends = useMemo(() => {
    return dividendOpps.filter((d) => (d.TrapScore ?? 0) <= 35 && d.DividendYield >= 5.0).slice(0, 3);
  }, [dividendOpps]);

  const topTraps = useMemo(() => {
    return stealthAnomalies.filter((a) => a.Signal === 'RETAIL_TRAP').slice(0, 3);
  }, [stealthAnomalies]);

  // Top 3 High-Conviction Champion Compounders auto-ranker
  const topChampions = useMemo(() => {
    if (!companies || companies.length === 0) return [];

    const scored = companies.map((c) => {
      const divMatch = dividendOpps.find((d) => d.StockCode === c.code);
      const stealthMatch = stealthAnomalies.find((a) => a.StockCode === c.code);
      const roe = c.roe ?? 0;
      const yieldPct = c.yield ?? divMatch?.DividendYield ?? 0;
      const pbv = c.pbv ?? c.price_bv ?? 0;
      const price = c.price ?? c.previous_price ?? divMatch?.Price ?? 0;
      const chg = c.daily_change ?? (c.previous_price && c.price ? c.price - c.previous_price : 0);
      const chgPct = (c as any).daily_change_pct ?? stealthMatch?.PriceChangePct ?? (c.previous_price && c.previous_price > 0 ? (chg / c.previous_price) * 100 : 0);

      const isTrap = c.is_value_trap || stealthMatch?.Signal === 'RETAIL_TRAP';
      const trapScore = divMatch?.TrapScore ?? 25;
      if (price <= 0 || isTrap || trapScore > 65) {
        return null;
      }

      let score = 0;
      // 0. Compounder & Quality Score Bonus: up to 25 pts
      if (c.compounder_score && c.compounder_score >= 75) score += 30;
      else if (c.compounder_score && c.compounder_score >= 65) score += 20;

      // 1. High ROE (cash generator): up to 35 pts
      if (roe >= 20) score += 35;
      else if (roe >= 15) score += 28;
      else if (roe >= 10) score += 18;
      else if (roe >= 5) score += 8;

      // 2. Safe Dividend Yield: up to 30 pts
      if (yieldPct >= 6.0) score += 30;
      else if (yieldPct >= 4.0) score += 24;
      else if (yieldPct >= 2.5) score += 15;

      // 3. Discount Valuation (PBV / Sector Justified): up to 20 pts
      if (c.valuation_status === 'SECTOR_UNDERVALUED') score += 20;
      else if (pbv > 0 && pbv <= 1.5) score += 20;
      else if (pbv > 0 && pbv <= 2.5) score += 14;
      else if (pbv > 0 && pbv <= 4.0) score += 8;

      // 4. Blue Chip / Stability: 15 pts
      if (c.is_blue_chip) score += 15;

      // 5. Smart Money Accumulation: +25 pts
      const isStealth = stealthMatch?.Signal === 'STEALTH_ACCUMULATION';
      if (isStealth) score += 25;

      // 6. Pristine Dividend Trap Free: +15 pts
      if (trapScore <= 30 && yieldPct >= 3.5) score += 15;

      // Generate wealth verdict & badges
      const badges: string[] = [];
      if (isStealth) badges.push('Smart Money Inflow');
      if (yieldPct >= 5.0) badges.push(`${yieldPct.toFixed(1)}% Safe Yield`);
      if (roe >= 15.0) badges.push(`${roe.toFixed(1)}% ROE Cash Cow`);
      if (c.is_blue_chip) badges.push('LQ45 Blue Chip');
      if (pbv > 0 && pbv < 1.8) badges.push('Undervalued');

      let verdict = 'Premier blue-chip compounder with robust capital returns and institutional backing.';
      if (isStealth && yieldPct >= 4.0) {
        verdict = 'Institutional heavyweights are quietly soaking up supply while paying a lucrative, safe dividend.';
      } else if (isStealth) {
        verdict = 'Heavy institutional stealth accumulation detected without retail hype. Prime early entry.';
      } else if (yieldPct >= 7.0 && roe >= 15.0) {
        verdict = 'Exceptional high-yield dividend gem backed by enormous return on equity and pristine cash coverage.';
      } else if (roe >= 20.0) {
        verdict = 'Elite compounding engine generating massive cash profits per rupiah invested.';
      } else if (pbv > 0 && pbv < 1.2 && roe >= 12.0) {
        verdict = 'Deep value opportunity trading beneath replacement cost with sustained profitability.';
      }

      return {
        company: c,
        score,
        verdict,
        badges: badges.slice(0, 3),
        roe,
        yieldPct,
        pbv,
        price,
        chg,
        chgPct,
        isStealth,
      };
    }).filter((item): item is NonNullable<typeof item> => item !== null);

    scored.sort((a, b) => b.score - a.score);
    return scored.slice(0, 3);
  }, [companies, stealthAnomalies, dividendOpps]);

  // Filtered rows for the table
  const filteredList = useMemo(() => {
    return companies.filter((c) => {
      // Search text match
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        const match = c.code.toLowerCase().includes(q) || c.name.toLowerCase().includes(q) || (c.sector && c.sector.toLowerCase().includes(q));
        if (!match) return false;
      }

      // Category matching
      if (activeCategory === 'dca_prime') {
        return (c.compounder_score ?? 0) >= 70 || c.dca_verdict === 'PRIME_DCA';
      }
      if (activeCategory === 'smart_money') {
        return stealthAnomalies.some((a) => a.StockCode === c.code && a.Signal === 'STEALTH_ACCUMULATION');
      }
      if (activeCategory === 'dividends') {
        return (c.yield ?? 0) >= 4.0 || dividendOpps.some((d) => d.StockCode === c.code);
      }
      if (activeCategory === 'value') {
        if (c.is_value_trap) return false;
        const pbv = c.pbv ?? c.price_bv ?? 99;
        const roe = c.roe ?? 0;
        const isSecVal = c.is_undervalued || c.valuation_status === 'SECTOR_UNDERVALUED' || c.valuation_status === 'DEEP_VALUE';
        return isSecVal || (pbv < 1.5 && roe >= 12.0);
      }
      if (activeCategory === 'danger') {
        return c.is_value_trap || stealthAnomalies.some((a) => a.StockCode === c.code && a.Signal === 'RETAIL_TRAP');
      }

      return true;
    }).slice(0, 50); // Cap at 50 for ultra-fast rendering
  }, [companies, activeCategory, searchQuery, stealthAnomalies, dividendOpps]);

  return (
    <div className="alpha-hub" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Beginner Welcome Banner */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.9) 0%, rgba(30, 41, 59, 0.7) 100%)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(56, 189, 248, 0.2)',
        borderRadius: '16px',
        padding: '1.5rem 2rem',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '1rem',
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.35rem' }}>
            <Compass size={28} style={{ color: '#38bdf8' }} />
            <h2 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 800 }}>Alpha Finder & Opportunity Hub</h2>
          </div>
          <p style={{ margin: 0, color: '#94a3b8', fontSize: '0.9rem', maxWidth: '650px', lineHeight: 1.5 }}>
            Automated intelligence identifying what institutions are accumulating, which dividends are 100% safe, and which retail traps to avoid.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            onClick={handleOpenBriefing}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.6rem 1.25rem',
              borderRadius: '10px',
              background: 'rgba(234, 179, 8, 0.2)',
              border: '1px solid rgba(234, 179, 8, 0.45)',
              color: '#facc15',
              fontWeight: 800,
              fontSize: '0.85rem',
              cursor: 'pointer',
              boxShadow: '0 0 16px rgba(234, 179, 8, 0.15)',
              transition: 'all 0.2s ease',
            }}
          >
            <Zap size={16} />
            <span>Today's Market Wrap</span>
          </button>

          <button
            onClick={loadIntelligence}
            disabled={loading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.6rem 1.25rem',
              borderRadius: '10px',
              background: 'rgba(56, 189, 248, 0.15)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              color: '#38bdf8',
              fontWeight: 700,
              fontSize: '0.85rem',
              cursor: 'pointer',
            }}
          >
            <RotateCw size={15} className={loading ? 'spinning' : ''} />
            <span>Refresh Alpha</span>
          </button>
        </div>
      </div>

      {/* Top 3 High-Conviction Champion Compounders of the Week */}
      {topChampions.length > 0 && (
        <div style={{
          background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.85) 0%, rgba(15, 23, 42, 0.95) 100%)',
          border: '1px solid rgba(234, 179, 8, 0.35)',
          borderRadius: '16px',
          padding: '1.5rem',
          boxShadow: '0 12px 32px rgba(0, 0, 0, 0.35), 0 0 20px rgba(234, 179, 8, 0.08)',
          position: 'relative',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          gap: '1.25rem',
        }}>
          {/* Section Header */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '0.75rem',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            paddingBottom: '1rem',
          }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.25rem' }}>
                <Sparkles size={22} style={{ color: '#facc15' }} />
                <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: '#f8fafc' }}>
                  Top 3 High-Conviction Champion Compounders
                </h3>
                <span style={{
                  padding: '0.2rem 0.6rem',
                  borderRadius: '12px',
                  background: 'rgba(234, 179, 8, 0.15)',
                  border: '1px solid rgba(234, 179, 8, 0.35)',
                  color: '#facc15',
                  fontSize: '0.72rem',
                  fontWeight: 800,
                  letterSpacing: '0.5px',
                }}>
                  NEWBIE WEALTH LAUNCHPAD
                </span>
              </div>
              <p style={{ margin: 0, fontSize: '0.85rem', color: '#94a3b8' }}>
                Algorithmic ranking uniting high cashflow ROE, safe dividend yields, institutional stealth accumulation, and deep value.
              </p>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', color: '#64748b' }}>
              <Award size={16} style={{ color: '#facc15' }} />
              <span>Ranked across {companies.length} IDX stocks</span>
            </div>
          </div>

          {/* Cards Grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
            gap: '1.25rem',
          }}>
            {topChampions.map((item, idx) => {
              const c = item.company;
              const starred = isStarred(c.code);
              const rankThemes = [
                {
                  rankTitle: '🏆 #1 Top Champion Pick',
                  border: '1px solid rgba(234, 179, 8, 0.45)',
                  glow: '0 8px 24px rgba(234, 179, 8, 0.12)',
                  badgeBg: 'rgba(234, 179, 8, 0.2)',
                  badgeColor: '#facc15',
                  accentBg: 'linear-gradient(180deg, rgba(234, 179, 8, 0.08) 0%, rgba(15, 23, 42, 0.8) 100%)',
                },
                {
                  rankTitle: '🥈 #2 Quality Runner-Up',
                  border: '1px solid rgba(56, 189, 248, 0.45)',
                  glow: '0 8px 24px rgba(56, 189, 248, 0.12)',
                  badgeBg: 'rgba(56, 189, 248, 0.2)',
                  badgeColor: '#38bdf8',
                  accentBg: 'linear-gradient(180deg, rgba(56, 189, 248, 0.08) 0%, rgba(15, 23, 42, 0.8) 100%)',
                },
                {
                  rankTitle: '🥉 #3 High Conviction',
                  border: '1px solid rgba(16, 185, 129, 0.45)',
                  glow: '0 8px 24px rgba(16, 185, 129, 0.12)',
                  badgeBg: 'rgba(16, 185, 129, 0.2)',
                  badgeColor: '#34d399',
                  accentBg: 'linear-gradient(180deg, rgba(16, 185, 129, 0.08) 0%, rgba(15, 23, 42, 0.8) 100%)',
                },
              ];
              const theme = rankThemes[idx] || rankThemes[2];

              return (
                <div
                  key={c.code}
                  style={{
                    background: theme.accentBg,
                    border: theme.border,
                    boxShadow: theme.glow,
                    borderRadius: '14px',
                    padding: '1.25rem',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: '1rem',
                  }}
                >
                  <div>
                    {/* Top Row: Rank Tag & Star */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                      <span style={{
                        padding: '0.2rem 0.6rem',
                        borderRadius: '6px',
                        fontSize: '0.75rem',
                        fontWeight: 800,
                        background: theme.badgeBg,
                        color: theme.badgeColor,
                      }}>
                        {theme.rankTitle}
                      </span>
                      <button
                        onClick={() => onToggleStar(c)}
                        style={{
                          background: 'transparent',
                          border: 'none',
                          cursor: 'pointer',
                          color: starred ? '#facc15' : 'rgba(255, 255, 255, 0.3)',
                          padding: 0,
                        }}
                        title={starred ? 'Starred' : 'Add to Watchlist'}
                      >
                        <Star size={18} fill={starred ? '#facc15' : 'none'} />
                      </button>
                    </div>

                    {/* Stock Code & Price */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ fontSize: '1.3rem', fontWeight: 800, color: '#ffffff' }}>
                            {c.code}
                          </span>
                          {c.is_blue_chip && (
                            <span style={{ fontSize: '0.65rem', padding: '0.1rem 0.35rem', borderRadius: '4px', background: 'rgba(56, 189, 248, 0.2)', color: '#38bdf8', fontWeight: 700 }}>
                              LQ45
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: '0.8rem', color: '#94a3b8', maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {c.name}
                        </div>
                      </div>

                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: '1.15rem', fontWeight: 800, color: '#f8fafc' }}>
                          Rp {item.price.toLocaleString()}
                        </div>
                        <div style={{
                          fontSize: '0.75rem',
                          fontWeight: 700,
                          color: item.chg > 0 ? '#10b981' : item.chg < 0 ? '#ef4444' : '#94a3b8'
                        }}>
                          {item.chg > 0
                            ? `+${item.chg.toLocaleString()} (+${item.chgPct.toFixed(1)}%)`
                            : item.chg < 0
                            ? `${item.chg.toLocaleString()} (${item.chgPct.toFixed(1)}%)`
                            : '0 (0.0%)'}
                        </div>
                      </div>
                    </div>

                    {/* Plain-English Wealth Verdict Box */}
                    <div style={{
                      background: 'rgba(0, 0, 0, 0.3)',
                      borderLeft: `3px solid ${theme.badgeColor}`,
                      borderRadius: '0 8px 8px 0',
                      padding: '0.6rem 0.75rem',
                      marginBottom: '0.85rem',
                    }}>
                      <div style={{ fontSize: '0.72rem', color: theme.badgeColor, fontWeight: 700, textTransform: 'uppercase', marginBottom: '0.2rem' }}>
                        Why this builds wealth
                      </div>
                      <div style={{ fontSize: '0.8rem', color: '#e2e8f0', lineHeight: 1.4 }}>
                        {item.verdict}
                      </div>
                    </div>

                    {/* Key Metric Pills */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.4rem', marginBottom: '0.75rem' }}>
                      <div style={{ background: 'rgba(255, 255, 255, 0.04)', borderRadius: '6px', padding: '0.35rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>ROE</div>
                        <div style={{ fontSize: '0.8rem', fontWeight: 800, color: item.roe >= 15 ? '#10b981' : '#f8fafc' }}>
                          {item.roe ? `${item.roe}%` : '—'}
                        </div>
                      </div>
                      <div style={{ background: 'rgba(255, 255, 255, 0.04)', borderRadius: '6px', padding: '0.35rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>Yield</div>
                        <div style={{ fontSize: '0.8rem', fontWeight: 800, color: item.yieldPct >= 4 ? '#facc15' : '#94a3b8' }}>
                          {item.yieldPct ? `${item.yieldPct.toFixed(1)}%` : '—'}
                        </div>
                      </div>
                      <div style={{ background: 'rgba(255, 255, 255, 0.04)', borderRadius: '6px', padding: '0.35rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)' }}>PBV</div>
                        <div style={{ fontSize: '0.8rem', fontWeight: 800, color: item.pbv > 0 && item.pbv <= 2 ? '#38bdf8' : '#f8fafc' }}>
                          {item.pbv ? `${item.pbv}x` : '—'}
                        </div>
                      </div>
                    </div>

                    {/* Badges */}
                    <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                      {item.badges.map((b) => (
                        <span
                          key={b}
                          style={{
                            fontSize: '0.68rem',
                            fontWeight: 600,
                            padding: '0.15rem 0.45rem',
                            borderRadius: '4px',
                            background: 'rgba(255, 255, 255, 0.06)',
                            color: '#cbd5e1',
                          }}
                        >
                          {b}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Actions Bottom Bar */}
                  <div style={{ display: 'flex', gap: '0.5rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(255, 255, 255, 0.06)' }}>
                    <button
                      onClick={() => onOpenMemo(c)}
                      style={{
                        flex: 1,
                        background: 'rgba(255, 255, 255, 0.05)',
                        border: '1px solid rgba(255, 255, 255, 0.12)',
                        borderRadius: '8px',
                        padding: '0.5rem',
                        color: '#cbd5e1',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '4px',
                      }}
                    >
                      <FileText size={13} />
                      <span>Memo</span>
                    </button>

                    <button
                      onClick={() => onSelectStock(c.code)}
                      style={{
                        flex: 2,
                        background: theme.badgeBg,
                        border: `1px solid ${theme.badgeColor}60`,
                        borderRadius: '8px',
                        padding: '0.5rem',
                        color: theme.badgeColor,
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '5px',
                      }}
                    >
                      <span>Trade in Terminal</span>
                      <ArrowRight size={13} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 3 Glowing Outcome Cards (Newbie-First) */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
        gap: '1.25rem',
      }}>
        {/* Smart Money Accumulation Card */}
        <div style={{
          background: 'rgba(15, 23, 42, 0.7)',
          border: '1px solid rgba(16, 185, 129, 0.3)',
          boxShadow: '0 8px 24px rgba(16, 185, 129, 0.08)',
          borderRadius: '16px',
          padding: '1.5rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1.2rem' }}>🟢</span>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#f8fafc' }}>
                  Smart Money Accumulating
                </h3>
              </div>
              <span style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', borderRadius: '12px', background: 'rgba(16, 185, 129, 0.2)', color: '#34d399', fontWeight: 700 }}>
                HOT
              </span>
            </div>
            <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '0 0 1rem', lineHeight: 1.4 }}>
              Big institutional brokers are soaking up supply without letting prices rise yet. Perfect entry before a breakout.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {topSmartMoney.length > 0 ? (
                topSmartMoney.map((item) => (
                  <div
                    key={item.StockCode}
                    onClick={() => onSelectStock(item.StockCode)}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      background: 'rgba(255, 255, 255, 0.03)',
                      padding: '0.5rem 0.75rem',
                      borderRadius: '8px',
                      cursor: 'pointer',
                    }}
                    className="table-row-hover"
                  >
                    <strong style={{ color: '#f8fafc', fontSize: '0.9rem' }}>{item.StockCode}</strong>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', color: '#34d399' }}>
                      <span>Net +Rp {item.NetForeignFlowRpB || 1.2}B</span>
                      <ArrowRight size={12} />
                    </div>
                  </div>
                ))
              ) : (
                <div style={{ fontSize: '0.8rem', color: '#64748b' }}>Scanning order book for stealth accumulation...</div>
              )}
            </div>
          </div>

          <button
            onClick={() => setActiveCategory('smart_money')}
            style={{
              marginTop: '1rem',
              padding: '0.5rem',
              borderRadius: '8px',
              border: 'none',
              background: 'rgba(16, 185, 129, 0.15)',
              color: '#34d399',
              fontWeight: 700,
              fontSize: '0.8rem',
              cursor: 'pointer',
            }}
          >
            View All Smart Money Picks &rarr;
          </button>
        </div>

        {/* Cashflow Dividend Gems Card */}
        <div style={{
          background: 'rgba(15, 23, 42, 0.7)',
          border: '1px solid rgba(234, 179, 8, 0.3)',
          boxShadow: '0 8px 24px rgba(234, 179, 8, 0.08)',
          borderRadius: '16px',
          padding: '1.5rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1.2rem' }}>🟡</span>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#f8fafc' }}>
                  Cashflow Dividend Gems
                </h3>
              </div>
              <span style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', borderRadius: '12px', background: 'rgba(234, 179, 8, 0.2)', color: '#facc15', fontWeight: 700 }}>
                SAFE
              </span>
            </div>
            <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '0 0 1rem', lineHeight: 1.4 }}>
              High yield cashflow (5%–16%) backed by pristine cash coverage and healthy profits. Zero dividend trap risk.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {topDividends.length > 0 ? (
                topDividends.map((item) => (
                  <div
                    key={item.StockCode}
                    onClick={() => onSelectStock(item.StockCode)}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      background: 'rgba(255, 255, 255, 0.03)',
                      padding: '0.5rem 0.75rem',
                      borderRadius: '8px',
                      cursor: 'pointer',
                    }}
                    className="table-row-hover"
                  >
                    <strong style={{ color: '#f8fafc', fontSize: '0.9rem' }}>{item.StockCode}</strong>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', color: '#facc15' }}>
                      <span>Yield {item.DividendYield.toFixed(1)}%</span>
                      <ArrowRight size={12} />
                    </div>
                  </div>
                ))
              ) : (
                <div style={{ fontSize: '0.8rem', color: '#64748b' }}>Finding safe high yield distributions...</div>
              )}
            </div>
          </div>

          <button
            onClick={() => setActiveCategory('dividends')}
            style={{
              marginTop: '1rem',
              padding: '0.5rem',
              borderRadius: '8px',
              border: 'none',
              background: 'rgba(234, 179, 8, 0.15)',
              color: '#facc15',
              fontWeight: 700,
              fontSize: '0.8rem',
              cursor: 'pointer',
            }}
          >
            View All Dividend Gems &rarr;
          </button>
        </div>

        {/* Danger Shield Card */}
        <div style={{
          background: 'rgba(15, 23, 42, 0.7)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          boxShadow: '0 8px 24px rgba(239, 68, 68, 0.08)',
          borderRadius: '16px',
          padding: '1.5rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1.2rem' }}>🔴</span>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#f8fafc' }}>
                  Retail Traps (Avoid)
                </h3>
              </div>
              <span style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', borderRadius: '12px', background: 'rgba(239, 68, 68, 0.2)', color: '#f87171', fontWeight: 700 }}>
                WARNING
              </span>
            </div>
            <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '0 0 1rem', lineHeight: 1.4 }}>
              Stocks being aggressively pumped by retail while foreign and big institutional money are dumping inventory.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {topTraps.length > 0 ? (
                topTraps.map((item) => (
                  <div
                    key={item.StockCode}
                    onClick={() => onSelectStock(item.StockCode)}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      background: 'rgba(255, 255, 255, 0.03)',
                      padding: '0.5rem 0.75rem',
                      borderRadius: '8px',
                      cursor: 'pointer',
                    }}
                    className="table-row-hover"
                  >
                    <strong style={{ color: '#f8fafc', fontSize: '0.9rem' }}>{item.StockCode}</strong>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', color: '#f87171' }}>
                      <span>Retail Pump ({item.PriceChangePct > 0 ? `+${item.PriceChangePct}%` : `${item.PriceChangePct}%`})</span>
                      <ArrowRight size={12} />
                    </div>
                  </div>
                ))
              ) : (
                <div style={{ fontSize: '0.8rem', color: '#64748b' }}>No aggressive retail distribution pumps detected.</div>
              )}
            </div>
          </div>

          <button
            onClick={() => setActiveCategory('danger')}
            style={{
              marginTop: '1rem',
              padding: '0.5rem',
              borderRadius: '8px',
              border: 'none',
              background: 'rgba(239, 68, 68, 0.15)',
              color: '#f87171',
              fontWeight: 700,
              fontSize: '0.8rem',
              cursor: 'pointer',
            }}
          >
            Inspect Danger Shield &rarr;
          </button>
        </div>
      </div>

      {/* Main Filter Bar & Search */}
      <div style={{
        background: 'rgba(15, 23, 42, 0.65)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '16px',
        padding: '1.25rem 1.5rem',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '1rem',
      }}>
        {/* Category Toggle Pills */}
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {[
            { id: 'all', label: 'All Opportunities', icon: Compass },
            { id: 'dca_prime', label: '⭐ Layak Tabung (DCA)', icon: Sparkles },
            { id: 'value', label: 'Undervalued Quality', icon: TrendingUp },
            { id: 'smart_money', label: 'Smart Money (Bandarmology)', icon: Zap },
            { id: 'dividends', label: 'Cashflow Gems', icon: Coins },
            { id: 'danger', label: 'Danger Shield', icon: ShieldAlert },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeCategory === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveCategory(tab.id as any)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  padding: '0.5rem 0.85rem',
                  borderRadius: '8px',
                  fontSize: '0.8rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  border: isActive ? '1px solid #38bdf8' : '1px solid rgba(255, 255, 255, 0.08)',
                  background: isActive ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.03)',
                  color: isActive ? '#38bdf8' : '#9ca3af',
                  transition: 'all 0.15s ease',
                }}
              >
                <Icon size={14} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Live Search */}
        <div style={{ position: 'relative', width: '220px' }}>
          <Search size={16} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: '#64748b' }} />
          <input
            type="text"
            placeholder="Search code or sector..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              padding: '0.5rem 0.75rem 0.5rem 2rem',
              borderRadius: '8px',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              background: 'rgba(0, 0, 0, 0.3)',
              color: '#f8fafc',
              fontSize: '0.85rem',
            }}
          />
        </div>
      </div>

      {/* Main Table */}
      <div style={{
        background: 'rgba(15, 23, 42, 0.55)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '16px',
        padding: '1.5rem',
        overflowX: 'auto',
      }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', color: 'var(--text-secondary)', textAlign: 'left' }}>
              <th style={{ padding: '0.75rem 0.5rem', width: '40px' }}>Star</th>
              <th style={{ padding: '0.75rem 0.5rem' }}>Stock</th>
              <th style={{ padding: '0.75rem 0.5rem' }}>Price & Change</th>
              <th style={{ padding: '0.75rem 0.5rem' }}>Plain-English Verdict</th>
              <th style={{ padding: '0.75rem 0.5rem' }}>ROE %</th>
              <th style={{ padding: '0.75rem 0.5rem' }}>PBV</th>
              <th style={{ padding: '0.75rem 0.5rem' }}>Yield</th>
              <th style={{ padding: '0.75rem 0.5rem', textAlign: 'right' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredList.map((c) => {
              const divMatch = dividendOpps.find((d) => d.StockCode === c.code);
              const stealthMatch = stealthAnomalies.find((a) => a.StockCode === c.code);
              const price = c.price ?? c.previous_price ?? divMatch?.Price ?? 0;
              const chg = c.daily_change ?? (c.previous_price && c.price ? c.price - c.previous_price : 0);
              const chgPct = (c as any).daily_change_pct ?? stealthMatch?.PriceChangePct ?? (c.previous_price && c.previous_price > 0 ? (chg / c.previous_price) * 100 : 0);
              const starred = isStarred(c.code);

              // Plain English verdict
              const isStealth = stealthAnomalies.some((a) => a.StockCode === c.code && a.Signal === 'STEALTH_ACCUMULATION');
              const isTrap = stealthAnomalies.some((a) => a.StockCode === c.code && a.Signal === 'RETAIL_TRAP');
              const isGoodDiv = (c.yield ?? 0) >= 5.0;

              let verdictBadge = { text: 'Quality Compounder', color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.15)' };
              if (isStealth) {
                verdictBadge = { text: 'Smart Money Accumulation', color: '#34d399', bg: 'rgba(16, 185, 129, 0.2)' };
              } else if (isTrap) {
                verdictBadge = { text: 'Retail Trap - Avoid', color: '#f87171', bg: 'rgba(239, 68, 68, 0.2)' };
              } else if (isGoodDiv) {
                verdictBadge = { text: 'Safe Cashflow Gem', color: '#facc15', bg: 'rgba(234, 179, 8, 0.2)' };
              }

              return (
                <tr
                  key={c.code}
                  onClick={() => onSelectStock(c.code)}
                  style={{
                    borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                    cursor: 'pointer',
                  }}
                  className="table-row-hover"
                >
                  <td style={{ padding: '0.85rem 0.5rem' }}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onToggleStar(c);
                      }}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        cursor: 'pointer',
                        color: starred ? '#facc15' : 'rgba(255, 255, 255, 0.2)',
                        padding: 0,
                      }}
                      title={starred ? 'Starred' : 'Add to Watchlist'}
                    >
                      <Star size={16} fill={starred ? '#facc15' : 'none'} />
                    </button>
                  </td>
                  <td style={{ padding: '0.85rem 0.5rem' }}>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <strong style={{ color: '#f8fafc', fontSize: '0.95rem' }}>{c.code}</strong>
                        {c.is_blue_chip && (
                          <span style={{ fontSize: '0.65rem', padding: '0.1rem 0.35rem', borderRadius: '4px', background: 'rgba(56, 189, 248, 0.2)', color: '#38bdf8' }}>
                            LQ45
                          </span>
                        )}
                      </div>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{c.name}</span>
                    </div>
                  </td>
                  <td style={{ padding: '0.85rem 0.5rem' }}>
                    {price > 0 ? (
                      <>
                        <div style={{ fontWeight: 700, color: '#f8fafc' }}>
                          Rp {price.toLocaleString()}
                        </div>
                        <div style={{
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          color: chg > 0 ? '#10b981' : chg < 0 ? '#ef4444' : '#94a3b8'
                        }}>
                          {chg > 0
                            ? `+${chg.toLocaleString()} (+${chgPct.toFixed(1)}%)`
                            : chg < 0
                            ? `${chg.toLocaleString()} (${chgPct.toFixed(1)}%)`
                            : '0 (0.0%)'}
                        </div>
                      </>
                    ) : (
                      <>
                        <div style={{ fontWeight: 600, color: '#64748b' }}>—</div>
                        <div style={{ fontSize: '0.75rem', color: '#64748b' }}>—</div>
                      </>
                    )}
                  </td>
                  <td style={{ padding: '0.85rem 0.5rem' }}>
                    <span style={{
                      padding: '0.25rem 0.6rem',
                      borderRadius: '6px',
                      fontSize: '0.72rem',
                      fontWeight: 700,
                      color: verdictBadge.color,
                      background: verdictBadge.bg,
                      border: `1px solid ${verdictBadge.color}40`,
                    }}>
                      {verdictBadge.text}
                    </span>
                  </td>
                  <td style={{ padding: '0.85rem 0.5rem', fontWeight: 600, color: (c.roe ?? 0) >= 15 ? '#10b981' : '#cbd5e1' }}>
                    {c.roe ? `${c.roe}%` : '—'}
                  </td>
                  <td style={{ padding: '0.85rem 0.5rem', color: '#cbd5e1' }}>
                    {c.pbv ?? c.price_bv ? `${c.pbv ?? c.price_bv}x` : '—'}
                  </td>
                  <td style={{ padding: '0.85rem 0.5rem', fontWeight: 700, color: (c.yield ?? 0) >= 4 ? '#eab308' : '#94a3b8' }}>
                    {c.yield ? `${c.yield.toFixed(1)}%` : '—'}
                  </td>
                  <td style={{ padding: '0.85rem 0.5rem', textAlign: 'right' }}>
                    <div style={{ display: 'inline-flex', gap: '0.4rem' }}>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpenMemo(c);
                        }}
                        style={{
                          background: 'rgba(255, 255, 255, 0.05)',
                          border: '1px solid rgba(255, 255, 255, 0.15)',
                          color: '#cbd5e1',
                          padding: '0.35rem 0.6rem',
                          borderRadius: '6px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                        }}
                        title="1-Click Printable Memo"
                      >
                        <FileText size={12} />
                        <span>Memo</span>
                      </button>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectStock(c.code);
                        }}
                        style={{
                          background: 'rgba(56, 189, 248, 0.15)',
                          border: '1px solid rgba(56, 189, 248, 0.3)',
                          color: '#38bdf8',
                          padding: '0.35rem 0.6rem',
                          borderRadius: '6px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                        }}
                      >
                        <span>Terminal</span>
                        <ArrowRight size={12} />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Daily Market-Close Executive Briefing Modal */}
      {briefingOpen && (
        <DailyBriefingModal
          briefingData={briefingData}
          onClose={() => setBriefingOpen(false)}
          onSelectStock={onSelectStock}
        />
      )}
    </div>
  );
};
