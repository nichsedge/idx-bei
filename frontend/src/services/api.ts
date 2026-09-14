import type { DashboardData } from '../types';

export async function fetchDashboardData(): Promise<DashboardData> {
  // Check if loaded via window script tag fallback (supports uppercase and camelCase)
  if (typeof window !== 'undefined') {
    const globalData = (window as any).NETWORK_ALPHA_DATA || (window as any).networkAlphaData;
    if (globalData && Array.isArray(globalData.companies) && globalData.companies.length > 0) {
      return globalData;
    }
  }

  const urls = [
    '/api/dashboard-data',
    '/data/network_alpha_data.json',
    '../data/network_alpha_data.json',
    'data/network_alpha_data.json',
    '/network_alpha_data.json',
    '/api/companies',
  ];

  for (const url of urls) {
    try {
      const resp = await fetch(url);
      if (resp.ok) {
        const json = await resp.json();
        if (Array.isArray(json)) {
          return {
            companies: json,
            super_insiders: [],
            conglomerates: [],
          };
        }
        if (json && Array.isArray(json.companies)) {
          return json;
        }
      }
    } catch {
      // try next path
    }
  }

  // Empty state when completely unreachable
  return {
    companies: [],
    super_insiders: [],
    conglomerates: [],
  };
}

export async function fetchStockData(ticker: string): Promise<any> {
  const resp = await fetch(`/api/stock/${ticker.toUpperCase()}`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch stock data for ${ticker}`);
  }
  return await resp.json();
}

export async function fetchUBO(ticker: string): Promise<any> {
  const resp = await fetch(`/api/graph/ubo/${ticker.toUpperCase()}`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch UBO for ${ticker}`);
  }
  return await resp.json();
}

export async function fetchGraphNetwork(ticker: string): Promise<any> {
  const resp = await fetch(`/api/graph/network/${ticker.toUpperCase()}`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch network graph for ${ticker}`);
  }
  return await resp.json();
}

export async function fetchCentrality(topN = 20): Promise<any[]> {
  const resp = await fetch(`/api/graph/centrality?top_n=${topN}`);
  if (!resp.ok) {
    throw new Error('Failed to fetch board centrality');
  }
  return await resp.json();
}

export async function fetchCrossHoldings(): Promise<any[]> {
  const resp = await fetch('/api/graph/cross-holdings');
  if (!resp.ok) {
    throw new Error('Failed to fetch cross holdings');
  }
  return await resp.json();
}

export async function fetchStealthAccumulation(lookbackDays = 5, minTurnoverRpB = 1.0): Promise<any> {
  const resp = await fetch(`/api/stealth-accumulation?lookback_days=${lookbackDays}&min_turnover_rp=${minTurnoverRpB * 1e9}`);
  if (!resp.ok) {
    throw new Error('Failed to fetch stealth accumulation');
  }
  return await resp.json();
}

export async function fetchBrokerFlow(date?: string, topK = 5): Promise<any> {
  const url = date ? `/api/broker-flow?date=${date}&top_k=${topK}` : `/api/broker-flow?top_k=${topK}`;
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error('Failed to fetch broker flow');
  }
  return await resp.json();
}

export async function fetchDividendScreen(minYield = 3.0, year = '2026', limit = 30): Promise<any> {
  const resp = await fetch(`/api/dividend?min_yield=${minYield}&year=${year}&limit=${limit}`);
  if (!resp.ok) {
    throw new Error('Failed to fetch dividend opportunities');
  }
  return await resp.json();
}

export async function fetchDividendAnalysis(ticker: string): Promise<any> {
  const resp = await fetch(`/api/dividend/${ticker.toUpperCase()}`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch dividend analysis for ${ticker}`);
  }
  return await resp.json();
}

export async function runBacktest(params: any): Promise<any> {
  const resp = await fetch('/api/backtest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: 'Backtest failed' }));
    throw new Error(err.detail || 'Backtest failed');
  }
  return await resp.json();
}

export async function fetchDailyBriefing(date?: string): Promise<any> {
  const url = date ? `/api/signals?date=${date}` : '/api/signals';
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error('Failed to fetch daily signals briefing');
  }
  return await resp.json();
}

export async function fetchStockBlocks(ticker: string): Promise<any> {
  const resp = await fetch(`/api/stock/${ticker.toUpperCase()}/blocks`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch verified block trades for ${ticker}`);
  }
  return await resp.json();
}

export async function fetchIngestionStatus(): Promise<any> {
  const resp = await fetch('/api/system/ingestion-status');
  if (!resp.ok) {
    throw new Error('Failed to fetch data ingestion status');
  }
  return await resp.json();
}

export async function triggerIngestion(params: {
  job_type: 'daily' | 'backfill';
  date?: string;
  start_date?: string;
  end_date?: string;
  concurrency?: number;
}): Promise<any> {
  const resp = await fetch('/api/system/trigger-ingestion', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: 'Failed to trigger ingestion' }));
    throw new Error(err.detail || 'Failed to trigger ingestion');
  }
  return await resp.json();
}



