import React, { useState, useMemo } from 'react';
import { 
  Search, 
  Building2, 
  TrendingUp, 
  Network, 
  Sparkles, 
  X, 
  ArrowUpDown, 
  ArrowUp, 
  ArrowDown, 
  Crown, 
  Gem, 
  ShieldCheck, 
  Percent, 
  RotateCcw,
  Zap
} from 'lucide-react';
import type { Company } from '../types';

interface ScreenerTabProps {
  companies: Company[];
  onSelectCompany: (company: Company) => void;
  selectedCompanyCode?: string;
}

export const ScreenerTab: React.FC<ScreenerTabProps> = ({
  companies,
  onSelectCompany,
  selectedCompanyCode,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSector, setSelectedSector] = useState('');
  const [scoreFilter, setScoreFilter] = useState<'all' | 'high' | 'medium' | 'low'>('all');
  const [valuationFilter, setValuationFilter] = useState<'all' | 'dca_prime' | 'sector_value' | 'undervalued' | 'pe15' | 'profitable' | 'dividend'>('all');

  // Quick toggle pill filters
  const [dcaOnly, setDcaOnly] = useState(false);
  const [noTrapsOnly, setNoTrapsOnly] = useState(true);
  const [blueChipOnly, setBlueChipOnly] = useState(false);
  const [tycoonOnly, setTycoonOnly] = useState(false);
  const [conglomOnly, setConglomOnly] = useState(false);
  const [deepValueOnly, setDeepValueOnly] = useState(false);
  const [highRoeOnly, setHighRoeOnly] = useState(false);

  // Sorting state
  const [sortKey, setSortKey] = useState<string>('score');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  // Unique sector list with company counts
  const sectorOptions = useMemo(() => {
    const counts = new Map<string, number>();
    companies.forEach((c) => {
      if (c.sector) {
        counts.set(c.sector, (counts.get(c.sector) || 0) + 1);
      }
    });
    return Array.from(counts.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [companies]);

  // Overall KPI statistics
  const stats = useMemo(() => {
    const total = companies.length;
    const npms = companies.map((c) => c.npm).filter((n): n is number => typeof n === 'number' && n > 0);
    const avgNpm = npms.length ? (npms.reduce((a, b) => a + b, 0) / npms.length).toFixed(1) + '%' : '0.0%';

    let totalBridges = 0;
    companies.forEach((c) => {
      totalBridges += c.shared_directors ? c.shared_directors.length : 0;
    });

    const topStock = companies.length > 0
      ? [...companies].sort((a, b) => (b.score?.total || 0) - (a.score?.total || 0))[0]
      : null;

    return {
      total,
      avgNpm,
      totalBridges,
      topStockCode: topStock ? topStock.code : 'N/A',
      topStockScore: topStock ? `${topStock.score.total.toFixed(0)} pts` : '',
    };
  }, [companies]);

  // Active filters count
  const hasActiveFilters = Boolean(
    searchQuery.trim() ||
    selectedSector ||
    scoreFilter !== 'all' ||
    valuationFilter !== 'all' ||
    dcaOnly ||
    !noTrapsOnly ||
    blueChipOnly ||
    tycoonOnly ||
    conglomOnly ||
    deepValueOnly ||
    highRoeOnly
  );

  const resetAllFilters = () => {
    setSearchQuery('');
    setSelectedSector('');
    setScoreFilter('all');
    setValuationFilter('all');
    setDcaOnly(false);
    setNoTrapsOnly(true);
    setBlueChipOnly(false);
    setTycoonOnly(false);
    setConglomOnly(false);
    setDeepValueOnly(false);
    setHighRoeOnly(false);
  };

  // Filter & Sort
  const filteredCompanies = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();

    const filtered = companies.filter((c) => {
      // 0. Anti-Value Trap Filter (Active by default)
      if (noTrapsOnly && c.is_value_trap) return false;

      // Search
      if (q) {
        const matchCode = c.code.toLowerCase().includes(q);
        const matchName = c.name.toLowerCase().includes(q);
        const matchSector = (c.sector || '').toLowerCase().includes(q);
        const matchIndustry = (c.industry || '').toLowerCase().includes(q);
        if (!matchCode && !matchName && !matchSector && !matchIndustry) return false;
      }

      // Sector
      if (selectedSector && c.sector !== selectedSector) return false;

      // Score filter
      const totalScore = c.score?.total || 0;
      if (scoreFilter === 'high' && totalScore < 70) return false;
      if (scoreFilter === 'medium' && (totalScore < 45 || totalScore >= 70)) return false;
      if (scoreFilter === 'low' && totalScore >= 45) return false;

      // Valuation & Quality dropdown
      const pbv = c.pbv ?? c.price_bv;
      const isSectorVal = c.is_undervalued || c.valuation_status === 'SECTOR_UNDERVALUED' || c.valuation_status === 'DEEP_VALUE';

      if (valuationFilter === 'dca_prime' && (!(c.compounder_score && c.compounder_score >= 70))) return false;
      if (valuationFilter === 'sector_value' && !isSectorVal) return false;
      if (valuationFilter === 'undervalued') {
        if (c.is_value_trap) return false;
        if (!isSectorVal && (!(pbv && pbv > 0 && pbv < 1.0))) return false;
      }
      if (valuationFilter === 'pe15' && (!(c.per && c.per > 0 && c.per < 15.0))) return false;
      if (valuationFilter === 'profitable' && (!(c.roe && c.roe >= 15.0))) return false;
      if (valuationFilter === 'dividend' && (!(c.yield && c.yield >= 4.0))) return false;

      // Quick pills
      if (dcaOnly && (!(c.compounder_score && c.compounder_score >= 70))) return false;
      if (blueChipOnly && !c.is_blue_chip) return false;
      if (tycoonOnly) {
        const hasTycoon = (c.shareholders || []).some((s) => s.is_super_insider);
        if (!hasTycoon) return false;
      }
      if (conglomOnly && !c.conglomerate) return false;
      if (deepValueOnly && (!(pbv && pbv > 0 && pbv < 1.0))) return false;
      if (highRoeOnly && (!(c.roe && c.roe >= 15.0))) return false;

      return true;
    });

    // Dynamic sorting
    filtered.sort((a, b) => {
      let valA: any;
      let valB: any;

      if (sortKey === 'score') {
        valA = a.score?.total ?? 0;
        valB = b.score?.total ?? 0;
      } else if (sortKey === 'code') {
        valA = a.code || '';
        valB = b.code || '';
      } else if (sortKey === 'name') {
        valA = a.name || '';
        valB = b.name || '';
      } else if (sortKey === 'sector') {
        valA = a.sector || '';
        valB = b.sector || '';
      } else if (sortKey === 'price_bv') {
        valA = a.pbv ?? a.price_bv ?? (sortOrder === 'asc' ? 999999 : -999999);
        valB = b.pbv ?? b.price_bv ?? (sortOrder === 'asc' ? 999999 : -999999);
      } else {
        valA = (a as any)[sortKey] ?? (sortOrder === 'asc' ? 999999 : -999999);
        valB = (b as any)[sortKey] ?? (sortOrder === 'asc' ? 999999 : -999999);
      }

      if (typeof valA === 'string' && typeof valB === 'string') {
        return sortOrder === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }
      return sortOrder === 'asc' ? valA - valB : valB - valA;
    });

    return filtered;
  }, [
    companies,
    searchQuery,
    selectedSector,
    scoreFilter,
    valuationFilter,
    blueChipOnly,
    tycoonOnly,
    conglomOnly,
    deepValueOnly,
    highRoeOnly,
    sortKey,
    sortOrder,
  ]);

  const handleHeaderClick = (key: string) => {
    if (sortKey === key) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortOrder(key === 'code' || key === 'name' || key === 'sector' ? 'asc' : 'desc');
    }
  };

  const renderSortArrow = (key: string) => {
    if (sortKey !== key) {
      return <ArrowUpDown size={12} style={{ opacity: 0.35, marginLeft: '4px' }} />;
    }
    return sortOrder === 'asc' ? (
      <ArrowUp size={13} style={{ color: 'var(--accent-gold)', marginLeft: '4px' }} />
    ) : (
      <ArrowDown size={13} style={{ color: 'var(--accent-gold)', marginLeft: '4px' }} />
    );
  };

  return (
    <div className="tab-panel active">
      {/* 4 Sleek Top Stat KPI Cards */}
      <div className="stats-grid">
        <div className="glass-card stat-card">
          <div className="stat-icon blue">
            <Building2 size={24} />
          </div>
          <div className="stat-info">
            <h3>Total Companies</h3>
            <p>{stats.total}</p>
          </div>
        </div>

        <div className="glass-card stat-card">
          <div className="stat-icon green">
            <TrendingUp size={24} />
          </div>
          <div className="stat-info">
            <h3>Avg Profit Margin</h3>
            <p>{stats.avgNpm}</p>
          </div>
        </div>

        <div className="glass-card stat-card">
          <div className="stat-icon purple">
            <Network size={24} />
          </div>
          <div className="stat-info">
            <h3>Overlapping Board Nodes</h3>
            <p>{stats.totalBridges}</p>
          </div>
        </div>

        <div className="glass-card stat-card">
          <div className="stat-icon orange">
            <Sparkles size={24} />
          </div>
          <div className="stat-info">
            <h3>Top Rated Stock</h3>
            <p style={{ fontSize: '1.35rem' }}>
              {stats.topStockCode}{' '}
              {stats.topStockScore && (
                <span style={{ fontSize: '0.85rem', color: 'var(--accent-gold)', fontWeight: 600 }}>
                  ({stats.topStockScore})
                </span>
              )}
            </p>
          </div>
        </div>
      </div>

      {/* Main Filter & Screener Container */}
      <div className="glass-card" style={{ marginBottom: '1.5rem' }}>
        {/* Header Title with Counter */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Zap size={22} style={{ color: 'var(--accent-gold)' }} />
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0 }}>Smart Money Synergy Screener</h2>
            <span style={{ fontSize: '0.75rem', background: 'rgba(59, 130, 246, 0.15)', color: 'var(--accent-blue)', padding: '0.15rem 0.5rem', borderRadius: '12px', border: '1px solid rgba(59, 130, 246, 0.25)', fontWeight: 600 }}>
              {filteredCompanies.length} of {companies.length}
            </span>
          </div>

          {hasActiveFilters && (
            <button className="btn-clear-filters" onClick={resetAllFilters}>
              <RotateCcw size={12} /> Reset All Filters
            </button>
          )}
        </div>

        {/* Primary Dropdowns Grid */}
        <div className="filter-bar">
          <div className="input-group">
            <Search size={16} />
            <input
              type="text"
              className="form-control"
              placeholder="Search ticker, name, industry (e.g. BBCA, Adaro, Coal)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                style={{ position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)', background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
              >
                <X size={14} />
              </button>
            )}
          </div>

          <div>
            <select
              className="form-control"
              value={selectedSector}
              onChange={(e) => setSelectedSector(e.target.value)}
            >
              <option value="">All Sectors ({companies.length})</option>
              {sectorOptions.map(([sector, count]) => (
                <option key={sector} value={sector}>
                  {sector} ({count})
                </option>
              ))}
            </select>
          </div>

          <div>
            <select
              className="form-control"
              value={scoreFilter}
              onChange={(e) => setScoreFilter(e.target.value as any)}
            >
              <option value="all">All SMSS Scores</option>
              <option value="high">🟢 High Alpha (≥70 SMSS)</option>
              <option value="medium">🟡 Medium Tier (45–70 SMSS)</option>
              <option value="low">🔴 Low Score (&lt;45 SMSS)</option>
            </select>
          </div>

          <div>
            <select
              className="form-control"
              value={valuationFilter}
              onChange={(e) => setValuationFilter(e.target.value as any)}
            >
              <option value="all">All Valuations</option>
              <option value="dca_prime">⭐ Layak Tabung (DCA Score ≥ 70)</option>
              <option value="sector_value">🏦 Sektor Undervalued (Justified Model)</option>
              <option value="undervalued">💎 Clean Undervalued (No Traps)</option>
              <option value="pe15">📊 Value P/E (P/E &lt; 15)</option>
              <option value="profitable">🚀 High Profit (ROE ≥ 15%)</option>
              <option value="dividend">💰 High Yield (Yield ≥ 4%)</option>
            </select>
          </div>
        </div>

        {/* Quick Filter Badges Row */}
        <div className="filter-pills-row" style={{ flexWrap: 'wrap', gap: '0.4rem' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 600, marginRight: '0.25rem' }}>
            Quick Filters:
          </span>

          <button
            className={`filter-pill green ${dcaOnly ? 'active' : ''}`}
            onClick={() => setDcaOnly(!dcaOnly)}
            style={{ fontWeight: 700 }}
          >
            <Sparkles size={14} /> ⭐ Layak Tabung (DCA)
          </button>

          <button
            className={`filter-pill ${noTrapsOnly ? 'active' : ''}`}
            onClick={() => setNoTrapsOnly(!noTrapsOnly)}
            style={{ background: noTrapsOnly ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)', border: noTrapsOnly ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(239, 68, 68, 0.4)' }}
            title="Saring otomatis saham dengan indikasi laba semu/penjualan aset sesaat"
          >
            <ShieldCheck size={14} /> 🛡️ Anti-Trap: {noTrapsOnly ? 'ON' : 'OFF'}
          </button>

          <button
            className={`filter-pill ${blueChipOnly ? 'active' : ''}`}
            onClick={() => setBlueChipOnly(!blueChipOnly)}
          >
            <ShieldCheck size={14} /> Blue Chips
          </button>

          <button
            className={`filter-pill gold ${tycoonOnly ? 'active' : ''}`}
            onClick={() => setTycoonOnly(!tycoonOnly)}
          >
            <Crown size={14} /> Tycoon Stakes
          </button>

          <button
            className={`filter-pill purple ${conglomOnly ? 'active' : ''}`}
            onClick={() => setConglomOnly(!conglomOnly)}
          >
            <Network size={14} /> Conglomerates
          </button>

          <button
            className={`filter-pill green ${deepValueOnly ? 'active' : ''}`}
            onClick={() => setDeepValueOnly(!deepValueOnly)}
          >
            <Gem size={14} /> PBV &lt; 1.0x
          </button>

          <button
            className={`filter-pill green ${highRoeOnly ? 'active' : ''}`}
            onClick={() => setHighRoeOnly(!highRoeOnly)}
          >
            <Percent size={14} /> ROE ≥ 15%
          </button>
        </div>
      </div>

      {/* Table Section */}
      <div className="glass-card" style={{ padding: '0.75rem 1.25rem' }}>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th onClick={() => handleHeaderClick('code')} style={{ cursor: 'pointer' }}>
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    Ticker {renderSortArrow('code')}
                  </div>
                </th>
                <th onClick={() => handleHeaderClick('name')} style={{ cursor: 'pointer' }}>
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    Company Name {renderSortArrow('name')}
                  </div>
                </th>
                <th onClick={() => handleHeaderClick('sector')} style={{ cursor: 'pointer' }}>
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    Sector {renderSortArrow('sector')}
                  </div>
                </th>
                <th onClick={() => handleHeaderClick('roe')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
                    ROE% {renderSortArrow('roe')}
                  </div>
                </th>
                <th onClick={() => handleHeaderClick('per')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
                    P/E {renderSortArrow('per')}
                  </div>
                </th>
                <th onClick={() => handleHeaderClick('price_bv')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
                    P/B {renderSortArrow('price_bv')}
                  </div>
                </th>
                <th onClick={() => handleHeaderClick('de_ratio')} style={{ cursor: 'pointer', textAlign: 'right' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
                    D/E {renderSortArrow('de_ratio')}
                  </div>
                </th>
                <th onClick={() => handleHeaderClick('score')} style={{ cursor: 'pointer', textAlign: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    SMSS Score {renderSortArrow('score')}
                  </div>
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredCompanies.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', padding: '3rem 1rem', color: 'var(--text-secondary)' }}>
                    <p style={{ fontSize: '1.1rem', marginBottom: '0.75rem' }}>No companies match the selected filters.</p>
                    <button className="nav-btn active" style={{ margin: '0 auto', cursor: 'pointer' }} onClick={resetAllFilters}>
                      <RotateCcw size={14} style={{ marginRight: '0.4rem' }} /> Clear Filters
                    </button>
                  </td>
                </tr>
              ) : (
                filteredCompanies.map((c) => {
                  const score = c.score ? c.score.total : 0;
                  let scoreClass = 'low';
                  if (score >= 70) scoreClass = 'high';
                  else if (score >= 45) scoreClass = 'medium';

                  const pbvVal = c.pbv ?? c.price_bv;
                  const isSelected = selectedCompanyCode === c.code;
                  const hasTycoon = (c.shareholders || []).some((s) => s.is_super_insider);

                  return (
                    <tr
                      key={c.code}
                      className={isSelected ? 'selected' : ''}
                      onClick={() => onSelectCompany(c)}
                    >
                      <td>
                        <span className="ticker-badge">{c.code}</span>
                        {c.is_blue_chip && <span className="tag-bc" title="Blue Chip Component">BC</span>}
                        {hasTycoon && <span className="tag-tycoon" title="Tycoon Stakes Owned">👑</span>}
                        {c.is_value_trap && (
                          <span style={{ background: 'rgba(239, 68, 68, 0.25)', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.4)', padding: '1px 5px', borderRadius: '4px', fontSize: '0.68rem', fontWeight: 800, marginLeft: '4px' }} title="Peringatan Forensik: Indikasi laba semu/penjualan aset sesaat">
                            ⚠️ TRAP
                          </span>
                        )}
                        {c.dca_verdict === 'PRIME_DCA' && (
                          <span style={{ background: 'rgba(16, 185, 129, 0.25)', color: '#34d399', border: '1px solid rgba(16, 185, 129, 0.4)', padding: '1px 5px', borderRadius: '4px', fontSize: '0.68rem', fontWeight: 800, marginLeft: '4px' }} title="Layak Tabung (DCA Prime Compounder)">
                            💎 DCA
                          </span>
                        )}
                        {c.valuation_status === 'SECTOR_UNDERVALUED' && (
                          <span style={{ background: 'rgba(56, 189, 248, 0.25)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.4)', padding: '1px 5px', borderRadius: '4px', fontSize: '0.68rem', fontWeight: 800, marginLeft: '4px' }} title="Sektor Undervalued: Justified Model">
                            🏦 VALUE
                          </span>
                        )}
                      </td>
                      <td className="company-name-cell">
                        <div style={{ maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {c.name}
                        </div>
                      </td>
                      <td style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                        {c.sector}
                      </td>
                      <td
                        className={`numeric ${c.roe && c.roe >= 15 ? 'positive' : c.roe && c.roe < 0 ? 'negative' : ''}`}
                        style={{ textAlign: 'right' }}
                      >
                        {c.roe !== null && c.roe !== undefined ? `${c.roe.toFixed(1)}%` : '-'}
                      </td>
                      <td
                        className={`numeric ${c.per && c.per > 0 && c.per <= 12 ? 'positive' : ''}`}
                        style={{ textAlign: 'right' }}
                      >
                        {c.per !== null && c.per !== undefined ? c.per.toFixed(1) : '-'}
                      </td>
                      <td
                        className={`numeric ${pbvVal && pbvVal > 0 && pbvVal < 1.0 ? 'positive' : ''}`}
                        style={{ textAlign: 'right' }}
                      >
                        {pbvVal !== null && pbvVal !== undefined ? pbvVal.toFixed(2) : '-'}
                      </td>
                      <td className="numeric" style={{ textAlign: 'right' }}>
                        {c.de_ratio !== null && c.de_ratio !== undefined ? c.de_ratio.toFixed(2) : '-'}
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <span className={`score-badge ${scoreClass}`}>
                          {score.toFixed(0)}
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
