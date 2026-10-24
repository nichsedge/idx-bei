export type TabType =
  | 'opportunities'
  | 'terminal'
  | 'power_map'
  | 'simulator'
  | 'ingestion'
  | 'deals'
  | 'rights'
  | 'momentum';

export interface DatasetTimeseriesMeta {
  total_dates: number;
  start_date: string | null;
  end_date: string | null;
  daily_partitions_count: number;
  compacted_partitions_count: number;
  total_size_mb: number;
}

export interface ParquetExportMeta {
  exists: boolean;
  row_count: number;
  size_mb: number;
  modified_iso: string | null;
}

export interface IngestionInventory {
  timeseries: Record<string, DatasetTimeseriesMeta>;
  parquet_exports: Record<string, ParquetExportMeta>;
  fundamental_snapshots: {
    total_listed_companies: number;
    detailed_profiles_scraped: number;
    profile_coverage_pct: number;
    financial_ratios: { exists: boolean; size_mb: number; modified_iso: string | null };
    corporate_actions: { exists: boolean; size_mb: number; modified_iso: string | null };
    broker_directory: { exists: boolean; size_mb: number; modified_iso: string | null };
  };
  ksei_drift: {
    files_count: number;
    files: Array<{ file: string; size_mb: number; modified_iso: string | null }>;
  };
  system: {
    usd_idr: { rate: number; last_updated: string | null };
  };
}

export interface CalendarGapInfo {
  dataset: string;
  start_date: string;
  end_date: string;
  total_calendar_weekdays: number;
  ingested_days: number;
  official_holidays_count: number;
  official_holidays: Array<{ date: string; holiday_name: string }>;
  true_missing_trading_days_count: number;
  true_missing_trading_days: string[];
  coverage_percentage: number;
}

export interface BackfillTier {
  tier: number;
  id: string;
  name: string;
  priority: string;
  description: string;
  target_range: { start: string; end: string };
  trading_days_to_fetch: number;
  estimated_payload_mb: number;
  estimated_runtime_seconds_c8: number;
  unlocked_capabilities: string[];
  recommended_cli_commands: string[];
}

export interface BackfillRecommendations {
  as_of_date: string;
  summary: {
    current_status: string;
    immediate_gaps_count: number;
    immediate_gaps: string[];
    recommended_action: string;
  };
  tiers: BackfillTier[];
}

export interface IngestionStatusResponse {
  status: 'healthy' | 'warning' | 'critical';
  health_score: number;
  inventory: IngestionInventory;
  gaps: CalendarGapInfo;
  recommendations: BackfillRecommendations;
  generated_at: string;
}

export interface ScoreBreakdown {
  financial: number;
  valuation: number;
  network: number;
  total: number;
}

export interface BoardMember {
  name: string;
  role?: string;
  title?: string;
  is_shared?: boolean;
}

export interface Shareholder {
  name: string;
  percentage: number;
  is_controller?: boolean;
  is_super_insider?: boolean;
}

export interface Subsidiary {
  name: string;
  percentage: number;
  bidang_usaha?: string;
}

export interface Company {
  code: string;
  name: string;
  sector: string;
  sub_sector?: string;
  industry?: string;
  sub_industry?: string;
  roe?: number | null;
  roa?: number | null;
  npm?: number | null;
  de_ratio?: number | null;
  per?: number | null;
  price_bv?: number | null;
  pbv?: number | null;
  price?: number;
  daily_change?: number;
  previous_price?: number;
  dps?: number | null;
  yield?: number | null;
  score: ScoreBreakdown;
  board_members?: BoardMember[];
  directors?: BoardMember[];
  commissioners?: BoardMember[];
  shareholders?: Shareholder[];
  subsidiaries?: Subsidiary[];
  shared_directors?: any[];
  market_cap?: number;
  is_blue_chip?: boolean;
  conglomerate?: string | null;
  // Forensic & Intellect Compounder Intelligence
  is_value_trap?: boolean;
  forensic_flags?: string[];
  forensic_reasons?: string[];
  valuation_status?: string;
  is_undervalued?: boolean;
  justified_pbv?: number | null;
  valuation_badge?: string;
  compounder_score?: number;
  dca_verdict?: string;
  dca_rating?: string;
  intellect_badges?: string[];
  ai_thesis?: string;
}

