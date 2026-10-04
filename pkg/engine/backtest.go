package engine

import (
	"math"
	"sort"
	"strings"
)

// BacktestTrade represents a simulated trade outcome.
type BacktestTrade struct {
	StockCode   string  `json:"stock_code"`
	EntryDate   string  `json:"entry_date"`
	EntryPrice  float64 `json:"entry_price"`
	ExitDate    string  `json:"exit_date"`
	ExitPrice   float64 `json:"exit_price"`
	ReturnPct   float64 `json:"return_pct"`
	ExitReason  string  `json:"exit_reason"`
}

// BacktestSummary summarizes strategy backtesting results.
type BacktestSummary struct {
	Strategy       string          `json:"strategy"`
	HoldingDays    int             `json:"holding_days"`
	TotalTrades    int             `json:"total_trades"`
	WinningTrades  int             `json:"winning_trades"`
	LosingTrades   int             `json:"losing_trades"`
	WinRatePct     float64         `json:"win_rate_pct"`
	AvgReturnPct   float64         `json:"avg_return_pct"`
	CumulativeRet  float64         `json:"cumulative_return_pct"`
	MaxDrawdownPct float64         `json:"max_drawdown_pct"`
	SharpeRatio    float64         `json:"sharpe_ratio"`
	TopTrades      []BacktestTrade `json:"top_trades"`
}

// RunStrategyBacktest simulates systematic strategy performance across historical partitions.
func RunStrategyBacktest(
	dataDir string,
	strategy string,
	holdingDays int,
	topN int,
	stopLossPct float64,
	takeProfitPct float64,
) (*BacktestSummary, error) {
	strategy = strings.ToLower(strings.TrimSpace(strategy))
	if strategy == "" {
		strategy = "foreign_flow"
	}
	if holdingDays <= 0 {
		holdingDays = 20
	}
	if topN <= 0 {
		topN = 10
	}

	dash, err := LoadDashboardData(dataDir)
	if err != nil {
		return nil, err
	}

	// Filter active high-quality stocks
	var targetTickers []string
	if strategy == "composite_alpha" {
		for _, c := range dash.Companies {
			if c.CompounderScore >= 65.0 && !c.IsValueTrap {
				targetTickers = append(targetTickers, c.Code)
			}
		}
	} else {
		// foreign_flow or general
		for _, c := range dash.Companies {
			if c.EstimatedMCap >= 1000.0 {
				targetTickers = append(targetTickers, c.Code)
			}
		}
	}

	if len(targetTickers) > 40 {
		targetTickers = targetTickers[:40]
	}

	var allTrades []BacktestTrade

	for _, ticker := range targetTickers {
		records, _, err := GetStockData(dataDir, ticker, 120)
		if err != nil || len(records) < 4 {
			continue
		}

		effHolding := holdingDays
		if effHolding >= len(records)-1 {
			effHolding = len(records) / 2
		}
		if effHolding < 1 {
			effHolding = 1
		}

		step := effHolding
		for i := 1; i+effHolding < len(records); i += step {
			entryRec := records[i]
			entryPrice := entryRec.Close
			if entryPrice <= 0 {
				continue
			}

			// Entry signal check
			shouldEnter := false
			if strategy == "foreign_flow" {
				var nff float64
				startJ := 0
				if i > 2 {
					startJ = i - 2
				}
				for j := startJ; j <= i; j++ {
					nff += records[j].NetForeignFlow
				}
				if nff > 0 {
					shouldEnter = true
				}
			} else {
				// Composite alpha entry
				shouldEnter = true
			}

			if !shouldEnter {
				continue
			}

			exitIdx := i + effHolding
			exitRec := records[exitIdx]
			exitPrice := exitRec.Close
			exitReason := "TIME_EXPIRY"

			// Check intermediate stop loss and take profit
			for k := i + 1; k <= exitIdx; k++ {
				currPrice := records[k].Close
				ret := ((currPrice - entryPrice) / entryPrice) * 100.0
				if stopLossPct > 0 && ret <= -stopLossPct {
					exitPrice = currPrice
					exitRec = records[k]
					exitReason = "STOP_LOSS"
					break
				}
				if takeProfitPct > 0 && ret >= takeProfitPct {
					exitPrice = currPrice
					exitRec = records[k]
					exitReason = "TAKE_PROFIT"
					break
				}
			}

			retPct := ((exitPrice - entryPrice) / entryPrice) * 100.0
			allTrades = append(allTrades, BacktestTrade{
				StockCode:  ticker,
				EntryDate:  entryRec.Date,
				EntryPrice: entryPrice,
				ExitDate:   exitRec.Date,
				ExitPrice:  exitPrice,
				ReturnPct:  retPct,
				ExitReason: exitReason,
			})
		}
	}

	if len(allTrades) == 0 {
		return &BacktestSummary{
			Strategy:    strategy,
			HoldingDays: holdingDays,
		}, nil
	}

	totalTrades := len(allTrades)
	winning := 0
	sumReturn := 0.0
	cumReturn := 1.0

	var returns []float64
	peak := 1.0
	maxDD := 0.0

	for _, t := range allTrades {
		if t.ReturnPct > 0 {
			winning++
		}
		sumReturn += t.ReturnPct
		tradeFactor := 1.0 + (t.ReturnPct / 100.0)
		cumReturn *= tradeFactor
		if cumReturn > peak {
			peak = cumReturn
		}
		dd := (peak - cumReturn) / peak * 100.0
		if dd > maxDD {
			maxDD = dd
		}
		returns = append(returns, t.ReturnPct)
	}

	avgReturn := sumReturn / float64(totalTrades)
	winRate := float64(winning) / float64(totalTrades) * 100.0

	// Calculate Sharpe ratio (annualized standard deviation assuming 252 sessions / holdingDays)
	var variance float64
	for _, r := range returns {
		diff := r - avgReturn
		variance += diff * diff
	}
	stdDev := math.Sqrt(variance / float64(totalTrades))
	sharpe := 0.0
	if stdDev > 0 {
		sharpe = (avgReturn / stdDev) * math.Sqrt(252.0/float64(holdingDays))
	}

	sort.Slice(allTrades, func(i, j int) bool {
		return allTrades[i].ReturnPct > allTrades[j].ReturnPct
	})

	topTrades := allTrades
	if len(topTrades) > 5 {
		topTrades = topTrades[:5]
	}

	return &BacktestSummary{
		Strategy:       strategy,
		HoldingDays:    holdingDays,
		TotalTrades:    totalTrades,
		WinningTrades:  winning,
		LosingTrades:   totalTrades - winning,
		WinRatePct:     winRate,
		AvgReturnPct:   avgReturn,
		CumulativeRet:  (cumReturn - 1.0) * 100.0,
		MaxDrawdownPct: maxDD,
		SharpeRatio:    sharpe,
		TopTrades:      topTrades,
	}, nil
}
