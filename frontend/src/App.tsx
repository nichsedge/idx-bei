import React, { useState, useEffect, Suspense, lazy } from 'react';
import { Header } from './components/Header';
import { AlphaHub } from './components/AlphaHub';
import { useDashboardData } from './hooks/useDashboardData';
import { useLiveStream } from './hooks/useLiveStream';
import { useWatchlist } from './hooks/useWatchlist';
import { AlertTriangle, Loader2 } from 'lucide-react';
import type { TabType, Company, LiveAlert } from './types';

// Code-split heavy sub-panels and visualization graphs
const ChartTab = lazy(() => import('./components/ChartTab').then(m => ({ default: m.ChartTab })));
const PowerMapTab = lazy(() => import('./components/PowerMapTab').then(m => ({ default: m.PowerMapTab })));
const BacktesterTab = lazy(() => import('./components/BacktesterTab').then(m => ({ default: m.BacktesterTab })));
const IngestionTab = lazy(() => import('./components/IngestionTab').then(m => ({ default: m.IngestionTab })));
const InvestorMemoModal = lazy(() => import('./components/InvestorMemoModal').then(m => ({ default: m.InvestorMemoModal })));
const WatchlistDrawer = lazy(() => import('./components/WatchlistDrawer').then(m => ({ default: m.WatchlistDrawer })));

const TabFallback: React.FC = () => (
  <div style={{
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '420px',
    gap: '1rem',
    color: 'var(--text-secondary)',
  }}>
    <Loader2 size={36} className="spinning" style={{ color: '#38bdf8' }} />
    <span style={{ fontSize: '0.9rem', fontWeight: 500 }}>Loading quantitative view...</span>
  </div>
);

