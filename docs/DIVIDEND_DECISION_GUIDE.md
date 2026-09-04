# IDX Dividend Decision Guide: Buy, Hold, or Sell?

A quantitative, battle-tested decision framework for Indonesian Stock Exchange (IDX / BEI) investors when a held stock declares a dividend.

---

## 1. The Core Dilemma: Anatomy of the IDX Dividend Trap

When a company announces a dividend (via RUPS resolution or IDX Keterbukaan Informasi), retail investors face a difficult question:
> *"Should I buy more to get higher cash payout, hold through the record date, or sell before Cum Date?"*

On the IDX, blind dividend holding often leads to the **Dividend Trap (*Jebakan Dividen*)**:
1. **Pre-Cum Euphoria**: As Cum Date approaches, retail buyers chase the stock for its advertised dividend yield, inflating the price.
2. **Ex-Date Markdown**: On Ex Date (the day after Cum Date), the stock price mechanically drops by roughly the Dividend Per Share ($\text{DPS}$).
3. **The Trap**: In cyclical stocks (e.g. coal, commodities, shipping) or companies paying out more than their ongoing earnings ($\text{DPR} > 80\%$), the market aggressively dumps shares on Ex Date, frequently triggering **Auto Rejection Bawah (ARB)** for 1–3 consecutive sessions. An investor collecting an 8% dividend yield can easily suffer a 12%–18% capital loss.

```
Announcement ──────► Cum Date (Peak Price) ──────► Ex Date (Drop ≥ DPS) ──────► Payment Date (Cash in RDN)
                     ▲                             ▼
                     │ Sell here if trap           │ Multi-day ARB risk if
                     │ (lock in capital gain)       │ cyclical / high DPR
```

---

## 2. The 3 Actions: Decision Matrix

| Dimension | 🟢 BUY / ACCUMULATE | 🔵 HOLD | 🔴 SELL BEFORE CUM DATE |
| :--- | :--- | :--- | :--- |
| **Dividend Yield** | 3% – 7% (Sustainable) | 2% – 6% (Incidental) | > 8% (High Yield / Cyclical) |
| **Payout Ratio (DPR)** | < 60% (Reinvesting in growth) | < 75% (Healthy buffer) | > 80% – 100%+ (Capital erosion) |
| **ROE & Earnings Trend** | ROE ≥ 15%, EPS Growing | ROE ≥ 12%, EPS Stable | ROE < 10% or EPS Peaking/Declining |
| **Smart Money Flow** | Foreign/Inst Net Accumulating | Neutral / Stable Holders | Smart Money Distributing to Retail |
| **Pre-Cum Run-up** | Flat or healthy consolidation | Normal market drift | Rallied > 15%–25% into Cum Date |
| **RSI-14 Momentum** | < 60 (Not overbought) | 45 – 65 (Balanced) | > 70 (Overbought euphoria) |
| **Audit Opinion** | WTP / WTM (Clean) | WTP / WTM (Clean) | Non-clean (WDP, TMP, TL) |
| **Typical Stocks** | Compounders (BBCA, ICBP) | Stable cash-cows (TLKM, ASII) | Cyclical commodity peaks (Coal/Metals) |

---

## 3. How to Execute via this Repository

The toolkit provides dedicated tools to evaluate any dividend declaration quantitatively.

### A. Run Instant Dividend Analysis on Any Stock
Analyze the dividend yield, DPR, 20-day foreign flow, technical RSI, Dividend Trap Risk score (0–100), and get a concrete verdict:

```bash
uv run idx dividend BBCA
uv run idx dividend PTBA
uv run idx dividend AALI
```