export interface InsiderHolding {
  code: string;
  percentage: number;
  value?: number;
  value_idr?: number;
  is_controller?: boolean;
}

export interface ConnectedRole {
  code: string;
  role: string;
  title: string;
}

export interface SuperInsider {
  name: string;
  clean_name?: string;
  total_value?: number;
  total_value_idr?: number;
  holdings?: InsiderHolding[];
  portfolio?: InsiderHolding[];
  holding_count?: number;
  connected_roles?: ConnectedRole[];
}

export interface Conglomerate {
  controller_name?: string;
  name?: string;
  companies: string[];
  total_assets?: number;
  total_market_cap?: number;
  average_roe?: number;
  median_roe?: number;
  average_pbv?: number;
  dominant_sector?: string;
}

export interface DashboardData {
  companies: Company[];
  super_insiders: SuperInsider[];
  conglomerates: Conglomerate[];
}

export interface StreamEvent {
  type: string;
  ticker?: string;
  price?: number;
  change?: number;
  score?: number;
  ohlc?: {
    time: string;
    open: number;
    high: number;
    low: number;
    close: number;
  };
  status?: string;
  data?: any;
}

export interface BacktestParams {
  strategy: 'foreign_flow' | 'bandarmology' | 'stealth_accumulation' | 'sharia_value' | 'composite_alpha' | 'dividend_arbitrage';
  holding_days: number;
  top_n: number;
  min_turnover_rp: number;
  start_date?: string;
  end_date?: string;
  stop_loss_pct?: number;
  take_profit_pct?: number;
  position_sizing?: 'equal_weight' | 'volatility_parity';
}

export interface BacktestMetrics {
  total_return_pct: number;
  cagr_pct?: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown_pct: number;
  win_rate_pct: number;
  profit_factor?: number;
  total_trades: number;
  avg_trade_return_pct: number;
  benchmark_return_pct: number;
  alpha_pct: number;
  strategy?: string;
  holding_days?: number;
  position_sizing?: string;
  total_events?: number;
  strategy_a_naive_hold?: BacktestMetrics;
  strategy_b_precum_exit?: BacktestMetrics;
  strategy_c_postex_rebuy?: BacktestMetrics;
}

export interface EquityPoint {
  time: string;
  value: number;
}

export interface BacktestTrade {
  EntryDate: string;
  ExitDate: string;
  StockCode: string;
  EntryPrice: number;
  ExitPrice: number;
  ReturnPct: number;
  Return: number;
  Weight?: number;
  WeightedReturn?: number;
}

export interface BacktestResponse {
  metrics: BacktestMetrics;
  equity_curve: EquityPoint[];
  trades: BacktestTrade[];
}

export interface StealthAnomaly {
  StockCode: string;
  PriceChangePct: number;
  CumPriceChangePct?: number;
  SmartMoneyDelta: number;
  NetForeignFlowRpB?: number;
  CumNetForeignFlowRpB?: number;
  TurnoverRpB?: number;
  FlowRatioPct?: number;
  AccumulationScore?: number;
  WyckoffPhase?: string;
  Signal: 'STEALTH_ACCUMULATION' | 'MARKUP_CONFIRMATION' | 'RETAIL_TRAP' | 'DISTRIBUTION' | string;
  Priority?: 'HIGH' | 'MEDIUM' | 'LOW' | string;
}

export interface StealthAccumulationSummary {
  on_date: string;
  smart_money_turnover_rp_b: number;
  retail_turnover_rp_b: number;
  smart_money_delta: number;
  market_signal: string;
  anomalies_detected: number;
}