function parseRouteFromUrl(): { tab: TabType; ticker: string } {
  if (typeof window === 'undefined') {
    return { tab: 'opportunities', ticker: 'BBCA' };
  }

  // Check search query parameters: ?tab=terminal&ticker=BBCA
  const searchParams = new URLSearchParams(window.location.search);
  let tabParam = searchParams.get('tab') as TabType | null;
  let tickerParam = searchParams.get('ticker') || searchParams.get('stock');

  // Check hash: #terminal?ticker=BBCA or #power_map or direct ticker like #BBCA
  const hash = window.location.hash.replace(/^#\/?/, '');
  if (hash) {
    const [hashPath, hashQuery] = hash.split('?');
    if (hashPath) {
      if (['opportunities', 'terminal', 'power_map', 'simulator', 'ingestion'].includes(hashPath)) {
        tabParam = hashPath as TabType;
      } else if (/^[A-Za-z0-9]{4,5}$/.test(hashPath)) {
        tabParam = 'terminal';
        tickerParam = hashPath.toUpperCase();
      }
    }
    if (hashQuery) {
      const hashParams = new URLSearchParams(hashQuery);
      if (hashParams.get('ticker')) tickerParam = hashParams.get('ticker');
      if (hashParams.get('stock')) tickerParam = hashParams.get('stock');
      if (hashParams.get('tab')) tabParam = hashParams.get('tab') as TabType;
    }
  }

  const validTabs: TabType[] = ['opportunities', 'terminal', 'power_map', 'simulator', 'ingestion'];
  const tab = tabParam && validTabs.includes(tabParam) ? tabParam : 'opportunities';
  const ticker = (tickerParam || 'BBCA').toUpperCase();

  return { tab, ticker };
}

function syncRouteToUrl(tab: TabType, ticker: string, replace = false) {
  if (typeof window === 'undefined') return;

  let newHash = `#${tab}`;
  if (tab === 'terminal') {
    newHash += `?ticker=${ticker.toUpperCase()}`;
  }

  // Automatically update document title for crisp browser bookmarks (Ctrl+D)
  if (tab === 'terminal') {
    document.title = `${ticker.toUpperCase()} • IDX Smart Money Terminal`;
  } else if (tab === 'opportunities') {
    document.title = 'Alpha Finder • IDX Smart Money';
  } else if (tab === 'power_map') {
    document.title = 'Tycoons & Power Map • IDX Smart Money';
  } else if (tab === 'simulator') {
    document.title = 'Strategy Simulator • IDX Smart Money';
  } else if (tab === 'ingestion') {
    document.title = 'Data Ingestion & Backfill • IDX Smart Money';
  }

  if (window.location.hash !== newHash) {
    if (replace) {
      window.history.replaceState(null, '', newHash);
    } else {
      window.history.pushState(null, '', newHash);
    }
  }
}

export const App: React.FC = () => {
  const initialRoute = parseRouteFromUrl();
  const [activeTab, setActiveTab] = useState<TabType>(initialRoute.tab);
  const [selectedTicker, setSelectedTicker] = useState<string>(initialRoute.ticker);
  const [memoCompany, setMemoCompany] = useState<Company | null>(null);
  const [isWatchlistOpen, setIsWatchlistOpen] = useState<boolean>(false);
  const [alerts, setAlerts] = useState<LiveAlert[]>([
    {
      id: 'alert-1',
      ticker: 'GOTO',
      type: 'STEALTH_ACCUMULATION',
      title: 'Stealth Accumulation Detected',
      message: 'Tier-1 institutional brokers accumulated net +Rp 840M while price remained flat at Rp 50.',
      timestamp: 'Today',
    },
    {
      id: 'alert-2',
      ticker: 'LABS',
      type: 'RETAIL_TRAP',
      title: 'Retail Distribution Trap',
      message: 'Retail brokers pumped price +23.6% while foreign institutional capital aggressively distributed.',
      timestamp: 'Today',
    },
  ]);

  const { data, loading, error, reload } = useDashboardData();
  const { isConnected, lastEvent } = useLiveStream();
  const { watchlist, isStarred, toggleStar, removeStar } = useWatchlist();

  // Sync route on mount and listen to browser Back/Forward (popstate/hashchange)
  useEffect(() => {
    syncRouteToUrl(activeTab, selectedTicker, true);

    const handleUrlChange = () => {
      const { tab, ticker } = parseRouteFromUrl();
      setActiveTab(tab);
      setSelectedTicker(ticker);
    };

    window.addEventListener('popstate', handleUrlChange);
    window.addEventListener('hashchange', handleUrlChange);

    return () => {
      window.removeEventListener('popstate', handleUrlChange);
      window.removeEventListener('hashchange', handleUrlChange);
    };
  }, []);

  // Handle ingestion completion or live anomalies from WebSocket
  useEffect(() => {
    if (!lastEvent) return;
    if (lastEvent.type === 'ingestion_completed') {
      console.log('[WebSocket] Ingestion event received -> reloading dashboard data');
      reload();
    } else if (lastEvent.type === 'stealth_accumulation' && lastEvent.ticker) {
      setAlerts((prev) => [
        {
          id: `alert-${Date.now()}`,
          ticker: lastEvent.ticker!,
          type: 'STEALTH_ACCUMULATION',
          title: 'Stealth Accumulation',
          message: `Institutional inflow detected on ${lastEvent.ticker}`,
          timestamp: 'Just now',
        },
        ...prev,
      ]);
    }
  }, [lastEvent, reload]);

  const handleSelectTab = (tab: TabType) => {
    setActiveTab(tab);
    syncRouteToUrl(tab, selectedTicker);
  };

  const handleSelectStock = (ticker: string) => {
    const upper = ticker.toUpperCase();
    setSelectedTicker(upper);
    setActiveTab('terminal');
    syncRouteToUrl('terminal', upper);
  };

  const handleSelectTicker = (ticker: string) => {
    const upper = ticker.toUpperCase();
    setSelectedTicker(upper);
    syncRouteToUrl('terminal', upper);
  };

  const handleOpenMemo = (company: Company) => {
    setMemoCompany(company);
  };

  return (
    <div className="app-container">
      <Header
        activeTab={activeTab}
        onSelectTab={handleSelectTab}
        isConnected={isConnected}
        watchlistCount={watchlist.length}
        onOpenWatchlist={() => setIsWatchlistOpen(true)}
        onOpenAlerts={() => setIsWatchlistOpen(true)}
        unreadAlertsCount={alerts.length}
      />

      <main className="main-container" style={{ padding: '1.5rem 2rem' }}>
        {error && !data && (
          <div className="error-banner">
            <AlertTriangle size={48} />
            <h2>Data Unavailable</h2>
            <p>{error}</p>
            <p>Ensure that the backend ingestion pipeline or mock file has run:</p>
            <code>uv run idx all && uv run idx serve</code>
          </div>
        )}

        {loading && !data && (
          <div style={{ textAlign: 'center', padding: '4rem', color: 'var(--text-secondary)' }}>
            <p style={{ fontSize: '1.2rem' }}>Loading quantitative intelligence...</p>
          </div>
        )}

        {data && (
          <Suspense fallback={<TabFallback />}>
            {/* 1. Alpha Finder (Opportunities Hub) */}
            {activeTab === 'opportunities' && (
              <AlphaHub
                companies={data.companies}
                onSelectStock={handleSelectStock}
                onOpenMemo={handleOpenMemo}
                isStarred={isStarred}
                onToggleStar={toggleStar}
              />
            )}

            {/* 2. Stock Terminal (TradingView Charts & Indicators & Order Flow) */}
            {activeTab === 'terminal' && (
              <ChartTab
                companies={data.companies}
                selectedTicker={selectedTicker}
                onSelectTicker={handleSelectTicker}
                lastLiveEvent={lastEvent}
                onOpenMemo={handleOpenMemo}
                isStarred={isStarred}
                onToggleStar={toggleStar}
              />
            )}

            {/* 3. Tycoons & Power Map (Super-Insiders, Conglomerates, & UBO Graph) */}
            {activeTab === 'power_map' && (
              <PowerMapTab
                companies={data.companies}
                superInsiders={data.super_insiders}
                conglomerates={data.conglomerates}
                onSelectCompany={handleSelectStock}
              />
            )}

            {/* 4. Strategy Simulator (Vectorized Backtester) */}
            {activeTab === 'simulator' && (
              <BacktesterTab
                onSelectStock={handleSelectStock}
              />
            )}

            {/* 5. Data Ingestion & Backfill Horizon Status */}
            {activeTab === 'ingestion' && (
              <IngestionTab
                lastLiveEvent={lastEvent}
              />
            )}

            {/* 1-Click Printable Investor Dossier / Memo Modal */}
            {memoCompany && (
              <InvestorMemoModal
                company={memoCompany}
                onClose={() => setMemoCompany(null)}
              />
            )}

            {/* Watchlist & Live Alerts Slide-over Drawer */}
            <WatchlistDrawer
              isOpen={isWatchlistOpen}
              onClose={() => setIsWatchlistOpen(false)}
              watchlist={watchlist}
              onRemoveWatchlist={removeStar}
              onSelectStock={handleSelectStock}
              alerts={alerts}
            />
          </Suspense>
        )}
      </main>

      <footer style={{
        textAlign: 'center',
        padding: '1.5rem',
        borderTop: '1px solid rgba(255, 255, 255, 0.06)',
        color: 'var(--text-secondary)',
        fontSize: '0.8rem',
      }}>
        <p style={{ margin: 0 }}>
          Smart Money & Network Alpha Finder &copy; 2026 &bull; Designed for high-conviction decision making on the Indonesia Stock Exchange.
        </p>
      </footer>
    </div>
  );
};

export default App;
