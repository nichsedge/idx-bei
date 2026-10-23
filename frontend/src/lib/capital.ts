// Client-side calculators and display helpers for the Deal Tracker and Rights Issue Tracker (plan §3.5, §3.10).
// Data (deals, rights issues, flags, backdoor score) comes from the Python API in idx/deals.py.
import type { DealStage } from '../types';

// ---------- Rights issue math (plan §3.10 c–d) ----------

export interface RightsTerms {
  ratioOld: number; // every N old shares ...
  ratioNew: number; // ... get M rights
  exercisePrice: number;
  cumPrice: number;
}

export interface RightsMetrics {
  terp: number;
  rightValue: number;
  discountToCum: number; // %
  discountToTerp: number; // %
  dilutionPct: number;
}

export function rightsMetrics(t: RightsTerms): RightsMetrics | null {
  if (!(t.ratioOld > 0 && t.ratioNew > 0 && t.cumPrice > 0 && t.exercisePrice >= 0)) return null;
  const terp = (t.ratioOld * t.cumPrice + t.ratioNew * t.exercisePrice) / (t.ratioOld + t.ratioNew);
  return {
    terp,
    rightValue: Math.max(0, terp - t.exercisePrice),
    discountToCum: (1 - t.exercisePrice / t.cumPrice) * 100,
    discountToTerp: terp > 0 ? (1 - t.exercisePrice / terp) * 100 : 0,
    dilutionPct: (t.ratioNew / (t.ratioOld + t.ratioNew)) * 100,
  };
}

export interface HolderInput extends RightsTerms {
  sharesHeld: number;
  avgCost: number;
  rightsPrice: number; // market price of the -R security
  buyFeePct: number;
  sellFeePct: number;
}

export interface Scenario {
  key: 'exercise' | 'sell' | 'nothing' | 'cash_neutral';
  label: string;
  exercised: number;
  sold: number;
  cashFlow: number; // + received, − paid
  sharesAfter: number;
  valueAfter: number; // shares × TERP + cash flow
  avgCostAfter: number;
  ownershipKeptPct: number; // share of the post-issue company vs a holder who exercised everything
  note: string;
}

/** Rights entitlement: floor(shares × M / N); fractional rights are rounded down. */
export function rightsEntitlement(sharesHeld: number, ratioOld: number, ratioNew: number): number {
  return Math.floor((sharesHeld * ratioNew) / ratioOld);
}

export function holderScenarios(
  h: HolderInput,
): { metrics: RightsMetrics; rights: number; scenarios: Scenario[] } | null {
  const m = rightsMetrics(h);
  if (!m || !(h.sharesHeld > 0)) return null;
  const rights = rightsEntitlement(h.sharesHeld, h.ratioOld, h.ratioNew);
  const buyFee = h.buyFeePct / 100;
  const sellFee = h.sellFeePct / 100;
  const costBasis = h.sharesHeld * h.avgCost;
  const fullStake = h.sharesHeld + rights;

  const make = (key: Scenario['key'], label: string, exercised: number, sold: number, note: string): Scenario => {
    const exerciseCost = exercised * h.exercisePrice * (1 + buyFee);
    const saleProceeds = sold * h.rightsPrice * (1 - sellFee);
    const sharesAfter = h.sharesHeld + exercised;
    const cashFlow = saleProceeds - exerciseCost;
    return {
      key,
      label,
      exercised,
      sold,
      cashFlow,
      sharesAfter,
      valueAfter: sharesAfter * m.terp + cashFlow,
      avgCostAfter: sharesAfter > 0 ? (costBasis + exerciseCost - saleProceeds) / sharesAfter : 0,
      ownershipKeptPct: fullStake > 0 ? (sharesAfter / fullStake) * 100 : 100,
      note,
    };
  };

  // Cash-neutral: exercise x and sell (rights − x) so that the sale pays for the exercise.
  const perExercise = h.exercisePrice * (1 + buyFee);
  const perSale = h.rightsPrice * (1 - sellFee);
  const cnExercise = perExercise + perSale > 0 ? Math.floor((rights * perSale) / (perExercise + perSale)) : 0;

  return {
    metrics: m,
    rights,
    scenarios: [
      make('exercise', 'Exercise all rights', rights, 0, 'Keeps your ownership; needs cash.'),
      make('sell', 'Sell all rights', 0, rights, 'Cash in; ownership diluted.'),
      make('nothing', 'Do nothing', 0, 0, 'Rights expire worthless after the exercise period.'),
      make(
        'cash_neutral',
        'Sell some, exercise the rest',
        cnExercise,
        rights - cnExercise,
        'Sale of rights pays for exercising the rest.',
      ),
    ],
  };
}

// ---------- Tender offer math (plan §3.5) ----------

export interface TenderInput {
  marketPrice: number;
  offerPrice: number;
  buyFeePct: number;
  daysToPayment: number;
}

export interface TenderResult {
  grossSpreadPct: number;
  netReturnPct: number;
  annualisedPct: number | null;
}

/** Buy at market, tender at the offer price. Tendering usually carries no exchange sell fee; add it to buyFeePct if your broker charges one. */
export function tenderReturn(t: TenderInput): TenderResult | null {
  if (!(t.marketPrice > 0 && t.offerPrice > 0)) return null;
  const cost = t.marketPrice * (1 + t.buyFeePct / 100);
  const net = t.offerPrice / cost - 1;
  return {
    grossSpreadPct: (t.offerPrice / t.marketPrice - 1) * 100,
    netReturnPct: net * 100,
    annualisedPct: t.daysToPayment > 0 && net > -1 ? (Math.pow(1 + net, 365 / t.daysToPayment) - 1) * 100 : null,
  };
}

export const STAGE_ORDER: DealStage[] = [
  'rumour',
  'negotiation',
  'takeover',
  'tender_offer',
  'free_float',
  'business_change',
  'asset_injection',
  'aftermath',
];

export const STAGE_LABELS: Record<DealStage, string> = {
  rumour: 'Rumour',
  negotiation: 'Negotiation',
  takeover: 'Takeover',
  tender_offer: 'Tender offer',
  free_float: 'Free float',
  business_change: 'Business change',
  asset_injection: 'Asset injection',
  aftermath: 'Aftermath',
};

// ---------- Formatting ----------

export const fmtInt = (n: number) => Math.round(n).toLocaleString('id-ID');
export const fmtRp = (n: number) => 'Rp' + Math.round(n).toLocaleString('id-ID');
/** Per-share price: keeps fractions (deals below Rp50 are often priced like Rp23,5). */
export const fmtPrice = (n: number) => 'Rp' + n.toLocaleString('id-ID', { maximumFractionDigits: 2 });
export const fmtPct = (n: number, digits = 1) => n.toFixed(digits) + '%';
export function fmtShares(n: number): string {
  if (n >= 1e9) return (n / 1e9).toFixed(2) + ' B';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + ' M';
  return fmtInt(n);
}