export interface StealthAccumulationResponse {
  summary: StealthAccumulationSummary | string;
  signal: string;
  smart_money_delta: number;
  anomalies: StealthAnomaly[];
}

export interface DividendOpportunity {
  StockCode: string;
  StockName?: string;
  Price?: number;
  DPS: number;
  DividendYield: number;
  CumDate: string;
  ExDate: string;
  PaymentDate?: string;
  PayoutRatio?: number;
  TrapScore?: number;
  Recommendation?: string;
}

export interface DividendAnalysis {
  ticker: string;
  has_dividend: boolean;
  message?: string;
  dividend?: {
    dps: number;
    yield_pct: number;
    cum_date: string;
    ex_date: string;
    payment_date: string;
  };
  metrics?: {
    payout_ratio: number;
    cash_coverage: number;
    fcf_yield: number;
    earnings_growth_yoy: number;
  };
  trap_score?: number;
  trap_level?: 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';
  recommendation?: 'BUY' | 'HOLD' | 'AVOID' | 'ARBITRAGE';
  playbook?: {
    strategy_a_naive_hold_return?: number;
    strategy_b_pre_cum_exit_return?: number;
    strategy_c_post_ex_rebuy_return?: number;
    best_strategy?: string;
  };
  risk_breakdown?: {
    payout_risk: number;
    cash_flow_risk: number;
    cyclicality_risk: number;
    leverage_risk: number;
  };
}

export interface WatchlistItem {
  code: string;
  name: string;
  sector?: string;
  price?: number;
  daily_change?: number;
  score?: number;
  addedAt: string;
}

export interface LiveAlert {
  id: string;
  ticker: string;
  type: 'STEALTH_ACCUMULATION' | 'RETAIL_TRAP' | 'DIVIDEND_CUM' | 'PASAR_NEGO';
  title: string;
  message: string;
  timestamp: string;
}

// --- Corporate actions & rights issues (Python API: idx/deals.py) ---
export interface CorporateActionItem {
  category: string;
  listing_date: string;
  shares: number;
  shares_after: number;
}

export type CapitalRaiseType = 'rights_issue' | 'private_placement';

export interface CapitalRaise {
  id: number;
  ticker: string;
  type: CapitalRaiseType;
  listing_date: string; // first listing of the new shares
  last_listing_date: string; // last batch, when IDX lists the issue in several batches
  tranches: number;
  new_shares: number;
  shares_after: number;
  shares_before: number;
  dilution_pct: number; // new ÷ after
  size_vs_old_pct: number; // new ÷ before
  raises_in_36m: number; // rights issues + private placements by this ticker in the 36 months up to this one
  flags: string[];
}

// --- Scheduled worker (Python: idx/worker.py) ---
export interface WorkerJobState {
  status?: 'ok' | 'failed';
  last_run?: string;
  last_ok?: string;
  duration_s?: number;
  message?: string;
  schedule?: string;
  consecutive_failures?: number;
  alert?: boolean;
}

export interface WorkerStatus {
  started_at?: string;
  updated_at?: string;
  stale: boolean;
  schedules?: Record<string, string>;
  jobs: Record<string, WorkerJobState>;
  recent_runs: (WorkerJobState & { job: string })[];
}

// --- Momentum rank board (Python API: idx/momentum.py) ---
export interface MomentumRow {
  code: string;
  no_price?: boolean;
  score?: number;
  market_rank?: number;
  close?: number;
  r1M?: number | null;
  r3M?: number | null;
  r6M?: number | null;
  r12M?: number | null;
  xs3M?: number | null;
  from_high?: number;
  above_ma20?: boolean;
  above_ma50?: boolean;
  value_20_60?: number | null;
  avg_value_20d?: number;
  adj_warning?: boolean;
  last_adjustment?: { date: string; factor: number } | null;
  context?: string;
  deal_score?: number | null;
  screen_score?: number;
  last_signal?: string;
}