**Sample Output:**
```text
╔══════════════════════════════════════════════════════════════════════════════╗
║  IDX DIVIDEND DECISION RADAR: PTBA   - PTBA                                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Current Price   : Rp     2,420      DPS Announced  : Rp    114.44           ║
║  Dividend Yield  :      4.73%       Ex-Date Drop   : ~    4.73%              ║
╟──────────────────────────────────────────────────────────────────────────────╢
║  TIMELINE DATES:                                                             ║
║  • Cum Date      : 2026-06-22   (Last day to buy for dividend eligibility)   ║
║  • Ex Date       : 2026-06-23   (Price adjusts down; selling still gets div) ║
║  • Recording DPS : 2026-06-24   • Payment Date: 2026-07-10                   ║
╟──────────────────────────────────────────────────────────────────────────────╢
║  FUNDAMENTAL HEALTH & SUSTAINABILITY:                                        ║
║  • Payout Ratio  :    23.7%       • EPS (LTM)    : Rp   482.35               ║
║  • ROE           :    27.3%       • DER          :      0.97x                ║
║  • PER           :     5.7x       • PBV          :      1.56x                ║
║  • Audit Opinion : Clean (WTP)                                               ║
╟──────────────────────────────────────────────────────────────────────────────╢
║  SMART MONEY & TECHNICAL MOMENTUM:                                           ║
║  • Foreign Net 5D: Rp     0.1B     • Foreign Net 20D : Rp     0.5B           ║
║  • 20D Run-up    :     3.86%      • RSI-14 (Trend)  :      54.3              ║
╟──────────────────────────────────────────────────────────────────────────────╢
║  DIVIDEND TRAP RISK SCORE: LOW (12.0/100)                                    ║
╟──────────────────────────────────────────────────────────────────────────────╢
║  DECISION VERDICT : 🔵 HOLD                                                  ║
║  Tactical Execution:                                                         ║
║  Hold existing position to collect cash dividend. Reinvest dividend under    ║
║  UU HPP to enjoy 0% income tax exemption. Do not chase aggressively if       ║
║  price has run up, but do not panic sell on Ex-Date.                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### B. Screen High-Yield Dividend Opportunities
Filter all companies that declared dividends, ranked by Yield and Trap Risk:

```bash
# Screen dividends with yield >= 4.0%
uv run idx dividend --screen --min-yield 4.0 --limit 20
```

### C. Check Bandarmology & Broker Flow
Confirm whether institutional brokers (Foreign: AK, BK, ZP, RX; Domestic institutions: CC, NI) are buying or if retail brokers (YP, PD, XC) are being dumped on:

```bash
uv run idx bandarmology
```

### D. Check Daily Alpha & Audit Shield
Ensure the company is not flagged on the Audit Risk Shield:

```bash
uv run idx signals
```

### E. AI Assistant (MCP) Integration
If using Claude Desktop, Cursor, or Antigravity via MCP:
- Call tool `idx_analyze_dividend(ticker="PTBA")` for automated real-time reasoning.

### F. REST API Endpoint
Integrate with internal trading bots or dashboards:
```http
GET http://localhost:8000/api/dividend/BBCA
GET http://localhost:8000/api/dividend?min_yield=5.0
```

---

## 4. Tactical Playbook: Step-by-Step Execution

### Scenario A: You Decide to SELL Before Cum Date (Dodge the Trap)
1. **When to Exit**: Sell on **Cum Date** (or 1 trading day before Cum Date) during the morning session (Sesi 1), when trading volume and retail liquidity peak.
2. **Why**:
   - You capture 100% of the pre-dividend price run-up as capital gains.
   - You avoid the guaranteed Ex-Date price drop.
   - You eliminate Indonesian individual dividend tax (10%).
   - You protect capital from potential multi-day ARB locks.
3. **Re-entry Strategy**: If you still like the business long-term, wait 3 to 7 trading days after Ex Date until post-dividend selling volume exhausts, then buy back shares at a significant discount.

### Scenario B: You Decide to HOLD (Compounding Wealth)
1. **Eligibility**: You must hold through the close of **Cum Date**. You can sell on **Ex Date** and still receive the cash dividend on Payment Date.
2. **Tax Exemption (UU HPP)**: Under Indonesian tax regulations (UU Harmonisasi Peraturan Perpajakan / UU HPP), cash dividends received by domestic individual tax residents are **0% exempt from income tax (PPh Final)** provided the proceeds are reinvested in Indonesian financial instruments (e.g. Indonesian stocks, SBN, mutual funds) for at least 3 years and reported in the annual SPT Tahunan.
3. **Reinvestment**: Reinvest the cash dividend into high-alpha compounders to accelerate compounding returns.

### Scenario C: You Decide to BUY / ACCUMULATE
1. **Pre-Cum Entry**: Only enter if RSI-14 < 60, price is within 3% of 20-day EMA, and Net Foreign Flow is strongly positive.
2. **Post-Ex Date Dip Buying**: Often the highest Sharpe-ratio trade is **not** buying before Cum Date, but waiting for the Ex-Date morning panic when retail dumps shares, and buying fundamentally strong compounders at a discount.

---

## 5. Summary Checklist

Before making your move, run through this 5-point checklist:

- [ ] **Yield Check**: Is the yield realistic (3%–7%) or an extreme trap (>10%)?
- [ ] **Earnings Check**: Is the company paying out of current profits ($\text{DPR} \le 75\%$) or liquidating cash reserves?
- [ ] **Smart Money Check**: Are institutional brokers accumulating or exiting?
- [ ] **Run-up Check**: Has the stock already surged >15% ahead of the announcement? (If yes, consider selling to lock in gains).
- [ ] **Audit Check**: Is the audit opinion clean (`WTP`)?

Run `uv run idx dividend <TICKER>` to execute this entire checklist automatically.
