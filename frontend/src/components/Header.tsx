import React from 'react';
import { Compass, CandlestickChart, Network, PlayCircle, Database, Star, Bell, Handshake, Layers, TrendingUp } from 'lucide-react';
import type { TabType } from '../types';

interface HeaderProps {
  activeTab: TabType;
  onSelectTab: (tab: TabType) => void;
  isConnected: boolean;
  watchlistCount: number;
  onOpenWatchlist: () => void;
  onOpenAlerts: () => void;
  unreadAlertsCount: number;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  onSelectTab,
  isConnected,
  watchlistCount,
  onOpenWatchlist,
  onOpenAlerts,
  unreadAlertsCount,
}) => {
  const tabs: { id: TabType; label: string; icon: React.ComponentType<{ size?: number; style?: React.CSSProperties }> }[] = [
    { id: 'opportunities', label: 'Alpha Finder', icon: Compass },
    { id: 'terminal', label: 'Stock Terminal', icon: CandlestickChart },
    { id: 'power_map', label: 'Tycoons & Power Map', icon: Network },
    { id: 'simulator', label: 'Strategy Simulator', icon: PlayCircle },
    { id: 'deals', label: 'Deal Tracker', icon: Handshake },
    { id: 'rights', label: 'Rights Issues', icon: Layers },
    { id: 'momentum', label: 'Momentum', icon: TrendingUp },
    { id: 'ingestion', label: 'Data Ingestion', icon: Database },
  ];

  return (
    <header style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0.85rem 2rem',
      background: 'rgba(7, 10, 19, 0.92)',
      backdropFilter: 'blur(20px)',
      borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      {/* Brand Logo */}
      <div className="logo-container" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', cursor: 'pointer' }} onClick={() => onSelectTab('opportunities')}>
        <div style={{
          width: '36px',
          height: '36px',
          borderRadius: '10px',
          background: 'linear-gradient(135deg, #0284c7 0%, #38bdf8 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 0 15px rgba(56, 189, 248, 0.3)',
        }}>
          <Compass size={22} style={{ color: '#fff' }} />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <span style={{ fontWeight: 800, fontSize: '1.05rem', color: '#f8fafc', letterSpacing: '-0.3px' }}>
            IDX Smart Money
          </span>
          <span style={{ fontSize: '0.7rem', color: '#38bdf8', fontWeight: 600 }}>
            Alpha Terminal &bull; BEI
          </span>
        </div>
      </div>

      {/* 4 Clean Pillars */}
      <nav style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', justifyContent: 'center' }}>
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              className={`nav-btn ${isActive ? 'active' : ''}`}
              onClick={() => onSelectTab(tab.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.55rem 1.1rem',
                borderRadius: '10px',
                fontSize: '0.85rem',
                fontWeight: 700,
                cursor: 'pointer',
                border: isActive ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid transparent',
                background: isActive ? 'rgba(56, 189, 248, 0.15)' : 'transparent',
                color: isActive ? '#38bdf8' : '#94a3b8',
                transition: 'all 0.15s ease',
              }}
            >
              <Icon size={16} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Utility Actions: Watchlist, Alerts, Live Feed */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        {/* Watchlist Pill Button */}
        <button
          onClick={onOpenWatchlist}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
            padding: '0.45rem 0.85rem',
            borderRadius: '20px',
            border: '1px solid rgba(250, 204, 21, 0.3)',
            background: 'rgba(250, 204, 21, 0.1)',
            color: '#facc15',
            fontSize: '0.8rem',
            fontWeight: 700,
            cursor: 'pointer',
          }}
          title="Open My Watchlist"
        >
          <Star size={14} fill="#facc15" />
          <span>Watchlist ({watchlistCount})</span>
        </button>

        {/* Live Anomaly Alerts Bell */}
        <button
          onClick={onOpenAlerts}
          style={{
            position: 'relative',
            background: 'rgba(255, 255, 255, 0.05)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: '50%',
            width: '34px',
            height: '34px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#cbd5e1',
            cursor: 'pointer',
          }}
          title="Live Anomaly Alerts"
        >
          <Bell size={16} />
          {unreadAlertsCount > 0 && (
            <span style={{
              position: 'absolute',
              top: '-2px',
              right: '-2px',
              background: '#ef4444',
              color: '#fff',
              fontSize: '0.65rem',
              fontWeight: 800,
              width: '16px',
              height: '16px',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '2px solid #070a13',
            }}>
              {unreadAlertsCount}
            </span>
          )}
        </button>

        {/* Live WebSocket Indicator */}
        <div
          id="wsBadge"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '0.75rem',
            padding: '0.35rem 0.65rem',
            borderRadius: '20px',
            border: isConnected ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(255, 255, 255, 0.1)',
            background: isConnected ? 'rgba(16, 185, 129, 0.12)' : 'rgba(255, 255, 255, 0.05)',
            color: isConnected ? '#10b981' : '#9ca3af',
            fontFamily: 'monospace',
            fontWeight: 600,
          }}
          title={isConnected ? 'Live WebSocket Connected' : 'Live Feed Disconnected'}
        >
          <span
            style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              background: isConnected ? '#10b981' : '#9ca3af',
              boxShadow: isConnected ? '0 0 8px #10b981' : 'none',
            }}
          />
          <span>{isConnected ? 'LIVE' : 'OFFLINE'}</span>
        </div>
      </div>
    </header>
  );
};