export interface MomentumGroup {
  key: string;
  title: string;
  rows: MomentumRow[];
}

export interface MomentumBoard {
  market: {
    as_of: string | null;
    first_date: string | null;
    trading_days: number;
    universe: number;
    ihsg: Record<string, number | null>;
  } | null;
  screen_period: string | null;
  groups: MomentumGroup[];
  error?: string;
}

export interface RightsIssuesResponse {
  flag_labels: Record<string, string>;
  raises: CapitalRaise[];
}

// --- Deal tracker (data/deals.json, plan §3.1–3.5 / §6) ---
export type DealStage =
  | 'rumour'
  | 'negotiation'
  | 'takeover'
  | 'tender_offer'
  | 'free_float'
  | 'business_change'
  | 'asset_injection'
  | 'aftermath';

export type DealType = 'acquisition' | 'backdoor_candidate' | 'tender_offer' | 'merger' | 'going_private';
export type DealStatus = 'active' | 'completed' | 'cancelled' | 'lapsed';
export type ReviewStatus = 'auto' | 'approved' | 'pending';

export interface DealEvent {
  stage: DealStage;
  event_type: string;
  event_date: string;
  title: string;
  source_url?: string;
  source_type: 'official' | 'news' | 'rumour';
  stake_pct?: number;
  shares?: number;
  price?: number;
  value?: number;
  tender_price?: number;
  tender_start?: string;
  tender_end?: string;
  notes?: string;
  confidence?: number;
  review_status?: ReviewStatus;
}

export interface BackdoorSignals {
  control_change?: boolean;
  different_sector?: boolean;
  shell_like_target?: boolean;
  business_change_plan?: boolean;
  large_capital_injection?: boolean;
  jumbo_ng_trades?: boolean;
  price_spike?: boolean;
}

export interface Deal {
  id: string;
  target_ticker: string;
  target_name?: string;
  deal_type: DealType;
  status: DealStatus;
  current_stage: DealStage;
  acquirer?: string;
  acquirer_group?: string;
  sellers?: string[];
  advisors?: string[];
  pre_announcement_price?: number;
  first_signal_at?: string;
  announced_at?: string;
  completed_at?: string;
  signals?: BackdoorSignals;
  events: DealEvent[];
  // Added by the API
  backdoor: BackdoorScore;
  tender_premium_pct: number | null;
  last_event_date: string;
  pending_review: number;
}

export interface BackdoorScore {
  score: number;
  label: string;
  signals: { key: keyof BackdoorSignals; label: string; weight: number; fired: boolean }[];
}

export interface DealsResponse {
  updated_at: string | null;
  deals: Deal[];
}

// Tracked capital raises (data/rights.json)
export type RaiseStage = 'plan' | 'egm' | 'registration' | 'effective' | 'trading' | 'listed';
export type RaiseStatus = 'watch' | 'active' | 'completed' | 'cancelled';

export interface RaiseEvent extends Omit<DealEvent, 'stage'> {
  stage: RaiseStage;
}

export interface TrackedRaise {
  id: string;
  ticker: string;
  name?: string;
  type: CapitalRaiseType;
  status: RaiseStatus;
  stage: RaiseStage;
  linked_deal?: string | null;
  announced_at?: string;
  terms?: {
    ratio_old?: number;
    ratio_new?: number;
    exercise_price?: number;
    max_new_shares?: number;
    max_value?: number;
    cum_price?: number;
    standby_buyer?: string | null;
    in_kind?: string;
    par_value?: number;
    shares_before?: number;
    authorised_after?: number;
  };
  key_dates?: Record<string, string>;
  notes?: string;
  events: RaiseEvent[];
  // Added by the API
  new_per_old: number | null;
  terp: number | null;
  last_event_date: string;
  pending_review: number;
}

export interface RightsPipelineResponse {
  updated_at: string | null;
  rights: TrackedRaise[];
}
