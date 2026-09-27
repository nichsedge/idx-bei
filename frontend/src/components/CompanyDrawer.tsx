import React, { useEffect } from 'react';
import { X, TrendingUp, Network } from 'lucide-react';
import type { Company } from '../types';
import { NetworkGraph } from './NetworkGraph';

interface CompanyDrawerProps {
  company: Company | null;
  onClose: () => void;
  onViewCharts: (code: string) => void;
}

export const CompanyDrawer: React.FC<CompanyDrawerProps> = ({
  company,
  onClose,
  onViewCharts,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!company) return null;

  const score = company.score || { financial: 0, valuation: 0, network: 0, total: 0 };

  return (
    <div className="workspace-detail glass-card active" style={{ width: '420px', maxWidth: '100%' }}>
      <div className="detail-header">
        <div>
          <span className="ticker-badge">{company.code}</span>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: '0.5rem' }}>{company.name}</h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
            {company.sector} {company.sub_sector ? `/ ${company.sub_sector}` : ''}
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button
            className="nav-btn active"
            style={{ padding: '0.35rem 0.65rem', fontSize: '0.8rem', cursor: 'pointer' }}
            onClick={() => onViewCharts(company.code)}
            title="View Interactive Chart"
          >
            <TrendingUp size={14} />
          </button>
          <button className="close-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
      </div>

      {/* Mini Financial Summary Cards */}
      <div className="metrics-summary-grid">
        <div className="metric-mini-card">
          <span>ROE</span>
          <p className={company.roe && company.roe >= 15 ? 'positive' : company.roe && company.roe < 0 ? 'negative' : ''}>
            {company.roe ? `${company.roe.toFixed(1)}%` : '-'}
          </p>
        </div>
        <div className="metric-mini-card">
          <span>P/E Ratio</span>
          <p className={company.per && company.per > 0 && company.per <= 12 ? 'positive' : ''}>
            {company.per ? company.per.toFixed(1) : '-'}
          </p>
        </div>
        <div className="metric-mini-card">
          <span>Price / Book</span>
          <p className={company.price_bv && company.price_bv < 1.0 ? 'positive' : ''}>
            {company.price_bv ? company.price_bv.toFixed(2) : '-'}
          </p>
        </div>
      </div>

      {/* AI Forensic & DCA Intelligence Card */}
      <div style={{
        marginTop: '1rem',
        padding: '1rem',
        borderRadius: '12px',
        background: company.is_value_trap ? 'rgba(239, 68, 68, 0.12)' : 'rgba(56, 189, 248, 0.08)',
        border: `1px solid ${company.is_value_trap ? 'rgba(239, 68, 68, 0.4)' : 'rgba(56, 189, 248, 0.25)'}`,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
          <span style={{ fontSize: '0.8rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.5px', color: company.is_value_trap ? '#f87171' : '#38bdf8' }}>
            🧠 AI Forensic & DCA Verdict
          </span>
          <span style={{
            fontSize: '0.75rem',
            fontWeight: 800,
            padding: '2px 8px',
            borderRadius: '6px',
            background: company.is_value_trap ? 'rgba(239, 68, 68, 0.25)' : (company.compounder_score && company.compounder_score >= 70 ? 'rgba(16, 185, 129, 0.25)' : 'rgba(255, 255, 255, 0.1)'),
            color: company.is_value_trap ? '#fca5a5' : (company.compounder_score && company.compounder_score >= 70 ? '#6ee7b7' : '#cbd5e1')
          }}>
            {company.dca_rating || (company.is_value_trap ? '🚨 Value Trap' : 'Neutral')}
          </span>
        </div>

        {company.justified_pbv && (
          <div style={{ fontSize: '0.78rem', color: '#93c5fd', marginBottom: '0.4rem', fontWeight: 600 }}>
            🏦 Sector Model: Justified PBV <strong>{company.justified_pbv}x</strong> vs Pasar <strong>{company.price_bv?.toFixed(2) || '-'}x</strong>
          </div>
        )}

        <p style={{ margin: 0, fontSize: '0.82rem', lineHeight: 1.45, color: company.is_value_trap ? '#fca5a5' : '#cbd5e1' }}>
          {company.ai_thesis || (company.is_value_trap 
            ? 'Peringatan Forensik: Indikasi laba semu atau pos luar biasa non-operasional. Hindari untuk tabungan jangka panjang.' 
            : 'Perusahaan memiliki profil operasional stabil.')}
        </p>

        {company.forensic_reasons && company.forensic_reasons.length > 0 && (
          <div style={{ marginTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '3px' }}>
            {company.forensic_reasons.map((r, i) => (
              <span key={i} style={{ fontSize: '0.72rem', color: '#f87171' }}>• {r}</span>
            ))}
          </div>
        )}
      </div>

      {/* SMSS Score Breakdown */}
      <div className="score-breakdown">
        <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '0.75rem', display: 'flex', justifyContent: 'space-between' }}>
          <span>SMSS Score Breakdown</span>
          <span style={{ color: 'var(--accent-gold)', fontWeight: 800 }}>{score.total.toFixed(0)} / 100</span>
        </h3>

        <div className="score-breakdown-row">
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Financial Health (40)</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.85rem', fontFamily: 'monospace' }}>{score.financial.toFixed(0)}</span>
            <div className="progress-bar-container">
              <div className="progress-bar financial" style={{ width: `${(score.financial / 40) * 100}%` }} />
            </div>
          </div>
        </div>

        <div className="score-breakdown-row">
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Valuation Discount (30)</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.85rem', fontFamily: 'monospace' }}>{score.valuation.toFixed(0)}</span>
            <div className="progress-bar-container">
              <div className="progress-bar valuation" style={{ width: `${(score.valuation / 30) * 100}%` }} />
            </div>
          </div>
        </div>

        <div className="score-breakdown-row">
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Network Leverage (30)</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.85rem', fontFamily: 'monospace' }}>{score.network.toFixed(0)}</span>
            <div className="progress-bar-container">
              <div className="progress-bar network" style={{ width: `${(score.network / 30) * 100}%` }} />
            </div>
          </div>
        </div>
      </div>

      {/* Corporate Relationship Vis.js Network Graph */}
      <h3 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px', marginTop: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
        <Network size={15} /> Corporate Relationship Graph
      </h3>
      <div style={{ marginTop: '0.5rem', position: 'relative' }}>
        <NetworkGraph company={company} />
      </div>

      {/* Board & Executive Roster */}
      <div className="accordion-section">
        <div className="accordion-header">
          <span>Board & Executive Roster</span>
          <span style={{ fontSize: '0.8rem', background: 'rgba(255, 255, 255, 0.05)', padding: '0.1rem 0.4rem', borderRadius: '4px' }}>
            {company.board_members?.length || 0}
          </span>
        </div>
        <div className="accordion-content">
          {(company.board_members || []).map((b, idx) => (
            <div key={`${b.name}-${idx}`} className="accordion-item">
              <span style={{ fontWeight: 500 }}>{b.name}</span>
              <span
                className="sub-role"
                style={{
                  background: b.role === 'Director' ? 'rgba(59, 130, 246, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                  color: b.role === 'Director' ? 'var(--accent-blue)' : 'var(--accent-orange)',
                }}
              >
                {b.title || b.role || 'Board'}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Top Registered Shareholders */}
      <div className="accordion-section">
        <div className="accordion-header">
          <span>Top Registered Shareholders</span>
          <span style={{ fontSize: '0.8rem', background: 'rgba(255, 255, 255, 0.05)', padding: '0.1rem 0.4rem', borderRadius: '4px' }}>
            {company.shareholders?.length || 0}
          </span>
        </div>
        <div className="accordion-content">
          {(company.shareholders || []).map((s, idx) => (
            <div key={`${s.name}-${idx}`} className="accordion-item">
              <span style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '180px' }}>
                {s.name}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {s.is_controller && (
                  <span style={{ fontSize: '0.65rem', color: 'var(--accent-gold)', border: '1px solid rgba(251, 191, 36, 0.3)', padding: '0.05rem 0.25rem', borderRadius: '3px' }}>
                    Controller
                  </span>
                )}
                <span className="numeric" style={{ fontWeight: 600 }}>
                  {s.percentage.toFixed(2)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Corporate Subsidiaries */}
      {company.subsidiaries && company.subsidiaries.length > 0 && (
        <div className="accordion-section">
          <div className="accordion-header">
            <span>Corporate Subsidiaries</span>
            <span style={{ fontSize: '0.8rem', background: 'rgba(255, 255, 255, 0.05)', padding: '0.1rem 0.4rem', borderRadius: '4px' }}>
              {company.subsidiaries.length}
            </span>
          </div>
          <div className="accordion-content">
            {company.subsidiaries.map((sub, idx) => (
              <div key={`${sub.name}-${idx}`} className="accordion-item">
                <span style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '180px' }}>
                  {sub.name}
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                    {sub.bidang_usaha || 'Subsidiary'}
                  </span>
                  <span className="numeric" style={{ fontWeight: 600 }}>
                    {sub.percentage.toFixed(1)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
